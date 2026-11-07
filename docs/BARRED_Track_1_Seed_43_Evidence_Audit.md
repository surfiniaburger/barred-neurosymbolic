# BARRED Track 1 — Seed 43 Evidence Audit

## Question audited

**Claim:** "The code is vulnerable to a NULL-pointer dereference in `gf128mul_4k_lle` when `ghash_update` (or `ghash_final`) is invoked before a successful `ghash_setkey` has populated `ctx->gf128`."

**Result:** **Confirmed vulnerable for this exact claim.** `ghash_setkey` populates `ctx->gf128` via `gf128mul_init_4k_lle` (and frees a prior value if present), but `ghash_update` and `ghash_flush`/`ghash_final` call `gf128mul_4k_lle((be128 *)dst, ctx->gf128)` with no NULL guard on `ctx->gf128`. If update/final is invoked on a `shash_desc` whose transform was allocated but never keyed, `ctx->gf128` is NULL and the call dereferences it. The benchmark `vulnerable` label agrees.

## What was examined

1. Seed 43 is from the 50-seed manifest (oracle `vulnerable`), `conclusion_not_deterministically_discharged` group.
2. `ghash_setkey`:
   ```c
   if (ctx->gf128)
       gf128mul_free_4k(ctx->gf128);
   ctx->gf128 = gf128mul_init_4k_lle((be128 *)key);
   if (!ctx->gf128)
       return -ENOMEM;
   ```
3. `ghash_update`: calls `gf128mul_4k_lle((be128 *)dst, ctx->gf128)` in three places (flush of partial block, full-block loop, tail) with no `if (ctx->gf128)` guard.
4. `ghash_flush`/`ghash_final` likewise call `gf128mul_4k_lle` unconditionally when `dctx->bytes` is nonzero.
5. The crypto shash framework does not enforce that `setkey` precedes `update` at this layer; the guard is the implementation's responsibility and is absent.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `gf128mul_4k_lle((be128 *)dst, ctx->gf128)` with `ctx->gf128 == NULL`. | Identified precisely. |
| Is there a NULL guard before the call? | No (in update/flush/final). | Guard absent. |
| Can update/final be reached with unkeyed ctx? | Yes — `crypto_alloc_shash` + `shash_desc` without `setkey`. | Reachable via caller misuse. |
| Is a trigger demonstrated? | Yes — invoke `ghash_update` on an unkeyed transform. | Claim substantiated. |

## Why the model results

The GEPA predicate is sound: the missing NULL guard is real and the dereference follows. The benchmark `vulnerable` label agrees.

This is a **confirmed vulnerable** verdict (mechanism sound; benchmark label agrees).

## Audit boundary

Limited to the exact seed-43 claim. Does not prove all of the crypto ghash safe, does not assess whether callers in practice always setkey first, and does not depend on the CVEFixes `vulnerable` label (which agrees here).
