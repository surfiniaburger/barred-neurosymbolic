"""
Contract and property tests for Epistemic Reachability, Exposure Calculation, and Curiosity Directives.
"""

import pytest
from unittest.mock import MagicMock

from barred_neurosymbolic.reachability import (
    AssetExposureState,
    EpistemicEvaluationResult,
    FlowGraphSnapshot,
    FlowSignature,
    GuardVerificationState,
    ReachabilityState,
    compute_operational_exposure,
    evaluate_epistemic_graph,
    evaluate_graph_reachability,
    gamma_asset_exposure,
    omega_reachability,
)
from barred_neurosymbolic.ast_flow import (
    extract_graphify_flow_snapshot,
)
from barred_neurosymbolic.reflector import mutate_system_prompt
from barred_neurosymbolic.reflector_schemas import (
    CuriosityDirective,
    GraphDiagnosticSignature,
    ReflectRequest,
    classify_graph_diagnostic,
)


def test_omega_reachability_multipliers():
    assert omega_reachability(ReachabilityState.PROVEN_REACHABLE) == 1.0
    assert omega_reachability(ReachabilityState.UNKNOWN_REACHABLE) == 1.0
    assert omega_reachability(ReachabilityState.PROVEN_UNREACHABLE) == 0.0


def test_gamma_asset_exposure_multipliers():
    assert gamma_asset_exposure(AssetExposureState.EXPOSED) == 1.0
    assert gamma_asset_exposure(AssetExposureState.UNKNOWN) == 1.0
    assert gamma_asset_exposure(AssetExposureState.ISOLATED) == 0.0


def test_compute_operational_exposure_formula_and_short_circuit():
    assert compute_operational_exposure(
        reachability=ReachabilityState.PROVEN_REACHABLE,
        guard_verification=GuardVerificationState.ABSENT,
        asset_exposure=AssetExposureState.EXPOSED,
        cvss_base=9.8,
    ) == 9.8

    assert compute_operational_exposure(
        reachability=ReachabilityState.UNKNOWN_REACHABLE,
        guard_verification=GuardVerificationState.CANDIDATE_ONLY,
        asset_exposure=AssetExposureState.UNKNOWN,
        cvss_base=7.5,
    ) == 7.5

    assert compute_operational_exposure(
        reachability=ReachabilityState.PROVEN_REACHABLE,
        guard_verification=GuardVerificationState.ABSENT,
        asset_exposure=AssetExposureState.ISOLATED,
        cvss_base=8.0,
    ) == 0.0

    assert compute_operational_exposure(
        reachability=ReachabilityState.PROVEN_UNREACHABLE,
        guard_verification=GuardVerificationState.ABSENT,
        asset_exposure=AssetExposureState.EXPOSED,
        cvss_base=10.0,
    ) == 0.0

    assert compute_operational_exposure(
        reachability=ReachabilityState.PROVEN_REACHABLE,
        guard_verification=GuardVerificationState.VERIFIED_COMPLETE,
        asset_exposure=AssetExposureState.EXPOSED,
        cvss_base=10.0,
    ) == 0.0


def test_proven_reachable_with_entrypoint_witness():
    sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="CALL_ARGUMENT",
        is_entrypoint_reachable=True,
    )
    snap = FlowGraphSnapshot(
        snapshot_id="snap_witness",
        scenario_id="sc_witness",
        version=1,
        created_at=100.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[sig],
        has_unresolved_callers=False,
    )

    res = evaluate_epistemic_graph(snap, cvss_base=8.5, asset_exposure=AssetExposureState.EXPOSED)
    assert res.reachability == ReachabilityState.PROVEN_REACHABLE
    assert res.witness_path == ["src_1", "sink_1"]
    assert res.guard_verification == GuardVerificationState.ABSENT
    assert res.operational_exposure == 8.5
    assert res.risk_score == 1.0


def test_unknown_reachable_on_unresolved_callers_emits_bucket_a():
    sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="CALL_ARGUMENT",
        is_entrypoint_reachable=False,
    )
    snap = FlowGraphSnapshot(
        snapshot_id="snap_unresolved",
        scenario_id="sc_unresolved",
        version=1,
        created_at=100.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[sig],
        has_unresolved_callers=True,
    )

    res = evaluate_epistemic_graph(snap)
    assert res.reachability == ReachabilityState.UNKNOWN_REACHABLE
    assert res.witness_path is None
    assert res.risk_score == 1.0
    assert res.curiosity_bucket == "BUCKET_A_CALLER_STRUCTURAL"
    assert "Investigate callers" in (res.curiosity_directive or "")


def test_proven_unreachable_exhaustive_proof_obligation():
    snap_clean = FlowGraphSnapshot(
        snapshot_id="snap_clean",
        scenario_id="sc_clean",
        version=1,
        created_at=100.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[
            FlowSignature(
                source_id="src_1",
                sink_id="sink_1",
                source_type="INTERNAL_CONST",
                sink_type="MEMORY_WRITE",
                flow_type="CONST_ASSIGN",
            )
        ],
        is_complete=True,
        has_unresolved_callers=False,
    )

    res_clean = evaluate_epistemic_graph(snap_clean)
    assert res_clean.reachability == ReachabilityState.PROVEN_UNREACHABLE
    assert res_clean.operational_exposure == 0.0
    assert res_clean.risk_score == 0.05

    snap_incomplete = FlowGraphSnapshot(
        snapshot_id="snap_incomp",
        scenario_id="sc_incomp",
        version=1,
        created_at=100.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[],
        is_complete=False,
        parse_error="Truncated function body",
    )
    res_incomp = evaluate_epistemic_graph(snap_incomplete)
    assert res_incomp.reachability == ReachabilityState.UNKNOWN_REACHABLE
    assert res_incomp.risk_score == 1.0


def test_guard_verification_promotion_contract():
    sig_candidate = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="CALL_ARGUMENT",
        sanitizer_type="BOUNDS_CHECK",
        guarded_target="dest_buf",
        is_guard_verified=False,
    )
    snap_cand = FlowGraphSnapshot(
        snapshot_id="snap_cand",
        scenario_id="sc_cand",
        version=1,
        created_at=100.0,
        nodes={"src_1": {}, "sink_1": {"target_var": "dest_buf"}},
        signatures=[sig_candidate],
    )

    res_cand = evaluate_epistemic_graph(snap_cand, cvss_base=9.0)
    assert res_cand.guard_verification == GuardVerificationState.CANDIDATE_ONLY
    assert res_cand.risk_score == 0.05
    assert res_cand.operational_exposure == 9.0
    assert res_cand.curiosity_bucket == "BUCKET_B_CONTRACT_SEMANTIC"
    assert "Verify candidate guard" in (res_cand.curiosity_directive or "")

    sig_verified = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="CALL_ARGUMENT",
        sanitizer_type="BOUNDS_CHECK",
        guarded_target="dest_buf",
        is_guard_verified=True,
        guard_proof_type="SYMBOLIC_COMPLETE",
    )
    snap_ver = FlowGraphSnapshot(
        snapshot_id="snap_ver",
        scenario_id="sc_ver",
        version=1,
        created_at=100.0,
        nodes={"src_1": {}, "sink_1": {"target_var": "dest_buf"}},
        signatures=[sig_verified],
    )

    res_ver = evaluate_epistemic_graph(snap_ver, cvss_base=9.0)
    assert res_ver.guard_verification == GuardVerificationState.VERIFIED_COMPLETE
    assert res_ver.reachability == ReachabilityState.PROVEN_UNREACHABLE
    assert res_ver.operational_exposure == 0.0
    assert res_ver.risk_score == 0.05
    assert res_ver.curiosity_bucket is None


def test_ast_extractor_static_linkage_routes_to_bucket_a():
    code = """
    static void handle_packet(char *payload, int len) {
        char buf[64];
        memcpy(buf, payload, len);
    }
    """
    snapshot = extract_graphify_flow_snapshot(code, scenario_id="test_static_func")
    assert snapshot.has_unresolved_callers is True
    assert len(snapshot.signatures) >= 1
    assert snapshot.signatures[0].is_entrypoint_reachable is False

    res = evaluate_epistemic_graph(snapshot)
    assert res.reachability == ReachabilityState.UNKNOWN_REACHABLE
    assert res.curiosity_bucket == "BUCKET_A_CALLER_STRUCTURAL"


def test_ast_extractor_public_entrypoint_reaches_proven_reachable():
    code = """
    int main(int argc, char **argv) {
        char buf[64];
        memcpy(buf, argv[1], 100);
        return 0;
    }
    """
    snapshot = extract_graphify_flow_snapshot(code, scenario_id="test_main_entrypoint")
    assert snapshot.has_unresolved_callers is False
    assert snapshot.signatures[0].is_entrypoint_reachable is True

    res = evaluate_epistemic_graph(snapshot)
    assert res.reachability == ReachabilityState.PROVEN_REACHABLE
    assert res.witness_path is not None


def test_reflector_agent_injects_curiosity_directive():
    mock_registry = MagicMock()
    mock_registry.get_known_dead_ends.return_value = set()
    mock_registry.get_pareto_variant_id.return_value = "var_pareto_1"

    directive = CuriosityDirective(
        bucket="BUCKET_A_CALLER_STRUCTURAL",
        target_symbol="handle_packet",
        reason="Static function has no callers in snippet",
        directive_text="Investigate callers of handle_packet before modifying buffer size.",
    )

    diag = GraphDiagnosticSignature(
        scenario_id="sc_test",
        predicate_family="BUFFER_OVERFLOW",
        failure_bucket="B_SINK_MISSING",
        curiosity_directive=directive,
    )

    req = ReflectRequest(
        attempt_index=1,
        scenario_id="sc_test",
        predicate_family="BUFFER_OVERFLOW",
        taxonomy_bucket="memory_safety",
        code_text="static void handle_packet() {}",
        graph_diagnostic=diag,
        current_system_prompt="Analyze code safety.",
        curiosity_directive=directive,
    )

    resp = mutate_system_prompt(req, mock_registry)
    assert resp.status == "SUCCESS"
    assert "[Curiosity Directive - BUCKET_A_CALLER_STRUCTURAL]" in resp.mutated_system_prompt
    assert directive.directive_text in resp.mutated_system_prompt
    assert resp.curiosity_directive == directive


def test_pareto_registry_find_best_variant_local_import(tmp_path):
    from barred_neurosymbolic.pareto_registry import ParetoRegistry
    reg = ParetoRegistry(gepa_dir=tmp_path)
    # Register a variant and retrieve pareto prompt
    reg.register_pareto_prompt(
        taxonomy="memory_safety",
        prompt="Sample Pareto Prompt",
        variant_id="var_test_1",
        score=1.5,
        rationale="Repaired test",
    )
    best = reg.get_pareto_prompt("memory_safety")
    assert best == "Sample Pareto Prompt"
    var_id = reg.get_pareto_variant_id("memory_safety")
    assert var_id == "var_test_1"
