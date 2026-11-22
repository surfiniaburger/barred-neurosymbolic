# BARRED Track 1 — Seed 50 Evidence Audit

## Question audited

**Claim:** “The code is vulnerable to an out-of-bounds read in `uri_decoded_copy` when parsing percent-encoded data.”

**Result:** **Proved safe for this exact out-of-bounds-read claim.**

This result concerns the stated boundary cases—an isolated trailing `%` and a trailing `%` followed by one hexadecimal digit—in the supplied `uri_decoded_copy` implementation. It does not make claims about unrelated parser behavior, other versions, or bugs elsewhere in librsvg/GLib.

## What was examined

1. I selected seed 50 because it is a self-contained parsing claim with two concrete proposed trigger strings: `data:,abc%` and `data:,abc%F`.
2. I traced the source to local CVEFixes row 6,187. It is C code labelled `safe` and exactly matches the benchmark topic (SHA-256 `cbfe54dfd25c3bbbd0646bc6032284724e0bbe623414f9ecaf63320bd75ab8e8`). As with seed 42, the CSV retains no project revision or commit metadata.
3. I traced both callers of `uri_decoded_copy` in the supplied source:
   - MIME-type input uses `start, end - start`, where `end` is derived from `strchr(start, ',')`.
   - payload input uses `start, strlen(start)`.

   In both cases, the passed range lies within a NUL-terminated URI string.
4. I checked the allocation contract. `g_strndup(part, length)` returns a newly allocated buffer of `length + 1` bytes that is always NUL-terminated. The GLib documentation records this contract explicitly: [GLib `g_strndup`](https://docs.gtk.org/glib/func.strndup.html).
5. I performed the exact C control-flow trace for the claimed boundary inputs below.
6. I checked whether a local AddressSanitizer confirmation could be compiled. GLib 2.86.2 is available, but the local compiler exits because the Xcode license has not been accepted. I did not change that user-level system state. This does not weaken the source-level proof below; a sanitizer test would be a confirmatory witness, not its foundation.

## Boundary trace

Let `n = length`. After `g_strndup(part, n)`, the buffer has readable indices `0` through `n`; index `n` holds `\0`.

| Input suffix | State at `%` | Evaluation | Result |
|---|---|---|---|
| `%` at the last input byte | `s[0] = '%'`, `s[1] = '\0'` | `!g_ascii_isxdigit(s[1])` is true. C `||` short-circuits, so `s[2]` is **not evaluated**. | No read beyond index `n`; `%` is copied literally. |
| `%F` at the last two input bytes | `s[0] = '%'`, `s[1] = 'F'`, `s[2] = '\0'` | First operand is false; second reads `s[2]`, which is the allocated NUL byte at index `n`, and is true. | No read beyond index `n`; `%F` is copied literally. |
| `%HH` with two hexadecimal digits | `s[1]` and `s[2]` are both input bytes before the NUL terminator. | Both checks are in bounds; `HEXCHAR(s)` reads the same two in-bounds bytes. | The escape is decoded. |

The `continue` path does not skip loop termination. It enters the `do ... while (*s++)` condition, reads the current `%`, advances to the next byte, then processes and copies the NUL terminator on the following iteration. The final increment creates a one-past pointer only after reading that NUL; it does not dereference the one-past pointer.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `s[1]` or `s[2]` after a trailing percent sign. | Identified precisely. |
| Does the buffer have a readable terminator? | `g_strndup` allocates `length + 1` and NUL-terminates it. | Yes. |
| Can `s[2]` be evaluated for an isolated `%`? | No: first `||` operand is true at `s[1] == '\0'`. | The alleged OOB read cannot occur. |
| Can `s[2]` be evaluated for `%F`? | Yes, but it equals the allocated NUL at index `n`. | The read remains in bounds. |
| Is a trigger demonstrated? | No; both proposed trigger families are disproved by the allocation and control-flow contracts. | Predicate refuted. |

## Why the model results were misleading

The GEPA predicate noticed literal index expressions and inferred an out-of-bounds read, but it omitted two decisive facts: the `g_strndup` NUL-terminator guarantee and C short-circuit evaluation. The replicated model outcomes are therefore not used as adjudication evidence.

This is **RFC Axis E: predicate invalidity**. The code has no explicit `length - offset` check because it transforms a NUL-terminated private copy, and the proposed bad read is blocked by the existing allocation/control-flow invariants.

## Audit boundary

This result is limited to the exact seed-50 claim of an out-of-bounds read from malformed percent encoding. It does not prove all URI parsing behavior safe, and it does not depend on the CVEFixes `safe` label.
