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

- **H1 (Evidence Substitution):** partially supported but not confirmed as a full equivalence claim. The reflector materially helps compact models, but the final Gemma escalated run still contains too much false-positive acceptance to treat the reflector as equivalent to frontier reasoning.
- **H2 (Sufficiency Ceiling):** not confirmed. The finalized Gemma and Gemini residuals do not support the blanket claim that the majority of all residual failures are Axis D; the failure mix is model-specific and varies between compact and frontier stacks. Moreover, Cell 4 alone cannot evaluate H2 — a valid cell comparison requires matched populations and a shared taxonomy, which the current Gemma (130 rejection attempts across 343 attempts) and Gemini (20 terminal failures under the seven-axis taxonomy) profiles do not satisfy.
- **H3 (Oracle Decoupling via Reasoning Reach):** strongly supported for Gemini. The final evidence shows a repeated pattern in which the frontier stack rejects benchmark-labeled predicates when the underlying argument is structurally or semantically invalid, and this is only meaningful when independently reconciled with deterministic evidence or POSIX semantics.
- **H4 (Diminishing Marginal Utility):** not confirmed under the final delta comparison. The compact model clearly benefits, but the frontier delta is not sufficiently smaller than the compact one to support the strict diminishing-return threshold.

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

  - evidence coverage gaps (`anchors_too_few_after_normalization`)
  - evidence sufficiency problems (`predicate_quality_failed`)
  - verifier failures (`verifier_failed`)
  - model utilization failures (`verifier_logic_error`)

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
| Parser coverage | present but relatively low | present but relatively low | both systems can lose structure in formatting/schema boundaries |
| Evidence coverage | strong dominant cluster | present but less dominant | compact models are more sensitive to incomplete anchor or slice extraction |
| Evidence sufficiency | strong | strong | both systems hit the ceiling where syntax is not enough to prove the runtime invariant |
| Model utilization | strong | moderate | compact models are more likely to reason from misleading narratives under prompt pressure |
| Oracle-label mismatch / predicate invalidity | important | important | the benchmark oracle does not guarantee that every supplied predicate is a valid proof object |

### Observed Gemma failure profile
The Gemma escalated-pareto run specifically showed a very strong concentration in:

- `anchors_too_few_after_normalization`
- `verifier_failed`
- `verifier_logic_error`

That pattern is an archetypal RFC failure cluster:

- evidence coverage gaps mean the reflector did not extract enough local proof structure,
- evidence sufficiency gaps mean the extracted facts were not enough to certify the runtime invariant,
- model utilization failures mean even when evidence reached the model, the model still accepted a misleading narrative.

### Observed Gemini failure profile
The Gemini escalated-pareto run still showed recovery, but not a clean proof ceiling. The dominant residual issues were more consistent with:

- semantic over-acceptance of a plausible but insufficient exploit story
- logic errors caught by the verifier
- adjudicated cases where the benchmark predicate was not fully justified by the actual runtime behavior

This is not a failure of the model to “reason”; it is a failure of the evidence contract to make the exact runtime invariant explicit enough for the model to verify.

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
