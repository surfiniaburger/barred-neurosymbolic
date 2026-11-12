# BARRED Track 1 — Seed 44 Evidence Audit

## Question audited

**Claim:** “The code is vulnerable to timing side-channel attacks in the `pointZZ_pMul` function (scalar multiplication) because it uses a secret-dependent branch (if-else on `mpz_tstbit`) that causes data-dependent execution paths.”

**Result:** **Confirmed vulnerable for this exact timing side-channel claim.** The supplied `pointZZ_pMul` (and `pointZZ_pShamirsTrick`) branch on secret scalar bits and execute different, data-dependent sequences of point additions and doublings. Unlike seeds 42, 46, 50, 66, and 68, the supplied source does contain the unchecked, secret-dependent operation the predicate describes; the benchmark `safe` label is wrong for this predicate (label mismatch).

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
   Hence the scalar's bit pattern leaks through multiple independent timing channels, not just the top-level branch.
5. Provenance: the supplied topic matches CVEFixes row 26613 exactly (SHA-256 `87aa43444950b40e263623745ce084a4be8bcbbaea96e2f8477744fc0800721d`, 8971 bytes, language `c`, safety `safe`). A second, shorter variant (row 18019, 7580 bytes) is labelled `vulnerable` in the same corpus. As with seeds 42, 46, 50, and 68, the CSV retains only `code`, `language`, and `safety` — no version/commit metadata. The CSV label `safe` disagrees with the demonstrable, source-level timing dependence; the label is a triage signal, not proof.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `if (mpz_tstbit(scalar, i)) { ... } else { ... }` in `pointZZ_pMul`, plus `mpz_tstbit`-driven branching in `pointZZ_pShamirsTrick`. | Identified precisely. |
| Is the branch secret-dependent? | Yes; `scalar` is the private scalar passed by the caller (Python binding `curvemath.mul` takes `d` as a decimal string and converts via `mpz_init_set_str`). | Secret-dependent. |
| Does execution time vary with the secret? | Yes; branch bodies differ in operand roles, and callees (`pointZZ_pAdd`, `pointZZ_pDouble`, `mpz_invert`) have data-dependent early returns and non-constant-time arithmetic. | Timing varies. |
| Is the scalar required to be secret? | For a curve-multiplication routine used in ECC, the scalar is the private key; constant-time is a standard requirement. The function exposes no constant-time alternative. | Applicable threat model. |
| Is a trigger demonstrated? | Reachability shown by construction: any non-trivial secret scalar exercises both branches; timing correlation follows from the data-dependent code paths. No runtime trace required. | Claim substantiated. |
| Benchmark label | CVEFixes labels this variant `safe`, but the source is demonstrably non-constant-time. | Label mismatch (benchmark wrong). |

## Why the model results were misleading

The GEPA predicate correctly identified a real, source-level timing dependence; it is not a false mechanism. The replicated model disagreement (Gemma 3/5 Pro-accepted vs. Gemini 0/5) is best explained by the benchmark label being wrong for this predicate rather than by either model failing: Gemma's Pro acceptances track the genuine non-constant-time code, while Gemini's rejections track the (incorrect) `safe` label. The model outcomes are process evidence only; the source settles the result.

This is a **label mismatch** (the predicate is sound and the code is vulnerable; the `safe` oracle label is incorrect), not Axis E predicate invalidity and not Axis D evidence insufficiency. The `safe` label must not be used as a correctness oracle for this seed.

## Audit boundary

This result is limited to the exact seed-44 claim of a timing side-channel in `pointZZ_pMul`/`pointZZ_pShamirsTrick` via secret-dependent `mpz_tstbit` branching and data-dependent arithmetic. It does not assess other functions in the module, does not constitute a full vulnerability report or exploitability assessment, and does not establish remote exploitability or key recovery. It does not depend on the CVEFixes `safe` label, which is incorrect for this predicate.