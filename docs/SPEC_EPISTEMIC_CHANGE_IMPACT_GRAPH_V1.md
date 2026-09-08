# From Diagnostic Graphs to Change-Impact & Epistemic Uncertainty Graphs

- **Document ID:** `SPEC_EPISTEMIC_CHANGE_IMPACT_GRAPH_V1`
- **System Lineage:** `silver-one` (BARRED-Swarm Core) / `barred-fleet` (Enterprise Operational Harness)
- **Focus:** Blast-Radius Bounding, Epistemic Uncertainty Modeling, Curiosity Buckets, and the 3-Gate Architecture (B-Gate, I-Gate, V-Gate)
- **Target Domain:** Legacy Code Modernization, Safety-Critical Systems, and Autonomous Vulnerability Remediation
- **Date:** September 2026

---

## Executive Summary

Current neurosymbolic code-reasoning architectures (including the foundational `silver-one` prototype) are highly optimized for **vulnerability diagnosis**:
> *"Given that this code exhibits a memory-safety flaw, what reasoning pattern and AST invariants should the agent swarm use to evaluate and repair it?"*

While this diagnostic framework achieved state-of-the-art token efficiency (**$66.30\%$ net token reduction**) and verifier integrity (**$0.0000$ logic error contamination**), real-world enterprise modernization (e.g. legacy C/C++, COBOL, kernel drivers, and financial transaction engines) presents a fundamentally harder question:
> *"If an autonomous agent modifies this legacy function, what else might that change affect (blast radius), what did our analyzers fail to observe, and what evidence guarantees that existing system behavior survives?"*

This specification defines the architectural evolution from a purely **Diagnostic AST Graph** to an **Epistemic Change-Impact & Uncertainty Graph**.

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE 2-STAGE EVOLUTION OF NEUROSYMBOLIC REASONING                          │
├────────────────────────────────────────────────────┬───────────────────────────────────────────────────┤
│ CURRENT SILVER-ONE: The Diagnostic Graph           │ NEXT-GEN SILVER-ONE: The Evidence & Impact Graph  │
├────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ • Primary Question: "Why did this code fail?"      │ • Primary Question: "What is the blast radius?"   │
│ • Graph Output: AST Sinks, Sources, Missing Guards │ • Graph Output: Knowns, Unknowns, Broken Invariants│
│ • Routing: 4-Way Taxonomy Pareto Pools             │ • Routing: Bounded Curiosity Directives           │
│ • Decision Gate: B-Gate (Security Correctness)     │ • Decision Gates: B-Gate + I-Gate + V-Gate        │
│ • Philosophy: Pinpoint the vulnerability           │ • Philosophy: "Unknown ≠ Safe" (Behavior Preserved)│
└────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

---

## 1. The Dual-Problem Formulation

| Dimension | 1. Vulnerability Diagnosis (Silver-One v1) | 2. Change-Impact & Modernization (Silver-One v2) |
| :--- | :--- | :--- |
| **Core Objective** | Identify and isolate the vulnerability mechanism. | Safely transform legacy code without breaking callers. |
| **Analyzer Scope** | Local function AST & dataflow reachability. | Call-graph closure, exported symbols, side effects. |
| **Failure Mode** | Hallucinated vulnerabilities / false positives. | Downstream protocol breakage, silent truncation bugs. |
| **Output Type** | Diagnostic classification (`B_SANITIZER_MISMATCH`). | Blast-radius envelope + Epistemic Uncertainty Certificate. |
| **Success Metric** | High yield, 0 logic errors, low token cost. | Zero behavioral regressions, bounded blast radius. |

---

## 2. The Blast-Radius Trap in Legacy Code

In isolated code evaluation benchmarks, an agent replacing an unsafe function call appears completely successful:

```c
// Legacy Code
void process_packet(char *input) {
    char buf[32];
    strcpy(buf, input); // Vulnerable to stack buffer overflow
    send_to_parser(buf);
}

// Agent Proposed Patch
void process_packet(char *input) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%s", input); // "Fixed"
    send_to_parser(buf);
}
```

### Why This Patch Can Cause Systemic Outages:
1. **Downstream Invariant Violation:** If `input` exceeds 31 bytes, `snprintf` silently truncates the payload. If `send_to_parser(buf)` expects an exact 32-byte binary protocol frame, silent truncation corrupts the downstream parser state machine.
2. **Hidden Caller Assumptions:** If external callers depend on undocumented side-effects (e.g., modifying adjacent struct members, specific return codes, or global errno states), the "clean" patch breaks the caller contract.
3. **Macro & Multi-Target Drift:** If `buf` size is conditional on preprocessor flags (`#ifdef _POSIX_C_SOURCE`), a hardcoded patch based on an x86 parse may silently fail on ARM or embedded toolchains.

**Core Realization:** A patch can be **100% security-correct** while simultaneously being **100% production-catastrophic**.

---

## 3. The Epistemic Graph: Knowing What the Analyzer Doesn't Know

A common architectural trap is assuming:
$$\text{More Graph Detail} \implies \text{More Confidence} \implies \text{Safer Transformation}$$

Because code parsers are bounded by incomplete headers, dynamic macros, and unresolvable pointer aliases (e.g., our measured AST coverage of $69.76\%$), building an overly dense graph creates a **false sense of completeness**.

The Epistemic Graph strictly delineates three distinct knowledge tiers:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           EPISTEMIC GRAPH PAYLOAD SCHEMA                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  1. PROVEN FACTS (High Confidence — Deterministic AST Extraction)                       │
│     • AST Sink: memcpy at line 42 with length variable 'len'                            │
│     • Buffer Allocation: 64 bytes on stack in translation unit packet.c                 │
│     • Internal Callers: 2 local static callers discovered in packet.c                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  2. UNCERTAIN BOUNDARIES (Medium Confidence — Triggers Targeted Curiosity Directives)    │
│     • External Callers: Symbol process_packet() is exported in packet.h (callers ??)    │
│     • Downstream Contract: send_to_parser() return value is unchecked in current TU     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  3. FAIL-CLOSED UNKNOWNS (Low Confidence — Requires Human Escalation or Deep Scans)    │
│     • Function Pointer Alias: Address of process_packet assigned to struct dispatch_tbl │
│     • Macro Expansion: Incomplete AST snapshot (is_complete = False)                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Bounded Curiosity Buckets

Instead of instructing an LLM to *"think hard about safety"* (which burns thousands of tokens on generic prose), the Epistemic Graph outputs **structured curiosity directives**:

```
                       CHANGE PROPOSAL
                              │
                              ▼
                      EPISTEMIC GRAPH
                              │
      ┌───────────────────────┼───────────────────────┐
      ▼                       ▼                       ▼
   CERTAIN                UNCERTAIN                UNKNOWN
      │                       │                       │
      ▼                       ▼                       ▼
   Proceed                Investigate              Escalate /
  to B-Gate            Curiosity Bucket            Fail-Closed
```

### The 5 Uncertainty Buckets:

* **Bucket A — Structural Uncertainty:**
  > *"Cannot determine all callers. Symbol is exported. Investigate callers in include graph before mutating buffer signature."*
* **Bucket B — Semantic Contract Uncertainty:**
  > *"Function calls `send_to_parser()`. Downstream contract is unresolved. Investigate header `parser.h` to confirm truncation handling."*
* **Bucket C — Boundary & Aliasing Uncertainty:**
  > *"Function address is referenced in `dispatch_table`. Confirm function pointer signature compatibility."*
* **Bucket D — Environmental / Platform Uncertainty:**
  > *"Buffer size depends on macro `MAX_PACKET_LEN`. Verify behavior under alternate compilation targets."*
* **Bucket E — Validation Uncertainty:**
  > *"No regression unit tests discovered for `process_packet()`. Synthesize differential test fixtures before approving patch."*

---

## 5. Question-Specific Micro-Graphs vs. The Monolithic Trap

To preserve our **10–50ms local CPU execution latency** and **$0$ LLM token diagnostic advantage**, we reject monolithic universal code graphs in favor of **on-demand question-specific micro-graphs**:

```text
                           Engineering Question
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
"Is this vulnerable?"     "What calls this?"          "Did tests survive?"
        │                           │                           │
        ▼                           ▼                           ▼
 ┌───────────────┐          ┌───────────────┐          ┌────────────────┐
 │ Diagnostic    │          │ Targeted Call │          │ Differential   │
 │ AST Dataflow  │          │ Graph Closure │          │ Test Harness   │
 └───────────────┘          └───────────────┘          └────────────────┘
```

Each micro-graph remains small, deterministic, isolated, and strictly fail-closed.

---

## 6. The 3-Tier Gate Architecture: B-Gate, I-Gate, and V-Gate

We expand the acceptance contract from a single B-Gate into three orthogonal gates:

```
                              Proposed Transformation
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
   ┌─────────┐                      ┌─────────┐                      ┌─────────┐
   │ B-GATE  │                      │ I-GATE  │                      │ V-GATE  │
   │ Security│                      │ Impact  │                      │ Valid-  │
   │ Correct │                      │ Bounds  │                      │ ation   │
   └────┬────┘                      └────┬────┘                      └────┬────┘
        │                                │                                │
        │ Is the flaw fixed?             │ Is blast radius proven?        │ Are behavioral
        │ Sanitizer valid for sink?      │ Unknown callers bounded?       │ contracts preserved?
        │ Zero logic error contamination?│ Missing evidence resolved?     │ Differential tests pass?
        │                                │                                │
        └────────────────────────┬───────┴────────────────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ DETERMINISTIC RELEASE │
                     └───────────────────────┘
```

1. **B-Gate (Bug / Security Gate):**
   - Validates that the vulnerability dataflow from source to sink is broken by a typed, enclosing sanitizer.
   - Enforces `accepted_logic_error_rate == 0.0000`.
2. **I-Gate (Impact / Blast-Radius Gate):**
   - Evaluates caller reachability, exported symbols, and shared memory mutations.
   - Rejects any patch where unresolved external dependencies remain in an un-audited state (*"Unknown $\neq$ Safe"*).
3. **V-Gate (Validation / Behavioral Gate):**
   - Executes differential fuzzing or invariant regression tests comparing pre-patch and post-patch execution traces.

---

## 7. The Grand Research & Modernization Roadmap

```text
Detection  ──►  Diagnosis  ──►  Patch Synthesis  ──►  Impact Graph  ──►  Evidence Gathering  ──►  Behavioral Proof
  [Phase 1]       [Phase 2]        [Phase 3]            [Phase 4]             [Phase 5]               [Phase 6]
  └───────────────┬────────────────────────┘            └─────────────────────┬───────────────────────────────┘
                  │                                                           │
        Where Silver-One is Proven                                   Where the Frontier Lives
```

### Grand Hypothesis ($H_{\text{Enterprise}}$):
> *"A neurosymbolic code agent that bounds its reasoning using an Epistemic Change-Impact Graph can modernize legacy systems with lower token cost, higher behavioral preservation, and zero hallucinated safety guarantees compared to unconstrained frontier LLMs."*

---

### Referenced System Artifacts
- [`docs/THE_NEUROSYMBOLIC_SWARM_LESSONS_AND_POSTMORTEM.md`](THE_NEUROSYMBOLIC_SWARM_LESSONS_AND_POSTMORTEM.md): 5-Phase post-mortem and empirical receipts.
- [`docs/EVALUATION_DISCIPLINE_GUIDE.md`](EVALUATION_DISCIPLINE_GUIDE.md): The 4 Anti-Gaming Invariants and statistical testing protocol.
- [`scenarios/debate/graphify_flow_extractor.py`](../scenarios/debate/graphify_flow_extractor.py): Tree-sitter AST dataflow reachability extractor.
- [`scenarios/debate/offline_b_gate.py`](../scenarios/debate/offline_b_gate.py): Deterministic B-gate invariant validation engine.
- [`scenarios/debate/reflector_agent.py`](../scenarios/debate/reflector_agent.py): Graph-Powered GEPA Pareto reflector.
