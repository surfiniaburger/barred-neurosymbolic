# BARRED Track 1 — Seed 47 Evidence Audit (Qwen pilot)

## Question audited

**Claim:** "The code is vulnerable to a possible use-after-free in `__gfs2_get_acl` when the buffer returned by `gfs2_xattr_acl_get` is freed immediately after `posix_acl_from_xattr` is called."

**Result:** **Proved safe for this exact use-after-free claim.** `posix_acl_from_xattr` allocates and populates its own `struct posix_acl` from the input buffer; it does not retain a pointer into the caller's `data` buffer. Therefore `kfree(data)` after the call frees only the original xattr buffer, which is no longer referenced by the returned ACL. No use-after-free occurs.

## What was examined

1. Seed 47 is from the Qwen pilot manifest (10 seeds, 42–51); benchmark label `vulnerable`. The relevant code in the supplied `gfs2/acl.c` excerpt:
   ```c
   len = gfs2_xattr_acl_get(ip, name, &data);
   if (len <= 0) return ERR_PTR(len);
   acl = posix_acl_from_xattr(&init_user_ns, data, len);
   kfree(data);
   return acl;
   ```
2. I verified the callee contract against upstream Linux. `posix_acl_from_xattr` (current `fs/posix_acl.c`) parses `value`/`size` into a freshly allocated `struct posix_acl *` via `posix_acl_alloc`/`kmalloc`; the returned ACL owns its own `a_entries` array and never aliases the input buffer. On parse failure it releases the ACL via `posix_acl_release` and returns `ERR_PTR(-EINVAL)`. The input `data` is consumed by value, not retained.
3. Therefore `kfree(data)` frees the xattr buffer, which the ACL no longer references. No dangling pointer is created; the returned ACL remains valid.
4. The Qwen pilot adjudication ledger (RFC Axis E) already classified this as predicate invalidity; this audit confirms it independently.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `kfree(data)` after `posix_acl_from_xattr(..., data, len)`, allegedly freeing memory still referenced by `acl`. | Identified precisely. |
| Does `posix_acl_from_xattr` retain `data`? | No; it allocates its own `struct posix_acl` and copies entries. | No aliasing. |
| Is `data` freed while still referenced? | No; only the xattr buffer is freed. | No UAF. |
| Is a trigger demonstrated? | No; no sequence produces a dangling dereference. | Claim refuted. |

## Why the model results were misleading

The GEPA predicate noticed `kfree(data)` immediately after a conversion call and inferred a use-after-free, but it omitted the decisive fact that `posix_acl_from_xattr` allocates and populates its own ACL rather than aliasing the input buffer. The replicated model outcomes are not used as adjudication evidence.

This is **RFC Axis E: predicate invalidity**. The `kfree(data)` is correct and necessary (it frees the xattr buffer); there is no ownership transfer to the ACL.

## Audit boundary

This result is limited to the exact seed-47 claim of a use-after-free in `__gfs2_get_acl` via `kfree(data)` after `posix_acl_from_xattr`. It does not prove all of GFS2's ACL path safe, does not assess other entry points, and does not depend on the CVEFixes `vulnerable` label (which is wrong for this predicate).
