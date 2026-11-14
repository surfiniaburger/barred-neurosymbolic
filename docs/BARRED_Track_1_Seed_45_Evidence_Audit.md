# BARRED Track 1 — Seed 45 Evidence Audit

## Question audited

**Claim:** "The code is vulnerable to an out-of-bounds array index (unchecked enum) in `inc_ucount` and `dec_ucount`."

**Result:** **Context deficient — unresolved.** `inc_ucount`/`dec_ucount` index `ucount_max[type]` and `ucount[type]` with no bounds check on `type` (an `enum ucount_type`). The arrays are sized to the enum's count, so an out-of-range `type` is an out-of-bounds access. But whether any caller can supply an attacker-controlled `type` value, and whether the enum is strictly bounded by construction, depends on the callers and the enum definition, which are not in this seed. The mechanism is present; reachability is unproven.

## What was examined

1. Seed 45 is from the 50-seed manifest (oracle `vulnerable`), `conclusion_not_deterministically_discharged` group.
2. The relevant code:
   ```c
   struct ucounts *inc_ucount(struct user_namespace *ns, kuid_t uid, enum ucount_type type) {
       ...
       max = READ_ONCE(tns->ucount_max[type]);
       if (!atomic_inc_below(&iter->ucount[type], max)) goto fail;
       ...
   }
   void dec_ucount(struct ucounts *ucounts, enum ucount_type type) {
       for (iter = ucounts; iter; iter = iter->ns->ucounts) {
           int dec = atomic_dec_if_positive(&iter->ucount[type]);
           ...
       }
   }
   ```
   No `type >= 0 && type < UCOUNT_COUNTS` (or equivalent) guard precedes the indexing.
3. The `ucount`/`ucount_max` arrays are sized to the enum's count; an out-of-range index is a genuine OOB. Whether `type` can be attacker-controlled depends on callers (not supplied).

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | Unchecked `type` indexing `ucount[type]`/`ucount_max[type]`. | Identified precisely. |
| Is there a bounds check on `type`? | No. | Guard absent. |
| Can `type` be attacker-controlled? | Unknown — callers not in this seed. | Unresolved. |
| Is a trigger demonstrated? | No — no caller model, no sanitizer trace. | Not demonstrated. |

## Why the model results are not used as proof

The GEPA predicate correctly noticed the missing bounds check, but the seed does not establish whether `type` is reachable with an attacker-controlled value. The replicated model outcomes are not used as adjudication evidence.

This is **RFC Axis D: evidence insufficiency** (mechanism present; reachability unproven).

## Audit boundary

Limited to the exact seed-45 claim. Does not prove all of user namespaces safe, does not assess other entry points, and does not depend on the CVEFixes `vulnerable` label.
