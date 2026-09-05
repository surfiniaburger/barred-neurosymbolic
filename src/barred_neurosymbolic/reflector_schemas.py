"""
Reflector Schemas & Deterministic Classifiers for Graph-Powered GEPA.

Implements the data contracts from SPEC_GRAPH_POWERED_GEPA_REFLECTOR.md:
  - Type aliases: FailureBucket, TaxonomyBucket, AttemptOutcome
  - Pydantic models: GraphDiagnosticSignature, ReflectRequest, ReflectResponse
  - Deterministic classifiers: classify_taxonomy_bucket, classify_graph_diagnostic
  - Static baseline prompts: get_static_baseline_prompt

All functions are pure (no I/O, no network, no filesystem).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from .reachability import (
    FlowGraphSnapshot,
    FlowSignature,
    is_sanitizer_valid_for_sink,
)

# ---------------------------------------------------------------------------
# §3.1  Closed-set taxonomy and failure-bucket type aliases
# ---------------------------------------------------------------------------

FailureBucket = Literal[
    "B_UNSUPPORTED_SYNTAX",
    "B_LOGIC_ERROR",
    "B_ANCHOR_UNMATCHED",
    "B_SOURCE_MISSING",
    "B_SINK_MISSING",
    "B_SANITIZER_MISMATCH",
    "B_SANITIZER_TARGET_MISMATCH",
]

TaxonomyBucket = Literal[
    "memory_safety",
    "integer_arithmetic",
    "concurrency",
    "input_validation",
]

AttemptOutcome = Literal[
    "VALID_ACCEPT",
    "LOGIC_ERROR",
    "DEAD_END_CHAIN",
    "RETRYABLE_FAILURE",
]

# ---------------------------------------------------------------------------
# §3.3  Canonical Graph Diagnostic Schema (μ_f^graph)
# ---------------------------------------------------------------------------


class GraphDiagnosticSignature(BaseModel):
    """
    Standardized graph diagnostic feedback emitted by the AST extraction layer.
    Reconciles FlowSignature fields with upstream debate audit telemetry.
    """

    scenario_id: str = Field(..., description="Scenario ID or HASH-{sha256[:10]}")
    predicate_family: str = Field(
        ...,
        description="e.g. BUFFER_OVERFLOW, USE_AFTER_FREE, COMMAND_INJECTION",
    )
    failure_bucket: FailureBucket = Field(
        ..., description="Canonical FailureBucket ID"
    )
    source_id: Optional[str] = None
    sink_id: Optional[str] = None
    source_type: Optional[str] = "UNTRUSTED_INPUT"
    sink_type: Optional[str] = None
    flow_type: Optional[str] = "data_flow"
    required_sanitizer: Optional[str] = None
    found_sanitizer: Optional[str] = None
    target_var: Optional[str] = Field(
        None, description="Operand targeted by the sink operation"
    )
    guarded_target: Optional[str] = Field(
        None, description="Operand protected by the sanitizer guard"
    )
    failed_anchor_lines: List[str] = Field(default_factory=list)
    invalid_at: Optional[float] = None
    verifier_logic_error: bool = False
    verifier_report: Dict[str, Any] = Field(default_factory=dict)
    judge_rationale: str = ""

    def to_flow_dict(self) -> Dict[str, Any]:
        """Adapter for backward compatibility with FlowSignature dict schemas."""
        return {
            "source_id": self.source_id or "",
            "sink_id": self.sink_id or "",
            "source_type": self.source_type or "UNTRUSTED_INPUT",
            "sink_type": self.sink_type or "",
            "flow_type": self.flow_type or "data_flow",
            "sanitizer_type": self.found_sanitizer,
            "target_var": self.target_var,
            "guarded_target": self.guarded_target,
            "failure_bucket": self.failure_bucket,
            "failed_anchor_lines": self.failed_anchor_lines,
            "invalid_at": self.invalid_at,
        }


# ---------------------------------------------------------------------------
# §3.4  A2A Reflector API Schema (HTTP Port 8004)
# ---------------------------------------------------------------------------


class ReflectRequest(BaseModel):
    """Inbound request to the Reflector service for prompt mutation."""

    attempt_index: int = Field(..., ge=1, description="Current attempt number")
    scenario_id: str
    predicate_family: str
    taxonomy_bucket: TaxonomyBucket
    code_text: str
    graph_diagnostic: GraphDiagnosticSignature
    current_system_prompt: str
    raw_execution_trace: Optional[Dict[str, Any]] = None


class ReflectResponse(BaseModel):
    """Outbound response from the Reflector service."""

    status: Literal["SUCCESS", "FALLBACK_BASELINE", "NO_MUTATION_NEEDED"]
    mutated_system_prompt: str = Field(
        ..., min_length=1, description="Must be non-empty valid prompt"
    )
    mutation_rationale: str
    applied_topological_rule: str
    taxonomy_bucket: TaxonomyBucket
    pareto_variant_id: str = Field(
        ..., min_length=1, description="Canonical mutation identifier"
    )
    estimated_correction_success_probability: float = Field(
        ..., ge=0.0, le=1.0
    )


# ---------------------------------------------------------------------------
# §5.1  Taxonomy Classification
# ---------------------------------------------------------------------------

# Keyword sets for deterministic predicate -> taxonomy routing.
# Order matters: first match wins within each bucket.
_MEMORY_SAFETY_KEYWORDS = frozenset({
    "buffer_overflow", "buffer overflow", "heap overflow", "stack overflow",
    "out_of_bounds", "out-of-bounds", "oob_write", "oob_read", "oob write",
    "use_after_free", "use-after-free", "double_free", "double free",
    "off_by_one", "off-by-one", "memcpy", "strcpy", "strncpy",
    "pointer", "null_deref", "null dereference", "dangling",
    "memory", "heap", "stack_buffer", "buffer",
})

_INTEGER_ARITHMETIC_KEYWORDS = frozenset({
    "integer_overflow", "integer overflow", "int_overflow",
    "unsigned_wrap", "unsigned wrap", "wrap-around", "wraparound",
    "width_truncation", "truncation", "signedness",
    "integer_underflow", "integer underflow",
})

_CONCURRENCY_KEYWORDS = frozenset({
    "toctou", "race_condition", "race condition",
    "deadlock", "double_checked_locking", "double-checked locking",
    "lock_free", "lock-free", "concurrent", "concurrency",
    "data_race", "data race", "thread_safety", "thread safety",
})

_INPUT_VALIDATION_KEYWORDS = frozenset({
    "command_injection", "command injection", "code_injection",
    "path_traversal", "path traversal", "directory_traversal",
    "format_string", "format string", "deserialization",
    "sql_injection", "sql injection", "xss", "cross_site",
    "injection", "untrusted", "input_validation",
})


_TAXONOMY_RULES: Tuple[Tuple[TaxonomyBucket, FrozenSet[str]], ...] = (
    ("memory_safety", _MEMORY_SAFETY_KEYWORDS),
    ("integer_arithmetic", _INTEGER_ARITHMETIC_KEYWORDS),
    ("concurrency", _CONCURRENCY_KEYWORDS),
    ("input_validation", _INPUT_VALIDATION_KEYWORDS),
)


def classify_taxonomy_bucket(predicate: str) -> TaxonomyBucket:
    """
    Classify a vulnerability predicate string into one of the four
    taxonomy buckets defined in Spec §5.1.

    Uses case-insensitive keyword matching with deterministic precedence:
    memory_safety > integer_arithmetic > concurrency > input_validation.

    Falls back to ``input_validation`` when no keyword matches.
    """
    lower = predicate.lower()
    for bucket, keywords in _TAXONOMY_RULES:
        if any(kw in lower for kw in keywords):
            return bucket
    return "input_validation"


# ---------------------------------------------------------------------------
# §3.2  Deterministic Graph Diagnostic Classifier
# ---------------------------------------------------------------------------


def _is_flow_sanitized(sig: FlowSignature, sink_node: Dict[str, Any]) -> bool:
    """Return True if signature has valid sanitizer type and matching guarded target."""
    if not sig.sanitizer_type or not is_sanitizer_valid_for_sink(sig.sink_type, sig.sanitizer_type):
        return False
    sink_target = sink_node.get("target_var")
    return bool(sig.guarded_target and sink_target and sig.guarded_target == sink_target)


def _find_first_unsanitized_sink(
    snapshot: FlowGraphSnapshot,
) -> Optional[FlowSignature]:
    """Return the first active signature with an untrusted unsanitized flow, or None."""
    for sig in snapshot.signatures:
        if sig.source_type == "UNTRUSTED_INPUT" and sig.sink_type in {
            "MEMORY_WRITE", "POINTER_DEREF", "ARRAY_INDEX", "SYSTEM_CALL",
        }:
            sink_node = snapshot.nodes.get(sig.sink_id, {})
            if not _is_flow_sanitized(sig, sink_node):
                return sig
    return None


def _find_first_sink_signature(
    snapshot: FlowGraphSnapshot,
) -> Optional[FlowSignature]:
    """Return the first signature with a recognized sink type."""
    for sig in snapshot.signatures:
        if sig.sink_type in {"MEMORY_WRITE", "POINTER_DEREF", "ARRAY_INDEX", "SYSTEM_CALL"}:
            return sig
    return None


def _determine_required_sanitizer(sink_type: Optional[str]) -> Optional[str]:
    """Map sink type to the primary required sanitizer."""
    mapping = {
        "MEMORY_WRITE": "BOUNDS_CHECK",
        "ARRAY_INDEX": "RANGE_VALIDATION",
        "POINTER_DEREF": "NULL_CHECK",
        "SYSTEM_CALL": "COMMAND_SANITIZATION",
    }
    return mapping.get(sink_type or "")


def _is_anchor_unmatched(debate_result: Any) -> bool:
    """Return True if candidate line anchors failed repository match."""
    b2_strict_fail = getattr(debate_result, "b2_strict_fail", False)
    b2_anchor_match = getattr(debate_result, "b2_anchor_match", True)
    return b2_strict_fail or not b2_anchor_match


def _has_recognized_sink(graph_snapshot: FlowGraphSnapshot) -> bool:
    """Return True if any recognized security-sensitive sink signature is present."""
    return any(
        sig.sink_type in {"MEMORY_WRITE", "POINTER_DEREF", "ARRAY_INDEX", "SYSTEM_CALL"}
        for sig in graph_snapshot.signatures
    )


def _has_tracked_source_for_sinks(graph_snapshot: FlowGraphSnapshot) -> bool:
    """Return True if at least one recognized sink signature has a tracked (non-UNKNOWN_ORIGIN) source."""
    return any(
        sig.source_type != "UNKNOWN_ORIGIN"
        for sig in graph_snapshot.signatures
        if sig.sink_type in {"MEMORY_WRITE", "POINTER_DEREF", "ARRAY_INDEX", "SYSTEM_CALL"}
    )


def _build_source_missing_diagnostic(
    first_sig: Optional[FlowSignature],
    base_fields: Dict[str, Any],
) -> GraphDiagnosticSignature:
    """Construct a B_SOURCE_MISSING diagnostic signature."""
    if first_sig is None:
        return GraphDiagnosticSignature(failure_bucket="B_SOURCE_MISSING", **base_fields)
    return GraphDiagnosticSignature(
        failure_bucket="B_SOURCE_MISSING",
        source_id=first_sig.source_id,
        source_type=first_sig.source_type,
        sink_id=first_sig.sink_id,
        sink_type=first_sig.sink_type,
        flow_type=first_sig.flow_type,
        **base_fields,
    )


def _build_sanitized_flow_diagnostic(
    first_sig: Optional[FlowSignature],
    graph_snapshot: FlowGraphSnapshot,
    base_fields: Dict[str, Any],
) -> GraphDiagnosticSignature:
    """Construct a B_LOGIC_ERROR diagnostic for a rejected attempt with a fully sanitized graph."""
    if first_sig is None:
        return GraphDiagnosticSignature(failure_bucket="B_LOGIC_ERROR", **base_fields)
    sink_node = graph_snapshot.nodes.get(first_sig.sink_id, {})
    return GraphDiagnosticSignature(
        failure_bucket="B_LOGIC_ERROR",
        source_id=first_sig.source_id,
        source_type=first_sig.source_type,
        sink_id=first_sig.sink_id,
        sink_type=first_sig.sink_type,
        flow_type=first_sig.flow_type,
        target_var=sink_node.get("target_var"),
        found_sanitizer=first_sig.sanitizer_type,
        guarded_target=first_sig.guarded_target,
        invalid_at=first_sig.invalid_at,
        **base_fields,
    )


def _classify_sanitizer_diagnostic(
    unsanitized: FlowSignature,
    graph_snapshot: FlowGraphSnapshot,
    base_fields: Dict[str, Any],
) -> GraphDiagnosticSignature:
    """Classify an unsanitized flow into Bucket 6 (MISMATCH) or Bucket 7 (TARGET_MISMATCH)."""
    sink_node = graph_snapshot.nodes.get(unsanitized.sink_id, {})
    target_var = sink_node.get("target_var")
    required = _determine_required_sanitizer(unsanitized.sink_type)

    is_type_valid = (
        unsanitized.sanitizer_type is not None
        and is_sanitizer_valid_for_sink(unsanitized.sink_type, unsanitized.sanitizer_type)
    )

    if not is_type_valid:
        return GraphDiagnosticSignature(
            failure_bucket="B_SANITIZER_MISMATCH",
            source_id=unsanitized.source_id,
            source_type=unsanitized.source_type,
            sink_id=unsanitized.sink_id,
            sink_type=unsanitized.sink_type,
            flow_type=unsanitized.flow_type,
            required_sanitizer=required,
            found_sanitizer=unsanitized.sanitizer_type,
            target_var=target_var,
            guarded_target=unsanitized.guarded_target,
            invalid_at=unsanitized.invalid_at,
            **base_fields,
        )

    return GraphDiagnosticSignature(
        failure_bucket="B_SANITIZER_TARGET_MISMATCH",
        source_id=unsanitized.source_id,
        source_type=unsanitized.source_type,
        sink_id=unsanitized.sink_id,
        sink_type=unsanitized.sink_type,
        flow_type=unsanitized.flow_type,
        required_sanitizer=required,
        found_sanitizer=unsanitized.sanitizer_type,
        target_var=target_var,
        guarded_target=unsanitized.guarded_target,
        invalid_at=unsanitized.invalid_at,
        **base_fields,
    )


def classify_graph_diagnostic(
    debate_result: Any,
    graph_snapshot: FlowGraphSnapshot,
    scenario_id: str = "",
    predicate_family: str = "",
) -> GraphDiagnosticSignature:
    """
    Classify a failed attempt into exactly one diagnostic bucket using strict
    top-to-bottom precedence from Spec §3.2.

    Precedence order (highest first):
      1. B_UNSUPPORTED_SYNTAX  — incomplete parse with no AST nodes
      2. B_LOGIC_ERROR         — verifier detected factual contradiction
      3. B_ANCHOR_UNMATCHED    — code anchors failed source-match
      4. B_SOURCE_MISSING      — sink present but source is untracked
      5. B_SINK_MISSING        — no sink operation in AST
      6. B_SANITIZER_MISMATCH  — sanitizer type doesn't match sink
      7. B_SANITIZER_TARGET_MISMATCH — sanitizer guards wrong variable

    Args:
        debate_result: Object with `verifier_logic_error`, `b2_strict_fail`,
            `b2_anchor_match` attributes.
        graph_snapshot: The FlowGraphSnapshot from Tree-sitter extraction.
        scenario_id: Scenario identifier for provenance.
        predicate_family: Vulnerability predicate family string.

    Returns:
        GraphDiagnosticSignature with the assigned failure bucket and
        all available topological metadata.
    """
    base_fields: Dict[str, Any] = {
        "scenario_id": scenario_id or graph_snapshot.scenario_id,
        "predicate_family": predicate_family,
        "verifier_logic_error": getattr(debate_result, "verifier_logic_error", False),
        "verifier_report": getattr(debate_result, "verifier_report", {}),
        "judge_rationale": getattr(debate_result, "judge_rationale", ""),
    }

    # ── Bucket 1 (Highest): B_UNSUPPORTED_SYNTAX ──
    if not graph_snapshot.is_complete and not graph_snapshot.nodes:
        return GraphDiagnosticSignature(
            failure_bucket="B_UNSUPPORTED_SYNTAX",
            **base_fields,
        )

    # ── Bucket 2: B_LOGIC_ERROR ──
    if getattr(debate_result, "verifier_logic_error", False):
        return GraphDiagnosticSignature(
            failure_bucket="B_LOGIC_ERROR",
            **base_fields,
        )

    # ── Bucket 3: B_ANCHOR_UNMATCHED ──
    if _is_anchor_unmatched(debate_result):
        failed_anchors = getattr(debate_result, "failed_anchor_lines", [])
        return GraphDiagnosticSignature(
            failure_bucket="B_ANCHOR_UNMATCHED",
            failed_anchor_lines=failed_anchors,
            **base_fields,
        )

    # ── Bucket 4: B_SOURCE_MISSING ──
    has_sink = _has_recognized_sink(graph_snapshot)
    if has_sink and not _has_tracked_source_for_sinks(graph_snapshot) and graph_snapshot.signatures:
        first_sig = _find_first_sink_signature(graph_snapshot)
        return _build_source_missing_diagnostic(first_sig, base_fields)

    # ── Bucket 5: B_SINK_MISSING ──
    if not has_sink:
        return GraphDiagnosticSignature(
            failure_bucket="B_SINK_MISSING",
            **base_fields,
        )

    # ── Bucket 6 & 7: Sanitizer checks on unsanitized flow ──
    unsanitized = _find_first_unsanitized_sink(graph_snapshot)
    if unsanitized is not None:
        return _classify_sanitizer_diagnostic(unsanitized, graph_snapshot, base_fields)

    # Fallback: if a recognized sink exists and all flows in the graph are sanitized,
    # the rejection is a verification/reasoning contradiction rather than a missing sink.
    first_sig = _find_first_sink_signature(graph_snapshot)
    return _build_sanitized_flow_diagnostic(first_sig, graph_snapshot, base_fields)


# ---------------------------------------------------------------------------
# §3.4  Static Baseline Specialist Prompts
# ---------------------------------------------------------------------------

_BASELINE_PROMPTS: Dict[str, str] = {
    "memory_safety": (
        "You are a security analyst specializing in memory safety vulnerabilities "
        "in C/C++ code. Focus on buffer overflows, use-after-free, double-free, "
        "off-by-one errors, and pointer dereference bugs. When analyzing code:\n"
        "1. Identify all memory write operations (memcpy, strcpy, strncpy, etc.)\n"
        "2. Trace data flow from untrusted input sources to memory sinks\n"
        "3. Verify bounds checking and range validation before write operations\n"
        "4. Quote exact line anchors from the source code\n"
        "5. Provide concrete source-to-sink data flow chains"
    ),
    "integer_arithmetic": (
        "You are a security analyst specializing in integer arithmetic vulnerabilities "
        "in C/C++ code. Focus on integer overflow, unsigned wrap-around, width "
        "truncation, and signedness comparison bugs. When analyzing code:\n"
        "1. Identify arithmetic operations that may overflow or wrap\n"
        "2. Check for implicit type conversions and width truncations\n"
        "3. Verify range validation before arithmetic is used in size computations\n"
        "4. Quote exact line anchors from the source code\n"
        "5. Trace how tainted integer values propagate to sensitive operations"
    ),
    "concurrency": (
        "You are a security analyst specializing in concurrency vulnerabilities "
        "in C/C++ code. Focus on TOCTOU race conditions, deadlocks, data races, "
        "and lock-ordering bugs. When analyzing code:\n"
        "1. Identify time-of-check to time-of-use windows\n"
        "2. Verify atomicity of check-then-act sequences\n"
        "3. Look for shared mutable state accessed without proper synchronization\n"
        "4. Quote exact line anchors from the source code\n"
        "5. Demonstrate the specific interleaving that triggers the vulnerability"
    ),
    "input_validation": (
        "You are a security analyst specializing in input validation vulnerabilities "
        "in C/C++ code. Focus on command injection, path traversal, format string "
        "bugs, and untrusted deserialization. When analyzing code:\n"
        "1. Identify all external input sources (user input, files, network)\n"
        "2. Trace input propagation to dangerous sinks (system, exec, open, etc.)\n"
        "3. Verify sanitization, allowlisting, or escaping before sink operations\n"
        "4. Quote exact line anchors from the source code\n"
        "5. Construct concrete exploit payloads demonstrating the attack vector"
    ),
}


def get_static_baseline_prompt(taxonomy: TaxonomyBucket) -> str:
    """
    Return the frozen specialist baseline prompt for the given taxonomy bucket.

    Raises:
        KeyError: If taxonomy is not one of the four defined buckets.
    """
    if taxonomy not in _BASELINE_PROMPTS:
        raise KeyError(
            f"Unknown taxonomy bucket: {taxonomy!r}. "
            f"Expected one of {list(_BASELINE_PROMPTS.keys())}"
        )
    return _BASELINE_PROMPTS[taxonomy]
