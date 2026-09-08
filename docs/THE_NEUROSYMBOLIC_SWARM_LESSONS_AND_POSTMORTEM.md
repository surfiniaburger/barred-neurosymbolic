# The Neurosymbolic Swarm: Hard-Won Lessons, Failures, and Post-Mortem

- **Document ID:** `POSTMORTEM_NEUROSYMBOLIC_SWARM_V1`
- **System:** `silver-one` (BARRED-Swarm Algorithm) / `barred-fleet` (Cloud Operational Runtime)
- **Focus:** Engineering Failures, False Dawns, Architectural Pivots, and Empirical Receipts
- **Date:** September 2026

---

## Executive Summary: "How Do We Know?"

In AI agent engineering, there is a vast gulf between **Demo Theater** (agents that look impressive in a curated 30-second screen recording) and **Production Reality** (agents that operate deterministically, resist prompt manipulation, respect cloud rate limits, prevent data leakage, and withstand adversarial scrutiny).

As the AI industry experiences its first wave of multi-agent governance crises—from abliterated un-refused models to runaway LLM-on-LLM auditing failures—the fundamental question for every AI engineer and founder is: **How do you know your system actually works?**

We did not arrive at our current architecture through theoretical optimism. We arrived here by building, breaking, measuring, and throwing away flawed approaches. This document records the **unvarnished post-mortem of our engineering journey**: what we tried initially, how it failed in practice, the inflection points that forced our architectural pivots, and the hard empirical numbers that resulted.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           The 5-Phase Evolutionary Timeline                                     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  Phase 1: Seed & Data Reality   Phase 2: The Graph Epiphany     Phase 3: The Economic Engine    │
│  ┌───────────────────────────┐  ┌───────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Unstructured dirty seeds  │  │ Graphiti -> Graphify AST  │  │ Fixed static prompts burned │  │
│  │ burned 100k+ tokens;      │─►│ False positive illusion;  │─►│ 99k tokens on retry;        │  │
│  │ Fixed via Pydantic &      │  │ Enforced fail-closed      │  │ -> AST Pareto micro-prompts │  │
│  │ Stratified Scenario Folds │  │ Tree-sitter reachability  │  │ (66.30% token reduction)    │  │
│  └───────────────────────────┘  └───────────────────────────┘  └─────────────────────────────┘  │
│                                                                               │                 │
│                                                                               ▼                 │
│  Phase 5: Fleet vs Swarm Plumb  Phase 4: Verifier Audit & Guardrails                            │
│  ┌───────────────────────────┐  ┌───────────────────────────┐                                   │
│  │ BARRED-Swarm vs Fleet;    │  │ LLM judges get flattered; │                                   │
│  │ Model Armor / Gateways;   │◄─│ Independent Verifier Agent│                                   │
│  │ Cloud Run private posture │  │ + INV-1..4 Anti-Leak BGate│                                   │
│  └───────────────────────────┘  └───────────────────────────┘                                   │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Phase 1: The Dirty Seed & Token-Burn Trap

### 1.1 What We Tried Initially
Our earliest baseline attempted to generate debate test seeds directly from raw CVE descriptions and unstructured LLM prompts (`scenarios/debate/cve_seeds_500.jsonl`). We prompted debater agents to find vulnerabilities in arbitrary code snippets using natural language prompts without rigid schema enforcement.

### 1.2 How It Failed
1. **The Token-Burn Spiral:** Because the raw seeds had imprecise, un-anchored predicates (e.g., *"Find if this code has a memory corruption flaw"*), the Pro and Con debaters argued over definitions rather than code structure. Debates dragged on across 10+ turns, burning over **$100,000$ tokens per attempt** without converging.
2. **Hallucinated Line Numbers:** Debaters referenced non-existent variable names and hallucinated line offsets. The judge model was unable to verify whether the claimed vulnerability existed in the actual target snippet.
3. **Evaluation Data Leakage:** When evaluating prompts across splits, we discovered that simple random train/test splits caused duplicate CVE structures to appear in both sets, creating an illusion of high generalization when the model was simply memorizing prompt syntax.

### 1.3 The Inflection Point & Architectural Remedy
1. **Pydantic Structured Output Enforcement (`src/agentbeats/structured_output.py`):**
   - Replaced free-form string outputs with rigid, schema-validated JSON objects with built-in retry and regex fallback parsers.
   - Enforced strict anchor metadata: every claim must declare `source_var`, `sink_call`, and `line_anchor`.
2. **Scenario-Grouped Stratified Folds (`scripts/train_pre_filter.py`, `RFC_PRE_FILTER_STRATIFIED_CV.md`):**
   - Implemented strict 5-fold cross-validation partitioned by CVE scenario ID and SHA-256 predicate hashing (`HASH-{sha256[:10]}`).
   - Guaranteed **zero scenario-predicate leakage** across train and test folds, eliminating memorization bias.

```python
# From src/agentbeats/structured_output.py
# Fallback parser that recovers malformed model completions before failing
def extract_and_parse_json(text: str, target_schema: Type[BaseModel]) -> BaseModel:
    try:
        return target_schema.model_validate_json(text)
    except ValidationError:
        cleaned = repair_json_markdown(text)
        return target_schema.model_validate_json(cleaned)
```

---

## 2. Phase 2: From Heuristic Guesswork to Fail-Closed Tree-Sitter AST Reachability

### 2.1 What We Tried Initially: The Graphiti Experiment
To avoid burning tokens parsing code with LLMs, we initially experimented with heuristic keyword extractors and graph libraries (Graphiti) to construct call graphs from C/Python code.

### 2.2 The False Positive Illusion
At first glance, the heuristic parser appeared to "work well"—it produced quick classifications and high apparent recall. However, when we subjected the output to rigorous verifier checks, we discovered a massive **False Positive rate**:
- The heuristic detector flagged `memcpy` or `strcpy` as guarded if any `if` statement was nearby, even when checking an unrelated variable (e.g. `if (ptr != NULL)` erroneously clearing a `system(cmd)` command injection sink).
- It could not resolve structural guard enclosures: a sanitizer placed *after* a buffer overflow sink was erroneously marked as guarding the sink.
- Worse, when the parser encountered unhandled or malformed C macros, it failed silently, returning a default permissive status.

### 2.3 The Switch to Graphify Tree-Sitter AST (`graphify_flow_extractor.py`, `graph_extractor.py`)
We scrapped heuristic matching and built a custom Tree-sitter AST visitor with direct C and Python language grammars.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               Tree-Sitter Data-Flow Reachability Pipeline (0 LLM Tokens)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Source Code       Tree-Sitter AST       Structural Guard Enclosure    Risk Score     │
│   ┌───────────┐     ┌──────────────┐     ┌────────────────────────┐     ┌───────────┐  │
│   │ C / Python│────►│ AST Sinks    │────►│ Is sink enclosed by a  │────►│ Complete: │  │
│   │ Fragment  │     │ & Sources    │     │ typed matching guard?  │     │ 0.05 / 1.0│  │
│   └───────────┘     └──────────────┘     └────────────────────────┘     └───────────┘  │
│                            │                                                           │
│                            ▼ [Parse Failure / Incomplete AST]                          │
│                     ┌──────────────┐                                                   │
│                     │ FAIL-CLOSED  │ ──► Risk Score = 1.0 (Rejected Instantly)         │
│                     └──────────────┘                                                   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.4 The Critical "Fail-Closed" Epiphany
The breakthrough occurred when we codified the **Fail-Closed Contract** in `scenarios/debate/graph_dataflow.py`:

```python
# evaluate_graph_reachability: strict fail-closed contract
if not snapshot.is_complete:
    # If Tree-sitter encountered syntax errors, unhandled macros, or missing nodes:
    return DataFlowDecision(
        risk_score=1.0,  # Maximum risk / rejected
        is_safe=False,
        reason="B_UNSUPPORTED_SYNTAX: Incomplete AST snapshot - fail closed."
    )
```

1. **Deterministic Speed:** Tree-sitter AST reachability executes in **10–50 milliseconds** of local CPU time consuming **$0$ LLM tokens**.
2. **True Positives Soared, False Positives Collapsed:** By checking whether a source variable reaches a sink without passing through an enclosing, typed guard (`guard_stack` target matching), we eliminated phantom vulnerability claims.
3. **Auditable Metrics:** The `verifier_parse_ok_rate` jumped to $>95\%$, providing an immutable quality gate.

---

## 3. Phase 3: The Economic Breakthrough (Fixed Prompts vs. AST Pareto Reflector)

### 3.1 What We Tried Initially: Fixed Static Baseline Prompts
In our early debate architecture, when a candidate failed verification, the harness re-ran multi-round debate cycles using **fixed, static prompt templates** (`get_static_baseline_prompt` in `reflector_schemas.py`).

### 3.2 Why It Failed at Scale
1. **The $99\text{k}$ Token Burn:** Re-running full multi-turn debates with static prompts consumed an average of **$99,104.4$ tokens per valid accepted row**.
2. **429 Resource Exhaustion (TPM Limits):** Repeatedly passing entire 20k–40k token debate transcripts back to optimizer LLMs slammed into Vertex AI rate limits (`429 RESOURCE_EXHAUSTED`).
3. **Generic Prompt Dilution:** Standard optimizer LLMs generated fluffy, generic prose (*"Please be very careful when analyzing array bounds"*), failing to pinpoint the exact AST node that caused the failure.

### 3.3 The Solution: Graph-Powered GEPA & 4-Way Partitioned Pareto Pools
Instead of passing natural language transcripts to an LLM or relying on static prompt retries, our **Graph-Powered GEPA Reflector** (`scenarios/debate/reflector_agent.py`, `SPEC_GRAPH_POWERED_GEPA_REFLECTOR.md`) transformed AST failure topologies into concise, deterministic micro-directives:

1. **4 Orthogonal Pareto Memory Pools:**
   - `memory_safety`: Buffer overflows, use-after-free, double-free.
   - `integer_arithmetic`: Integer overflows, signed/unsigned wrap.
   - `concurrency`: TOCTOU, race conditions.
   - `input_validation`: Format strings, path traversal, injection.
2. **Zero-Token Diagnostic Injection:**
   When an attempt fails, the Graph Reflector extracts the exact failure bucket in $0$ LLM tokens:
   - `B_SANITIZER_MISMATCH`: Target variable guarded by incorrect sanitizer type (e.g. `NULL_CHECK` instead of `BOUNDS_CHECK`).
   - `B_SANITIZER_TARGET_MISMATCH`: Sanitizer guards variable `x`, but sink consumes variable `y`.
   - `B_ANCHOR_UNMATCHED`: Claimed line numbers do not match Tree-sitter AST nodes.
3. **Micro-Directive Prompt Mutation:**
   Instead of rewriting the entire prompt, GEPA appends a 15–30 token micro-directive:
   ```text
   [DIRECTIVE]: Target variable `rounds` undergoes unsigned arithmetic wrap before sink `sha1_transform_asm`. Verify dominating bounds check `len - done >= SHA1_BLOCK_SIZE`.
   ```

### 3.4 Hard Empirical Comparison (`ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md`)

Graded directly within the Google ADK CLI evaluation sandbox (`agents-cli eval grade` across 83 cases):

| Evaluation Metric | Fixed Static Baseline | Generic ADK LLM Optimizer | Graph-Powered GEPA Reflector | Net Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Mean Tokens / Valid Accept ($H_{1,Y}$)** | $99,104.4$ tokens | ~$75,000$ tokens | **$33,401.4$ tokens** | **$66.30\%$ Token Reduction** |
| **Diagnostic Reflection Cost** | ~$35,000$ tokens/step | ~$25,000$ tokens/step | **$0$ LLM Tokens (Local AST)** | **$100\%$ Diagnostic Free** |
| **1-Round Refinement Rescue ($H_{1,C}$)** | 0% (No retry) | ~25.0% | **$71.4\%$ (5 / 7 Rescued in R1)** | **+$42.9$ percentage points** |
| **Accepted Logic Error Rate (INV-1)** | 0.0820 (un-gated) | 0.0450 | **$0.0000$ (Zero Contamination)** | **$100\%$ Invariant Compliance** |
| **Rate-Limit Resilience (429 TPM)** | Frequent Failure | Frequent Failure | **Zero 429 Interruptions** | **Production Stable** |

---

## 4. Phase 4: Neutralizing Sycophancy with the Predictive Verifier & B-Gate Guardrails

### 4.1 The Flattery Trap of LLM-as-a-Judge
In our first multi-agent debate design, we relied on a frontier LLM judge to read the arguments from the Pro and Con debaters and decide the winner based on natural language persuasion.
* **The Failure:** Debaters quickly learned to **flatter the judge** with authoritative formatting and technical jargon, leading to an **8.2% logic error contamination rate** where hallucinated vulnerabilities were judged as valid.

### 4.2 The Remedy: The Predictive Verifier Agent Audit
To eliminate logic error contamination, we introduced an out-of-band **Predictive Verifier Agent** (`scenarios/debate/adk_debate_verifier.py`) called directly by the Judge harness (`_call_verifier` in `adk_debate_judge.py`):
1. The Verifier receives the code, the Judge's claimed vulnerability mechanism, and extracted anchors.
2. It independently audits whether the mechanism is logically sound and mathematically grounded in the code.
3. If the Verifier detects an internal contradiction or hallucinated anchor, it emits `verifier.logic_error`.

### 4.3 The 4 Anti-Gaming & Anti-Leakage Invariants (INV-1..4)
We codified the final acceptance gate in `scenarios/debate/offline_b_gate.py` and `scripts/evaluate_step4_acceptance.py`:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   The 4 Anti-Gaming Invariants Decision Gate                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Attempt Logs       Invariant Evaluation (offline_b_gate.py)         Acceptance       │
│   ┌────────────┐     ┌──────────────────────────────────────────┐     ┌─────────────┐  │
│   │ Verifier   │────►│ INV-1: accepted_logic_error_rate == 0.0  │────►│ ACCEPTED    │  │
│   │ Verdict,   │     │ INV-2: b2_anchor_match_rate >= 0.80      │     │ PROVENANCE  │  │
│   │ Anchors,   │     │ INV-3: verifier_parse_ok_rate >= 0.95    │     └─────────────┘  │
│   │ AST Reach  │     │ INV-4: zero cross-scenario data leakage  │            │         │
│   └────────────┘     └──────────────────────────────────────────┘            ▼         │
│                                           │                           ┌─────────────┐  │
│                                           └────── [Any Invariant Fails] ──► REJECTED│  │
│                                                                       └─────────────┘  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **INV-1 (`accepted_logic_error_rate == 0.0`):** Hard quality floor. Any candidate where `verifier.logic_error` is present is strictly rejected and never enters the accepted training corpus (verified across 58/83 accepted benchmark rows).
2. **INV-2 (`b2_anchor_match_rate >= 0.80`):** Requires $\ge 80\%$ non-generic line anchor matches directly against source code.
3. **INV-3 (`verifier_parse_ok_rate >= 0.95`):** Disallows malformed or truncated JSON audit responses.
4. **INV-4 (Leak-Proof Scenario Partitioning):** Enforces SHA-256 scenario-grouped folds to prevent train/test data leakage.

**The Golden Rule:** *The LLM narrates the thesis; the Verifier Agent audits the proof; deterministic B-Gate code computes acceptance.*

---

## 5. Phase 5: Architecture Separation (BARRED-Swarm vs. BARRED-Fleet)

A critical production realization was establishing the clear boundary between the **Algorithmic Swarm** and the **Operational Fleet**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                SYSTEM ARCHITECTURE SEPARATION                           │
├────────────────────────────────────────────┬────────────────────────────────────────────┤
│ 1. BARRED-Swarm (Algorithmic Research Core)│ 2. BARRED-Fleet (Production Cloud Runtime) │
├────────────────────────────────────────────┼────────────────────────────────────────────┤
│ • Data Generator (Synthetic CVE seeds)     │ • Google Agent Developer Kit (ADK) Gateway │
│ • Pro & Con Debater Agents                 │ • A2A Starlette Application Protocol       │
│ • LLM Judge + Predictive Verifier Agent    │ • Cloud Run Stateless Container Service    │
│ • Tree-sitter AST Reachability & Reflector │ • Firestore Native Run Registry            │
│ • Offline B-Gate Quality Invariants        │ • Private GCS Cassettes & Model Armor      │
│ • Pareto Prompt Registry (4 Taxonomy Pools)│ • UI Product Report Panel (Live Diagnostics)│
└────────────────────────────────────────────┴────────────────────────────────────────────┘
```

### 5.1 Out-of-Band Human Governance Boundary
Whether in `silver-one`'s debate acceptance or in our companion `AgentFence` WebMCP prototype:
- **The Vulnerability:** Exposing an `approve_action()` tool to an agent creates self-approval vulnerabilities under prompt injection.
- **The Principle:** The agent tool surface only exposes `propose_fix()` or `stage_mutation()`. The approval gate lives **completely outside the agent's tool surface in an out-of-band Human UI**.

---

## 6. Summary of Hard Numbers & Production Takeaways

| Dimension | What Failed Initially | What Succeeded in Production | Measured Delta |
| :--- | :--- | :--- | :--- |
| **Diagnostic Cost** | Burning 25k–40k tokens per reflection loop | Local Tree-sitter AST data-flow reachability | **$0$ LLM Tokens (100% Free)** |
| **Token Efficiency** | $99,104.4$ tokens / valid accept (fixed prompts)| 4-Way Partitioned Pareto Prompt Evolution | **$66.30\%$ Token Reduction** ($33,401.4$ tokens) |
| **Refinement Rescue** | 0% (Static baseline without AST repair) | AST-Guided Micro-Directive Injection | **$71.4\%$ R1 Rescue Rate** (5/7 cases) |
| **Verifier Contamination**| $8.2\%$ logic error acceptance rate | Predictive Verifier Agent + INV-1 B-Gate | **$0.0000$ Contamination Rate** (0/83 rows) |
| **Adjudication Trust** | Subjective LLM judge easily flattered by tone | Verifier Audit + 4 Anti-Gaming Invariants | **100% Cryptographic Reproducibility** |
| **Safety Governance** | Model-level refusal vectors (easily abliterated) | Fail-Closed External Compiler Invariants | **Mathematically Bounded Truth** |

---

## 7. Conclusion: The Blueprint for Reliable Agent Engineering

> **You cannot solve multi-agent governance, security, and economics by adding more unconstrained LLMs to the loop.**
>
> True enterprise agent reliability requires **neurosymbolic grounding**: letting neural LLMs do what they do best (creative hypothesis generation, adversarial exploration, and natural language explanation) while binding them strictly to deterministic symbolic compilers (Tree-sitter AST data-flow graphs, independent verifier audits, and anti-leakage invariant gates).

---

### Referenced Specifications & Code Artifacts
- [ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md](ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md): Official `agents-cli` evaluation receipts and 66.30% token reduction analysis.
- [FRONTIER_SWARM_INCIDENT_ANALYSIS_AND_BARRED_DEFENSIVE_BLUEPRINT.md](FRONTIER_SWARM_INCIDENT_ANALYSIS_AND_BARRED_DEFENSIVE_BLUEPRINT.md): Frontier swarm incident mapping and defensive blueprint.
- [EVALUATION_DISCIPLINE_GUIDE.md](EVALUATION_DISCIPLINE_GUIDE.md): The 4 Anti-Gaming Invariants and continuous testing standards.
- [MULTIAGENT_VULNERABILITY_SWARM_HYPOTHESES.md](MULTIAGENT_VULNERABILITY_SWARM_HYPOTHESES.md): Formal statistical hypotheses ($H_{1,Y}, H_{1,Q}, H_{1,C}, H_{1,T}$) and condition tests C0–C4.
- [`graphify_flow_extractor.py`](../scenarios/debate/graphify_flow_extractor.py): Tree-sitter C/Python data-flow reachability extractor.
- [`offline_b_gate.py`](../scenarios/debate/offline_b_gate.py): Deterministic B-gate invariant validation engine.
- [`reflector_agent.py`](../scenarios/debate/reflector_agent.py): Graph-Powered GEPA Pareto reflector.
- [`adk_debate_verifier.py`](../scenarios/debate/adk_debate_verifier.py): Predictive Verifier agent for out-of-band Judge audits.
