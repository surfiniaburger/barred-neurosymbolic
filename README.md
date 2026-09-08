# BARRED-Neurosymbolic: Fail-Closed AST Reachability & Invariant Verification for Autonomous Agent Swarms

[![CI: Tests](https://github.com/surfiniaburger/barred-neurosymbolic/actions/workflows/ci.yml/badge.svg)](https://github.com/surfiniaburger/barred-neurosymbolic/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![Token Reduction: -66.30%](https://img.shields.io/badge/token%20reduction--66.30%25-success.svg)]()
[![Logic Error Rate: 0.0000](https://img.shields.io/badge/logic%20error%20rate-0.0000-brightgreen.svg)]()

---

## 📌 Executive Summary

**BARRED-Neurosymbolic** is an open-source neurosymbolic framework that solves the three existential crises of multi-agent AI systems:
1. **The Flattery / Conformity Trap:** LLMs easily flatter LLM judges into accepting invalid vulnerability claims.
2. **The "Slop-Vestigation" Collapse:** Using ungrounded LLMs to audit agent transcripts results in hallucinated audits and spoofed execution logs.
3. **The Economic Token Burn:** Re-running debate loops with fixed static prompts burns tens of thousands of tokens per retry, rapidly exhausting cloud TPM quotas (`429 RESOURCE_EXHAUSTED`).

By binding neural agents (adversarial Pro/Con debaters) to **out-of-band Predictive Verifiers** and **deterministic symbolic compilers** (Tree-sitter AST data-flow graphs, 4 hard anti-gaming & anti-leakage invariants, and 4-way partitioned Pareto prompt evolution), BARRED-Neurosymbolic achieves:
- **$0$ LLM Diagnostic Overhead** (Local C/Python AST reachability in 10–50 ms).
- **$66.30\%$ Measured Token Reduction** ($99,104.4 \rightarrow 33,401.4$ tokens per valid accepted result).
- **$71.4\%$ Single-Round Rescue Rate** on failed debate attempts (+42.9 percentage points over baseline).
- **$0.0000$ Logic Error Contamination Rate** (Strict verification invariant compliance across accepted corpus rows).

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        BARRED-Neurosymbolic Core Architecture                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│   Target C / Python Snippet                   4 Anti-Gaming Invariant Gate (INV-1..4)           │
│   ┌────────────────────────┐                  ┌──────────────────────────────────────────────┐  │
│   │ Tree-sitter AST Parser │                  │ • INV-1: accepted_logic_error_rate == 0.0    │  │
│   │ (0 LLM Tokens Spent)   │                  │ • INV-2: b2_anchor_match_rate >= 0.80        │  │
│   └───────────┬────────────┘                  │ • INV-3: verifier_parse_ok_rate >= 0.95      │  │
│               │                               │ • INV-4: zero cross-scenario data leakage    │  │
│               ▼                               └──────────────────────┬───────────────────────┘  │
│   ┌────────────────────────┐                                         │                          │
│   │ Fail-Closed Reachability│                                        │                          │
│   │ Evaluator (0.05 or 1.0) │                                        ▼                          │
│   └───────────┬────────────┘                          ┌──────────────────────────────┐          │
│               │                                       │ Deterministic ACCEPT / REJECT│          │
│               ▼                                       └──────────────────────────────┘          │
│   ┌────────────────────────┐                                         ▲                          │
│   │ 4-Way Partitioned      │                                         │                          │
│   │ Pareto GEPA Reflector  │─────────────────────────────────────────┘                          │
│   │ (Memory/Arith/Conc/Val)│                                                                    │
│   └────────────────────────┘                                                                    │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Empirical Side-by-Side Benchmark Receipts

Evaluated and graded directly within the Google Agents CLI sandbox (`agents-cli eval grade` across 83 multi-round cases):

| Evaluation Metric | Fixed Static Baseline | Generic ADK LLM Optimizer | BARRED-Neurosymbolic (Graph-GEPA) | Net Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Mean Tokens / Valid Accept ($H_{1,Y}$)** | $99,104.4$ tokens | ~$75,000$ tokens | **$33,401.4$ tokens** | **$66.30\%$ Token Reduction** |
| **Diagnostic Reflection Cost** | ~$35,000$ tokens/step | ~$25,000$ tokens/step | **$0$ LLM Tokens (Local AST)** | **$100\%$ Diagnostic Free** |
| **1-Round Refinement Rescue ($H_{1,C}$)** | 28.5% (2 / 7) | ~25.0% | **$71.4\%$ (5 / 7 Rescued in R1)** | **+$42.9$ percentage points** |
| **Accepted Logic Error Rate (INV-1)** | 0.0820 (un-gated) | 0.0450 | **$0.0000$ (Zero Contamination)** | **$100\%$ Invariant Compliance** |
| **Rate-Limit Resilience (429 TPM)** | Frequent Failure | Frequent Failure | **Zero 429 Interruptions** | **Production Stable** |

---

## 🚀 Quickstart

### 1. Installation
```bash
git clone https://github.com/surfiniaburger/barred-neurosymbolic.git
cd barred-neurosymbolic
pip install -e .
```

### 2. Run AST Data-Flow Reachability Verification
```python
from barred_neurosymbolic.ast_flow import extract_graphify_flow_snapshot
from barred_neurosymbolic.reachability import evaluate_graph_reachability

code = """
void handle_packet(char *user_input, int len) {
    char buffer[64];
    memcpy(buffer, user_input, len); // Unguarded memory write sink
}
"""

snapshot = extract_graphify_flow_snapshot(code, scenario_id="cve_demo_1")
decision = evaluate_graph_reachability(snapshot)

print(f"Is Complete AST: {snapshot.is_complete}")
print(f"Risk Score: {decision.risk_score}")  # 1.0 (Vulnerable / Fail-Closed)
print(f"Diagnostic Reason: {decision.reason}")
```

### 3. Run Test Suite
```bash
pytest tests/ -v
```

---

## 📚 Key Research & Engineering Documentation

- 📄 [**Engineering Post-Mortem & Hard-Won Lessons**](docs/THE_NEUROSYMBOLIC_SWARM_LESSONS_AND_POSTMORTEM.md): Complete post-mortem detailing the 5 engineering phases, false dawns, Predictive Verifier audits, and how we solved them.
- 🎬 [**YouTube Masterclass Video Script**](docs/YOUTUBE_NEUROSYMBOLIC_SWARM_SCRIPT.md): Complete 8–10 minute technical video script with visual cues, code anchors, and terminal walkthroughs.
- 📈 [**ADK Optimizer vs. Graph-GEPA Comparison Report**](docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md): Official `agents-cli` evaluation receipts and grading scorecards.
- 🛡️ [**Frontier Swarm Incident Analysis & Defensive Blueprint**](docs/FRONTIER_SWARM_INCIDENT_ANALYSIS_AND_BARRED_DEFENSIVE_BLUEPRINT.md): Analysis of the August 2026 Black Hat disclosures and architectural remedies.
- 📐 [**Evaluation Discipline Guide**](docs/EVALUATION_DISCIPLINE_GUIDE.md): The 4 Anti-Gaming Invariants, data-leakage prevention, and statistical rigor.

---

## ⚖️ License

Apache License 2.0. See [LICENSE](LICENSE) for details.
