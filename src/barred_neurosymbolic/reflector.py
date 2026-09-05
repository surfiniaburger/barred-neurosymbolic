"""
Graph-Powered GEPA Pareto Prompt Reflector Agent & Microservice (Port 8004).

Implements Spec §3.4, §4, §5, §6:
  - Deterministic work-memory reflection engine adapted from Graphify reflect.py
    (time-decayed signed scoring, multi-seed corroboration, cross-seed dead-end suppression).
  - Topological prompt mutation generation using closed-set failure buckets.
  - FastAPI microservice endpoints on Port 8004 (/reflect, /record_attempt, /health).
  - Dual-mode ReflectorClient (fast in-process execution and HTTP network client).
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agentbeats.clock import RunClock
from scenarios.debate.pareto_registry import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_MIN_CORROBORATION,
    ParetoRegistry,
)
from .reflector_schemas import (
    AttemptOutcome,
    FailureBucket,
    GraphDiagnosticSignature,
    ReflectRequest,
    ReflectResponse,
    TaxonomyBucket,
    get_static_baseline_prompt,
)

logger = logging.getLogger("gepa.reflector_agent")

# ---------------------------------------------------------------------------
# §4.1  Deterministic Work-Memory Reflection Algorithms (Graphify Adaptation)
# ---------------------------------------------------------------------------


def parse_datetime(dt_val: str | datetime | None, clock: Optional[RunClock] = None) -> datetime:
    """Parse ISO datetime string or aware datetime object to UTC aware datetime."""
    if dt_val is None or (isinstance(dt_val, str) and not dt_val.strip()):
        dt_val = (clock or RunClock.from_env()).now_iso()
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val
    try:
        clean_str = str(dt_val).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        fallback = (clock or RunClock.from_env()).now_iso()
        return datetime.fromisoformat(fallback.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)


def compute_time_decay(
    observed_at: str | datetime,
    evaluated_at: str | datetime,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    clock: Optional[RunClock] = None,
) -> float:
    """
    Compute time-decay weight in (0, 1]: halves every `half_life_days`.
    Formula: 2^(-delta_t / tau)
    """
    t0 = parse_datetime(observed_at, clock=clock)
    t1 = parse_datetime(evaluated_at, clock=clock)
    age_days = max(0.0, (t1 - t0).total_seconds() / 86400.0)
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def outcome_sign(outcome: str) -> float:
    """
    Map attempt outcome to its signed scoring weight (Spec §4.1):
      - VALID_ACCEPT: +1.0
      - LOGIC_ERROR / DEAD_END_CHAIN: -1.5
      - RETRYABLE_FAILURE / others: -0.5
    """
    if outcome == "VALID_ACCEPT":
        return 1.0
    if outcome in {"LOGIC_ERROR", "DEAD_END_CHAIN"}:
        return -1.5
    return -0.5


def calculate_rule_score(
    history_records: List[Dict[str, Any]],
    now: Optional[datetime] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    clock: Optional[RunClock] = None,
) -> float:
    """
    Calculate the aggregated, time-decayed signed score for a mutation rule:
      S(n) = sum_i Sign(Outcome_i) * 2^(-delta_t_i / tau)
    """
    if not history_records:
        return 0.0

    current_time = now or parse_datetime(None, clock=clock)
    total_score = 0.0

    for rec in history_records:
        rec_time = rec.get("evaluated_at") or rec.get("observed_at")
        decay = compute_time_decay(
            rec_time, current_time, half_life_days=half_life_days, clock=clock
        )
        sign = outcome_sign(rec.get("outcome", "RETRYABLE_FAILURE"))
        total_score += sign * decay

    return round(total_score, 6)


def count_corroborating_seeds(history_records: List[Dict[str, Any]]) -> int:
    """Count distinct successful seed IDs for corroboration promotion (Spec §4.1)."""
    successful_seeds = {
        str(rec.get("seed_id"))
        for rec in history_records
        if rec.get("outcome") == "VALID_ACCEPT" and rec.get("seed_id")
    }
    return len(successful_seeds)


def is_mutation_preferred(
    history_records: List[Dict[str, Any]],
    min_corroboration: int = DEFAULT_MIN_CORROBORATION,
) -> bool:
    """Return True if prompt mutation rule is corroborated by >= min_corroboration distinct seeds."""
    return count_corroborating_seeds(history_records) >= min_corroboration


def is_cross_seed_dead_end(
    history_records: List[Dict[str, Any]],
    clock: Optional[RunClock] = None,
) -> bool:
    """
    Return True if the mutation rule has failed >= 3 consecutive attempts across distinct seeds
    with zero recoveries (Spec §4.2).
    """
    if len(history_records) < 3:
        return False

    # Check last 3 chronological traces using normalized datetime
    sorted_records = sorted(
        history_records,
        key=lambda r: parse_datetime(
            r.get("evaluated_at") or r.get("observed_at"), clock=clock
        ),
    )
    last_3 = sorted_records[-3:]

    # Must be all failures
    all_failed = all(r.get("outcome") != "VALID_ACCEPT" for r in last_3)
    if not all_failed:
        return False

    # Must span distinct seeds
    distinct_seeds = {str(r.get("seed_id")) for r in last_3 if r.get("seed_id")}
    return len(distinct_seeds) >= 2


def classify_attempt_outcome(
    is_valid: bool,
    verifier_logic_error: bool,
    prior_mutation_traces: List[Dict[str, Any]],
    seed_id: str = "",
    evaluated_at: str = "",
    clock: Optional[RunClock] = None,
) -> AttemptOutcome:
    """
    Classify the outcome of an attempt in relation to its cross-seed trajectory (Spec §4.1 / §4.2):
      - VALID_ACCEPT: satisfied 3-layer adjudication contract
      - LOGIC_ERROR: verifier detected factual contradiction
      - DEAD_END_CHAIN: completed >= 3 consecutive cross-seed failures with zero recoveries
      - RETRYABLE_FAILURE: standard recoverable failure
    """
    if is_valid:
        return "VALID_ACCEPT"
    if verifier_logic_error:
        return "LOGIC_ERROR"

    # Evaluate potential dead-end trigger including the current attempt's seed
    normalized_eval_ts = parse_datetime(evaluated_at, clock=clock).isoformat()
    current_attempt = {
        "outcome": "RETRYABLE_FAILURE",
        "seed_id": seed_id,
        "evaluated_at": normalized_eval_ts,
    }
    simulated_history = [*prior_mutation_traces, current_attempt]
    if is_cross_seed_dead_end(simulated_history, clock=clock):
        return "DEAD_END_CHAIN"

    return "RETRYABLE_FAILURE"


# ---------------------------------------------------------------------------
# §3.4  Topological Prompt Mutation Generator
# ---------------------------------------------------------------------------

_BUCKET_REPAIR_TEMPLATES: Dict[FailureBucket, str] = {
    "B_UNSUPPORTED_SYNTAX": (
        "Ensure complete, valid C/C++ AST syntax with properly matched delimiters and clean variable declarations."
    ),
    "B_LOGIC_ERROR": (
        "Eliminate factual contradictions; rigorously ground all safety claims in verified source code semantics."
    ),
    "B_ANCHOR_UNMATCHED": (
        "Quote exact source line anchors verbatim from the target codebase (ensure non-generic syntax tokens)."
    ),
    "B_SOURCE_MISSING": (
        "Trace explicit tainted data-flow propagation originating from untrusted input parameters."
    ),
    "B_SINK_MISSING": (
        "Identify and ground concrete security-sensitive sink operations (memory write, dereference, system call)."
    ),
    "B_SANITIZER_MISMATCH": (
        "Apply valid sink-specific guard validation ({required_sanitizer}) rather than {found_sanitizer}."
    ),
    "B_SANITIZER_TARGET_MISMATCH": (
        "Ensure sanitizer guard protects sink target '{target_var}' instead of guarding '{guarded_target}'."
    ),
    "B_EDGE_MISSING": (
        "Ensure data-flow graph contains an active, unbroken edge between source and sink AST nodes."
    ),
}


def build_topological_repair_instruction(diag: GraphDiagnosticSignature) -> str:
    """Construct concrete repair directive from the diagnostic signature."""
    template = _BUCKET_REPAIR_TEMPLATES.get(
        diag.failure_bucket,
        "Verify data-flow reachability and eliminate unsanitized sink dereferences.",
    )
    return template.format(
        required_sanitizer=diag.required_sanitizer or "strict bounds checking",
        found_sanitizer=diag.found_sanitizer or "missing guard",
        target_var=diag.target_var or "target operand",
        guarded_target=diag.guarded_target or "unrelated variable",
    )


def mutate_system_prompt(
    request: ReflectRequest,
    registry: ParetoRegistry,
) -> ReflectResponse:
    """
    Generate an evolutionary prompt mutation constrained by topological graph feedback
    and active dead-end negative constraints (Spec §3.4).
    """
    diag = request.graph_diagnostic
    repair_directive = build_topological_repair_instruction(diag)
    dead_ends = registry.get_known_dead_ends(request.taxonomy_bucket)

    # Build negative constraint clause if dead-ends exist
    dead_end_clause = ""
    if dead_ends:
        formatted_constraints = "\n".join(f"- DO NOT {c}" for c in dead_ends[:3])
        dead_end_clause = f"\n\n[Active Negative Constraints]\n{formatted_constraints}"

    # Construct the mutated prompt
    rule_text = f"[{diag.failure_bucket}] {repair_directive}"

    mutated_prompt = (
        f"{request.current_system_prompt}\n\n"
        f"[Topological Repair Directive - {diag.failure_bucket}]\n"
        f"{repair_directive}"
        f"{dead_end_clause}"
    ).strip()

    # Hash the complete mutated prompt text for collision-resistant variant tracking
    variant_hash = f"var_{hashlib.sha256(mutated_prompt.encode('utf-8')).hexdigest()}"

    # Probability estimation from historical traces
    history = registry.get_recent_traces_for_mutation(request.taxonomy_bucket, variant_hash)
    score = calculate_rule_score(history)
    prob = 1.0 / (1.0 + math.exp(-score))  # Sigmoid mapping to [0, 1]

    # Check dead-end suppression
    if diag.failure_bucket == "B_SANITIZER_TARGET_MISMATCH" and diag.guarded_target:
        if is_cross_seed_dead_end(history):
            registry.add_dead_end_constraint(
                request.taxonomy_bucket,
                f"guard operand '{diag.guarded_target}' when sink targets '{diag.target_var}'",
            )

    # Register the mutated prompt in Pareto frontier
    registry.register_pareto_prompt(
        taxonomy=request.taxonomy_bucket,
        prompt=mutated_prompt,
        variant_id=variant_hash,
        score=score,
        rationale=f"Repaired {diag.failure_bucket} by applying {repair_directive}",
        topological_rule=rule_text,
    )

    return ReflectResponse(
        status="SUCCESS",
        mutated_system_prompt=mutated_prompt,
        mutation_rationale=f"Repaired {diag.failure_bucket} by applying {repair_directive}",
        applied_topological_rule=rule_text,
        taxonomy_bucket=request.taxonomy_bucket,
        pareto_variant_id=variant_hash,
        estimated_correction_success_probability=round(prob, 4),
    )


# ---------------------------------------------------------------------------
# §5  FastAPI Microservice Endpoints (Port 8004)
# ---------------------------------------------------------------------------


class RecordAttemptRequest(BaseModel):
    taxonomy_bucket: TaxonomyBucket
    predicate_family: str
    seed_id: str
    scenario_id: str
    prompt: str = ""
    attempt_index: int = Field(default=1, ge=1)
    is_valid: bool = False
    verifier_logic_error: bool = False
    observed_at: str = ""
    evaluated_at: str = ""
    canonical_mutation_id: str = "baseline_v0"
    details: Dict[str, Any] = Field(default_factory=dict)


class RecordAttemptResponse(BaseModel):
    outcome: AttemptOutcome
    rule_score: float
    is_preferred: bool
    corroborating_seeds: int


def create_app(registry: Optional[ParetoRegistry] = None) -> FastAPI:
    """Create configured FastAPI application for GEPA Reflector microservice."""
    reg = registry or ParetoRegistry()
    app = FastAPI(title="GEPA Graph-Powered Prompt Reflector", version="1.0.0")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "healthy", "service": "gepa_reflector", "port": 8004}

    @app.get("/pareto_prompt/{taxonomy}")
    def get_pareto_prompt_endpoint(taxonomy: TaxonomyBucket) -> Dict[str, str]:
        prompt = reg.get_pareto_prompt(taxonomy)
        variant_id = reg.get_pareto_variant_id(taxonomy)
        return {"taxonomy": taxonomy, "prompt": prompt, "variant_id": variant_id}

    @app.post("/reflect")
    def reflect(request: ReflectRequest) -> ReflectResponse:
        try:
            return mutate_system_prompt(request, reg)
        except Exception as e:
            logger.exception("Mutation failed: %s", e)
            baseline = get_static_baseline_prompt(request.taxonomy_bucket)
            return ReflectResponse(
                status="FALLBACK_BASELINE",
                mutated_system_prompt=baseline,
                mutation_rationale=f"Fallback due to exception: {e}",
                applied_topological_rule="FALLBACK_BASELINE_STATIC",
                taxonomy_bucket=request.taxonomy_bucket,
                pareto_variant_id="baseline_v0",
                estimated_correction_success_probability=0.0,
            )

    @app.post("/record_attempt")
    def record_attempt(req: RecordAttemptRequest) -> RecordAttemptResponse:
        clock = RunClock.from_env()
        observed_ts = parse_datetime(req.observed_at, clock=clock).isoformat()
        evaluated_ts = parse_datetime(req.evaluated_at, clock=clock).isoformat()

        prior_traces = reg.get_recent_traces_for_mutation(
            req.taxonomy_bucket, req.canonical_mutation_id
        )
        outcome = classify_attempt_outcome(
            is_valid=req.is_valid,
            verifier_logic_error=req.verifier_logic_error,
            prior_mutation_traces=prior_traces,
            seed_id=req.seed_id,
            evaluated_at=evaluated_ts,
            clock=clock,
        )

        trace_details = dict(req.details)
        if req.prompt:
            trace_details["prompt"] = req.prompt

        reg.record_attempt_trace(
            taxonomy=req.taxonomy_bucket,
            predicate_family=req.predicate_family,
            seed_id=req.seed_id,
            scenario_id=req.scenario_id,
            attempt_index=req.attempt_index,
            outcome=outcome,
            canonical_mutation_id=req.canonical_mutation_id,
            observed_at=observed_ts,
            evaluated_at=evaluated_ts,
            details=trace_details,
        )

        all_traces = reg.get_recent_traces_for_mutation(
            req.taxonomy_bucket, req.canonical_mutation_id
        )
        score = calculate_rule_score(
            all_traces, now=parse_datetime(evaluated_ts, clock=clock), clock=clock
        )
        preferred = is_mutation_preferred(all_traces)
        seeds_count = count_corroborating_seeds(all_traces)

        return RecordAttemptResponse(
            outcome=outcome,
            rule_score=score,
            is_preferred=preferred,
            corroborating_seeds=seeds_count,
        )

    return app


def get_app() -> FastAPI:
    """Lazy ASGI factory target: uvicorn scenarios.debate.reflector_agent:get_app --factory"""
    return create_app()


# ---------------------------------------------------------------------------
# §6  Reflector Client (Dual-Mode: In-Process & Network HTTP)
# ---------------------------------------------------------------------------


class ReflectorClient:
    """
    Client for debate orchestrators (run_batch.py).
    Supports both fast in-process execution and HTTP network calls.
    """

    def __init__(
        self,
        registry: Optional[ParetoRegistry] = None,
        base_url: Optional[str] = None,
        in_process: bool = True,
    ) -> None:
        self.registry = registry or ParetoRegistry()
        self.base_url = base_url or "http://localhost:8004"
        self.in_process = in_process

    async def get_pareto_prompt(self, taxonomy: TaxonomyBucket) -> str:
        """Retrieve the current best Pareto-optimal prompt for the taxonomy bucket."""
        if not self.in_process:
            import httpx
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                resp = await client.get(f"/pareto_prompt/{taxonomy}")
                resp.raise_for_status()
                return str(resp.json().get("prompt", get_static_baseline_prompt(taxonomy)))
        return self.registry.get_pareto_prompt(taxonomy)

    async def record_attempt_and_classify_outcome(
        self,
        taxonomy_bucket: TaxonomyBucket,
        predicate_family: str,
        seed_id: str,
        scenario_id: str,
        prompt: str,
        attempt_index: int,
        is_valid: bool,
        verifier_logic_error: bool,
        observed_at: str,
        evaluated_at: str,
        canonical_mutation_id: str = "baseline_v0",
        details: Optional[Dict[str, Any]] = None,
    ) -> AttemptOutcome:
        """Record attempt evaluation in work-memory and return classified AttemptOutcome."""
        rec_details = dict(details or {})
        if prompt:
            rec_details["prompt"] = prompt

        clock = RunClock.from_env()
        observed_ts = parse_datetime(observed_at, clock=clock).isoformat()
        evaluated_ts = parse_datetime(evaluated_at, clock=clock).isoformat()

        if not self.in_process:
            import httpx
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                payload = {
                    "taxonomy_bucket": taxonomy_bucket,
                    "predicate_family": predicate_family,
                    "seed_id": seed_id,
                    "scenario_id": scenario_id,
                    "prompt": prompt,
                    "attempt_index": attempt_index,
                    "is_valid": is_valid,
                    "verifier_logic_error": verifier_logic_error,
                    "observed_at": observed_ts,
                    "evaluated_at": evaluated_ts,
                    "canonical_mutation_id": canonical_mutation_id,
                    "details": rec_details,
                }
                resp = await client.post("/record_attempt", json=payload)
                resp.raise_for_status()
                return resp.json()["outcome"]

        prior_traces = self.registry.get_recent_traces_for_mutation(
            taxonomy_bucket, canonical_mutation_id
        )
        outcome = classify_attempt_outcome(
            is_valid=is_valid,
            verifier_logic_error=verifier_logic_error,
            prior_mutation_traces=prior_traces,
            seed_id=seed_id,
            evaluated_at=evaluated_ts,
            clock=clock,
        )

        self.registry.record_attempt_trace(
            taxonomy=taxonomy_bucket,
            predicate_family=predicate_family,
            seed_id=seed_id,
            scenario_id=scenario_id,
            attempt_index=attempt_index,
            outcome=outcome,
            canonical_mutation_id=canonical_mutation_id,
            observed_at=observed_ts,
            evaluated_at=evaluated_ts,
            details=rec_details,
        )
        return outcome

    async def reflect(self, request: ReflectRequest) -> ReflectResponse:
        """Mutate system prompt guided by graph diagnostic feedback."""
        if not self.in_process:
            import httpx
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                resp = await client.post("/reflect", json=request.model_dump())
                resp.raise_for_status()
                return ReflectResponse.model_validate(resp.json())

        try:
            return mutate_system_prompt(request, self.registry)
        except Exception as e:
            logger.exception("Reflector mutation failed: %s", e)
            baseline = get_static_baseline_prompt(request.taxonomy_bucket)
            return ReflectResponse(
                status="FALLBACK_BASELINE",
                mutated_system_prompt=baseline,
                mutation_rationale=f"Fallback due to client exception: {e}",
                applied_topological_rule="FALLBACK_BASELINE_STATIC",
                taxonomy_bucket=request.taxonomy_bucket,
                pareto_variant_id="baseline_v0",
                estimated_correction_success_probability=0.0,
            )
