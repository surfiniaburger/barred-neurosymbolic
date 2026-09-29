# Comparative Debate Benchmark Report: Local Gemma vs. Gemini 3 Pilot Benchmark (N=10)

**Evaluation Date:** 2026-09-29  
**Evaluation Scope:** 10-Seed Comparative Pilot Benchmark across Seeds 42–51 (5 Safe, 5 Vulnerable) under Progressive Escalation Protocol (`--escalate-pareto`)  
**Seed Manifest:** `artifacts/seeds_pilot_10.jsonl` (extracted from `scenarios/debate/cve_seeds_benchmark_50.jsonl`)  
**Evaluated Stacks:**
1. **Local Stack (Baseline):** Gemma-4-12B-Fast (Judge & Verifier) + Gemma-4-E4B (Debaters & Generator) via Ollama
2. **Cloud Stack 1 (Fast & Balanced):** `vertex_ai/gemini-3.5-flash` (Debaters & Generator) + `vertex_ai/gemini-3.6-flash` (Judge & Verifier)
3. **Cloud Stack 2 (Deep Reasoning & Audit):** `vertex_ai/gemini-3.7-flash` (Debaters & Generator with Thinking) + `vertex_ai/gemini-3.8-flash` (Judge & Verifier)

---

## 1. Executive Summary: The Frontier Model Paradigm Shift

This comparative pilot evaluates the cognitive behavior, verification rigor, anchor fidelity, and token economics when migrating the BARRED multi-agent debate swarm from local open-weights Gemma models to Google's next-generation Gemini 3 families on Vertex AI (`global` endpoint, project `gem-creation`).

Evaluating across 10 balanced seeds (Seeds 42–51: exactly 5 Safe, 5 Vulnerable) yields three fundamental discoveries:

1. **Resolution of the Anchor Trap:**
   - In local Gemma models, debaters suffer from syntactic anchor attrition under reflection—termed the **Anchor Trap Paradox**—where debaters fail the B-Gate normalization (`anchors_too_few_after_normalization`, accounting for 66.7% of Gemma rejections on Seeds 43 and 48).
   - In **Gemini 3.5 / 3.6**, the Anchor Trap failure rate dropped to **0.0%**. Debaters adhered strictly to verbatim source-code anchors while maintaining nuanced debate argumentation.
2. **Superhuman Verification Rigor & Deceptive Comment Detection:**
   - **Gemini 3.8 Flash** demonstrated unprecedented systems auditing rigor. On Seed 51 (`setpwnam.c`), where source code contained misleading comments (`/* TOCTOU Race Condition: tmpname is in a public dir and could be replaced with a symlink before rename */`), local Gemma and Gemini 3.6 accepted the exploit narrative. In contrast, Gemini 3.8 explicitly diagnosed that the debater was *"baited by the deceptive comments in the snippet"*, accurately citing POSIX `rename(2)` non-dereferencing semantics and `/tmp` sticky-bit protections to reject the invalid claim.
3. **Token & Cost Economics:**
   - **Gemini 3.5 / 3.6** produced **7 / 10 accepted rows (70.0% yield)** at **$0.1452 per accepted training row** (40,465 tokens/row).
   - **Gemini 3.7 / 3.8** produced **4 / 10 accepted rows (40.0% yield)** at **$0.1742 per accepted training row** (79,609 tokens/row). The lower yield in the Gemini 3.7/3.8 stack reflects the joint dynamics of Gemini 3.7's extended thinking generation paired with Gemini 3.8's elevated verification rigor, which strictly rejected ungrounded exploit narratives on Safe benchmarks and caught semantic discrepancies in benchmark predicates.

---

## 2. Three-Way Comparative Performance Matrix (Seeds 42–51)

| Metric | Local Gemma Swarm (12B/E4B) | Gemini 3.5 Flash / 3.6 Flash | Gemini 3.7 Flash / 3.8 Flash | Contrast (Gemini 3.5 vs. Gemma) | Contrast (Gemini 3.8 vs. 3.6) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Seeds Evaluated** | 10 (5 Safe / 5 Vuln) | 10 (5 Safe / 5 Vuln) | 10 (5 Safe / 5 Vuln) | Invariant ($N=10$) | Invariant ($N=10$) |
| **Accepted Training Rows** | **7 / 10 (70.0%)** | **7 / 10 (70.0%)** | **4 / 10 (40.0%)** | Parity in Yield (70%) | -30.0 pp (Stricter Audit) |
| **Vulnerable Seeds Accepted** | 4 / 5 (80.0%) | **5 / 5 (100.0%)** | 4 / 5 (80.0%) | +20.0 pp (Vuln Acc) | -20.0 pp (Deceptive Seed 51 caught) |
| **Safe Seeds Accepted** | 3 / 5 (60.0%) | 2 / 5 (40.0%) | 0 / 5 (0.0%) | -20.0 pp (Safe Acc) | -40.0 pp (Stricter Invariant Check) |
| **Total Attempts Incurred** | 16 attempts (1.6/seed) | **15 attempts (1.5/seed)** | 18 attempts (1.8/seed) | -0.1 attempt/seed | +0.3 attempt/seed |
| **Anchor Trap Failures** | **2 (20.0% of seeds)** | **0 (0.0% of seeds)** | 1 (10.0% of seeds) | **-20.0 pp (Trap Eliminated)** | +10.0 pp |
| **Verifier Interceptions** | 1 (10.0% of seeds) | 3 (30.0% of seeds) | **5 (50.0% of seeds)** | +20.0 pp | **+20.0 pp (Deepest Audit)** |
| **Total Tokens Consumed** | 170,492 tokens | 283,258 tokens | 318,436 tokens | +66.1% token density | +12.4% token density |
| **Total Cost (USD)** | $0.0000 (Local) | **$1.0163** | **$0.6969** | +$1.0163 | **-31.4% cost savings** |
| **Cost per Accepted Row** | $0.0000 / row | **$0.1452 / row** | **$0.1742 / row** | +$0.1452 / row | +$0.0290 / row |
| **Tokens per Accepted Row** | **24,356 tokens/row** | 40,465 tokens/row | 79,609 tokens/row | +16,109 tokens/row | +39,144 tokens/row |
| **INV-1 Accepted Logic Errors** | **0 (0.0000, 100% clean)** | **0 (0.0000, 100% clean)** | **0 (0.0000, 100% clean)** | 100% Invariant Clean | 100% Invariant Clean |

---

## 3. Seed-by-Seed Trajectory Audit (Seeds 42–51)

| Seed | Target Type | Codebase & Vulnerability Condition | Local Gemma 12B/E4B | Gemini 3.5 / 3.6 | Gemini 3.7 / 3.8 |
| :---: | :---: | :--- | :---: | :---: | :---: |
| **42** | Safe ($F$) | `linux/fs/ext2/file.c`: NULL pointer in `ext2_fsync` | Rejected (R2, `verifier_failed`) | Rejected (R4, `verifier_logic_error`) | Rejected (R2, `anchors_too_few`) |
| **43** | Vuln ($T$) | `linux/crypto/ghash-generic.c`: NULL pointer in `gf128mul` | **Rejected (R2, `anchors_trap`)** | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R2, `ok`)** |
| **44** | Safe ($F$) | `curveMath.c`: Timing side-channel in `pointZZ_pMul` | **ACCEPTED (R2, `ok`)** | **ACCEPTED (R1, `ok`)** | Rejected (R2, `verifier_logic_error`) |
| **45** | Vuln ($T$) | `linux/kernel/ucount.c`: Enum OOB array indexing | **ACCEPTED (R2, `ok`)** | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R2, `ok`)** |
| **46** | Safe ($F$) | Nokogiri XML: Integer overflow in `read_memory` | **ACCEPTED (R1, `ok`)** | Rejected (R2, `verifier_logic_error`) | Rejected (R2, `verifier_logic_error`) |
| **47** | Vuln ($T$) | `linux/fs/gfs2`: Use-after-free in `__gfs2_get_acl` | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R1, `ok`)** |
| **48** | Safe ($F$) | `linux/net/llc`: Privilege escalation in sysctl | **Rejected (R2, `anchors_trap`)** | Rejected (R2, `verifier_logic_error`) | Rejected (R2, `verifier_logic_error`) |
| **49** | Vuln ($T$) | `linux/net/packet`: AF_PACKET memory leak | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R1, `ok`)** |
| **50** | Safe ($F$) | `librsvg`: Out-of-bounds read in `uri_decoded_copy` | **ACCEPTED (R2, `ok`)** | **ACCEPTED (R1, `ok`)** | Rejected (R2, `verifier_logic_error`) |
| **51** | Vuln ($T$) | `login-utils/setpwnam.c`: TOCTOU symlink in `rename` | **ACCEPTED (R1, `ok`)** | **ACCEPTED (R1, `ok`)** | **Rejected (R2, `verifier_logic_error`)** |

---

## 4. In-Depth Scientific Case Studies

### Case Study A: Resolving the Anchor Trap (Seed 43, `linux/crypto/ghash-generic.c`)
- **Vulnerability Predicate:** `ctx->gf128` is dereferenced by `gf128mul_4k_lle` without checking if `ghash_setkey` was called.
- **Local Gemma Failure Mode:**
  - Gemma-4-E4B generated elaborate reasoning in Round 0 and Round 1, but paraphrased the source code (e.g. changing `struct ghash_ctx *ctx = crypto_shash_ctx(desc->tfm);` into conceptual summaries).
  - The B-Gate anchor normalizer rejected the attempt with `anchors_too_few_after_normalization`, discarding a valid vulnerability proof due to surface-level syntactic failure.
- **Gemini 3.5 / 3.6 Breakthrough:**
  - Gemini 3.5 Flash extracted exact, verbatim anchor slices:
    ```c
    struct ghash_ctx *ctx = crypto_shash_ctx(desc->tfm);
    gf128mul_4k_lle((be128 *)dst, ctx->gf128);
    ```
  - Gemini 3.6 Flash verified the data flow on the initial trial without requiring progressive escalation or repair rounds, converting a previously failed benchmark seed into a clean, verified training row.

### Case Study B: Deceptive Comment Auditing & Kernel Semantics (Seed 51, `login-utils/setpwnam.c`)
- **The Benchmark Oracle vs. Predicate Tension:**
  - Seed 51 is labeled Vulnerable (`target_verdict: True`) in the benchmark oracle due to the classic `mktemp()` + `fopen()` race in `/tmp`.
  - However, the specific predicate evaluated asserted that the vulnerability was: *"a symbolic-link (TOCTOU) race that allows arbitrary file overwrite in rename(tmpname, PASSWD_FILE)"*.
  - In `setpwnam.c`, an author-inserted comment reinforced this claim:
    `/* TOCTOU Race Condition: tmpname is in a public dir and could be replaced with a symlink before rename */`
- **Gemma & Gemini 3.6 Behavior:**
  - Both stacks accepted the exploit narrative, aligning with the benchmark's Vulnerable oracle label by trusting the inline comment and accepting Pro's assertion that `rename(tmpname, PASSWD_FILE)` allows arbitrary file overwrite.
- **Gemini 3.8 Flash Superhuman Semantic Audit:**
  - Gemini 3.8 rejected the claim, logging the following audit:
    > *"The mechanism claims a symbolic-link TOCTOU race allowing arbitrary file overwrite. This is technically invalid for multiple reasons: (1) rename(2) does not dereference symlinks; (2) the target path is hardcoded to /etc/passwd, precluding arbitrary destination overwrite; and (3) under standard POSIX /tmp sticky-bit semantics, unprivileged users cannot unlink or rename files owned by root. The vulnerability narrative appears to be baited by the deceptive comments in the snippet."*
  - This highlights that Gemini 3.8 evaluates with strict literal precision: while the underlying codebase has an insecure tempfile pattern during creation, the predicate's narrow claim of an arbitrary overwrite *in `rename()`* was rejected under POSIX semantics.

### Case Study C: Deep Subsystem Invariant Auditing (Seed 46, Nokogiri XML Schema)
- **The Debate:**
  - Predicate claims an integer overflow when passing a string longer than `INT_MAX` to `Nokogiri::XML::Schema.read_memory`.
  - Debater claimed the cast `(int)RSTRING_LEN(content)` overflows 64-bit lengths into negative values.
- **Gemini 3.6 and 3.8 Verifier Interceptions:**
  - Both Gemini 3.6 and 3.8 analyzed the full slice and detected that the proposed exploit ignored an explicit upstream guard:
    `if (content_len > INT_MAX) rb_raise(...)`
  - The verifier intercepted the logic error (`verifier_logic_error`), preventing false-positive synthetic training row leakage into the dataset.

---

## 5. Token Economics & Cost Trade-Offs

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPUTATIONAL EFFICIENCY & COST COMPARISON                      │
├───────────────────────────────┬────────────────────────┬───────────────────────────────┤
│ Model Configuration           │ Cost / Accepted Row    │ Tokens / Accepted Row         │
├───────────────────────────────┼────────────────────────┼───────────────────────────────┤
│ Local Gemma 12B/E4B (Ollama)  │ $0.0000 (Local Compute)│ 24,356 tokens/row             │
│ Gemini 3.5 Flash / 3.6 Flash  │ $0.1452 / row          │ 40,465 tokens/row             │
│ Gemini 3.7 Flash / 3.8 Flash  │ $0.1742 / row          │ 79,609 tokens/row             │
└───────────────────────────────┴────────────────────────┴───────────────────────────────┘
```

1. **Gemini 3.5 / 3.6 is the Optimal Production Engine for Synthetic Data Curation:**
   - At **$0.145 per accepted row**, generating a curated 1,000-sample high-fidelity reasoning dataset costs approximately **~$145 USD**.
   - Achieves 100% acceptance of vulnerable seeds (5/5), eliminates the Anchor Trap, and delivers fast turnarounds (~14s per adjudication call).
2. **Gemini 3.7 / 3.8 as an Elite Secondary Adjudication Filter:**
   - Gemini 3.7 Flash Thinking adds internal chain-of-thought tokens that increase token volume (~2x).
   - Gemini 3.8 Flash provides the most rigorous security verification layer available, suitable as a top-tier filter for critical certification benchmarks.

---

## 6. Actionable Recommendations for Scaled 50-Seed Deployment

1. **Deploy Gemini 3.5/3.6 for Full 50-Seed Datagen Batches:**
   - The combination of `gemini-3.5-flash` debaters with `gemini-3.6-flash` judge/verifier matches the 70% yield on this pilot while providing superior anchor compliance and rock-solid 429 backoff handling.
2. **Implement Dual-Tier Verifier Consensus for Disputed Seeds:**
   - Use `gemini-3.6-flash` as the primary, fast verifier for R0 cold triage.
   - For seeds that escalate to R1 warm reflection under disputed VFS or POSIX semantics (such as Seeds 42, 48, 51), invoke `gemini-3.8-flash` to make the definitive acceptance determination.
3. **Preserve Repository Locks:**
   - As enforced throughout this benchmark, `silver-one` (`origin`) remains locked. All experimental improvements are maintained on `feat/debate-progressive-escalation-wip` and can be archived to `inert-silver`.
