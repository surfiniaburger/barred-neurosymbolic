# BARRED Track 1 — Seed 48 Evidence Audit

## Question audited

**Claim:** "The code is vulnerable to privilege escalation via writable sysctl entries in `llc2_timeout_table`."

**Result:** **Proved safe only for unprivileged writes.** Every entry in `llc2_timeout_table` is registered with `.mode = 0644` (owner read/write, group read, others read). This table is registered on `init_net`. Linux grants the owner-mode bits to any task for which `CAP_NET_ADMIN` is effective in `init_net`'s owning user namespace, so such a task can write these entries. A task that is neither the sysctl owner nor capable with `CAP_NET_ADMIN` in that user namespace has no write access. No write path exists for the audit's unprivileged attacker model; the table does contain a privileged write path.

## What was examined

1. Seed 48 is from the 50-seed manifest (oracle `safe`), `conclusion_not_deterministically_discharged` group.
2. The relevant table in `net/llc/sysctl_net_llc.c`:
   ```c
   static struct ctl_table llc2_timeout_table[] = {
       { .procname = "ack",  .data = &sysctl_llc2_ack_timeout,  .maxlen = sizeof(...), .mode = 0644, .proc_handler = proc_dointvec_jiffies },
       { .procname = "busy", ... .mode = 0644, ... },
       { .procname = "p",    ... .mode = 0644, ... },
       { .procname = "rej",  ... .mode = 0644, ... },
       { },
   };
   ```
   All four timeout entries use mode `0644`. The station table is empty.
3. In the Linux sysctl framework, mode `0644` means owner (root) has read+write, group and others have read-only. Unprivileged users cannot write to these entries.
4. The GEPA predicate assumed the entries were writable, but the mode field explicitly restricts writes to root.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | Unprivileged write to `llc2_timeout_table` sysctl entries. | Identified precisely. |
| What is the file mode? | `0644` on every entry. | Root-writable only. |
| Can an unprivileged user write? | No. | No privilege escalation. |
| Is a write by the specified unprivileged attacker possible? | No. `0644` denies write access without `CAP_NET_ADMIN` in the network namespace's owning user namespace. | Claim refuted. |

## Why the model results were misleading

The GEPA predicate assumed the sysctl entries were world-writable, but the mode field (`0644`) restricts writes to root. The replicated model outcomes are not used as adjudication evidence.

This is **RFC Axis E: predicate invalidity**. The mode field makes the claimed privilege escalation impossible.

## Audit boundary

Limited to the exact seed-48 claim of privilege escalation via writable sysctl entries in `llc2_timeout_table`. Does not prove all of the LLC subsystem safe, does not assess other sysctl tables, and does not depend on the CVEFixes `safe` label.
