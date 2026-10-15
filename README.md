# BARRED-Neurosymbolic: Fail-Closed AST Reachability and Invariant-Gated Evaluation for AI-Assisted Code Security

[![CI Tests](https://github.com/surfiniaburger/barred-neurosymbolic/actions/workflows/ci.yml/badge.svg)](https://github.com/surfiniaburger/barred-neurosymbolic/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Measured Token Reduction: 66.30%](https://img.shields.io/badge/measured%20token%20reduction-66.30%25-success.svg)](docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md)
[![Evaluated Accepted Logic Errors: 0](https://img.shields.io/badge/evaluated%20accepted%20logic%20errors-0-brightgreen.svg)](docs/EVALUATION_DISCIPLINE_GUIDE.md)

BARRED-Neurosymbolic is an open-source research framework for evaluating how deterministic code analysis, explicit invariants, adversarial debate, and targeted prompt evolution can improve AI-assisted code-security workflows.

**Core idea:** Neural agents propose and challenge vulnerability claims. Deterministic analysis checks code-derived evidence. Explicit invariants constrain acceptance. Reflection is used to recover from failed attempts.

The goal is not to treat agreement between agents as proof of correctness. It is to investigate how much model reasoning and repeated inference can be avoided when relevant evidence is exposed and checked mechanically.

## Executive summary

AI-assisted security analysis faces several recurring failure modes:

1. **Conformity and judge failure:** A judge may accept a persuasive but invalid vulnerability claim, especially when the evaluation process relies on ungrounded model judgments.
2. **Unverifiable audit trails:** An agent's explanation or transcript may not establish that the claimed execution, evidence, or verification actually occurred.
3. **Repeated reasoning cost:** Retrying a failed analysis with largely unchanged prompts can consume substantial inference tokens without resolving the underlying uncertainty.

BARRED addresses these problems through a neurosymbolic workflow combining:

- **Adversarial Pro/Con analysis** to challenge vulnerability claims.
- **Tree-sitter-based AST and data-flow analysis** to extract code-derived structural evidence.
- **Fail-closed reachability evaluation** to avoid treating incomplete analysis as proof of safety.
- **Explicit acceptance invariants** to enforce measurable conditions on evaluated outputs.
- **Partitioned Pareto/GEPA prompt evolution** to explore targeted improvements across memory safety, arithmetic, concurrency, and input validation.
- **Progressive reflection and retry** to revisit selected failed attempts rather than relying exclusively on repeated static-prompt debates.

These components address different failure modes. AST analysis does not establish every semantic property of a program; model debate does not independently prove correctness; and a deterministic gate is only as trustworthy as its implementation, evidence, and acceptance criteria.

### Reported evaluation results

The current benchmark reports the following results under its evaluated conditions:

| Metric | Reported result | Interpretation |
|---|---:|---|
| Tokens per valid accepted result | 99,104.4 → 33,401.4 | 66.30% reduction against the fixed-static baseline |
| Local AST diagnostic step | No LLM calls required | The local diagnostic step does not incur LLM inference tokens |
| Single-round refinement rescue | 5 of 7 failed attempts (71.4%) | Observed rescue rate in the reported subset |
| Accepted logic-error rate | 0.0000 | No accepted logic-error cases observed in the evaluated corpus |
| Rate-limit interruptions | Zero 429 interruptions | Observed during the reported evaluation |

The evaluation used `agents-cli eval grade` across 83 multi-round cases. These are **evaluation-specific findings, not universal guarantees**. In particular, zero observed accepted logic errors does not establish that all accepted results are correct, and a zero-429 evaluation does not establish production reliability.

See the [ADK Optimizer vs. Graph-GEPA Comparison Report](docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md) for the reported comparison.

## Architecture

```text
                 AI-Assisted Code-Security Workflow
                               |
                               v
                    Target C / Python Code
                               |
                               v
                    AST / Data-Flow Extraction
                               |
                               v
                   Structural Evidence Snapshot
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
         Pro / Con Analysis          Reachability Evaluator
                 |                           |
                 v                           v
        Challenge Vulnerability      Evidence / Completeness
              Claims                       Checks
                 |                           |
                 +-------------+-------------+
                               |
                               v
                     Invariant Acceptance Gate
                         INV-1 through INV-4
                               |
                   +-----------+-----------+
                   |                       |
                   v                       v
             ACCEPT / REJECT       Escalate / Reflect
                                           |
                                           v
                                  Pareto / GEPA Prompts
                                           |
                                           v
                                    Targeted Retry
```

The diagram represents the intended workflow at a conceptual level. A component's presence in the architecture should not be interpreted as proof that every failure mode is detected or every possible execution path is covered.

### Acceptance invariants

BARRED's reported evaluation uses four explicit invariants:

| Invariant | Acceptance condition | Purpose |
|---|---|---|
| INV-1 | `accepted_logic_error_rate == 0.0` | Prevent known logic-error cases from contaminating the accepted evaluation corpus |
| INV-2 | `b2_anchor_match_rate >= 0.80` | Enforce a minimum anchor-match rate |
| INV-3 | `verifier_parse_ok_rate >= 0.95` | Enforce a minimum verifier parse-success rate |
| INV-4 | Zero cross-scenario data leakage | Prevent evidence or state from leaking between benchmark scenarios |

These are evaluation gates, not proofs of general program safety. Their effectiveness depends on correct implementation, valid benchmark labels, representative scenarios, and independent assessment of accepted and rejected results.

## Empirical benchmark comparison

The following figures are reported by the project's comparison evaluation, graded using `agents-cli eval grade` across 83 multi-round cases.

| Evaluation metric | Fixed static baseline | Generic ADK LLM optimizer | BARRED-Neurosymbolic (Graph-GEPA) |
|---|---:|---:|---:|
| Mean tokens per valid accepted result | 99,104.4 | ~75,000 | **33,401.4** |
| Diagnostic reflection cost | ~35,000 tokens per step | ~25,000 tokens per step | **0 LLM tokens for local AST diagnostics** |
| One-round refinement rescue | 28.6% (2/7) | ~25.0% | **71.4% (5/7)** |
| Accepted logic-error rate | 0.0820 | 0.0450 | **0.0000 observed** |
| Rate-limit interruptions in reported evaluation | Frequent failures reported | Frequent failures reported | **Zero 429 interruptions observed** |

### What the numbers support

- **Inference efficiency:** The reported comparison shows fewer tokens per valid accepted result than the fixed-static baseline.
- **Targeted recovery:** Five of seven failed attempts in the reported refinement subset were rescued in one round.
- **Gated acceptance:** No logic-error cases were observed among accepted rows in the evaluated corpus.
- **Local diagnostic efficiency:** The AST diagnostic step can run without an LLM call.

### What the numbers do not establish

- That BARRED eliminates security vulnerabilities or hallucinations.
- That a zero observed accepted logic-error rate will generalize to unseen code or benchmark distributions.
- That AST reachability analysis captures every relevant semantic or runtime behavior.
- That the measured token savings translate into lower total cost for every workload.
- That zero rate-limit interruptions in one evaluation establish production stability.
- That multi-agent debate by itself constitutes coordination, governance, or protection against unauthorized agent actions.

The baseline, evaluation configuration, acceptance definitions, and measurement procedure matter when interpreting these results. Consult the comparison report and evaluation guide before using the figures to make claims about other systems or workloads.

## Quickstart

### 1. Installation

```bash
git clone https://github.com/surfiniaburger/barred-neurosymbolic.git
cd barred-neurosymbolic
pip install -e .
```

### 2. Run AST data-flow reachability analysis

The following example illustrates the intended diagnostic workflow for a potentially unsafe memory write. The actual result depends on the installed parser, snapshot extraction, and reachability evaluator.

```python
from barred_neurosymbolic.ast_flow import extract_graphify_flow_snapshot
from barred_neurosymbolic.reachability import evaluate_graph_reachability

code = """
void handle_packet(char *user_input, int len) {
    char buffer[64];
    memcpy(buffer, user_input, len); // Potentially unguarded memory write
}
"""

snapshot = extract_graphify_flow_snapshot(
    code,
    scenario_id="cve_demo_1",
)

decision = evaluate_graph_reachability(snapshot)

print(f"Is complete AST: {snapshot.is_complete}")
print(f"Risk score: {decision.risk_score}")
print(f"Diagnostic reason: {decision.reason}")
```

**Important:** A diagnostic risk score is not a complete vulnerability verdict. The example illustrates a potentially unsafe operation; confirming exploitability requires considering relevant bounds, call-site conditions, input constraints, and program semantics. An incomplete analysis should not be interpreted as proof that the code is safe.

### 3. Run the test suite

```bash
uv run pytest tests/ -v
```

Run the tests in your local environment and inspect their results before relying on the implementation in a security-sensitive workflow.

## Research questions and limitations

BARRED investigates a specific engineering question:

> How much model reasoning can deterministic code evidence discharge before the available evidence becomes insufficient to support a decision?

The framework also motivates several related questions:

- Does structured evidence improve security-decision quality independently of retry and escalation policies?
- Does targeted reflection improve recovery enough to justify its additional inference cost?
- Can token savings be achieved without increasing false acceptance or hiding unresolved risks?
- How often do failures arise from model reasoning, evidence extraction, parser limitations, invalid benchmark predicates, or disagreement between evaluators?

These questions require more than aggregate acceptance yield. Useful evaluations should include independent review of accepted and rejected cases, false-acceptance and false-rejection rates, residual security defects, review effort, total cost, and uncertainty across repeated runs.

### Known limitations

- **AST analysis is not complete semantic verification.** Structural evidence can miss runtime behavior, aliasing, indirect calls, concurrency interactions, and other language- or environment-dependent properties.
- **Fail-closed is a policy, not a correctness guarantee.** Rejecting incomplete evidence can reduce unsafe acceptance but may also reject valid code or valid vulnerability claims.
- **Invariants depend on valid oracles.** Incorrect benchmark labels or predicates can cause a gate to enforce the wrong conclusion consistently.
- **Agent agreement is not independent proof.** Multiple agents can share assumptions, repeat the same error, or fail to examine relevant evidence.
- **Token reduction is not equivalent to total cost reduction.** Parser execution, retries, infrastructure, human review, and false decisions also contribute to operational cost.
- **Code verification is not general agent governance.** This framework's code-analysis and acceptance gates should not be treated as comprehensive controls for prompt injection, credential misuse, unauthorized web actions, or other external agent behavior.

## Research and engineering documentation

- [Engineering Post-Mortem & Hard-Won Lessons](docs/THE_NEUROSYMBOLIC_SWARM_LESSONS_AND_POSTMORTEM.md) — Engineering phases, failed approaches, verifier audits, and lessons learned.
- [ADK Optimizer vs. Graph-GEPA Comparison Report](docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md) — Reported evaluation results, comparisons, and grading receipts.
- [Evaluation Discipline Guide](docs/EVALUATION_DISCIPLINE_GUIDE.md) — Acceptance invariants, leakage prevention, and evaluation methodology.
- [Frontier Swarm Incident Analysis & Defensive Blueprint](docs/FRONTIER_SWARM_INCIDENT_ANALYSIS_AND_BARRED_DEFENSIVE_BLUEPRINT.md) — Analysis of agent-related incidents and potential defensive approaches.
- [YouTube Masterclass Video Script](docs/YOUTUBE_NEUROSYMBOLIC_SWARM_SCRIPT.md) — Technical walkthrough script with visual cues and code references.

## License

BARRED-Neurosymbolic is released under the Apache License 2.0. See [LICENSE](LICENSE) for details.
