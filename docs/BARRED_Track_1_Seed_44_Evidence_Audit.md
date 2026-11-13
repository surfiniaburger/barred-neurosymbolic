# BARRED Track 1 — Seed 44 Evidence Audit

## Question audited

**Claim:** “The code is vulnerable to timing side-channel attacks in the `pointZZ_pMul` function (scalar multiplication) because it uses a secret-dependent branch (if-else on `mpz_tstbit`) that causes data-dependent execution paths.”

**Result:** **Potential timing side-channel (not confirmed).** The supplied `pointZZ_pMul` (and `pointZZ_pShamirsTrick`) branch on scalar bits and execute operand-swapped sequences of point additions and doublings, but the shown branch difference alone does not establish a secret-correlated timing difference (both branches perform one add + one double). Callees may be data-dependent, yet no measurement evidence of secret-correlated timing is provided. Contingent on the scalar being secret (unverified) and on measurement evidence (absent). Unlike seeds 42, 46, 50, 66, and 68, the supplied source does contain the operation the predicate describes (branching on scalar bits). Whether the benchmark `safe` label is 'wrong' for this predicate is unresolved: it depends on whether the scalar is secret in the caller's context and on what `safe` denotes, neither of which the corpus establishes (label meaning unresolved).

## What was examined

1. I selected seed 44 because it carries the strongest Gemma pro-claim signal among the remaining unaudited persistent-split seeds (3/5 accepted Pro claims in Gemma escalation vs. 0/5 in Gemini), and the allegation is mechanically checkable against the supplied source.
2. The relevant function is `pointZZ_pMul`:
   ```c
   for (i = dbits - 2; i >= 0; i--) {
       if (mpz_tstbit(scalar, i)) {
           mpz_set(tmp.x, R0.x); mpz_set(tmp.y, R0.y);
           pointZZ_pAdd(&R0, &R1, &tmp, curve);   // R0 = R0 + R1
           mpz_set(tmp.x, R1.x); mpz_set(tmp.y, R1.y);
           pointZZ_pDouble(&R1, &tmp, curve);      // R1 = 2*R1
       } else {
           mpz_set(tmp.x, R1.x); mpz_set(tmp.y, R1.y);
           pointZZ_pAdd(&R1, &R0, &tmp, curve);   // R1 = R0 + R1
           mpz_set(tmp.x, R0.x); mpz_set(tmp.y, R0.y);
           pointZZ_pDouble(&R0, &tmp, curve);     // R0 = 2*R0
       }
   }
   ```
   The branch condition `mpz_tstbit(scalar, i)` depends on a secret bit of the scalar. The two branches perform the same *count* of operations (one add + one double) but with operands swapped between `R0` and `R1`, and they touch different memory/branches inside `pointZZ_pAdd` and `pointZZ_pDouble`.
3. `pointZZ_pShamirsTrick` repeats the pattern: it calls `mpz_tstbit(scalar1, l)` and `mpz_tstbit(scalar2, l)` to choose which point to add, so its execution path also depends on secret bits.
4. The operations are not constant-time even aside from control flow:
   - `pointZZ_pAdd` and `pointZZ_pDouble` contain early returns for identity elements (`pointZZ_pIsIdentityElement`) and equal points (`pointZZ_pEqual`), so their runtime varies with intermediate point values.
   - Both call `mpz_invert(..., curve->p)`, and GMP's modular inverse is not constant-time.
   - `mpz_cmp`, `mpz_cmp_ui`, and the conditional `mpz_set` calls are data-dependent in timing.
   The callees may introduce data-dependent timing, but a secret-correlated timing difference across the whole operation is not demonstrated by the shown code or by measurement.
5. Provenance: the supplied topic matches CVEFixes row 26613 exactly (SHA-256 `87aa43444950b40e263623745ce084a4be8bcbbaea96e2f8477744fc0800721d`, 8971 bytes, language `c`, safety `safe`). A second, shorter variant (row 18019, 7580 bytes) is labelled `vulnerable` in the same corpus. As with seeds 42, 46, 50, and 68, the CSV retains only `code`, `language`, and `safety` — no version/commit metadata. The source exhibits a potential source-level timing dependence (branching on scalar bits plus data-dependent arithmetic in callees), but a secret-correlated timing difference is not demonstrated. The CSV `safe` label's meaning is not defined by the corpus (no version/commit metadata), so whether it is 'wrong' for this predicate is unresolved — it may describe a particular fixed state rather than timing behavior. The label is a triage signal, not proof.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `if (mpz_tstbit(scalar, i)) { ... } else { ... }` in `pointZZ_pMul`, plus `mpz_tstbit`-driven branching in `pointZZ_pShamirsTrick`. | Identified precisely. |
| Is the branch secret-dependent? | The branch condition depends on bits of `scalar`. Whether `scalar` is secret in any caller is not established by the available evidence: the cited binding only shows string-to-integer parsing, and no caller of `curvemath.mul` or the point-multiplication functions was found outside this audit. | Open question (conditional on a secret scalar). |
| Does execution time vary with the secret? | Not established by the shown code: branch bodies perform the same count of operations (one add + one double) with operands swapped between `R0` and `R1`, so no cost difference between branches is visible. Callees (`pointZZ_pAdd`, `pointZZ_pDouble`, `mpz_invert`) have data-dependent early returns and non-constant-time arithmetic that may vary with intermediate values, but secret-correlated timing is not demonstrated. | Potential (unverified). |
| Is the scalar required to be secret? | For a curve-multiplication routine used in ECC, the scalar is conventionally the private key and constant-time is a standard requirement, but this presumes the caller treats it as secret, which is unverified (see above). The function exposes no constant-time alternative. | Applicable threat model only if the scalar is secret (unverified). |
| Is a trigger demonstrated? | Reachability of both branches shown by construction (any non-trivial scalar exercises both). Timing correlation is not demonstrated; no runtime measurement provided. | Not substantiated as a timing leak. |
| Benchmark label | CVEFixes labels this variant `safe`. The source is demonstrably non-constant-time in the respects above; whether that contradicts the label depends on what `safe` denotes, which is unresolved. The conclusion is conditional on the scalar being secret. | Timing finding documented; label meaning unresolved. |

## Why the model results were misleading

The GEPA predicate correctly identified a real, source-level timing dependence; it is not a false mechanism. The replicated model disagreement (Gemma 3/5 Pro-accepted vs. Gemini 0/5) is consistent with the benchmark label being misleading for this predicate, but that explanation is conditional on the scalar being secret and on what `safe` denotes, both unresolved; it is not established that the label is 'wrong'. The model outcomes are process evidence only; the source settles the result.

This is a **timing finding** (the predicate identifies a real, source-level non-constant-time operation, contingent on the scalar being secret), not a settled label mismatch: whether the `safe` oracle label is incorrect depends on what `safe` denotes, which is unresolved. It is not Axis E predicate invalidity and not Axis D evidence insufficiency. The `safe` label must not be treated as a correctness oracle for this seed without defining its meaning.

## Audit boundary

This result is limited to the exact seed-44 claim of a timing side-channel in `pointZZ_pMul`/`pointZZ_pShamirsTrick` via secret-dependent `mpz_tstbit` branching and data-dependent arithmetic. It does not assess other functions in the module, does not constitute a full vulnerability report or exploitability assessment, and does not establish remote exploitability or key recovery. It documents a timing finding independent of how the CVEFixes `safe` label should be interpreted, which is unresolved.
