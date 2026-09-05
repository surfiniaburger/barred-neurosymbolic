"""
Contract tests for FlowSignature, FlowGraphSnapshot, and evaluate_graph_reachability.
Verifies serialization, sanitizer proof matching, time-aware invalidation, fail-closed handling, node endpoint validation, snapshot immutability, and non-finite timestamp validation.
"""

import pytest
import math
import time
from barred_neurosymbolic.reachability import (
    FlowSignature,
    FlowGraphSnapshot,
    evaluate_graph_reachability,
    is_graph_candidate_rejected,
    is_sanitizer_valid_for_sink,
)


def test_flow_signature_serialization():
    sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
        guarded_target="len_var",
        invalid_at=100.0,
    )
    data = sig.to_dict()
    assert data["source_id"] == "src_1"
    assert data["sanitizer_type"] == "BOUNDS_CHECK"
    assert data["invalid_at"] == 100.0

    restored = FlowSignature.from_dict(data)
    assert restored == sig


def test_flow_graph_snapshot_serialization_and_created_at():
    sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="POINTER_DEREF",
        flow_type="DEREF",
        sanitizer_type="NULL_CHECK",
    )
    snapshot = FlowGraphSnapshot(
        snapshot_id="snap_123",
        scenario_id="scenario_abc",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {"kind": "source"}, "sink_1": {"kind": "sink", "target_var": "ptr"}},
        signatures=[sig],
    )
    data = snapshot.to_dict()
    assert data["snapshot_id"] == "snap_123"
    assert data["created_at"] == 1000.0

    restored = FlowGraphSnapshot.from_dict(data)
    assert restored.snapshot_id == snapshot.snapshot_id
    assert restored.created_at == 1000.0

    # Deserialization without explicit created_at fails hard
    data_bad = {"snapshot_id": "s", "scenario_id": "sc", "version": 1}
    with pytest.raises(KeyError, match="created_at"):
        FlowGraphSnapshot.from_dict(data_bad)


def test_flow_graph_snapshot_immutability():
    original_nodes = {"src_1": {"kind": "source"}, "sink_1": {"kind": "sink"}}
    original_signatures = [
        FlowSignature(
            source_id="src_1",
            sink_id="sink_1",
            source_type="UNTRUSTED_INPUT",
            sink_type="MEMORY_WRITE",
            flow_type="DIRECT_ASSIGN",
        )
    ]
    snapshot = FlowGraphSnapshot(
        snapshot_id="snap_immut",
        scenario_id="scenario_abc",
        version=1,
        created_at=1000.0,
        nodes=original_nodes,
        signatures=original_signatures,
    )
    # Mutating original caller list should not alter snapshot.signatures
    original_signatures.clear()
    assert len(snapshot.signatures) == 1

    # Mutating original caller dictionary should not alter snapshot.nodes
    original_nodes["src_1"]["kind"] = "MUTATED_CALLER"
    assert snapshot.nodes["src_1"]["kind"] == "source"

    # Mutating dictionary returned by to_dict() should not alter snapshot.nodes
    serialized = snapshot.to_dict()
    serialized["nodes"]["src_1"]["kind"] = "MUTATED_SERIALIZED"
    assert snapshot.nodes["src_1"]["kind"] == "source"


def test_sink_specific_sanitizer_matching():
    # POINTER_DEREF strictly requires NULL_CHECK
    assert is_sanitizer_valid_for_sink("POINTER_DEREF", "NULL_CHECK") is True
    assert is_sanitizer_valid_for_sink("POINTER_DEREF", "BOUNDS_CHECK") is False
    assert is_sanitizer_valid_for_sink("POINTER_DEREF", None) is False

    # MEMORY_WRITE and ARRAY_INDEX require BOUNDS_CHECK or RANGE_VALIDATION
    assert is_sanitizer_valid_for_sink("MEMORY_WRITE", "BOUNDS_CHECK") is True
    assert is_sanitizer_valid_for_sink("MEMORY_WRITE", "RANGE_VALIDATION") is True
    assert is_sanitizer_valid_for_sink("MEMORY_WRITE", "NULL_CHECK") is False

    assert is_sanitizer_valid_for_sink("ARRAY_INDEX", "BOUNDS_CHECK") is True
    assert is_sanitizer_valid_for_sink("ARRAY_INDEX", "RANGE_VALIDATION") is True

    # SYSTEM_CALL requires COMMAND_SANITIZATION or ALLOWLIST_CHECK
    assert is_sanitizer_valid_for_sink("SYSTEM_CALL", "COMMAND_SANITIZATION") is True
    assert is_sanitizer_valid_for_sink("SYSTEM_CALL", "ALLOWLIST_CHECK") is True
    assert is_sanitizer_valid_for_sink("SYSTEM_CALL", "NULL_CHECK") is False


def test_evaluate_reachability_vulnerable_and_guarded():
    # Unsanitized memory write -> High Risk (1.0 => Reject)
    vulnerable_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type=None,
    )
    snap_vuln = FlowGraphSnapshot(
        snapshot_id="s1",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[vulnerable_sig],
    )
    assert evaluate_graph_reachability(snap_vuln) == 1.0
    assert is_graph_candidate_rejected(snap_vuln, risk_threshold=0.10) is True

    # Guarded memory write -> Low Risk (0.05 => Pass)
    guarded_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
        guarded_target="buffer_len",
    )
    snap_guarded = FlowGraphSnapshot(
        snapshot_id="s2",
        scenario_id="sc1",
        version=2,
        created_at=1000.0,
        nodes={"src_1": {}, "sink_1": {"target_var": "buffer_len"}},
        signatures=[guarded_sig],
    )
    assert evaluate_graph_reachability(snap_guarded) == 0.05
    assert is_graph_candidate_rejected(snap_guarded, risk_threshold=0.10) is False


def test_time_aware_invalidation():
    # Signature invalidated at t=100.0
    sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type=None,
        invalid_at=100.0,
    )
    snap = FlowGraphSnapshot(
        snapshot_id="s_time",
        scenario_id="sc1",
        version=1,
        created_at=50.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[sig],
    )

    # Evaluation at t=50.0 (before invalidation): Signature active -> Vulnerable (1.0)
    assert evaluate_graph_reachability(snap, as_of=50.0) == 1.0

    # Evaluation at t=100.0 (exact invalidation): All signatures inactive -> Fail Closed (1.0)
    assert evaluate_graph_reachability(snap, as_of=100.0) == 1.0

    # Evaluation at t=150.0 (after invalidation): All signatures inactive -> Fail Closed (1.0)
    assert evaluate_graph_reachability(snap, as_of=150.0) == 1.0


def test_non_finite_and_malformed_timestamps_fail_closed():
    guarded_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
    )
    # NaN created_at -> Fails closed (1.0)
    snap_nan_created = FlowGraphSnapshot(
        snapshot_id="s_nan",
        scenario_id="sc1",
        version=1,
        created_at=float("nan"),
        nodes={"src_1": {}, "sink_1": {"target_var": "buffer_len"}},
        signatures=[guarded_sig],
    )
    assert evaluate_graph_reachability(snap_nan_created) == 1.0

    # Malformed string created_at -> Fails closed (1.0)
    snap_str_created = FlowGraphSnapshot(
        snapshot_id="s_str",
        scenario_id="sc1",
        version=1,
        created_at="invalid_timestamp",  # type: ignore
        nodes={"src_1": {}, "sink_1": {"target_var": "buffer_len"}},
        signatures=[guarded_sig],
    )
    assert evaluate_graph_reachability(snap_str_created) == 1.0

    # Inf as_of -> Fails closed (1.0)
    snap_valid = FlowGraphSnapshot(
        snapshot_id="s_valid",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {}, "sink_1": {"target_var": "buffer_len"}},
        signatures=[guarded_sig],
    )
    assert evaluate_graph_reachability(snap_valid, as_of=float("inf")) == 1.0
    assert evaluate_graph_reachability(snap_valid, as_of="invalid_as_of") == 1.0  # type: ignore

    # NaN invalid_at -> Fails closed (1.0)
    nan_invalid_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
        invalid_at=float("nan"),
    )
    snap_nan_invalid = FlowGraphSnapshot(
        snapshot_id="s_nan_inv",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {}, "sink_1": {"target_var": "buffer_len"}},
        signatures=[nan_invalid_sig],
    )
    assert evaluate_graph_reachability(snap_nan_invalid) == 1.0

    # Malformed string invalid_at -> Fails closed (1.0)
    str_invalid_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
        invalid_at="not_a_float",  # type: ignore
    )
    snap_str_invalid = FlowGraphSnapshot(
        snapshot_id="s_str_inv",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {}, "sink_1": {"target_var": "buffer_len"}},
        signatures=[str_invalid_sig],
    )
    assert evaluate_graph_reachability(snap_str_invalid) == 1.0



def test_endpoint_node_validation_fails_closed():
    sig = FlowSignature(
        source_id="src_missing",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
    )
    # Endpoint node "src_missing" is missing from nodes dictionary -> Fails closed (1.0)
    snap_missing_node = FlowGraphSnapshot(
        snapshot_id="s_missing",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"sink_1": {}},
        signatures=[sig],
    )
    assert evaluate_graph_reachability(snap_missing_node) == 1.0

    # Signatures without a populated node registry are malformed evidence and fail closed.
    snap_empty_nodes = FlowGraphSnapshot(
        snapshot_id="s_empty_nodes",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={},
        signatures=[sig],
    )
    assert evaluate_graph_reachability(snap_empty_nodes) == 1.0


def test_sanitizer_proof_requires_guarded_target_identity():
    missing_target_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="MEMORY_WRITE",
        flow_type="DIRECT_ASSIGN",
        sanitizer_type="BOUNDS_CHECK",
        guarded_target=None,
    )
    snap_missing_target = FlowGraphSnapshot(
        snapshot_id="s_missing_target",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {"kind": "source"}, "sink_1": {"kind": "sink", "target_var": "i"}},
        signatures=[missing_target_sig],
    )
    assert evaluate_graph_reachability(snap_missing_target) == 1.0

    wrong_target_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="ARRAY_INDEX",
        flow_type="SUBSCRIPT_INDEX",
        sanitizer_type="BOUNDS_CHECK",
        guarded_target="j",
    )
    snap_wrong_target = FlowGraphSnapshot(
        snapshot_id="s_wrong_target",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {"kind": "source"}, "sink_1": {"kind": "sink", "target_var": "i"}},
        signatures=[wrong_target_sig],
    )
    assert evaluate_graph_reachability(snap_wrong_target) == 1.0


def test_fail_closed_on_incomplete_evidence_or_errors():
    # Incomplete extraction -> Fails closed (1.0)
    snap_incomplete = FlowGraphSnapshot(
        snapshot_id="s_inc", scenario_id="sc1", version=1, created_at=1000.0, is_complete=False
    )
    assert evaluate_graph_reachability(snap_incomplete) == 1.0

    # Parse error -> Fails closed (1.0)
    snap_err = FlowGraphSnapshot(
        snapshot_id="s_err",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        parse_error="SyntaxError in snippet",
    )
    assert evaluate_graph_reachability(snap_err) == 1.0

    # Unknown sink type -> Fails closed (1.0)
    unknown_sink_sig = FlowSignature(
        source_id="src_1",
        sink_id="sink_1",
        source_type="UNTRUSTED_INPUT",
        sink_type="UNKNOWN_DANGEROUS_SINK",
        flow_type="DIRECT_ASSIGN",
    )
    snap_unknown = FlowGraphSnapshot(
        snapshot_id="s_unk",
        scenario_id="sc1",
        version=1,
        created_at=1000.0,
        nodes={"src_1": {}, "sink_1": {}},
        signatures=[unknown_sink_sig],
    )
    assert evaluate_graph_reachability(snap_unknown) == 1.0
