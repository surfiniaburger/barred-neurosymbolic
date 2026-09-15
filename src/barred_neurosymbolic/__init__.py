"""
BARRED-Neurosymbolic Core Package.
Deterministic Acceptance Boundaries, Epistemic Change-Impact Graphs & AST-Guided GEPA for AI Swarms.
"""

from .ast_flow import extract_graphify_flow_snapshot
from .reachability import (
    evaluate_graph_reachability,
    evaluate_epistemic_graph,
    compute_operational_exposure,
    omega_reachability,
    FlowGraphSnapshot,
    FlowSignature,
    ReachabilityState,
    GuardVerificationState,
    AssetExposureState,
    EpistemicEvaluationResult,
)
from .reflector_schemas import (
    classify_graph_diagnostic,
    CuriosityBucket,
    CuriosityDirective,
    GraphDiagnosticSignature,
    ReflectRequest,
    ReflectResponse,
)
from .pareto_registry import ParetoRegistry
from .invariants import compute_b_metrics, check_anti_gaming_invariants

__all__ = [
    "extract_graphify_flow_snapshot",
    "evaluate_graph_reachability",
    "evaluate_epistemic_graph",
    "compute_operational_exposure",
    "omega_reachability",
    "FlowGraphSnapshot",
    "FlowSignature",
    "ReachabilityState",
    "GuardVerificationState",
    "AssetExposureState",
    "EpistemicEvaluationResult",
    "classify_graph_diagnostic",
    "CuriosityBucket",
    "CuriosityDirective",
    "GraphDiagnosticSignature",
    "ReflectRequest",
    "ReflectResponse",
    "ParetoRegistry",
    "compute_b_metrics",
    "check_anti_gaming_invariants",
]
