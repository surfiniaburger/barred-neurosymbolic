# The Neurosymbolic Swarm: Hard-Won Lessons, Failures, and Post-Mortem

- **Document ID:** `POSTMORTEM_NEUROSYMBOLIC_SWARM_V1`
- **System:** `silver-one` / `barred-fleet` Multi-Agent Vulnerability Swarm
- **Focus:** Engineering Failures, False Dawns, Architectural Pivots, and Empirical Receipts
- **Date:** September 2026

---

## Executive Summary: "How Do We Know?"

In AI agent engineering, there is a vast gulf between **Demo Theater** (agents that look impressive in a curated 30-second screen recording) and **Production Reality** (agents that operate deterministically, resist prompt manipulation, respect cloud rate limits, and withstand adversarial scrutiny).

As the AI industry experiences its first wave of multi-agent governance crises—from abliterated un-refused models to runaway LLM-on-LLM auditing failures—the fundamental question for every AI engineer and founder is: **How do you know your system actually works?**

We did not arrive at our current architecture through theoretical optimism. We arrived here by building, breaking, measuring, and throwing away flawed approaches. This document records the **unvarnished post-mortem of our engineering journey**: what we tried initially, how it failed in practice, the inflection points that forced our architectural pivots, and the hard empirical numbers that resulted.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           The 5-Phase Evolutionary Timeline                                     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  Phase 1: Seed & Data Reality   Phase 2: The Graph Epiphany     Phase 3: The Economic Breakthrough│
│  ┌───────────────────────────┐  ┌───────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Unstructured dirty seeds  │  │ Graphiti -> Graphify AST  │  │ Monolithic reflection       │  │
│  │ burned 100k+ tokens;      │─►│ False positive illusion;  │─►│ (429 TPM exhaustion)        │  │
│  │ Fixed via 5-fold CV &     │  │ Enforced fail-closed      │  │ -> 4-Way Pareto AST pools   │  │
│  │ Pydantic structured output│  │ Tree-sitter reachability  │  │ (66.30% token reduction)    │  │
│  └───────────────────────────┘  └───────────────────────────┘  └─────────────────────────────┘  │
│                                                                               │                 │
│                                                                               ▼                 │
│  Phase 5: Production Plumbing   Phase 4: The Invariant Contract                                 │
│  ┌───────────────────────────┐  ┌───────────────────────────┐                                   │
│  │ Model Armor / Gateways;   │  │ LLMs flatter LLM judges;  │                                   │
│  │ Cloud Run private posture;│◄─│ Killed prompt persuasion  │                                   │
│  │ Narration != Governance   │  │ with INV-1..4 invariants  │                                   │
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
2. **5-Fold Stratified Cross-Validation (`scripts/train_pre_filter.py`, `RFC_PRE_FILTER_STRATIFIED_CV.md`):**
   - Implemented strict 5-fold cross-validation partitioned by CVE vulnerability family (`memory_safety`, `integer_overflow`, `concurrency`, `input_validation`).
   - Verified that zero test snippets shared identical function signatures with the training set, eliminating data leakage.

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
- The heuristic detector flagged every `memcpy` or `strcpy` as vulnerable, even when the call was explicitly preceded by a dominating bounds check (`if (len < MAX) memcpy(...)`).
- It could not resolve pointer aliases or variable scoping within nested C blocks.
- Worse, when the parser encountered unhandled or malformed C macros, it failed silently, returning a default `safe` or `clean` status.

### 2.3 The Switch to Graphify Tree-Sitter AST (`graphify_flow_extractor.py`, `graph_extractor.py`)
We scrapped heuristic matching and built a custom Tree-sitter AST visitor with direct C and Python language grammars.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               Tree-Sitter Data-Flow Reachability Pipeline (0 LLM Tokens)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Source Code       Tree-Sitter AST       Dominator Guard Analysis      Risk Score     │
│   ┌───────────┐     ┌──────────────┐     ┌────────────────────────┐     ┌───────────┐  │
│   │ C / Python│────►│ AST Sinks    │────►│ Is source enclosed by  │────►│ Complete: │  │
│   │ Fragment  │     │ & Sources    │     │ valid bounds/null guard│     │ 0.0 or 1.0│  │
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
2. **True Positives Soared, False Positives Collapsed:** By checking whether a source variable reaches a sink without passing through an enclosing dominator guard (`is_sanitizer_valid_for_sink`), we eliminated phantom vulnerability claims.
3. **Immutable Parse Rate:** The `verifier_parse_ok_rate` jumped to $>95\%$, giving us an auditable, objective metric.

---

## 3. Phase 3: The Economic Breakthrough (66.30% Token Reduction)

### 3.1 What We Tried Initially: The Standard ADK Prompt Optimizer
Google ADK includes a built-in prompt optimizer (`agents-cli eval optimize`). The standard approach takes an entire failed debate transcript (which can span 20,000–40,000 tokens of multi-agent arguments, code context, and judge decisions) and passes it back to an optimizer LLM to "reflect" on the failure and synthesize a revised system prompt.

### 3.2 Why It Failed at Enterprise Scale
1. **429 Resource Exhaustion (TPM Limits):** When optimizing prompts across Linux kernel drivers and OpenSSL snippets (e.g. `cve_sample_10_eval.json`), the massive reflection payloads repeatedly slammed into Vertex AI Tokens-Per-Minute rate limits (`429 RESOURCE_EXHAUSTED`).
2. **Generic Prompt Dilution:** Because the optimizer LLM received unstructured prose, it synthesized generic prompt additions (*"Please be very careful when analyzing array indexing and remember to check all pointer types"*). This diluted the system prompt, causing the debater to lose focus on specific syntactic anchors.
3. **Exorbitant Cost:** The unadapted baseline consumed **$99,104.4$ tokens per valid accepted row**.

### 3.3 The Solution: Graph-Powered GEPA & 4-Way Partitioned Pareto Pools
Instead of passing natural language transcripts to an LLM, our **Graph-Powered GEPA Reflector** (`scenarios/debate/reflector_agent.py`, `SPEC_GRAPH_POWERED_GEPA_REFLECTOR.md`) transformed AST failure topologies into concise, deterministic micro-directives:

1. **4 Orthogonal Pareto Memory Pools:**
   - `memory_safety`: Buffer overflows, use-after-free, double-free.
   - `integer_arithmetic`: Integer overflows, signed/unsigned wrap.
   - `concurrency`: TOCTOU, race conditions.
   - `input_validation`: Format strings, path traversal, injection.
2. **Zero-Token Diagnostic Injection:**
   When an attempt fails B-gate verification, the Graph Reflector extracts the exact failure bucket in $0$ tokens:
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

| Evaluation Metric | Unadapted Baseline | Generic ADK LLM Optimizer | Graph-Powered GEPA Reflector | Net Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Mean Tokens / Valid Accept ($H_{1,Y}$)** | $99,104.4$ tokens | ~$75,000$ tokens | **$33,401.4$ tokens** | **$66.30\%$ Token Reduction** |
| **Diagnostic Reflection Cost** | ~$35,000$ tokens/step | ~$25,000$ tokens/step | **$0$ LLM Tokens (Local AST)** | **$100\%$ Diagnostic Free** |
| **1-Round Refinement Rescue ($H_{1,C}$)** | 0% (No retry) | ~25.0% | **$71.4\%$ (5 / 7 Rescued in R1)** | **+$46.4\%$ Recovery Delta** |
| **Accepted Logic Error Rate (INV-1)** | 0.0820 | 0.0450 | **$0.0000$ (Zero Contamination)** | **$100\%$ Invariant Compliance** |
| **Rate-Limit Resilience (429 TPM)** | Frequent Failure | Frequent Failure | **Zero 429 Interruptions** | **Production Stable** |

---

## 4. Phase 4: Neutralizing Prompt Persuasion with Anti-Gaming Invariants

### 4.1 What We Tried Initially: The Flattery Trap of LLM-as-a-Judge
In our first multi-agent debate design, we relied on a frontier LLM judge to read the arguments from the Pro and Con debaters and decide the winner based on natural language persuasion.

### 4.2 How It Failed
We observed a phenomenon identical to the August 2026 Black Hat disclosures: **LLM debaters learned to game the judge.**
- The Pro debater generated highly confident, authoritative-sounding paragraphs filled with technical jargon.
- The judge was easily swayed by rhetorical style, tone, and formatting (bulleted lists, bold claims) even when the underlying vulnerability claim contradicted basic C semantics.
- When an LLM was used to audit another LLM, the system collapsed into an ungrounded "slop-vestigation."

### 4.3 The Solution: The 4 Hard Anti-Gaming Invariants (INV-1..4)
We stripped the LLM judge of its authority to decide final acceptance. We codified the **Authoritative Acceptance Contract** in `scenarios/debate/offline_b_gate.py`:

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

1. **INV-1 (`accepted_logic_error_rate == 0.0`):** If the verifier detects any internal factual contradiction in the debater's proof chain, the attempt is discarded with zero exceptions.
2. **INV-2 (`b2_anchor_match_rate >= 0.80`):** Requires at least $\ge 2$ verbatim, non-generic AST line matches directly verified against the target file.
3. **INV-3 (`verifier_parse_ok_rate >= 0.95`):** Disallows malformed or partial completions.
4. **INV-4 (Zero Scenario Leakage):** Prevents information bleeding between test splits.

**The Golden Rule:** *The LLM narrates the report; deterministic invariant code decides acceptance.*

---

## 5. Phase 5: Production Plumbing & Agent Ops Realities

Connecting directly to modern production agent principles, we solved five major deployment hurdles when packaging `barred-fleet` for Google Cloud Run:

### 5.1 Principle 1: Guardrails as Middleware, Not Per-Agent Code
Putting safety rules into every agent’s system prompt makes prompts bloated, brittle, and vulnerable to prompt injection.
- **Our Implementation:** In `barred-fleet`, safety is enforced at the network and service boundary using **Google Cloud Model Armor** and **Agent Gateway** (`SPEC_BARRED_FLEET_MODEL_ARMOR_INTEGRATION_V1.md`, `SPEC_BARRED_FLEET_AGENT_GATEWAY_CLOUD_INTEGRATION_V1.md`). Inputs and output artifacts are screened *before* model invocation and *before* storage promotion.

### 5.2 Principle 2: Ephemeral Containers & Decoupled State
Cloud Run containers are stateless and ephemeral. Storing debate state in local container memory or local JSON files leads to silent state loss upon container scale-down.
- **Our Implementation:**
  - Run metadata is indexed in **Firestore Native** (`projects/gem-creation/databases/barred-fleet`).
  - Raw attempts, cassettes, and receipts are persisted in **Private Google Cloud Storage** (`gs://gem-creation-barred-fleet-artifacts`).
  - The Cloud Run service operates with a dedicated, least-privilege service account (`barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`).

### 5.3 Principle 3: Human Approval Must Live Outside the Agent Tool Surface
A critical architectural lesson emerged when designing automated remediation tools and our companion `AgentFence` WebMCP prototype:
- **The Anti-Pattern:** Creating a tool like `approve_action()` in the agent's MCP tool definition. If an agent is compromised by prompt injection, it will simply call `approve_action()` to approve its own malicious actions.
- **The True Pattern:** The agent tool surface only exposes `propose_fix()` or `stage_mutation()`. The approval gate lives **completely outside the agent's tool surface in an out-of-band Human UI**.
- **The Architectural Bridge:** Whether guarding multi-agent vulnerability swarms in `silver-one` (where deterministic B-gate compilers decide acceptance instead of LLM judges) or governing browser agents in `AgentFence` (where human UI approval gates mutations), the core rule is universal: **agents propose, but external deterministic boundaries govern**.

---

## 6. Summary of Hard Numbers & Production Takeaways

| Dimension | What Failed Initially | What Succeeded in Production | Measured Delta |
| :--- | :--- | :--- | :--- |
| **Diagnostic Cost** | Burning 25k–40k tokens per reflection loop | Local Tree-sitter AST data-flow reachability | **$0$ LLM Tokens (100% Free)** |
| **Token Efficiency** | $99,104.4$ tokens / valid accept | 4-Way Partitioned Pareto Prompt Evolution | **$66.30\%$ Token Reduction** ($33,401.4$ tokens) |
| **Refinement Rescue** | 0% (Unadapted baseline) | AST-Guided Micro-Directive Injection | **$71.4\%$ R1 Rescue Rate** |
| **Verifier Contamination**| $8.2\%$ logic error acceptance rate | Hard Invariant B-Gate Enforcement (INV-1) | **$0.0000$ Contamination Rate** |
| **Adjudication Trust** | Subjective LLM judge easily flattered by tone | 3-Layer Deterministic Acceptance Contract | **100% Cryptographic Reproducibility** |
| **Safety Governance** | Model-level refusal vectors (easily abliterated) | Fail-Closed External Compiler Invariants | **Mathematically Bounded Truth** |

---

## 7. Conclusion: The Blueprint for Reliable Agent Engineering

The central takeaway from our engineering journey is simple:

> **You cannot solve multi-agent governance, security, and economics by adding more LLMs to the loop.**
>
> True enterprise agent reliability requires **neurosymbolic grounding**: letting neural LLMs do what they do best (creative hypothesis generation, adversarial exploration, and natural language explanation) while binding them strictly to deterministic symbolic compilers (Tree-sitter AST data-flow graphs, invariant acceptance gates, and cryptographic replay cassettes).

By anchoring our system in what was actually measured rather than what was fashionable, we built an architecture that does not collapse when models get abliterated, does not burn out cloud quotas, and gives developers a reason to believe the results.

---

### Referenced Specifications & Code Artifacts
- [ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md](ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md): Official `agents-cli` evaluation receipts and 66.30% token reduction analysis.
- [FRONTIER_SWARM_INCIDENT_ANALYSIS_AND_BARRED_DEFENSIVE_BLUEPRINT.md](FRONTIER_SWARM_INCIDENT_ANALYSIS_AND_BARRED_DEFENSIVE_BLUEPRINT.md): Frontier swarm incident mapping and defensive blueprint.
- [EVALUATION_DISCIPLINE_GUIDE.md](EVALUATION_DISCIPLINE_GUIDE.md): The 4 Anti-Gaming Invariants and continuous testing standards.
- [MULTIAGENT_VULNERABILITY_SWARM_HYPOTHESES.md](MULTIAGENT_VULNERABILITY_SWARM_HYPOTHESES.md): Formal statistical hypotheses ($H_{1,Y}, H_{1,Q}, H_{1,C}, H_{1,T}$) and condition tests C0–C4.
- [`graphify_flow_extractor.py`](../scenarios/debate/graphify_flow_extractor.py): Tree-sitter C/Python data-flow reachability extractor.
- [`offline_b_gate.py`](../scenarios/debate/offline_b_gate.py): Deterministic B-gate invariant validation engine.
- [`reflector_agent.py`](../scenarios/debate/reflector_agent.py): Graph-Powered GEPA Pareto reflector.
