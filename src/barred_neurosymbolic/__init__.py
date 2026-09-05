"""
BARRED-Neurosymbolic Core Package.
Deterministic Acceptance Boundaries & AST-Guided GEPA for AI Swarms.
"""

from .ast_flow import extract_graphify_flow_snapshot
from .reachability import evaluate_graph_reachability, FlowGraphSnapshot, FlowSignature
from .invariants import compute_b_metrics, check_anti_gaming_invariants

__all__ = [
    "extract_graphify_flow_snapshot",
    "evaluate_graph_reachability",
    "FlowGraphSnapshot",
    "FlowSignature",
    "compute_b_metrics",
    "check_anti_gaming_invariants",
]
