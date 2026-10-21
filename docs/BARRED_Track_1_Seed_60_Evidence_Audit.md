# BARRED Track 1 — Seed 60 Evidence Audit

## Question audited

**Claim:** “The code is vulnerable to an unchecked/invalid-pointer dereference in `gss_get_mic` when `context_handle` is not a valid `gss_union_ctx_id_t` object.”

**Result:** **Mechanism reproduced in harness; reachability still open.** The unchecked dereference is present and real, and a harness (`/tmp/harness60/harness.c`) reproduced a crash for a crafted handle whose `internal_ctx_id != GSS_C_NO_CONTEXT` and whose `mech_type` points to unmapped memory. This demonstrates the dereference path in the harness, but does not establish upstream lookup behavior or reachability from a real GSSAPI caller. What remains open is attacker reachability — whether any real caller passes attacker-influenced data as a `gss_ctx_id_t` — which is a threat-model question no source fetch settles.

## What was examined

1. I selected seed 60 from the replicated Gemma/Gemini persistent-disagreement queue because the allegation is a concrete ownership/validation claim: an opaque handle is cast and dereferenced without verifying it references a bona fide `gss_union_ctx_id_t`.
2. The relevant functions are `val_get_mic_args` and `gss_get_mic` in the supplied Sun Microsystems GSSAPI glue (`g_sign.c`, 1998):
   ```c
   static OM_uint32 val_get_mic_args(..., gss_ctx_id_t context_handle, ...) {
       ...
       if (context_handle == GSS_C_NO_CONTEXT)
           return (GSS_S_CALL_INACCESSIBLE_READ | GSS_S_NO_CONTEXT);
       ...
       return (GSS_S_COMPLETE);
   }

   OM_uint32 gss_get_mic(...) {
       ...
       status = val_get_mic_args(minor_status, context_handle, ...);
       if (status != GSS_S_COMPLETE) return (status);

       ctx = (gss_union_ctx_id_t) context_handle;
       if (ctx->internal_ctx_id == GSS_C_NO_CONTEXT)
           return (GSS_S_NO_CONTEXT);
       mech = gssint_get_mechanism(ctx->mech_type);
       ...
   }
   ```
   The only guard before the dereference is a NULL/`GSS_C_NO_CONTEXT` check. There is no type tag, magic number, or handle-registry lookup verifying that `context_handle` points to a live `gss_union_ctx_id_t`.
3. The dereference precedes any mechanism lookup: `ctx->internal_ctx_id` and `ctx->mech_type` are read before `gssint_get_mechanism(ctx->mech_type)` is called, so no downstream validation can prevent the bad read.
4. The Python/Python-binding surface is not relevant here (this is C GSSAPI glue), but the caller contract is: GSSAPI treats `gss_ctx_id_t` as an opaque handle issued by `gss_init_sec_context`/`gss_accept_sec_context`. Whether an attacker can supply a crafted non-NULL value depends on whether any caller passes untrusted data as a handle, which the seed does not establish.
5. I checked the CVEFixes provenance. The supplied topic matches CVEFixes row 26502 exactly (SHA-256 `48a057e29ec4311cf8914766b33ab1aa77fb5aa1e389197644809bb7ff9649d8`, 3699 bytes, language `c`, safety `safe`). As with seeds 42, 44, 46, 50, and 68, the CSV retains only `code`, `language`, and `safety` — no version/commit metadata. The `safe` label reflects the normal trusted-caller model and is not, by itself, proof that the handle cannot be attacker-controlled.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | Cast of unvalidated `context_handle` to `gss_union_ctx_id_t` followed by `ctx->internal_ctx_id`/`ctx->mech_type` reads. | Identified precisely. |
| Is there a handle-validation guard? | No; only `context_handle == GSS_C_NO_CONTEXT` (NULL) is checked. | Guard absent. |
| Does the dereference precede downstream validation? | Yes; `ctx->internal_ctx_id` and `ctx->mech_type` are read before `gssint_get_mechanism`. | Unchecked deref confirmed. |
| Can an attacker supply a crafted handle? | Not established by the seed; depends on whether any caller passes untrusted data as a `gss_ctx_id_t` and on the surrounding mechglue. | Unresolved. |
| Does the mechglue provide a handle registry? | Not in the supplied snippet. | Unknown. |
| Is a trigger demonstrated? | Yes (mechanism, in-harness): harness reproduced a crash for a crafted handle (internal_ctx_id != 0, garbage mech_type). This demonstrates the dereference path in the harness; it does not establish upstream lookup behavior or reachability from a real GSSAPI caller. | Mechanism demonstrated in harness; reachability open. |

## Why the model results are not used as proof

The GEPA predicate correctly noticed the missing validation and the unchecked dereference, but the supplied snippet does not establish who controls `context_handle`, whether the mechglue validates handles elsewhere, or a reachable crafted handle. The replicated model outcomes are therefore not used as adjudication evidence.

This is **RFC Axis D: evidence insufficiency** (not Axis E predicate invalidity). The unchecked dereference is visible and real; what is missing is the caller/attacker model, the handle-registry contract, and a witness that reaches the alleged bad operation. The `safe` label is consistent with the normal trusted-caller model but does not prove the handle is unforgeable.

## Required next evidence

**Partially resolved — mechanism now confirmed by runtime trace, reachability still open.**

A minimal C harness was written (`/tmp/harness60/harness.c`) that defines `gss_union_ctx_id_t` from the upstream mechglue layout, implements `val_get_mic_args` and `gss_get_mic` verbatim from the seed, and supplies a stub `gssint_get_mechanism` that dereferences its `mech_type` argument (mirroring the real mechglue lookup). It calls `gss_get_mic` with a crafted handle whose `internal_ctx_id != GSS_C_NO_CONTEXT` (so it passes the NULL check) and whose `mech_type` points to unmapped memory. By construction this dereferences `ctx->internal_ctx_id` (passes) then dereferences the garbage `mech_type` in `gssint_get_mechanism` (crash).

**Runtime trace (2026-10-18).** The harness `/tmp/harness60/harness.c` was compiled with clang after the Xcode license was accepted and executed: `./harness` printed `RESULT: crash (SIGSEGV/SIGBUS) on crafted handle -> dereference reachable`. The harness reproduced a crash for a crafted handle with `internal_ctx_id != GSS_C_NO_CONTEXT` and a garbage `mech_type`. This demonstrates the dereference path in the harness, but does not establish upstream lookup behavior or reachability from a real GSSAPI caller.

What remains is the threat-model gap (reachability): whether any real caller passes attacker-influenced data as a `gss_ctx_id_t`. The 1998 Sun glue and the GSSAPI calling convention are what matter; a modern mechglue fetch does not settle the caller model. A documented trusted-caller-only contract, or a harness running in a real GSSAPI caller path with a crafted handle, would settle reachability. Until reachability is established this stays Axis D on security relevance, even though the mechanism is confirmed.

## Audit boundary

This result is limited to the exact seed-60 claim of an arbitrary-pointer dereference in `gss_get_mic` from an unvalidated `context_handle`. It does not prove all of the GSSAPI glue safe, does not assess other entry points (`gss_verify_mic`, `gss_wrap`, etc.), and does not depend on the CVEFixes `safe` label. The missing validation is a real code characteristic; its security status depends on the caller model, which the seed does not supply.