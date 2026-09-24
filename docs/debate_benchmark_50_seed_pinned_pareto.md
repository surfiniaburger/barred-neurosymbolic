# Scaled Debate Benchmark Report: Final Pinned Pareto (Angle 3, N=50 Multi-Replicate)

**Evaluation Date:** 2026-09-22  
**Evaluation Scope:** Scaled Benchmark across 50 Virgin Scenarios with Frozen Terminal Pareto Prompts ($N=5$ Replicates, $249$ Canonical Scenario Episodes)  
**Evaluation Harness:** BARRED-Fleet Swarm (Gemma-4-12B Judge/Verifier, Gemma-4-E4B Debaters)  
**Seed Manifest:** `scenarios/debate/cve_seeds_benchmark_50.jsonl` (50 C codebase scenarios: 25 Safe, 25 Vulnerable)  
**Methodological Protocol:** **Regime 3 (Condition C: Final Pinned Pareto / `--pin-pareto`)** — Evaluates whether accumulated prompt knowledge can replace online adaptation. Debaters initialize with the terminal 669-entry Pareto frontier prompts produced after the five active-online replicates in `artifacts/gepa_pareto_50/pareto_frontier.json`. Unlike Regime 2 (Active Online Learning), live Reflector mutation and prompt rewrite are strictly disabled: failed Round 0 attempts retry in Round 1 using the *same warm prompt without topological mutations*, and no accepted prompts are promoted into the ledger. The Pareto frontier and mutations ledger remain 100% immutable.

---

## 1. Executive Summary: Epistemic Adaptation vs. Prompt Memory

Angle 3 investigates the benchmark question: **Can accumulated prompt knowledge in a frozen prompt reproduce the performance of live online reflection?**

Across five independent 50-seed replicates ($N=249$ canonical scenario evaluations under Regime 3's frozen terminal prompt vs. $N=250$ canonical evaluations under Regime 2's dynamically evolving prompt), the empirical comparison reveals key protocol-level differences:

1. **Observed Protocol-Level Recovery Gap:** Across the 249 canonical episodes in Regime 3, 150 seeds passed Round 0, leaving **99 failed episodes that triggered Round 1 refinement**. Retrying with the *same frozen prompt* under Pinned Pareto recovered **37 of 99 episodes (37.4% recovery rate)**. In comparison, the dynamic refinement protocol in Regime 2 achieved a **50.4% recovery rate (57/113)**. While differing starting prompt configurations and episode sets preclude attributing the +13.0 pp gap solely to runtime adaptation, this demonstrates a substantial protocol-level recovery difference between static retries and active online adaptation.
2. **Net Yield Hierarchy:** 
   - **Regime 2 (Active Online Learning):** **$40.20 \pm 2.77$ rows / run ($80.4\% \pm 5.5\%$)**
   - **Regime 1 (Stationary Baseline):** **$39.20 \pm 2.59$ rows / run ($78.4\% \pm 5.2\%$)**
   - **Regime 3 (True Pinned Pareto):** **$37.40 \pm 2.41$ rows / run ($75.1\% \pm 4.8\%$)**
3. **The "Anchor Trap" in Frozen Prompts:** Both warm Pareto regimes suffer from a lower Round-0 yield (~57–60%) than the cold baseline (72.0%) due to instruction competition between complex domain directives and verbatim anchor constraints. Active Online recovered 57/113 Round-0 failures (50.4%). Pinned Pareto also recovered 37/99 (37.4%) using the same frozen prompt, without prompt mutation. Its recovery rate exceeded the baseline's 16/70 (22.9%), but its lower Round-0 yield left its net yield below baseline.
4. **Compute Economics Tradeoff:** Pinned Pareto burned **22,127.6 tokens / accepted row** (replicate mean; 22,026.6 pooled aggregate) compared to **20,316.3 tokens / accepted row** for the baseline and **21,571.0 tokens / accepted row** for Active Online. Across the evaluated regimes, retrying with an unadapted static prompt prior yielded higher recovery but higher per-sample token cost than the stationary baseline.
5. **Safety Invariance:** All five replicates maintained **zero accepted logic errors (INV-1 = 0.0000, 100% clean)** across 187 accepted rows. The Pareto ledger remained 100% immutable (SHA256 verified).

```text
                             ROUND 0 EVALUATION
                                     │
                   ┌─────────────────┴─────────────────┐
                   │                                   │
            Pinned (Frozen v669)            Online (Dynamic v355→v669)
                60.2% (150/249)                     57.6% (144/250)
                   │                                   │
                   ▼                                   ▼
                FAILURE                             FAILURE
                   │                                   │
                   ▼                                   ▼
             same prompt retry                   graph diagnosis
                   │                                   │
                   ▼                             prompt mutation
             37.4% recovery                            │
               (37/99 rows)                            ▼
                   │                             50.4% recovery
                   ▼                              (57/113 rows)
           Net Yield: 75.1%                            │
              (187/249)                                ▼
                                               Net Yield: 80.4%
                                                  (201/250)
```

---

## 2. Tri-Regime Multi-Replicate Performance Matrix

| Metric | Regime 1: Sliced Baseline Mean ($N=5$) | Regime 2: Active Online Mean ($N=5$) | **Regime 3: Pinned Pareto Mean ($N=5$)** | Contrast: Reg 3 vs. Reg 1 (Baseline) | Contrast: Reg 3 vs. Reg 2 (Online) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Seeds Evaluated** | 50 (25 S / 25 V) | 50 (25 S / 25 V) | **49.8 (24.8 S / 25.0 V)** | Invariant ($N \approx 50$) | Invariant ($N \approx 50$) |
| **Canonical Episodes** | 250 (5 runs $\times$ 50) | 250 canonical (257 total) | **249 (1 token repeat error on Rep 4)** | Invariant | Invariant |
| **Prompt Provenance** | Cold (`baseline_v0`) | Dynamic ($355 \to 669$ muts) | **Frozen Terminal ($669$ muts)** | Evolved vs. Cold | Frozen vs. Evolving |
| **Accepted Training Rows** | 39.20 ± 2.59 (78.4% ± 5.2%) | 40.20 ± 2.77 (80.4% ± 5.5%) | **37.40 ± 2.41 (75.1% ± 4.8%)** | -3.3 pp | -5.3 pp |
| **Round 0 Accepted Rows** | 36.00 ± 2.00 (72.0%) | 28.80 ± 2.49 (57.6%) | **30.00 ± 3.08 (60.2%)** | -11.8 pp (Anchor Gap) | +2.6 pp (Comparable) |
| **Round 0 Rejections (Eligible R1)** | 14.00 ± 2.00 (28.0%) | 21.20 ± 2.49 (42.4%) | **19.80 ± 2.77 (39.8%, 99 total)** | +11.8 pp | -2.6 pp |
| **Round 1 Recoveries** | 16 / 70 (22.9%) | 57 / 113 (**50.4%**) | **37 / 99 (37.4%)** | +14.5 pp | **-13.0 pp (Post-Failure Gap)** |
| **Accepted Logic Errors (INV-1)** | **0.0000 ± 0.0000** | **0.0000 ± 0.0000** | **0.0000 ± 0.0000 (0 / 187)** | Invariant (100% clean) | Invariant (100% clean) |
| **Total Attempts / Run** | 67.20 ± 3.27 (1.34/seed) | 74.00 ± 5.74 (1.48/seed) | **69.60 ± 2.51 (1.40/seed)** | +0.06/seed | -0.08/seed |
| **Total Benchmark Tokens** | 791,116.8 ± 64,572.6 | 863,003.4 ± 46,854.9 | **823,793.0 ± 26,159.5** | +4.1% | -4.5% |
| **Tokens / Accepted Row** | 20,316.3 ± 2,820.5 | 21,571.0 ± 2,179.0 | **22,127.6 ± 1,996.2 (mean) / 22,026.6 (agg)** | +8.9% | +2.6% |
| **Safe Accepted Rate** | 18.20 ± 2.39 (72.8%) | 19.60 ± 2.07 (78.4%) | **16.40 ± 1.52 (66.1%)** | -6.7 pp | -12.3 pp |
| **Vulnerable Accepted Rate** | 21.00 ± 0.71 (84.0%) | 20.60 ± 1.14 (82.4%) | **21.00 ± 1.73 (84.0%)** | 0.0 pp | +1.6 pp |

---

## 3. Replicate-by-Replicate Canonical Breakdown (Regime 3)

| Replicate ID | Seed | Evaluated | Acc Yield | Round 0 Pass | Round 0 Fail | Round 1 Recovery | Attempts | Total Tokens | Tokens / Acc Row | INV-1 Errors |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `unrun-pinned-pareto-50-rep1` | 42 | 50 | **36 / 50 (72.0%)** | 28 / 50 (56.0%) | 22 | 8 / 22 (36.4%) | 72 | 841,103 | 23,364.0 | **0 (0.0000)** |
| `unrun-pinned-pareto-50-rep2` | 43 | 50 | **40 / 50 (80.0%)** | 34 / 50 (68.0%) | 16 | 6 / 16 (37.5%) | 66 | 804,295 | 20,107.4 | **0 (0.0000)** |
| `unrun-pinned-pareto-50-rep3` | 44 | 50 | **35 / 50 (70.0%)** | 31 / 50 (62.0%) | 19 | 4 / 19 (21.1%) | 69 | 826,088 | 23,602.5 | **0 (0.0000)** |
| `unrun-pinned-pareto-50-rep4` | 45 | 49 | **36 / 49 (73.5%)** | 26 / 49 (53.1%) | 23 | 10 / 23 (43.5%) | 72 | 855,773 | 23,771.5 | **0 (0.0000)** |
| `unrun-pinned-pareto-50-rep5` | 46 | 50 | **40 / 50 (80.0%)** | 31 / 50 (62.0%) | 19 | 9 / 19 (47.4%) | 69 | 791,706 | 19,792.7 | **0 (0.0000)** |
| **Summary / Total** | — | **249** | **187 / 249 (75.1%)** | **150 / 249 (60.2%)** | **99** | **37 / 99 (37.4%)** | **348** | **4,118,965** | **22,026.6** | **0 / 187 (0.0000)** |

> **Note on Attempt Log Accounting:** As in Regime 2, subsequent rerun/resume executions against existing output corpora appended diagnostic attempts (62 attempts total across Reps 2–4) to `artifacts/attempts/`. The canonical breakdown above rigorously tracks the single-retry execution sequence for each seed: 150 Round 0 successes + 99 Round 0 failures + 99 Round 1 retries = 348 canonical attempts, resulting in exactly 187 accepted rows across the five corpus files listed in Section 5 (`test_corpus_pinned_pareto_50_rep1.jsonl` through `test_corpus_pinned_pareto_50_rep5.jsonl`).

---

## 4. In-Depth Scientific Analysis

### A. Observed Protocol-Level Differences Between Static Prompts and Dynamic Adaptation
Comparing Regime 3's frozen terminal prompt (249 canonical episodes) against Regime 2's dynamic prompt mutation protocol (250 canonical episodes) demonstrates a notable protocol-level recovery gap:
- In Round 0, both warm regimes perform similarly ($57.6\%$ active vs. $60.2\%$ pinned).
- But upon failure, the observed trajectories diverge:
  - Under the **frozen prompt retry protocol** (Regime 3), debaters recover **$37.4\%$** of failed episodes (37/99).
  - Under the **dynamic prompt mutation protocol** (Regime 2), debaters recover **$50.4\%$** (57/113), representing an observed +13.0 pp protocol-level difference.
- *Interpretation:* Because Regime 3 initializes with the terminal 669-mutation frontier while Regime 2 evolves dynamically from 355 to 669 mutations, a matched ablation holding the starting prompt and episode set strictly constant would be required to isolate runtime adaptation as the exclusive causal mechanism. Nonetheless, the empirical comparison indicates that accumulated prompt knowledge in a frozen configuration does not reproduce the elevated recovery rates observed under the active reflection protocol.

### B. The Mechanism of the Anchor Trap
The data is consistent with an association between the "Round 0 Anchor Trap" and prompt complexity:
- Cold minimal prompt (`baseline_v0`): **72.0%** Round 0 yield.
- Evolved warm prompts (Regimes 2 & 3): **57.6% – 60.2%** Round 0 yield.
- Detailed directives regarding sinks, taint reachability, and memory invariants may create cognitive competition with verbatim anchor extraction rules. 
- In Regime 2, this overhead is redeemed by the Reflector's 50.4% recovery rate. In Regime 3, without the Reflector, the swarm pays the initial compliance penalty without having the repair loop, resulting in a net yield ($75.1\%$) lower than the un-evolved baseline ($78.4\%$).

### C. Compute Economics: Observed Tradeoffs Across Protocols
- Across the three regimes, token expenditure per accepted row reflects distinct operational tradeoffs:
  - Regime 1 (Stationary Baseline) achieved the lowest cost at **20,316.3 tokens / accepted row**, benefiting from high first-pass compliance (72.0%).
  - Regime 2 (Active Online Adaptation) required **21,571.0 tokens / accepted row**, spending additional tokens on live Reflector passes and Round 1 re-debates, but achieving the highest net yield (80.4%).
  - Regime 3 (Pinned Pareto) required **22,127.6 tokens / accepted row** (replicate mean; 22,026.6 pooled aggregate). In this configuration, failed seeds incurred the full token expenditure of Round 1 re-debates, but without dynamic prompt mutations, fewer retries converted to accepted rows (37.4% recovery vs. 50.4% in Regime 2).
- *Observation:* Across the tested configurations, dynamic adaptation traded higher total benchmark compute for higher sample recovery, whereas retrying with a static prompt prior yielded both lower recovery and higher per-sample token cost than the stationary baseline. Determining whether active adaptation is economically optimal depends on application-specific valuations of accepted yield versus raw token cost, and a matched ablation holding the starting prompt state constant would be required to establish strict causal efficiency.

---

## 5. Replicate Progress Log & Artifact Receipts

| Replicate ID | Status | Output Corpus | Attempts Log | Run Manifest |
| :--- | :---: | :--- | :--- | :--- |
| `unrun-pinned-pareto-50-rep1` | **Completed** | `test_corpus_pinned_pareto_50_rep1.jsonl` | `artifacts/attempts/unrun-pinned-pareto-50-rep1.jsonl` | `artifacts/runs/unrun-pinned-pareto-50-rep1/batch_manifest.json` |
| `unrun-pinned-pareto-50-rep2` | **Completed** | `test_corpus_pinned_pareto_50_rep2.jsonl` | `artifacts/attempts/unrun-pinned-pareto-50-rep2.jsonl` | `artifacts/runs/unrun-pinned-pareto-50-rep2/batch_manifest.json` |
| `unrun-pinned-pareto-50-rep3` | **Completed** | `test_corpus_pinned_pareto_50_rep3.jsonl` | `artifacts/attempts/unrun-pinned-pareto-50-rep3.jsonl` | `artifacts/runs/unrun-pinned-pareto-50-rep3/batch_manifest.json` |
| `unrun-pinned-pareto-50-rep4` | **Completed** | `test_corpus_pinned_pareto_50_rep4.jsonl` | `artifacts/attempts/unrun-pinned-pareto-50-rep4.jsonl` | `artifacts/runs/unrun-pinned-pareto-50-rep4/batch_manifest.json` |
| `unrun-pinned-pareto-50-rep5` | **Completed** | `test_corpus_pinned_pareto_50_rep5.jsonl` | `artifacts/attempts/unrun-pinned-pareto-50-rep5.jsonl` | `artifacts/runs/unrun-pinned-pareto-50-rep5/batch_manifest.json` |

- **Frontier Invariance Verification:** `artifacts/gepa_pareto_50/pareto_frontier.json` SHA256 verified at `516c2f76de1af896a9a410fe86133b4233fbbec25283a1d92c3dd5a2152e57d0` across all 5 replicates. 0 ledger mutations recorded.
