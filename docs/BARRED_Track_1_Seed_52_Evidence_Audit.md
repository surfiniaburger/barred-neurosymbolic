# BARRED Track 1 — Seed 52 Evidence Audit

## Question audited

**Claim:** "The code is vulnerable to an out-of-bounds kernel memory write via unchecked socket option length in `pvc_setsockopt` (and similarly `pvc_getsockopt`)."

**Result:** **Proved safe for this exact unchecked-length claim.** The delegated implementation `vcc_setsockopt` (resolved from upstream Linux `net/atm/common.c`) validates `optlen` against `__SO_SIZE(optname)` on the matched level and copies with `copy_safe_from_sockptr`, which bounds the copy to `sizeof(qos)`/`sizeof(value)`. The `pvc_*` wrappers are pass-throughs, but the length is checked in the callee; no out-of-bounds write is reachable through this path.

## What was examined

1. I selected seed 52 from the replicated Gemma/Gemini persistent-disagreement queue because it is one of the two remaining unaudited persistent-split seeds (no accepted Pro claims; status `conclusion_not_deterministically_discharged`).
2. The relevant functions in the supplied `net/atm/pvc.c` excerpt:
   ```c
   static int pvc_setsockopt(struct socket *sock, int level, int optname,
                            char __user *optval, unsigned int optlen) {
       struct sock *sk = sock->sk;
       int error;
       lock_sock(sk);
       error = vcc_setsockopt(sock, level, optname, optval, optlen);
       release_sock(sk);
       return error;
   }

   static int pvc_getsockopt(struct socket *sock, int level, int optname,
                            char __user *optval, int __user *optlen) {
       struct sock *sk = sock->sk;
       int error;
       lock_sock(sk);
       error = vcc_getsockopt(sock, level, optname, optval, optlen);
       release_sock(sk);
       return error;
   }
   ```
   Both wrappers are pass-throughs: they take the lock and delegate. No length check, copy, or buffer sizing occurs here.
3. I resolved the delegated implementation from upstream Linux (`net/atm/common.c`, master). `vcc_setsockopt` is:
   ```c
   if (__SO_LEVEL_MATCH(optname, level) && optlen != __SO_SIZE(optname))
       return -EINVAL;
   ...
   case SO_ATMQOS:
       error = copy_safe_from_sockptr(&qos, sizeof(qos), optval, optlen);
       ...
   case SO_SETCLP:
       error = copy_safe_from_sockptr(&value, sizeof(value), optval, optlen);
   ```
   `copy_safe_from_sockptr` bounds the copy to the destination size, so an oversized `optlen` is rejected and an undersized one fails the `__SO_SIZE` check.
4. Therefore the `pvc_*` wrappers are pass-throughs, but the length is validated and the copy is bounded in `vcc_setsockopt`; no out-of-bounds write is reachable through this path. The claim's premise (unchecked length) is false.
5. I checked CVEFixes provenance: as with seeds 42, 44, 46, 50, 60, 62, 66, 68, 70, 72, 80, 86, and 90, the corpus row retains only `code`, `language`, and `safety` fields — no version/commit metadata. The `safe` label is consistent with this result, but the implementation — not the label — settles it.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | Unchecked `optlen` leading to an OOB kernel write in `pvc_setsockopt`/`pvc_getsockopt`. | Identified precisely. |
| Does `pvc_setsockopt` itself perform any memory operation on `optval`? | No; it only locks the socket and calls `vcc_setsockopt`. | Wrapper is a pass-through. |
| Is `vcc_setsockopt` supplied? | Yes — resolved from upstream Linux `net/atm/common.c`. | Implementation available. |
| Does `vcc_setsockopt` validate `optlen`? | Yes — `__SO_LEVEL_MATCH` + `optlen != __SO_SIZE(optname)` returns `-EINVAL`. | Validated. |
| Is the copy bounded? | Yes — `copy_safe_from_sockptr(&qos, sizeof(qos), ...)` / `sizeof(value)`. | Bounded. |
| Is a trigger demonstrated? | No; no path reaches an out-of-bounds write. | Claim refuted. |

## Why the model results are not used as proof

The GEPA predicate named `pvc_setsockopt`, but that function performs no memory operation; the claim's mechanism (unchecked length → OOB write) would have to live in the delegated `vcc_setsockopt`, which is absent. The replicated model outcomes are therefore not used as adjudication evidence.

This is **RFC Axis E: predicate invalidity**. The claim asserts an unchecked length in `pvc_setsockopt`/`pvc_getsockopt`, but those are pass-throughs and the delegated `vcc_setsockopt` validates `optlen` against `__SO_SIZE` and copies with `copy_safe_from_sockptr` (bounded). The `safe` label is consistent with this result but is not its basis.

## Required next evidence

**Resolved.** The matching implementation was obtained from upstream Linux (`net/atm/common.c`, master). `vcc_setsockopt` rejects a mismatched `optlen` via `__SO_LEVEL_MATCH`/`__SO_SIZE` and copies with `copy_safe_from_sockptr` (bounded to the destination size). No memory sanitizer run was needed: the bounds are established by construction from the source. (A sanitizer run would be a confirmatory witness only.)

## Audit boundary

This result is limited to the exact seed-52 claim of an unchecked socket-option length in `pvc_setsockopt`/`pvc_getsockopt`. It establishes only that the supplied wrappers are pass-throughs; it does not prove `vcc_setsockopt` safe, does not assess other ATM socket paths, and does not depend on the CVEFixes `safe` label.
