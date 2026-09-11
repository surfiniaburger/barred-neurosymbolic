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

```text
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
Proceed to Gate          Investigate              Escalate /
   Pipeline            Curiosity Bucket          Fail-Closed
(B -> I -> V)
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

```text
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

## 8. Exposure Management vs. Vulnerability Management: Grounding Epistemic Impact in Transitive Attack Surfaces and Runtime Telemetry

### 8.1 The Flaw-Count Fallacy vs. Contextual Risk
Vulnerability management programs frequently encounter operational bottlenecks when remediation backlogs are prioritized primarily by raw CVSS v3.1 base severity scores ($0.0 - 10.0$) without code reachability or environmental context:
1. **Context Blindness:** A critical CVSS 9.8 vulnerability in an isolated test harness or unreachable dead-code branch is treated as an urgent blocker, while a medium CVSS 6.5 flaw in an internet-facing API gateway with access to backend databases is neglected.
2. **Exploitation Evidence:** CISA maintains the Known Exploited Vulnerabilities ([CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)) catalog to establish an evidence-based baseline of vulnerabilities actively exploited in the wild, helping organizations prioritize remediation based on observed attacker activity rather than theoretical base severity alone.
3. **The DARPA AIxCC Accelerated Timeline:** As demonstrated during the semifinal round of DARPA’s Artificial Intelligence Cyber Challenge ([DARPA AIxCC](https://www.darpa.mil/news/2024/ai-cyber-challenge-cybersecurity)), autonomous Cyber Reasoning Systems successfully identified 22 synthetic vulnerabilities across critical real-world codebases (Jenkins, Linux kernel, Nginx, SQLite3, Apache Tika), automatically patched 15 of them, and responsibly disclosed an undiscovered bug in SQLite3. As automated tools accelerate vulnerability discovery and triage cycles, manual, context-blind patch queues become an operational bottleneck.

### 8.2 AST Code Reachability ($R_{\text{reach}}$) and Independent Epistemic Predicates
Finding a vulnerable function in a dependency or codebase does not imply exposure. The neurosymbolic engine evaluates reachability and defensive state deterministically using Tree-Sitter AST dataflow extraction across strictly independent predicates:
- **Untrusted Sources ($S$):** Network reads (`recv`, `recvfrom`), file streams (`fread`, `fgets`), environment variables (`getenv`), or deserializers (`cJSON_Parse`).
- **Security-Sensitive Sinks ($K$):** 
  - `MEMORY_WRITE`: Memory manipulation and buffer writes (`memcpy`, `strcpy`, `snprintf`).
  - `POINTER_DEREF`: Unbounded pointer resolutions and member accesses.
  - `SYSTEM_CALL`: Process execution calls (`system`, `popen`, `exec*`).
  - `FILE_OPERATION`: File descriptor creations and path operations (`open`, `creat`, `unlink`), requiring explicit path validation.

The three independent epistemic predicates are:
1. **Reachability Predicate ($R_{\text{reach}}$):**
   $$R_{\text{reach}}(v) \in \{\text{PROVEN\_REACHABLE}, \text{UNKNOWN\_REACHABLE}, \text{PROVEN\_UNREACHABLE}\}$$
   - A source-to-sink dataflow path is classified as $\text{PROVEN\_REACHABLE}$ whenever tainted input propagates into the sink argument vector (regardless of whether a guard exists).
   - Incomplete ASTs, unresolvable pointer aliases, dynamic FFI calls, or unmapped macro expansions produce $\text{UNKNOWN\_REACHABLE}$, which **fails closed** ($\omega(R_{\text{reach}}) = 1.0$) and triggers Curiosity Bucket escalation.
2. **Guard Verification Predicate ($\text{GuardVerified}$):**
   $$\text{GuardVerified}(v) \in \{\text{VERIFIED\_COMPLETE}, \text{CANDIDATE\_ONLY}, \text{ABSENT}\}$$
   - Syntactic presence of an AST sanitizer (`RANGE_VALIDATION`, `BOUNDS_CHECK`, `NULL_CHECK`, `ALLOWLIST_CHECK`, `PATH_CONFINEMENT`) marks the guard as $\text{CANDIDATE\_ONLY}$.
   - The guard is elevated to $\text{VERIFIED\_COMPLETE}$ if and only if it satisfies one of three completeness criteria: (a) path-complete symbolic verification, (b) verified invariant regression test evidence, or (c) active runtime enforcement proof demonstrating non-bypassable mediation.
3. **Asset Exposure Predicate ($\text{AssetExposed}$):**
   $$\text{AssetExposed}(v) \in \{\text{EXPOSED}, \text{UNKNOWN}, \text{ISOLATED}\}$$
   - Assets in production network paths or internet-facing gateways evaluate to $\text{EXPOSED}$.
   - Assets evaluate to $\text{ISOLATED}$ only when formally proven unreachable across all threat-model attack vectors in scope (including lateral traversal, internal authenticated segments, and IPC channels). If isolation cannot be proven path-complete across the threat model, the asset fails closed as $\text{UNKNOWN}$ ($\gamma = 1.0$).

#### Decoupled Operational Exposure Formulation:
Operational exposure remains bounded within the canonical CVSS domain $[0.0, 10.0]$:
$$\text{Operational Exposure}(v) = \begin{cases} 
0.0 & \text{if } R_{\text{reach}}(v) = \text{PROVEN\_UNREACHABLE} \\
0.0 & \text{else if } \text{GuardVerified}(v) = \text{VERIFIED\_COMPLETE} \\
0.0 & \text{else if } \text{AssetExposed}(v) = \text{ISOLATED} \land \text{ThreatModelIsolated}(v) \\
\text{CVSS}_{\text{base}}(v) \times \omega(R_{\text{reach}}) \times \gamma(\text{AssetExposed}) & \text{otherwise (Fail-Closed)}
\end{cases}$$
where $\omega(\text{PROVEN\_REACHABLE}) = 1.0$, $\omega(\text{UNKNOWN\_REACHABLE}) = 1.0$, and $\gamma(\text{EXPOSED}) = \gamma(\text{UNKNOWN}) = 1.0$.

### 8.3 The Multi-Tiered Transitive Attack Surface & Unresolved Edge Semantics
Modern runtime binaries are composites of deep dependency trees:
$$\text{Application Logic} \longrightarrow \text{Direct Dependency} \longrightarrow \text{Transitive Dependency} \longrightarrow \text{OS Packages} \longrightarrow \text{Container / Cloud Runtime}$$
While Software Bills of Materials (SBOMs; e.g. CycloneDX via Syft) catalog package existence, they fail to prove execution reachability. The Epistemic Change-Impact Graph extends AST reachability across package boundaries into **Transitive Call-Graph Closure**:
- **Bucket A (Structural Uncertainty):** Traces external exported symbols into downstream caller call-graphs.
- **Bucket B (Semantic Contract Uncertainty):** Detects whether upstream package upgrades introduce breaking API contract mutations or silent data truncations.
- **Unresolved Edge Propagation:** If dynamic linking, indirect function pointers, callbacks, reflection, or stripped binaries prevent complete caller resolution, the graph engine strictly forbids under-approximating the caller set. All unresolvable call-edges propagate as $\text{UNKNOWN\_REACHABLE}$ to the I-Gate, preventing false `PROVEN_UNREACHABLE` classifications.

### 8.4 Candidate Compensating Controls as Invariant Guards
When upstream patches are unavailable, delayed, or introduce breaking API changes, the Epistemic Graph synthesizes **Candidate Compensating Invariant Guards**:
- For `MEMORY_WRITE` sinks: Enclosing `RANGE_VALIDATION` and `BOUNDS_CHECK` AST sanitizers.
- For `POINTER_DEREF` sinks: Enclosing `NULL_CHECK` AST guards.
- For `SYSTEM_CALL` sinks: Strict `COMMAND_SANITIZATION` and `ALLOWLIST_CHECK` filters.
- For `FILE_OPERATION` sinks: Strict `PATH_CONFINEMENT` and `CANONICALIZATION_CHECK` path sanitizers.

*Safety Rigor Note:* Syntactic AST presence alone does not guarantee semantic path coverage or runtime boundary enforcement. These constructs remain *candidate* compensating controls that lower triage priority only after path-complete symbolic verification or active runtime validation confirms non-bypassability.

### 8.5 Bridging Compile-Time Epistemic AST to External Runtime Telemetry (`AgentFence` & OpenTelemetry)
To provide defense-in-depth across the software lifecycle, the compile-time AST epistemic model interfaces with the external **AgentFence** runtime telemetry and policy framework:
1. **Compile-Time AST Invariant Extraction (Silver-One Core):** Identifies proven invariants, uncertain boundaries, and un-sanitized sink flows across code diffs, emitting versioned JSON schemas (`diffAnalysis`, `silverOneDataflow`, `schema_version: "1.0.0"`). Payloads lacking valid schema versions or containing incompatible field structures are rejected and treated as fail-closed unknowns.
2. **External Runtime Telemetry & Policy Gateway (AgentFence OTel Gateway):** As an external runtime mediator, AgentFence ingests AST export graphs to inject contextual OpenTelemetry spans and metric events around uncertain AST boundaries (Curiosity Buckets A/B). 
   - **Sink-Specific Enforcement Contracts:** In active proxy mode, AgentFence intercepts runtime request boundaries to enforce typed invariant checks corresponding to each sink class: argument bounds for memory writes, non-null assertions for pointer dereferences, command allowlists for system calls, and canonical path confinement for file operations.
   - **Enforcement Decision Points & Missing Metadata:** If AST contract metadata is missing or unresolvable for a target boundary, the proxy enforces a deterministic deny rather than falling back to an unvalidated audit path (*"Unknown $\neq$ Safe"*).
   - **Telemetry Degradation Resiliency:** If OpenTelemetry export buffers saturate or connection to telemetry collectors fails, active proxy enforcement remains fully enabled; the gateway continues enforcing contract denials while buffering critical security audit events locally.

---

### Referenced System Artifacts
- [`docs/THE_NEUROSYMBOLIC_SWARM_LESSONS_AND_POSTMORTEM.md`](THE_NEUROSYMBOLIC_SWARM_LESSONS_AND_POSTMORTEM.md): 5-Phase post-mortem and empirical receipts.
- [`docs/EVALUATION_DISCIPLINE_GUIDE.md`](EVALUATION_DISCIPLINE_GUIDE.md): The 4 Anti-Gaming Invariants and statistical testing protocol.
- [`scenarios/debate/graphify_flow_extractor.py`](../scenarios/debate/graphify_flow_extractor.py): Tree-sitter AST dataflow reachability extractor.
- [`scenarios/debate/offline_b_gate.py`](../scenarios/debate/offline_b_gate.py): Deterministic B-gate invariant validation engine.
- [`scenarios/debate/reflector_agent.py`](../scenarios/debate/reflector_agent.py): Graph-Powered GEPA Pareto reflector.

