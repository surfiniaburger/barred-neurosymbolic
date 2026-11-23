# BARRED Track 1 — Seed 51 Evidence Audit (Qwen pilot)

## Question audited

**Claim:** "The code is vulnerable to a symbolic-link (TOCTOU) race that allows arbitrary file overwrite in `rename(tmpname, PASSWD_FILE)`."

**Result:** **Proved safe for this exact symlink-overwrite claim.** POSIX `rename(2)` replaces the directory entry at the destination path; it does **not** dereference a symlink at the destination. A symlink placed at `PASSWD_FILE` is replaced (removed) by the rename, not followed, so its target cannot be overwritten by this call. The destination is also the fixed path `PASSWD_FILE`, not an attacker-selected path.

## What was examined

1. Seed 51 is from the Qwen pilot manifest (10 seeds, 42–51); benchmark label `vulnerable`. The relevant code: creates `tmpname` under `/etc`, then calls `rename(tmpname, PASSWD_FILE)`.
2. I verified against the POSIX `rename()` specification: `rename()` replaces the directory entry at the destination pathname. If the destination is a symbolic link, the link itself is replaced; the link is not dereferenced and its target is not modified. This is distinct from `open()` with `O_NOFOLLOW` semantics and from `renameat2` with flags.
3. The destination `PASSWD_FILE` is a fixed, compile-time path, not attacker-selected, so an attacker cannot redirect the rename to an arbitrary location. The only attacker influence would be placing a symlink at that fixed path, which (per point 2) is replaced rather than followed.
4. The Qwen pilot adjudication ledger (RFC Axis E) already classified this as predicate invalidity; this audit confirms it independently.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `rename(tmpname, PASSWD_FILE)` allegedly follows a symlink at `PASSWD_FILE` and overwrites its target. | Identified precisely. |
| Does POSIX `rename()` dereference a destination symlink? | No; it replaces the directory entry (the link itself). | No follow. |
| Is the destination attacker-selected? | No; `PASSWD_FILE` is a fixed path. | No arbitrary target. |
| Is a trigger demonstrated? | No; no sequence causes an overwrite of a symlink target. | Claim refuted. |

## Why the model results were misleading

The GEPA predicate assumed `rename()` dereferences symlinks like `open()`, but POSIX `rename()` replaces the destination entry without dereferencing. The replicated model outcomes are not used as adjudication evidence.

This is **RFC Axis E: predicate invalidity**. The claimed symlink-target-overwrite mechanism is impossible under POSIX `rename()` semantics.

## Audit boundary

This result is limited to the exact seed-51 claim of a symlink-target overwrite via `rename(tmpname, PASSWD_FILE)`. It does not prove the program has no other file-handling flaw, does not assess `renameat`/`renameat2` variants with flags, and does not depend on the CVEFixes `vulnerable` label (which is wrong for this predicate).
