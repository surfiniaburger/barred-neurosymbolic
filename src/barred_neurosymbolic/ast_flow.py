"""
Graphify-Inspired Tree-Sitter Data-Flow Extractor.
Integrates robust, error-tolerant Tree-Sitter AST extraction inspired by Graphify
to extract sources, sinks, sanitizers, and FlowGraphSnapshots across partial C/C++ fragments.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple

import tree_sitter
import tree_sitter_c

from .reachability import (
    FlowGraphSnapshot,
    FlowSignature,
    is_sanitizer_valid_for_sink,
)

logger = logging.getLogger(__name__)

C_LANGUAGE = tree_sitter.Language(tree_sitter_c.language())

# Security-sensitive call sinks
MEMORY_SINKS: Set[str] = {
    "memcpy", "strcpy", "strncpy", "strcat", "strncat", "sprintf", "vsprintf",
    "snprintf", "vsnprintf", "memset", "memmove", "bcopy", "malloc", "calloc",
    "realloc", "pb_realloc", "cJSON_malloc", "kmap", "free", "kfree",
}

SYSTEM_SINKS: Set[str] = {
    "system", "popen", "exec", "execl", "execlp", "execle", "execv", "execvp",
    "execvpe", "open", "creat", "crypto_unregister_alg", "crypto_unregister_algs",
    "unlink", "remove", "chmod", "chown",
}

INPUT_SOURCES: Set[str] = {
    "read", "recv", "recvfrom", "recvmsg", "fread", "fgets", "gets", "scanf",
    "fscanf", "sscanf", "getenv", "getopt", "gather_time_entropy", "cJSON_Parse",
    "mp_read_unsigned_bin", "copy_from_user", "get_user",
}

# Ordered sanitizer preferences per sink type
SANITIZER_PREFERENCES: Dict[str, Tuple[str, ...]] = {
    "MEMORY_WRITE": ("RANGE_VALIDATION", "BOUNDS_CHECK"),
    "ARRAY_INDEX": ("RANGE_VALIDATION", "BOUNDS_CHECK"),
    "POINTER_DEREF": ("NULL_CHECK",),
    "SYSTEM_CALL": ("COMMAND_SANITIZATION", "ALLOWLIST_CHECK"),
}


def strip_markdown_fences(code_text: str) -> str:
    """Removes markdown code fences (e.g. ```c ... ```) from snippet text."""
    lines = code_text.splitlines()
    filtered: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        filtered.append(line)
    return "\n".join(filtered)


def wrap_in_function_if_needed(code_text: str) -> List[str]:
    """Generates candidate code variants to maximize Tree-sitter AST recovery."""
    clean = strip_markdown_fences(code_text).strip()
    if not clean:
        return []

    candidates: List[str] = [clean]

    # Terminate standalone statements without corrupting control/continuation lines
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    terminated_lines: List[str] = []
    for line in lines:
        needs_semi = (
            not line.endswith((";", "{", "}", ",", "(", "\\"))
            and not line.startswith("#")
            and not line.startswith(("if", "for", "while", "else", "switch", "case", "do"))
        )
        terminated_lines.append(line + ";" if needs_semi else line)

    semi_code = "\n".join(terminated_lines)

    # Add wrapped candidate for untouched clean code
    candidates.append(f"void __vuln_harness_func() {{\n{clean}\n}}")

    if semi_code != clean:
        candidates.append(semi_code)
        candidates.append(f"void __vuln_harness_func() {{\n{semi_code}\n}}")

    return candidates


class GraphifyFlowVisitor:
    """
    Error-tolerant AST visitor that walks tree-sitter C nodes to extract:
    1. Sources: function parameters, return values from input functions, field dereferences.
    2. Sinks: memory writes, pointer dereferences, system calls, array index operations.
    3. Guards: enclosing if/while bounds checks and NULL checks.
    """

    def __init__(self, code_bytes: bytes):
        self.code_bytes = code_bytes
        self.nodes: Dict[str, dict] = {}
        self.signatures: List[FlowSignature] = []
        self.sources: Dict[str, Tuple[str, str]] = {}  # var_name -> (source_node_id, source_type)
        self.guard_stack: List[Dict[str, Set[str]]] = []  # var_name -> set(sanitizer_types)
        self.node_counter = 0

    def _gen_id(self, prefix: str) -> str:
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"

    def _get_node_text(self, node: tree_sitter.Node) -> str:
        return self.code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()

    def _register_source(
        self, var_name: str, source_kind: str, node: tree_sitter.Node, source_type: str = "UNTRUSTED_INPUT"
    ) -> str:
        if not var_name:
            var_name = "untrusted_input"
        if var_name in self.sources:
            return self.sources[var_name][0]

        src_id = self._gen_id(f"src_{var_name}")
        self.nodes[src_id] = {
            "id": src_id,
            "kind": "source",
            "label": f"Source({var_name})",
            "type": source_type,
            "target_var": var_name,
            "source_kind": source_kind,
            "lineno": node.start_point[0] + 1,
            "col_offset": node.start_point[1],
        }
        self.sources[var_name] = (src_id, source_type)
        return src_id

    def _get_or_create_source(self, var_name: str, node: tree_sitter.Node) -> Tuple[str, str]:
        """Returns existing source or registers a structural source."""
        if var_name in self.sources:
            return self.sources[var_name]
        src_id = self._register_source(var_name, "implicit_source", node, source_type="UNTRUSTED_INPUT")
        return src_id, "UNTRUSTED_INPUT"

    def _active_guards_for(self, target_var: str) -> Set[str]:
        guards: Set[str] = set()
        for frame in self.guard_stack:
            if target_var in frame:
                guards.update(frame[target_var])
        return guards

    def _resolve_sanitizer(self, sink_type: str, target_var: str) -> Tuple[Optional[str], Optional[str]]:
        if not target_var:
            return None, None
        guards = self._active_guards_for(target_var)
        preferred = SANITIZER_PREFERENCES.get(sink_type, ())
        for candidate in preferred:
            if candidate in guards and is_sanitizer_valid_for_sink(sink_type, candidate):
                return candidate, target_var
        return None, None

    def _resolve_sanitizer_for_vars(
        self, sink_type: str, candidate_vars: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolves active sanitizer across primary target and related call arguments."""
        for var in candidate_vars:
            san_type, san_target = self._resolve_sanitizer(sink_type, var)
            if san_type is not None:
                return san_type, san_target
        return None, None

    def _emit_sink(
        self,
        node: tree_sitter.Node,
        sink_type: str,
        flow_type: str,
        target_var: str,
        label: str,
        id_prefix: str,
        related_vars: Optional[List[str]] = None,
    ) -> None:
        """Unified sink node construction and FlowSignature emission helper."""
        if not target_var:
            return
        src_id, src_type = self._get_or_create_source(target_var, node)
        sink_id = self._gen_id(id_prefix)

        vars_to_check = [target_var] + (related_vars or [])
        san_type, san_target = self._resolve_sanitizer_for_vars(sink_type, vars_to_check)

        self.nodes[sink_id] = {
            "id": sink_id,
            "kind": "sink",
            "type": sink_type,
            "target_var": target_var,
            "label": label,
            "lineno": node.start_point[0] + 1,
            "col_offset": node.start_point[1],
        }
        self.signatures.append(
            FlowSignature(
                source_id=src_id,
                sink_id=sink_id,
                source_type=src_type,
                sink_type=sink_type,
                flow_type=flow_type,
                sanitizer_type=san_type,
                guarded_target=san_target,
            )
        )

    def visit(self, node: tree_sitter.Node):
        """Recursively visit AST nodes."""
        node_type = node.type

        if node_type == "parameter_declaration":
            self._handle_parameter(node)
        elif node_type == "if_statement":
            self._handle_if_statement(node)
            return  # Managed recursion within guard frame
        elif node_type == "call_expression":
            self._handle_call(node)
        elif node_type == "assignment_expression":
            self._handle_assignment(node)
        elif node_type == "subscript_expression":
            self._handle_subscript(node)
        elif node_type == "field_expression":
            self._handle_field_expression(node)

        for child in node.children:
            self.visit(child)

    def _handle_parameter(self, node: tree_sitter.Node):
        ident = self._find_first_identifier(node)
        if ident:
            self._register_source(ident, "function_parameter", node, source_type="UNTRUSTED_INPUT")

    def _extract_null_checked_idents(self, cond_node: tree_sitter.Node) -> Set[str]:
        """Extracts identifiers checked against NULL or 0 in a condition node."""
        null_idents: Set[str] = set()

        # Unary negation: if (!ptr)
        if cond_node.type == "unary_expression":
            op_node = cond_node.child_by_field_name("operator")
            arg_node = cond_node.child_by_field_name("argument")
            if op_node and self._get_node_text(op_node) == "!" and arg_node:
                null_idents.update(self._extract_all_identifiers(arg_node))
            return null_idents

        # Binary comparison: if (ptr == NULL) or if (ptr != 0)
        if cond_node.type == "binary_expression":
            left = cond_node.child_by_field_name("left")
            right = cond_node.child_by_field_name("right")
            if left and right:
                left_txt = self._get_node_text(left)
                right_txt = self._get_node_text(right)
                if right_txt in ("NULL", "0", "nullptr", "NULL_PTR"):
                    null_idents.update(self._extract_all_identifiers(left))
                elif left_txt in ("NULL", "0", "nullptr", "NULL_PTR"):
                    null_idents.update(self._extract_all_identifiers(right))
            return null_idents

        # Parenthesized or compound expressions
        for child in cond_node.named_children:
            null_idents.update(self._extract_null_checked_idents(child))

        return null_idents

    def _handle_if_statement(self, node: tree_sitter.Node):
        cond_node = node.child_by_field_name("condition")
        guard_map: Dict[str, Set[str]] = {}
        if cond_node:
            cond_text = self._get_node_text(cond_node)
            idents = self._extract_all_identifiers(cond_node)

            # Range/Bounds check on relational operations
            if any(op in cond_text for op in ("<", ">", "<=", ">=")):
                for id_name in idents:
                    guard_map.setdefault(id_name, set()).add("BOUNDS_CHECK")

            # Precise NULL checks on operands
            null_checked = self._extract_null_checked_idents(cond_node)
            for id_name in null_checked:
                guard_map.setdefault(id_name, set()).add("NULL_CHECK")

        self.guard_stack.append(guard_map)
        try:
            consequence = node.child_by_field_name("consequence")
            if consequence:
                self.visit(consequence)
        finally:
            self.guard_stack.pop()

        alternative = node.child_by_field_name("alternative")
        if alternative:
            self.visit(alternative)

    def _handle_call(self, node: tree_sitter.Node):
        func_name = self._extract_call_func_name(node)
        if not func_name:
            return

        arg_idents = self._extract_call_arg_idents(node)

        # Check if call is an input source
        if func_name in INPUT_SOURCES:
            target = arg_idents[0] if arg_idents else "input_data"
            self._register_source(target, f"call_{func_name}", node, source_type="UNTRUSTED_INPUT")

        # Check if call is a memory sink
        if func_name in MEMORY_SINKS:
            target_var = arg_idents[0] if arg_idents else "dest_buf"
            self._emit_sink(
                node=node,
                sink_type="MEMORY_WRITE",
                flow_type="CALL_ARGUMENT",
                target_var=target_var,
                label=f"Call({func_name})",
                id_prefix=f"sink_mem_{func_name}",
                related_vars=arg_idents[1:],
            )

        # Check if call is a system sink
        if func_name in SYSTEM_SINKS:
            target_var = arg_idents[0] if arg_idents else "cmd_str"
            self._emit_sink(
                node=node,
                sink_type="SYSTEM_CALL",
                flow_type="SYSTEM_INVOCATION",
                target_var=target_var,
                label=f"SysCall({func_name})",
                id_prefix=f"sink_sys_{func_name}",
                related_vars=arg_idents[1:],
            )

    def _handle_assignment(self, node: tree_sitter.Node):
        left_node = node.child_by_field_name("left") or (node.children[0] if node.children else None)
        right_node = node.child_by_field_name("right") or (node.children[2] if len(node.children) > 2 else None)
        if not left_node:
            return

        # If left node is subscript: arr[i] = val
        if left_node.type == "subscript_expression":
            idx_vars = self._extract_subscript_index_vars(left_node)
            target_var = idx_vars[0] if idx_vars else self._extract_target_ident(left_node)
            if target_var:
                self._emit_sink(
                    node=node,
                    sink_type="MEMORY_WRITE",
                    flow_type="ARRAY_INDEX_WRITE",
                    target_var=target_var,
                    label="SubscriptWrite",
                    id_prefix="sink_idx_write",
                    related_vars=idx_vars,
                )

        # If right side is a tainted field expression or pointer arithmetic
        if right_node and right_node.type in ("field_expression", "pointer_expression", "binary_expression"):
            target_var = self._extract_target_ident(left_node)
            if target_var:
                self._register_source(target_var, "tainted_expression", node, source_type="UNTRUSTED_INPUT")

    def _handle_subscript(self, node: tree_sitter.Node):
        idx_vars = self._extract_subscript_index_vars(node)
        if not idx_vars:
            return
        target_var = idx_vars[0]
        self._emit_sink(
            node=node,
            sink_type="ARRAY_INDEX",
            flow_type="ARRAY_INDEX_READ",
            target_var=target_var,
            label=f"Subscript({target_var})",
            id_prefix="sink_subscript_read",
            related_vars=idx_vars,
        )

    def _handle_field_expression(self, node: tree_sitter.Node):
        # Resolve pointer dereference via AST child argument
        arg_child = node.child_by_field_name("argument")
        field_child = node.child_by_field_name("field")
        op_child = node.child_by_field_name("operator")

        is_pointer_deref = bool(
            (op_child and self._get_node_text(op_child) == "->")
            or ("->" in self._get_node_text(node))
        )

        if is_pointer_deref and arg_child:
            base_ident = self._find_first_identifier(arg_child)
            field_name = self._get_node_text(field_child) if field_child else "field"
            if base_ident:
                self._emit_sink(
                    node=node,
                    sink_type="POINTER_DEREF",
                    flow_type="POINTER_ACCESS",
                    target_var=base_ident,
                    label=f"PtrDeref({base_ident}->{field_name})",
                    id_prefix="sink_ptr_deref",
                )

    def _find_first_identifier(self, node: Optional[tree_sitter.Node]) -> Optional[str]:
        if not node:
            return None
        if node.type == "identifier":
            return self._get_node_text(node)
        for child in node.children:
            res = self._find_first_identifier(child)
            if res:
                return res
        return None

    def _extract_all_identifiers(self, node: tree_sitter.Node) -> Set[str]:
        idents: Set[str] = set()
        if node.type == "identifier":
            idents.add(self._get_node_text(node))
        for child in node.children:
            idents.update(self._extract_all_identifiers(child))
        return idents

    def _extract_call_func_name(self, node: tree_sitter.Node) -> Optional[str]:
        func_node = node.child_by_field_name("function")
        if func_node:
            if func_node.type == "identifier":
                return self._get_node_text(func_node)
            if func_node.type == "field_expression":
                field_child = func_node.child_by_field_name("field")
                if field_child:
                    return self._get_node_text(field_child)
        return self._find_first_identifier(node)

    def _extract_call_arg_idents(self, node: tree_sitter.Node) -> List[str]:
        arg_list = node.child_by_field_name("arguments")
        if not arg_list:
            return []
        idents: List[str] = []
        for child in arg_list.named_children:
            ident = self._find_first_identifier(child)
            if ident:
                idents.append(ident)
        return idents

    def _extract_subscript_index_vars(self, node: tree_sitter.Node) -> List[str]:
        idx_node = node.child_by_field_name("index")
        if not idx_node:
            return []
        return sorted(self._extract_all_identifiers(idx_node))

    def _extract_target_ident(self, node: Optional[tree_sitter.Node]) -> Optional[str]:
        if not node:
            return None
        return self._find_first_identifier(node)


def extract_graphify_flow_snapshot(
    code_text: str,
    scenario_id: str,
    snapshot_id: str = "snap_1",
    version: int = 1,
    created_at: float = 0.0,
) -> FlowGraphSnapshot:
    """
    Graphify-inspired robust Tree-sitter AST extraction function.
    Parses fragments, extracts sources, sinks, and FlowSignatures with error tolerance.
    """
    if not code_text or not code_text.strip():
        return FlowGraphSnapshot(
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
            version=version,
            created_at=created_at,
            nodes={},
            signatures=[],
            is_complete=False,
            parse_error="Empty code input",
        )

    candidates = wrap_in_function_if_needed(code_text)
    if not candidates:
        return FlowGraphSnapshot(
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
            version=version,
            created_at=created_at,
            nodes={},
            signatures=[],
            is_complete=False,
            parse_error="No viable candidate code variants generated",
        )

    # Create thread-safe fresh parser per extraction call
    parser = tree_sitter.Parser(C_LANGUAGE)

    best_visitor: Optional[GraphifyFlowVisitor] = None
    max_signatures = -1
    best_is_clean = False

    for candidate in candidates:
        try:
            code_bytes = candidate.encode("utf-8")
            tree = parser.parse(code_bytes)
            visitor = GraphifyFlowVisitor(code_bytes)
            visitor.visit(tree.root_node)

            is_clean = not tree.root_node.has_error
            sig_count = len(visitor.signatures)

            # Prefer clean error-free ASTs; break ties by signature count
            if (is_clean, sig_count) > (best_is_clean, max_signatures):
                max_signatures = sig_count
                best_visitor = visitor
                best_is_clean = is_clean
        except RecursionError:
            logger.warning("RecursionError during Tree-sitter AST traversal on scenario %s", scenario_id)
            continue

    if best_visitor is None or not best_visitor.nodes:
        return FlowGraphSnapshot(
            snapshot_id=snapshot_id,
            scenario_id=scenario_id,
            version=version,
            created_at=created_at,
            nodes={},
            signatures=[],
            is_complete=False,
            parse_error="No valid AST nodes extracted from Tree-sitter parse",
        )

    return FlowGraphSnapshot(
        snapshot_id=snapshot_id,
        scenario_id=scenario_id,
        version=version,
        created_at=created_at,
        nodes=best_visitor.nodes,
        signatures=best_visitor.signatures,
        is_complete=True,
        parse_error=None,
    )
