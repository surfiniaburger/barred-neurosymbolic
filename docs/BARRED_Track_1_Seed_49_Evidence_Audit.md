# BARRED Track 1 — Seed 49 Evidence Audit (Qwen pilot)

## Question audited

**Claim:** "The code is vulnerable to an out-of-bounds write in `gdImageWBMPCtx` when processing images with extremely large dimensions (integer overflow in `createwbmp` allocation / `pos` index)."

**Result:** **Context deficient — unresolved.** The supplied seed contains `gdImageWBMPCtx`, which calls `createwbmp(gdImageSX(image), gdImageSY(image), WBMP_WHITE)` and then writes `wbmp->bitmap[pos]` with `pos` incremented per pixel, but the `createwbmp` implementation lives in `wbmp.c` (included via `wbmp.h`, not supplied). Whether `createwbmp`'s size arithmetic overflows, returns a `NULL`/undersized allocation, or validates dimensions cannot be determined from this seed. The Qwen pilot adjudication already classified this as Axis D.

## What was examined

1. Seed 49 is from the Qwen pilot manifest (10 seeds, 42–51); benchmark label `vulnerable`. The supplied code:
   ```c
   if ((wbmp = createwbmp(gdImageSX(image), gdImageSY(image), WBMP_WHITE)) == NULL) {
       gd_error("Could not create WBMP\n");
       return;
   }
   pos = 0;
   for (y = 0; y < gdImageSY(image); y++) {
       for (x = 0; x < gdImageSX(image); x++) {
           if (gdImageGetPixel(image, x, y) == fg) {
               wbmp->bitmap[pos] = WBMP_BLACK;
           }
           pos++;
       }
   }
   ```
   `pos` is a plain `int`; `wbmp->bitmap` is allocated inside `createwbmp`.
2. The `createwbmp` implementation is in `wbmp.c` (not included in this seed), so the allocation size, any overflow in `width * height`, and any dimension validation are outside the supplied code.
3. The `NULL` check on `createwbmp`'s return handles allocation failure, but does not establish that a non-NULL undersized allocation (from an overflowed size) is impossible. Conversely, the claim of an OOB write is not substantiated without `createwbmp`.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `wbmp->bitmap[pos]` write with `pos` up to `width*height`, allocated by `createwbmp`. | Identified precisely. |
| Is `createwbmp` supplied? | No; lives in `wbmp.c`, not in this seed. | Decisive code missing. |
| Does the NULL check suffice? | It handles NULL returns, but not an undersized non-NULL allocation from overflow. | Insufficient alone. |
| Is a trigger demonstrated? | No; no implementation, no sanitizer trace. | Not demonstrated. |

## Why the model results are not used as proof

The GEPA predicate asserts an OOB write, but the decisive allocation/size-arithmetic lives in `createwbmp`, which is not in this seed. The replicated model outcomes are not used as adjudication evidence.

This is **RFC Axis D: evidence insufficiency** (not Axis E predicate invalidity). The `createwbmp` implementation and its dimension/overflow handling are missing; neither the vulnerability nor its refutation can be established from this seed. The `vulnerable` label is a triage signal, not proof.

## Required next evidence

Obtain the matching `wbmp.c` (`createwbmp`) and inspect whether `width * height` (or the row-size computation) is checked for overflow before allocation, and whether a non-NULL undersized allocation is possible. Then run a harness with extremely large dimensions under a memory sanitizer. A crash or controlled write proves the claim; an explicit overflow check or allocation failure refutes it.
