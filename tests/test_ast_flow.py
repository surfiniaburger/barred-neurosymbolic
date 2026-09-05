"""
Unit tests for the Tree-sitter Flow Extractor in barred-neurosymbolic.
"""

from __future__ import annotations

from barred_neurosymbolic.ast_flow import (
    extract_graphify_flow_snapshot,
    strip_markdown_fences,
    wrap_in_function_if_needed,
)
from barred_neurosymbolic.reachability import evaluate_graph_reachability


def test_empty_and_whitespace_code_input():
    """Verify that empty and whitespace-only strings return incomplete snapshots."""
    snap_empty = extract_graphify_flow_snapshot("", "test_empty")
    assert not snap_empty.is_complete
    assert snap_empty.parse_error == "Empty code input"
    assert len(snap_empty.signatures) == 0

    snap_space = extract_graphify_flow_snapshot("   \n\t  ", "test_space")
    assert not snap_space.is_complete
    assert snap_space.parse_error == "Empty code input"


def test_malformed_syntax_failure():
    """Verify that completely unparseable syntax with no extracted AST nodes returns incomplete snapshot."""
    malformed = "!@#$%^&*() ~`{}[]|\\:"
    snap = extract_graphify_flow_snapshot(malformed, "test_malformed")
    assert not snap.is_complete
    assert snap.parse_error is not None
    assert len(snap.signatures) == 0


def test_markdown_fence_stripping():
    """Verify markdown fences are cleanly stripped."""
    fenced = "```c\nint x = 42;\nmemcpy(buf, src, 10);\n```"
    stripped = strip_markdown_fences(fenced)
    assert "```" not in stripped
    assert "memcpy(buf, src, 10);" in stripped


def test_wrap_in_function_candidates():
    """Verify candidates generate valid compilable function wrappers."""
    snippet = "int a = 1;\nint b = 2"
    candidates = wrap_in_function_if_needed(snippet)
    assert len(candidates) >= 2
    assert any("__vuln_harness_func" in c for c in candidates)


def test_unguarded_memory_write():
    """Verify extraction of an unguarded memcpy memory sink."""
    code = """
    void handle_packet(char *user_input, int len) {
        char buffer[64];
        memcpy(buffer, user_input, len);
    }
    """
    snap = extract_graphify_flow_snapshot(code, "scenario_mem_1")
    assert snap.is_complete
    assert snap.parse_error is None
    assert len(snap.signatures) >= 1

    mem_sigs = [s for s in snap.signatures if s.sink_type == "MEMORY_WRITE"]
    assert len(mem_sigs) >= 1
    assert all(s.sanitizer_type is None for s in mem_sigs)
    assert all(s.guarded_target is None for s in mem_sigs)

    decision = evaluate_graph_reachability(snap)
    assert decision == 1.0


def test_guarded_memory_write_bounds_check():
    """Verify that bounds check in if-statement correctly attaches to guarded sink."""
    code = """
    void safe_copy(char *src, int len) {
        char dest[128];
        if (len <= 128) {
            memcpy(dest, src, len);
        }
    }
    """
    snap = extract_graphify_flow_snapshot(code, "scenario_safe_mem")
    assert snap.is_complete

    mem_sigs = [s for s in snap.signatures if s.sink_type == "MEMORY_WRITE"]
    assert len(mem_sigs) >= 1
    guarded = [s for s in mem_sigs if s.sanitizer_type == "BOUNDS_CHECK"]
    assert len(guarded) >= 1
    assert guarded[0].guarded_target in ("len", "dest")

    decision = evaluate_graph_reachability(snap)


def test_unguarded_pointer_dereference():
    """Verify detection of raw pointer dereference."""
    code = """
    struct vmcb_save_area *save = svm->vmcb->save;
    save->rip = next_rip;
    """
    snap = extract_graphify_flow_snapshot(code, "scenario_ptr_1")
    assert snap.is_complete
    assert snap.parse_error is None
    ptr_sigs = [s for s in snap.signatures if s.sink_type == "POINTER_DEREF"]
    assert len(ptr_sigs) >= 1
    assert ptr_sigs[0].flow_type == "POINTER_ACCESS"


def test_guarded_pointer_dereference_null_check():
    """Verify NULL check correctly attaches to pointer dereference."""
    code = """
    void update_state(struct node *ptr) {
        if (ptr != NULL) {
            ptr->val = 42;
        }
    }
    """
    snap = extract_graphify_flow_snapshot(code, "scenario_ptr_safe")
    assert snap.is_complete
    ptr_sigs = [s for s in snap.signatures if s.sink_type == "POINTER_DEREF"]
    assert len(ptr_sigs) >= 1
    assert ptr_sigs[0].sanitizer_type == "NULL_CHECK"
    assert ptr_sigs[0].guarded_target == "ptr"

    decision = evaluate_graph_reachability(snap)


def test_sanitizer_preference_sink_rejection():
    """Verify that NULL_CHECK does not sanitize SYSTEM_CALL."""
    code_sys_null = """
    void run_cmd(char *cmd) {
        if (cmd != NULL) {
            system(cmd);
        }
    }
    """
    snap_sys = extract_graphify_flow_snapshot(code_sys_null, "scenario_sys_null")
    assert snap_sys.is_complete
    sys_sigs = [s for s in snap_sys.signatures if s.sink_type == "SYSTEM_CALL"]
    assert len(sys_sigs) >= 1
    assert all(s.sanitizer_type is None for s in sys_sigs)

    decision = evaluate_graph_reachability(snap_sys)
    assert decision == 1.0
