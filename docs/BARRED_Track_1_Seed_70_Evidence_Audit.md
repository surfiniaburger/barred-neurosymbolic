# BARRED Track 1 — Seed 70 Evidence Audit

## Question audited

**Claim:** “The code is vulnerable to integer-overflow-induced heap buffer overflow in the `grow_gap` function (called from `decode_entities`) when the expression `e_offset + grow + 1` wraps around size_t.”

**Result:** **Context deficient — unresolved.** The unchecked size expression is present, but the supplied snippet does not establish the relevant Perl scalar-size limits, the `SvGROW` overflow behavior, or a reachable replacement length. The claim therefore cannot be proved or refuted from the seed alone.

## What was examined

1. I selected seed 70 because the allegation is precise and arithmetic: `SvGROW(sv, e_offset + grow + 1)` in `grow_gap`.
2. The supplied source is Perl (HTML::Entities-style `decode_entities`). The relevant code:
   ```c
   STRLEN t_offset = *t - SvPVX(sv);
   STRLEN s_offset = *s - SvPVX(sv);
   STRLEN e_offset = *e - SvPVX(sv);
   SvGROW(sv, e_offset + grow + 1);
   ```
   where `grow = repl_len - (s - t)`, and the only guard before the call is:
   ```c
   if (t + repl_len > s) { grow_gap(...); }
   ```
3. The expression `e_offset + grow + 1` has no explicit overflow check in this function. The supplied file does not define `STRLEN` or `SvGROW`, so it does not establish the applicable integer-width, maximum-scalar-size, or allocation-failure contracts.
4. The guard `t + repl_len > s` is not a demonstrated bound on `repl_len`. For an out-of-range `repl_len`, forming `t + repl_len` itself is not valid portable C pointer arithmetic; it must not be described as wrapping and cannot serve as an overflow proof either way.
5. In the shown path, `repl_len` comes from the value returned by `hv_fetch(entity2char, ...)` through `SvPV(*svp, repl_len)` (or from `bytes_to_utf8` for a single replacement). `entity2char` is a function parameter, but the supplied snippet alone does not establish that an untrusted attacker can supply or populate it, nor does it show its maximum value length.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `e_offset + grow + 1` in `SvGROW`, with `grow = repl_len - (s - t)`. | Identified precisely. |
| Is there an overflow guard in `grow_gap`? | No explicit arithmetic check appears in this function; `SvGROW` is not defined in the supplied source. | Local guard absent; callee contract unknown. |
| Is the guard `t + repl_len > s` sufficient? | No demonstrated numeric bound follows from it; out-of-range pointer arithmetic is not portable C. | Cannot establish safety or reachability. |
| What is the maximum possible `repl_len`? | Not in the supplied snippet; it is obtained from a hash value, but the scalar and API limits are absent. | Unresolved. |
| Is a trigger demonstrated? | No; no matching runtime, scalar limit, controlled hash construction, or sanitizer trace is supplied. | Not demonstrated. |

## Why the model results are not used as proof

The GEPA predicate correctly noticed an unchecked expression, but the supplied snippet does not show whether a replacement length sufficient to overflow it is reachable, whether the caller controls the entity table, or whether the matching `SvGROW` implementation rejects an impossible allocation. The replicated model outcomes are therefore not used as adjudication evidence.

This is **RFC Axis D: evidence insufficiency** (not Axis E predicate invalidity). The unchecked arithmetic is visible; what is missing is the matching Perl runtime contract, the entity-table ownership and bound, and a witness that reaches the alleged bad operation.

## Required next evidence

**Partially resolved.** The upstream implementation was located (`HTML::Parser` `util.c`, `grow_gap`) and matches the seed byte-for-byte; `perlguts` documents `SvGROW` as "can only increase, does not add a trailing NUL" but does not promise overflow protection. The remaining gaps are: (a) whether `entity2char` is attacker-controllable (in `HTML::Entities` it is a fixed module table, but `decode_entities` accepts any HV), (b) the `STRLEN` width / max-scalar size on the target Perl build, and (c) whether `safemalloc` rejects a wrapped size. A harness (`/tmp/harness70.c`) was compiled and run against Perl 5.44. It called `SvGROW(sv, (STRLEN)-1)` (a max-size request simulating the overflowed value). Result: SvGROW did **not** return normally - the process exited (code 9) without printing the post-SvGROW line, i.e. `safemalloc`/`sv_grow` refused the oversized allocation rather than silently wrapping to a small buffer. This rules out the "SvGROW wraps to a small allocation" failure mode for huge sizes.

However, the harness also shows the residual risk: SvGROW has no way to know that a *small* requested size is the result of an overflow. If the arithmetic wraps to a small value, `SvGROW(sv, small)` allocates `small` bytes successfully, and the subsequent `Move(*s, *s+grow, *e - *s, char)` in `grow_gap` copies the full (large) span into the undersized buffer - the OOB write. SvGROW therefore does **not** protect against this; the protection must come from a bound on `repl_len` (and hence `grow`).

The remaining gaps are: (a) whether `entity2char` is attacker-controllable (in `HTML::Entities` it is a fixed module table, but `decode_entities` accepts any HV), and (b) the max representable replacement length on the target Perl build. A large-replacement harness (caller-supplied HV with a huge replacement string) under a memory sanitizer would settle reachability. Until then this stays Axis D.

## Audit boundary

This result is limited to the exact seed-70 claim of a size_t wraparound in `grow_gap`. It does not prove all of `decode_entities` safe, and it does not depend on the CVEFixes `safe` label.
