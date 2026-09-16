"""
Graph-Topology Semantic Data-Flow Schema and Evaluator Module.
Implements the contract specified in RFC_GRAPH_DATAFLOW_PRE_FILTER.md.
"""

import copy
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Dict, List, Optional, Set, Tuple


SUPPORTED_SINKS = {"MEMORY_WRITE", "POINTER_DEREF", "ARRAY_INDEX", "SYSTEM_CALL"}
VALID_SANITIZERS = {"BOUNDS_CHECK", "RANGE_VALIDATION", "NULL_CHECK", "COMMAND_SANITIZATION", "ALLOWLIST_CHECK"}
VERIFIED_GUARD_PROOFS = {"SYMBOLIC_COMPLETE", "RUNTIME_MEDIATION", "DESCRIPTOR_PINNED"}


class ReachabilityState(str, Enum):
    PROVEN_REACHABLE = "PROVEN_REACHABLE"
    UNKNOWN_REACHABLE = "UNKNOWN_REACHABLE"
    PROVEN_UNREACHABLE = "PROVEN_UNREACHABLE"


class GuardVerificationState(str, Enum):
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    CANDIDATE_ONLY = "CANDIDATE_ONLY"
    ABSENT = "ABSENT"


class AssetExposureState(str, Enum):
    EXPOSED = "EXPOSED"
    UNKNOWN = "UNKNOWN"
    ISOLATED = "ISOLATED"


@dataclass(frozen=True)
class EpistemicEvaluationResult:
    reachability: ReachabilityState
    guard_verification: GuardVerificationState
    asset_exposure: AssetExposureState
    operational_exposure: float
    risk_score: float
    witness_path: Optional[List[str]] = None
    unresolved_reasons: List[str] = field(default_factory=list)
    curiosity_bucket: Optional[str] = None
    curiosity_directive: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "reachability": self.reachability.value,
            "guard_verification": self.guard_verification.value,
            "asset_exposure": self.asset_exposure.value,
            "operational_exposure": self.operational_exposure,
            "risk_score": self.risk_score,
            "witness_path": self.witness_path,
            "unresolved_reasons": list(self.unresolved_reasons),
            "curiosity_bucket": self.curiosity_bucket,
            "curiosity_directive": self.curiosity_directive,
        }


@dataclass(frozen=True)
class FlowSignature:
    source_id: str
    sink_id: str
    source_type: str
    sink_type: str
    flow_type: str
    sanitizer_type: Optional[str] = None
    guarded_target: Optional[str] = None
    invalid_at: Optional[float] = None
    is_guard_verified: bool = False
    guard_proof_type: Optional[str] = None
    is_entrypoint_reachable: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "sink_id": self.sink_id,
            "source_type": self.source_type,
            "sink_type": self.sink_type,
            "flow_type": self.flow_type,
            "sanitizer_type": self.sanitizer_type,
            "guarded_target": self.guarded_target,
            "invalid_at": self.invalid_at,
            "is_guard_verified": self.is_guard_verified,
            "guard_proof_type": self.guard_proof_type,
            "is_entrypoint_reachable": self.is_entrypoint_reachable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FlowSignature":
        return cls(
            source_id=data["source_id"],
            sink_id=data["sink_id"],
            source_type=data["source_type"],
            sink_type=data["sink_type"],
            flow_type=data["flow_type"],
            sanitizer_type=data.get("sanitizer_type"),
            guarded_target=data.get("guarded_target"),
            invalid_at=data.get("invalid_at"),
            is_guard_verified=bool(data.get("is_guard_verified", False)),
            guard_proof_type=data.get("guard_proof_type"),
            is_entrypoint_reachable=data.get("is_entrypoint_reachable"),
        )


@dataclass
class FlowGraphSnapshot:
    snapshot_id: str
    scenario_id: str
    version: int
    created_at: float
    nodes: Dict[str, dict] = field(default_factory=dict)
    signatures: List[FlowSignature] = field(default_factory=list)
    is_complete: bool = True
    parse_error: Optional[str] = None
    has_unresolved_callers: bool = False

    def __post_init__(self):
        # Detach mutable inputs to preserve snapshot immutability
        self.nodes = copy.deepcopy(self.nodes)
        self.signatures = list(self.signatures)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "scenario_id": self.scenario_id,
            "version": self.version,
            "created_at": self.created_at,
            "nodes": copy.deepcopy(self.nodes),
            "signatures": [sig.to_dict() for sig in self.signatures],
            "is_complete": self.is_complete,
            "parse_error": self.parse_error,
            "has_unresolved_callers": self.has_unresolved_callers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FlowGraphSnapshot":
        if "created_at" not in data:
            raise KeyError("FlowGraphSnapshot deserialization requires explicit 'created_at' timestamp")
        return cls(
            snapshot_id=data["snapshot_id"],
            scenario_id=data["scenario_id"],
            version=data["version"],
            created_at=float(data["created_at"]),
            nodes=copy.deepcopy(data.get("nodes", {})),
            signatures=[FlowSignature.from_dict(s) for s in data.get("signatures", [])],
            is_complete=data.get("is_complete", True),
            parse_error=data.get("parse_error"),
            has_unresolved_callers=data.get("has_unresolved_callers", False),
        )


def _is_finite_numeric(val: float) -> bool:
    """Returns True if val is a finite int or float (excluding bool and non-numeric types)."""
    if val is None or isinstance(val, bool):
        return False
    if isinstance(val, (int, float)):
        return math.isfinite(val)
    return False


def is_sanitizer_valid_for_sink(sink_type: str, sanitizer_type: Optional[str]) -> bool:
    """Verifies that sanitizer proof matches specific sink requirements."""
    if not sanitizer_type:
        return False
    if sink_type in ("MEMORY_WRITE", "ARRAY_INDEX"):
        return sanitizer_type in ("BOUNDS_CHECK", "RANGE_VALIDATION")
    if sink_type == "POINTER_DEREF":
        return sanitizer_type == "NULL_CHECK"
    if sink_type == "SYSTEM_CALL":
        return sanitizer_type in ("COMMAND_SANITIZATION", "ALLOWLIST_CHECK")
    return False


def _has_valid_signature_endpoints(sig: FlowSignature, nodes: Dict[str, dict]) -> bool:
    return sig.source_id in nodes and sig.sink_id in nodes


def _is_signature_active(sig: FlowSignature, eval_time: float) -> Optional[bool]:
    if sig.invalid_at is None:
        return True
    if not _is_finite_numeric(sig.invalid_at):
        return None
    return sig.invalid_at > eval_time


def _filter_active_signatures(
    graph_snapshot: FlowGraphSnapshot, eval_time: float
) -> Optional[List[FlowSignature]]:
    """
    Extracts active signatures evaluated at eval_time.
    Returns None (failing closed) if non-finite/non-numeric timestamps, unsupported sinks, or invalid node endpoints appear.
    """
    if graph_snapshot.signatures and not graph_snapshot.nodes:
        return None

    active: List[FlowSignature] = []
    for sig in graph_snapshot.signatures:
        if sig.sink_type not in SUPPORTED_SINKS:
            return None  # Unsupported sink -> Fail closed

        if not _has_valid_signature_endpoints(sig, graph_snapshot.nodes):
            return None  # Missing endpoint nodes -> Fail closed

        is_active = _is_signature_active(sig, eval_time)
        if is_active is None:
            return None  # Malformed or non-finite invalid_at -> Fail closed
        if not is_active:
            continue  # Invalidated edge

        active.append(sig)

    return active


def _is_sanitizer_proof_valid(sig: FlowSignature, sink_node: dict) -> bool:
    """Returns True only when sanitizer type and guarded target both prove this sink."""
    if not is_sanitizer_valid_for_sink(sig.sink_type, sig.sanitizer_type):
        return False

    sink_target = sink_node.get("target_var")
    if not sig.guarded_target or not sink_target:
        return False

    return sig.guarded_target == sink_target


def _has_unsanitized_path(
    active_signatures: List[FlowSignature], graph_snapshot: FlowGraphSnapshot
) -> bool:
    """Returns True if any active signature contains an unsanitized untrusted flow."""
    for sig in active_signatures:
        if sig.source_type == "UNTRUSTED_INPUT" and sig.sink_type in SUPPORTED_SINKS:
            sink_node = graph_snapshot.nodes.get(sig.sink_id, {})
            if not _is_sanitizer_proof_valid(sig, sink_node):
                return True
    return False


def omega_reachability(state: ReachabilityState) -> float:
    """Multiplier omega for reachability state: 1.0 for reachable/unknown, 0.0 for proven unreachable."""
    if state == ReachabilityState.PROVEN_REACHABLE:
        return 1.0
    elif state == ReachabilityState.UNKNOWN_REACHABLE:
        return 1.0  # Fail closed
    elif state == ReachabilityState.PROVEN_UNREACHABLE:
        return 0.0
    return 1.0


def gamma_asset_exposure(state: AssetExposureState) -> float:
    """Multiplier gamma for asset exposure: 1.0 for exposed/unknown, 0.0 for isolated."""
    if state == AssetExposureState.EXPOSED:
        return 1.0
    elif state == AssetExposureState.UNKNOWN:
        return 1.0  # Fail closed
    elif state == AssetExposureState.ISOLATED:
        return 0.0
    return 1.0


def compute_operational_exposure(
    reachability: ReachabilityState,
    guard_verification: GuardVerificationState,
    asset_exposure: AssetExposureState,
    cvss_base: float = 10.0,
) -> float:
    """
    Computes operational exposure according to Spec Eq. 1:
      Exposure = CVSS_base * omega(R_reach) * gamma(AssetExposed)
    Short-circuits to 0.0 if GuardVerified == VERIFIED_COMPLETE.
    """
    if guard_verification == GuardVerificationState.VERIFIED_COMPLETE:
        return 0.0

    omega = omega_reachability(reachability)
    gamma = gamma_asset_exposure(asset_exposure)
    cvss = float(cvss_base) if _is_finite_numeric(cvss_base) else 10.0
    cvss = max(0.0, min(10.0, cvss))
    return round(cvss * omega * gamma, 4)


def _build_fail_closed_result(
    reason: str,
    asset_exposure: AssetExposureState,
    cvss_base: float,
    curiosity_bucket: Optional[str] = None,
    curiosity_directive: Optional[str] = None,
) -> EpistemicEvaluationResult:
    reachability = ReachabilityState.UNKNOWN_REACHABLE
    guard_state = GuardVerificationState.ABSENT
    exposure = compute_operational_exposure(reachability, guard_state, asset_exposure, cvss_base)
    return EpistemicEvaluationResult(
        reachability=reachability,
        guard_verification=guard_state,
        asset_exposure=asset_exposure,
        operational_exposure=exposure,
        risk_score=1.0,
        witness_path=None,
        unresolved_reasons=[reason],
        curiosity_bucket=curiosity_bucket,
        curiosity_directive=curiosity_directive,
    )


def _check_snapshot_integrity(
    graph_snapshot: FlowGraphSnapshot,
    as_of: Optional[float],
    asset_exposure: AssetExposureState,
    cvss_base: float,
) -> Optional[EpistemicEvaluationResult]:
    if not graph_snapshot.is_complete or graph_snapshot.parse_error is not None:
        reason = graph_snapshot.parse_error or "Incomplete AST graph snapshot"
        return _build_fail_closed_result(
            reason=reason,
            asset_exposure=asset_exposure,
            cvss_base=cvss_base,
            curiosity_bucket="BUCKET_A_CALLER_STRUCTURAL",
            curiosity_directive="Investigate syntax/parse errors and structural caller-graph completeness.",
        )
    if not _is_finite_numeric(graph_snapshot.created_at) or (as_of is not None and not _is_finite_numeric(as_of)):
        return _build_fail_closed_result(
            reason="Non-finite or malformed timestamp",
            asset_exposure=asset_exposure,
            cvss_base=cvss_base,
        )
    return None


def _evaluate_empty_untrusted_graph(
    graph_snapshot: FlowGraphSnapshot,
    asset_exposure: AssetExposureState,
    cvss_base: float,
) -> EpistemicEvaluationResult:
    if graph_snapshot.is_complete and not graph_snapshot.has_unresolved_callers:
        reachability = ReachabilityState.PROVEN_UNREACHABLE
        exposure = compute_operational_exposure(reachability, GuardVerificationState.ABSENT, asset_exposure, cvss_base)
        return EpistemicEvaluationResult(
            reachability=reachability,
            guard_verification=GuardVerificationState.ABSENT,
            asset_exposure=asset_exposure,
            operational_exposure=exposure,
            risk_score=0.05,
        )
    return _build_fail_closed_result(
        reason="Unresolved callers prevent exhaustive unreachability proof",
        asset_exposure=asset_exposure,
        cvss_base=cvss_base,
        curiosity_bucket="BUCKET_A_CALLER_STRUCTURAL",
        curiosity_directive="Investigate callers and entrypoint closures before asserting unreachability.",
    )


def _analyze_guard_proofs(
    untrusted_signatures: List[FlowSignature],
    graph_snapshot: FlowGraphSnapshot,
) -> Tuple[bool, bool, Optional[str], Optional[str]]:
    all_guards_verified = True
    any_candidate_guard = False
    curiosity_bucket: Optional[str] = None
    curiosity_directive: Optional[str] = None

    for sig in untrusted_signatures:
        sink_node = graph_snapshot.nodes.get(sig.sink_id, {})
        if not _is_sanitizer_proof_valid(sig, sink_node):
            all_guards_verified = False
            continue

        any_candidate_guard = True
        is_verified = sig.is_guard_verified or (sig.guard_proof_type in VERIFIED_GUARD_PROOFS)
        if not is_verified:
            all_guards_verified = False
            if not curiosity_directive:
                curiosity_bucket = "BUCKET_B_CONTRACT_SEMANTIC"
                curiosity_directive = (
                    f"Verify candidate guard '{sig.sanitizer_type}' on target '{sig.guarded_target}' "
                    f"with path-complete symbolic verification or runtime mediation proof."
                )

    return all_guards_verified, any_candidate_guard, curiosity_bucket, curiosity_directive


def _evaluate_unsanitized_flow(
    untrusted_signatures: List[FlowSignature],
    graph_snapshot: FlowGraphSnapshot,
    any_candidate_guard: bool,
    asset_exposure: AssetExposureState,
    cvss_base: float,
) -> EpistemicEvaluationResult:
    guard_state = (
        GuardVerificationState.CANDIDATE_ONLY
        if any_candidate_guard
        else GuardVerificationState.ABSENT
    )
    unresolved = graph_snapshot.has_unresolved_callers
    witness_candidate: Optional[List[str]] = None

    for sig in untrusted_signatures:
        sink_node = graph_snapshot.nodes.get(sig.sink_id, {})
        if not _is_sanitizer_proof_valid(sig, sink_node):
            if sig.is_entrypoint_reachable is False:
                unresolved = True
            if witness_candidate is None:
                witness_candidate = [sig.source_id, sig.sink_id]

    if unresolved:
        reachability = ReachabilityState.UNKNOWN_REACHABLE
        reasons = ["Callers or entrypoint reachability cannot be resolved"]
        curiosity_bucket = "BUCKET_A_CALLER_STRUCTURAL"
        target_var = untrusted_signatures[0].guarded_target or untrusted_signatures[0].sink_id
        curiosity_directive = (
            f"Investigate callers of entrypoint for sink {target_var} before modifying buffer signature."
        )
        witness_path = None
    else:
        reachability = ReachabilityState.PROVEN_REACHABLE
        reasons = []
        curiosity_bucket = None
        curiosity_directive = None
        witness_path = witness_candidate

    exposure = compute_operational_exposure(reachability, guard_state, asset_exposure, cvss_base)
    return EpistemicEvaluationResult(
        reachability=reachability,
        guard_verification=guard_state,
        asset_exposure=asset_exposure,
        operational_exposure=exposure,
        risk_score=1.0,
        witness_path=witness_path,
        unresolved_reasons=reasons,
        curiosity_bucket=curiosity_bucket,
        curiosity_directive=curiosity_directive,
    )


def _evaluate_sanitized_flow(
    all_guards_verified: bool,
    graph_snapshot: FlowGraphSnapshot,
    asset_exposure: AssetExposureState,
    cvss_base: float,
    curiosity_bucket: Optional[str],
    curiosity_directive: Optional[str],
) -> EpistemicEvaluationResult:
    if all_guards_verified:
        return EpistemicEvaluationResult(
            reachability=ReachabilityState.PROVEN_UNREACHABLE,
            guard_verification=GuardVerificationState.VERIFIED_COMPLETE,
            asset_exposure=asset_exposure,
            operational_exposure=0.0,
            risk_score=0.05,
        )

    guard_state = GuardVerificationState.CANDIDATE_ONLY
    if graph_snapshot.has_unresolved_callers:
        reachability = ReachabilityState.UNKNOWN_REACHABLE
        reasons = ["Unresolved caller closure under candidate guard"]
    else:
        reachability = ReachabilityState.PROVEN_REACHABLE
        reasons = []

    exposure = compute_operational_exposure(reachability, guard_state, asset_exposure, cvss_base)
    return EpistemicEvaluationResult(
        reachability=reachability,
        guard_verification=guard_state,
        asset_exposure=asset_exposure,
        operational_exposure=exposure,
        risk_score=0.05,
        witness_path=None,
        unresolved_reasons=reasons,
        curiosity_bucket=curiosity_bucket,
        curiosity_directive=curiosity_directive,
    )


def evaluate_epistemic_graph(
    graph_snapshot: FlowGraphSnapshot,
    as_of: Optional[float] = None,
    asset_exposure: AssetExposureState = AssetExposureState.UNKNOWN,
    cvss_base: float = 10.0,
) -> EpistemicEvaluationResult:
    """
    Full Epistemic Graph Evaluation Engine.
    Computes tri-state reachability (PROVEN_REACHABLE, UNKNOWN_REACHABLE, PROVEN_UNREACHABLE),
    guard verification state (VERIFIED_COMPLETE, CANDIDATE_ONLY, ABSENT),
    operational exposure, and Curiosity Bucket directives.
    """
    integrity_error = _check_snapshot_integrity(graph_snapshot, as_of, asset_exposure, cvss_base)
    if integrity_error is not None:
        return integrity_error

    eval_time = float(as_of) if as_of is not None else float(graph_snapshot.created_at)
    active = _filter_active_signatures(graph_snapshot, eval_time)
    if not active:
        return _build_fail_closed_result(
            reason="No active flow signatures at evaluation time",
            asset_exposure=asset_exposure,
            cvss_base=cvss_base,
        )

    untrusted_signatures = [
        sig for sig in active
        if sig.source_type == "UNTRUSTED_INPUT" and sig.sink_type in SUPPORTED_SINKS
    ]
    if not untrusted_signatures:
        return _evaluate_empty_untrusted_graph(graph_snapshot, asset_exposure, cvss_base)

    all_verified, any_candidate, bucket_b, directive_b = _analyze_guard_proofs(
        untrusted_signatures, graph_snapshot
    )

    if _has_unsanitized_path(active, graph_snapshot):
        return _evaluate_unsanitized_flow(
            untrusted_signatures, graph_snapshot, any_candidate, asset_exposure, cvss_base
        )

    return _evaluate_sanitized_flow(
        all_verified, graph_snapshot, asset_exposure, cvss_base, bucket_b, directive_b
    )


def evaluate_graph_reachability(
    graph_snapshot: FlowGraphSnapshot,
    as_of: Optional[float] = None,
) -> float:
    """
    Computes deterministic risk score based on source-to-sink graph topology.
    Fails closed (returns 1.0 / High Risk) if evidence is incomplete, parse errors occur,
    timestamps are non-finite/non-numeric (NaN / Inf / string / None), or signature endpoint nodes are missing.
    
    - Returns 1.0 (High Risk) for unsanitized paths, incomplete graphs, or invalid endpoints.
    - Returns 0.05 (Low Risk) for verified guarded or safe flows.
    """
    result = evaluate_epistemic_graph(graph_snapshot, as_of=as_of)
    return result.risk_score


def is_graph_candidate_rejected(
    graph_snapshot: FlowGraphSnapshot,
    as_of: Optional[float] = None,
    risk_threshold: float = 0.10,
) -> bool:
    """
    Evaluates whether candidate should be rejected based on advisory risk_threshold (default 0.10).
    Returns True if risk_score >= risk_threshold, False otherwise.
    """
    score = evaluate_graph_reachability(graph_snapshot, as_of=as_of)
    return score >= risk_threshold
