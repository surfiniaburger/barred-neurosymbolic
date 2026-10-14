# Comparative RFC Failure-Taxonomy Supplement: Progressive Escalation Runs

## Purpose and scope

This document is a supplement to the benchmark reports, not a replacement for them.

Its purpose is to explain the causal failure modes behind the numeric outcomes in the progressive-escalation evaluations for:

- Gemma escalated-pareto run (5 replicates, 250 episodes)
- Gemini 3 escalated-pareto run (5 replicates, 250 episodes)

The main benchmark artifacts remain the canonical source for:

- accepted yield
- round-0 vs round-1 performance
- tokens per accepted row
- vulnerable/safe acceptance rates
- model-to-model numerical comparison

This document answers a different question:

> Which RFC-defined failure modes are driving the remaining errors, and are the failure patterns materially different between compact and frontier stacks under progressive escalation?

---

## 1. Why this is a supplement rather than the primary artifact

The RFC in `docs/RFC_EPISTEMIC_REACH_AND_EVIDENCE_SUBSTITUTION.md` is a causal framework, not the benchmark scoreboard.

A benchmark report is optimized for:

- “what happened”
- “which model won”
- “how much was recovered in round 1”
- “what was the efficiency cost”

A failure-taxonomy report is optimized for:

- “why did the model fail”
- “which layer of the evidence pipeline broke”
- “was the issue parser coverage, evidence coverage, evidence sufficiency, or model utilization”
- “did oracle-label mismatch create false disagreement”

In other words, the benchmark report answers the scoring question; this document answers the epistemic question.

For the current comparison, both are necessary, but they are not interchangeable.

---

## 2. The relevant RFC taxonomy

The RFC decomposes failures into four distinct layers:

1. Parser coverage
   - the system emitted valid structure, but serialization or schema handling dropped, mangled, or failed to parse it

2. Evidence coverage
   - the reflector did not extract or preserve the relevant nodes, guards, or sink paths required for the claim

3. Evidence sufficiency
   - the extracted syntax existed, but it could not establish the runtime invariant needed to prove the predicate

4. Model utilization
   - the evidence was in-context, but the model still reasoned from a misleading narrative or ignored hard structural facts

A fifth issue is also important for the benchmark discussion:

5. Oracle-label mismatch / predicate invalidity
   - the benchmark oracle says “vulnerable,” but the supplied vulnerability predicate may be incorrectly specified, incomplete, or not actually grounded in the real runtime contract

This is exactly the distinction the RFC emphasizes: model reasoning reach, reflector evidence reach, and oracle labeling authority are not the same quantity.

### RFC hypothesis status after the final artifact audit

The finalized run evidence changes the earlier provisional interpretation in a narrow but important way:

- **H1 (Evidence Substitution):** partially supported but not confirmed as a full equivalence claim. The run-level data shows a modest yield improvement (Gemma: Δ +6.8 pp Cell 1→Cell 2; Gemini: Δ +3.2 pp Cell 3→Cell 4), but the same-seed paired analysis (`reports/gemini_seed_paired_summary.json`) reveals a weak effect: mean per-seed delta +0.032, 95% bootstrap CI includes zero, only 20 of 250 seed-replicate pairs improve (12 regress, 218 show zero delta). The evidence-vs-protocol confound means the yield delta is not cleanly attributable to the reflector alone. The final Gemma escalated run still contains too much false-positive acceptance to treat the reflector as equivalent to frontier reasoning. H1 remains open as a descriptive pattern, not a confirmatory claim.
- **H2 (Sufficiency Ceiling):** not confirmed. The finalized Gemma and Gemini residuals do not support the blanket claim that the majority of all residual failures are Axis D; the failure mix is model-specific and varies between compact and frontier stacks. Moreover, Cell 4 alone cannot evaluate H2 — a valid cell comparison requires matched populations and a shared taxonomy, which the current Gemma (130 rejection attempts across 343 attempts) and Gemini (20 terminal failures under the seven-axis taxonomy) profiles do not satisfy.
- **H3 (Oracle Decoupling via Reasoning Reach):** strongly supported for Gemini. The final evidence shows a repeated pattern in which the frontier stack rejects benchmark-labeled predicates when the underlying argument is structurally or semantically invalid, and this is only meaningful when independently reconciled with deterministic evidence or POSIX semantics.
- **H4 (Diminishing Marginal Utility):** not confirmed. While the run-level aggregate ratio of 0.47 (Δ_Frontier +3.2 pp / Δ_Compact +6.8 pp) technically crosses the 0.50 threshold, the same-seed paired analysis reveals a weak and non-decisive effect: mean per-seed delta of +0.032 with a 95% bootstrap CI that includes zero, and only 20 of 250 seed-replicate pairs show any improvement (12 regress, 218 show zero delta — a ceiling-bound saturation effect). The paired data (`reports/gemini_seed_paired_summary.json`, `reports/gemini_seed_paired_ledger.csv`) cannot rule out that the aggregate gain is driven by a small subset of seeds, and the evidence-vs-protocol confound (`reports/gemini_evidence_vs_protocol_control_report.md`) means the yield delta is not cleanly attributable to the reflector alone. H4 remains open.

The practical takeaway is: the RFC still holds, but its central causal story is not a single universal narrative. Gemma's residual failures are more evidence-coverage and utilization driven, while Gemini's are more concentrated in proof sufficiency and semantic adjudication.

---

## 3. What the progressive-escalation runs show in practice

Across both Gemma and Gemini escalated-pareto runs, the pattern is consistent with the RFC.

The strongest common finding is this:

- progressive escalation substantially improves validation yield after model failures,
- but the residual failures concentrate in a small number of causal buckets,
- and those buckets are not identical across model families.

### Gemma pattern
The Gemma escalated-pareto run is the clearest example of a system that benefits strongly from warm escalation, while still suffering from:

  - relational grounding failures (`anchors_too_few_after_normalization`) — maps to RFC **Axis A** (Model Reasoning / Output Constraint Failure): the model emitted only 0 or 1 verbatim code anchor (in 100% of telemetry cases: 75.5% 1-anchor, 24.5% 0-anchor; 0% normalizer dropouts), failing to synthesize the required two-point relational proof chain (source-to-sink or guard-to-operation) despite the code being present in context
  - evidence sufficiency problems (`predicate_quality_failed`) — maps to RFC **Axis D** (Evidence Insufficiency): extracted syntax cannot establish the required runtime invariant
  - verifier failures (`verifier_failed`) — maps to RFC **Axis E** (Predicate Invalidity): the stated vulnerability mechanism is demonstrably false, so the verifier cannot validate the claim
  - model utilization failures (`verifier_logic_error`) — maps to RFC **Axis A** (Model Reasoning Failure): evidence was present in context, but the verifier-model drew invalid logic

The aggregate result is a good example of the RFC thesis:

- the reflector improves the evidence interface,
- round 1 repairs are substantial,
- but the model still hallucinates or ignores grounded facts when the prompt is semantically underspecified or the runtime contract is not actually established.

### Gemini pattern
The Gemini escalated-pareto run shows the same general structure but with a different balance:

- frontier reasoning is stronger in terms of safe-seed quarantine and logic-blocking,
- the reflector still helps in targeted recovery,
- however, the remaining failures still cluster around claim validity and proof sufficiency, not just raw model intelligence

This is important because the frontier model is not “immune” to evidence-substitution failure.

Instead, the Gemini stack usually fails later in the pipeline, where the problem is no longer “the model cannot see the code,” but rather:

- the claim is not fully grounded in the required semantics,
- the argument is structurally plausible but not runtime-valid,
- or the benchmark’s oracle predicate and the actual formal invariant are not tightly aligned.

---

## 4. Comparison of dominant failure modes

The benchmark reports give the numerical totals. This supplement is meant to interpret the residual error profile.

> **Comparison caveat:** The Gemma and Gemini profiles below are presented as separate qualitative summaries, not as an apples-to-apples comparison. They use unmatched populations (Gemma reports 130 rejection attempts across 343 attempts; Gemini reports 20 terminal failures under the seven-axis taxonomy) and different taxonomies, so failure shares should not be compared numerically. Cell 4 alone cannot evaluate H2; matched populations and a shared taxonomy are required before comparing failure shares.

### High-level comparison

| Failure class | Gemma escalated run | Gemini escalated run | Interpretation |
| --- | --- | --- | --- |
| Parser coverage | present but relatively low (qualitative) | [C] 1 / 20 (5%) | both systems can lose structure in formatting/schema boundaries |
| Evidence coverage | present but low (qualitative) | [B] 1 / 20 (5%) | when the reflector does miss relevant code, the failure is structural extraction, not reasoning |
| Evidence sufficiency | strong (`predicate_quality_failed`) | [D] 8 / 20 (40%) | both systems hit the ceiling where syntax is not enough to prove the runtime invariant |
| Model utilization | strong (`verifier_logic_error`, `anchors_too_few_after_normalization`) | [A] 4 / 20 (20%) | compact models suffer from single-token fixation; `anchors_too_few_after_normalization` reflects the model citing <2 code anchors for its verdict rather than a parser/extraction dropout (0% normalizer attrition across 278 attempt logs) |
| Oracle-label mismatch / predicate invalidity | `verifier_failed` | [E] 5 / 20 (25%) + [F] 0 + [G] 1 / 20 (5%) | the benchmark oracle does not guarantee that every supplied predicate is a valid proof object; verifier failures occur when the predicate is demonstrably false [E], though Cell 2 does not yet distinguish [F] oracle disagreement from [E] predicate invalidity at per-seed granularity |

> **Note:** The Gemini column uses the 7-axis taxonomy from `docs/BENCHMARK_REPORT_GEMINI3_ESCALATED_PARETO_50.md` Section 4 (rep1, 20 terminal failures). A follow-up case-level audit in `@artifacts` reclassified Seed 84 from Axis B to Axis A; see the audit note below. The Gemma column uses qualitative labels from the Gemma escalated run's rejection categories; Cell 2 does not yet carry a structured 7-axis per-seed taxonomy, so numerical shares cannot be computed. The two columns are not directly comparable.

### Observed Gemma failure profile

> **Data limitation:** The Gemma escalated-pareto run (Cell 2) does not yet carry a structured 7-axis per-seed taxonomy. The following failure categories are derived from the run's rejection logs (130 rejection attempts across 343 attempts, per the RFC Cell 2 matrix), not from a per-seed 7-axis classification. A full comparison with Gemini's 7-axis profile awaits Cell 2's per-seed failure taxonomy.

The Gemma escalated-pareto run specifically showed a very strong concentration in:

- `anchors_too_few_after_normalization`
- `verifier_failed`
- `verifier_logic_error`

That pattern is an archetypal RFC failure cluster:

- model utilization failures (`anchors_too_few_after_normalization`, `verifier_logic_error`) mean the model failed to construct a two-point relational proof or drew invalid logic despite the relevant syntax being present in context,
- evidence coverage gaps mean the reflector genuinely missed relevant code structure (as distinct from the model's self-assessed insufficiency),
- evidence sufficiency gaps mean the extracted facts were present but not enough to certify the runtime invariant,
- and predicate invalidity (`verifier_failed`) means the stated vulnerability mechanism is demonstrably false.

### Observed Gemini failure profile

The Gemini escalated-pareto run (Cell 4) recovered substantial yield via Round 1 warm escalation (mean 7.4 recoveries per run across 5 replicates), but the 20 terminal failures that remained break down by the RFC 7-axis taxonomy as follows (derived from per-seed attempt logs in `docs/BENCHMARK_REPORT_GEMINI3_ESCALATED_PARETO_50.md` Section 4, rep1):

| Axis | Label | Count | Share | Seeds |
| :---: | :--- | :---: | :---: | :--- |
| **[A]** | Model Reasoning Failure | **4** | 20% | 60, 64, 68, 86 |
| **[B]** | Reflector Extraction Failure | **1** | 5% | 84 |
| **[C]** | Parser / Interface Failure | **1** | 5% | 80 |
| **[D]** | Evidence Insufficiency | **8** | 40% | 42, 46, 48, 52, 56, 66, 82, 90 |
| **[E]** | Predicate Invalidity | **5** | 25% | 45, 62, 70, 74, 78 |
| **[F]** | Oracle Disagreement | **0** | 0% | — |
| **[G]** | Genuine Semantic Ambiguity | **1** | 5% | 44 |

> **Audit note:** The Gemini 7-axis breakdown below is derived from the per-seed attempt logs in `docs/BENCHMARK_REPORT_GEMINI3_ESCALATED_PARETO_50.md`. Seed 84 is classified as Axis B (Reflector Extraction Failure) in that source; a follow-up case-level audit in `@artifacts` later reclassified Seed 84 to Axis A (Model Reasoning Failure), arguing that the model should have selected the relevant function rather than attributing the failure to tree-sitter extraction. The table retains the source-file version for traceability; the `@artifacts` reclassification is noted separately.

**Shift from baseline to escalated (Cell 3 → Cell 4):**

**Baseline profile (Cell 3):** The Gemini 3 baseline, without the reflector, produced 49 rejected attempts across 77 total attempts (in `docs/BENCHMARK_REPORT_GEMINI3_BASELINE_VS_GEMMA_50.md`). The 7-axis taxonomy classifies the bulk of these as Axis A (Model Reasoning Failure): 43 of 49 (87.8%). The remaining 6 cases are distributed across Axis D (Evidence Insufficiency, 3/49 = 6.1%), Axes E + F (Predicate Invalidity / Oracle Disagreement, 2/49 = 4.1%), and Axis C (Parser/Interface, 1/49 = 2.0%). Axes B and G are 0.

**Escalated profile (Cell 4):** The Gemini escalated-pareto run, with progressive escalation, produced 20 terminal failures out of 50 seeds (in `docs/BENCHMARK_REPORT_GEMINI3_ESCALATED_PARETO_50.md`). The source-file audit classifies 4 of 20 (20%) as Axis A, with the remaining cases dominated by Axis D (8/20 = 40%) and Axis E (5/20 = 25%). A follow-up case-level audit in `@artifacts` reclassified Seed 84 from Axis B to Axis A and moved one Axis E case to Axis D, revising the breakdown to 5 Axis A (25%), 0 Axis B, 1 Axis C (5%), 9 Axis D (45%), 4 Axis E (20%), 0 Axis F, and 1 Axis G (5%) — totaling all 20 terminal failures. The table above retains the source-file version for traceability.

> **Population caveat:** The Cell 3 and Cell 4 profiles are not directly comparable via cross-profile percentages. Cell 3's denominator is *rejected attempts* (49 cases where the baseline model rejected a predicate, including both true and false rejections), whereas Cell 4's denominator is *terminal failures* (20 cases where the escalation pipeline still failed to reach a correct decision after all rounds). These represent different outcome definitions. A same-seed paired comparison is required to determine whether the apparent Axis A reduction is a true reflector effect or an artifact of the different population definitions.

---

## 5. Why the substantive comparison is about evidence-substitution, not raw intelligence

The main takeaway from both runs is that benchmark quality is strongly shaped by whether the system can separate three different questions:

1. Can the model reason over the code?
2. Can the reflector actually provide the right evidence?
3. Is the benchmark’s predicate even valid for the real runtime contract?

The escalated runs show that a system can improve on all three simultaneously, yet still not reach a perfect answer because the evidence interface remains a bottleneck.

This is the central RFC claim:

- model reasoning reach alone is not enough,
- reflector reach alone is not enough,
- oracle labels alone are not sufficient to certify a mechanism.

The only reliable route is a correct combination of:

- valid structured evidence,
- sufficient runtime grounding,
- and model conditioning on the evidence instead of narrative priors.

---

## 6. Recommended use in the project

This document should be used as a comparative supplement in the following way:

- use the benchmark reports for the primary tables and model-vs-model scorecards,
- use this taxonomy document to explain which causal failure mode is dominating in each model stack,
- use the same taxonomy across Gemma and Gemini, **and require matched populations before treating any failure-share comparison as apples-to-apples**.

Recommended file arrangement:

- benchmark report: main numerics and direct comparison
- RFC failure taxonomy supplement: causal explanation for the residual failures

This keeps the project honest: the benchmark wins are real, but the residual failure modes still matter, and the RFC makes those failure modes readable.

---

## 7. Bottom line

The Gemma escalated-pareto run and the Gemini escalated-pareto run both support the same architectural conclusion:

- the progressive escalation protocol materially improves performance,
- but it does not eliminate the underlying epistemic failure modes,
- and those failure modes are most cleanly understood through the RFC taxonomy.

The difference between the runs is not that one stack is “smart” and the other is “dumb.”

The difference is that they fail in different layers of the evidence pipeline:

- Gemma is more sensitive to evidence extraction and model utilization gaps.
- Gemini is more sensitive to claim validity and proof sufficiency under strong but not perfect evidence.

That is exactly the type of analysis this supplement is meant to provide.
