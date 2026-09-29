# Comparative Debate Benchmark Report: Local Gemma vs. Gemini 3 Exploratory Pilot (N=10)

**Evaluation Date:** 2026-09-29  
**Evaluation Scope:** 10-Seed Comparative Pilot Benchmark across Seeds 42–51 (5 Safe, 5 Vulnerable) under Progressive Escalation Protocol (`--escalate-pareto`)  
**Seed Manifest:** `artifacts/seeds_pilot_10.jsonl` (extracted from `scenarios/debate/cve_seeds_benchmark_50.jsonl`)  
**Evaluated Stacks:**
1. **Local Stack (Baseline):** Gemma-4-12B-Fast (Judge & Verifier) + Gemma-4-E4B (Debaters & Generator) via Ollama
2. **Cloud Stack 1:** `vertex_ai/gemini-3.5-flash` (Debaters & Generator) + `vertex_ai/gemini-3.6-flash` (Judge & Verifier)
3. **Cloud Stack 2:** `vertex_ai/gemini-3.7-flash` (Debaters & Generator with Thinking) + `vertex_ai/gemini-3.8-flash` (Judge & Verifier)

---

## 1. Executive Summary: The Benchmark Validity Caveat

Following the scaled progressive escalation experiments with local open-weights models, we conducted an exploratory pilot across 10 balanced seeds (5 Safe, 5 Vulnerable) to investigate swarm behavior when transitioning to Gemini 3 families on Vertex AI (`global` endpoint, project `gem-creation`).

Because this is a small exploratory sample ($N=10$), this pilot is **not a definitive model ranking**. Instead, it surfaced a fundamental conceptual caveat regarding the benchmark itself:

1. **The Acceptance Asymmetry:**
   - Across the pilot, the evaluated model stacks exhibited a progressively stronger acceptance asymmetry between Vulnerable and Safe seed classes:
     - **Local Gemma (12B/E4B):** 4/5 Vulnerable (80.0%), 3/5 Safe (60.0%) accepted [7/10 total]
     - **Gemini 3.5 / 3.6:** 5/5 Vulnerable (100.0%), 2/5 Safe (40.0%) accepted [7/10 total]
     - **Gemini 3.7 / 3.8:** 4/5 Vulnerable (80.0%), 0/5 Safe (0.0%) accepted [4/10 total]
   - Rather than concluding that higher-capability models simply "prefer vulnerable seeds," audit of individual failure trajectories revealed that **acceptance does not equal classification accuracy**.

2. **The Oracle vs. Predicate Tension:**
   - In Seed 51 (`login-utils/setpwnam.c`), the benchmark oracle labels the codebase Vulnerable. However, Gemini 3.8 rejected the argument because the specific predicate asserted an arbitrary file overwrite *in `rename()`*, which is invalid under POSIX `rename(2)` non-dereferencing semantics.
   - This exposed a key benchmark design flaw: **a seed can be historically vulnerable while the specific vulnerability predicate supplied to the debaters is technically flawed or over-specified**.

3. **Core Methodological Takeaway:**
   > **"A perfectly deterministic gate can consistently enforce a poorly specified predicate."**
   - The primary research objective is therefore not merely whether the agent agrees with the benchmark oracle, but whether it produces a technically defensible proof of the exact predicate independently of human benchmark annotations.

---

## 2. Three-Way Comparative Performance Matrix (Seeds 42–51)

| Metric | Local Gemma Swarm (12B/E4B) | Gemini 3.5 Flash / 3.6 Flash | Gemini 3.7 Flash / 3.8 Flash | Contrast (Gemini 3.5 vs. Gemma) | Contrast (Gemini 3.8 vs. 3.6) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Seeds Evaluated** | 10 (5 Safe / 5 Vuln) | 10 (5 Safe / 5 Vuln) | 10 (5 Safe / 5 Vuln) | Invariant ($N=10$) | Invariant ($N=10$) |
| **Accepted Training Rows** | **7 / 10 (70.0%)** | **7 / 10 (70.0%)** | **4 / 10 (40.0%)** | Parity in Yield (70%) | -30.0 pp (Stricter Audit) |
| **Vulnerable Seeds Accepted** | 4 / 5 (80.0%) | **5 / 5 (100.0%)** | 4 / 5 (80.0%) | +20.0 pp (Vuln Acc) | -20.0 pp (Deceptive Seed 51 caught) |
| **Safe Seeds Accepted** | 3 / 5 (60.0%) | 2 / 5 (40.0%) | 0 / 5 (0.0%) | -20.0 pp (Safe Acc) | -40.0 pp (Stricter Invariant Check) |
| **Total Attempts Incurred** | 16 attempts (1.6/seed) | **15 attempts (1.5/seed)** | 18 attempts (1.8/seed) | -0.1 attempt/seed | +0.3 attempt/seed |
| **Anchor Trap Failures** | 2 (20.0% of seeds) | **0 (0.0% of seeds)** | 1 (10.0% of seeds) | -20.0 pp (Trap Eliminated) | +10.0 pp |
| **Verifier Interceptions** | 1 (10.0% of seeds) | 3 (30.0% of seeds) | **5 (50.0% of seeds)** | +20.0 pp | +20.0 pp (Elevated Audit) |
| **Total Tokens Consumed** | 170,492 tokens | 283,258 tokens | 318,436 tokens | +66.1% token density | +12.4% token density |
| **Total Cost (USD)** | $0.0000 (Local) | **$1.0163** | **$0.6969** | +$1.0163 | -31.4% cost savings |
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

### Case Study A: Syntactic Anchoring and the Anchor Trap (Seed 43, `linux/crypto/ghash-generic.c`)
- **Vulnerability Predicate:** `ctx->gf128` is dereferenced by `gf128mul_4k_lle` without checking if `ghash_setkey` was called.
- **Local Gemma Failure Mode:**
  - Gemma-4-E4B generated elaborate reasoning in Round 0 and Round 1, but paraphrased the source code (e.g., summarizing rather than quoting `struct ghash_ctx *ctx = crypto_shash_ctx(desc->tfm);`).
  - The B-Gate anchor normalizer rejected the attempt with `anchors_too_few_after_normalization`, failing a valid vulnerability proof due to surface-level syntactic attrition.
- **Gemini 3.5 / 3.6 Behavior:**
  - Gemini 3.5 Flash extracted exact, verbatim anchor slices:
    ```c
    struct ghash_ctx *ctx = crypto_shash_ctx(desc->tfm);
    gf128mul_4k_lle((be128 *)dst, ctx->gf128);
    ```
  - Gemini 3.6 Flash verified the data flow on the initial trial without requiring progressive escalation or repair rounds, converting a previously failed benchmark seed into a clean, verified training row.

### Case Study B: The Oracle vs. Predicate Tension (Seed 51, `login-utils/setpwnam.c`)
- **The Benchmark Oracle vs. Predicate Tension:**
  - Seed 51 is labeled Vulnerable (`target_verdict: True`) in the benchmark oracle due to the classic `mktemp()` + `fopen()` race in `/tmp`.
  - However, the specific predicate evaluated asserted that the vulnerability was: *"a symbolic-link (TOCTOU) race that allows arbitrary file overwrite in rename(tmpname, PASSWD_FILE)"*.
  - In `setpwnam.c`, an author-inserted comment reinforced this claim:
    `/* TOCTOU Race Condition: tmpname is in a public dir and could be replaced with a symlink before rename */`
- **Gemma & Gemini 3.6 Behavior:**
  - Both stacks accepted the exploit narrative, aligning with the benchmark's Vulnerable oracle label by trusting the inline comment and accepting Pro's assertion that `rename(tmpname, PASSWD_FILE)` allows arbitrary file overwrite.
- **Gemini 3.8 Flash Semantic Audit:**
  - Gemini 3.8 rejected the claim, logging the following audit:
    > *"The mechanism claims a symbolic-link TOCTOU race allowing arbitrary file overwrite. This is technically invalid for multiple reasons: (1) rename(2) does not dereference symlinks; (2) the target path is hardcoded to /etc/passwd, precluding arbitrary destination overwrite; and (3) under standard POSIX /tmp sticky-bit semantics, unprivileged users cannot unlink or rename files owned by root. The vulnerability narrative appears to be baited by the deceptive comments in the snippet."*
  - This highlights that Gemini 3.8 evaluates with strict literal precision: while the underlying codebase has an insecure tempfile pattern during creation, the predicate's narrow claim of an arbitrary overwrite *in `rename()`* was rejected under POSIX semantics.

### Case Study C: Upstream Guard Detection (Seed 46, Nokogiri XML Schema)
- **The Debate:**
  - Predicate claims an integer overflow when passing a string longer than `INT_MAX` to `Nokogiri::XML::Schema.read_memory`.
  - Debater claimed the cast `(int)RSTRING_LEN(content)` overflows 64-bit lengths into negative values.
- **Gemini 3.6 and 3.8 Verifier Interceptions:**
  - Both Gemini 3.6 and 3.8 analyzed the full slice and detected that the proposed exploit ignored an explicit upstream guard:
    `if (content_len > INT_MAX) rb_raise(...)`
  - The verifiers intercepted the logic error (`verifier_logic_error`), correctly recognizing that the exploit premise failed code-level invariants.

---

## 5. Token & Compute Profile

The measured token volume across the 10-seed pilot provides an initial empirical profile for the evaluated configurations:

- **Local Gemma 12B/E4B (Ollama):** 170,492 total tokens across 16 attempts ($24,356$ tokens/accepted row) at zero API cost on local hardware.
- **Gemini 3.5 Flash / 3.6 Flash:** 283,258 total tokens across 15 attempts ($40,465$ tokens/accepted row), incurring $1.0163 USD total ($0.1452/row).
- **Gemini 3.7 Flash / 3.8 Flash:** 318,436 total tokens across 18 attempts ($79,609$ tokens/accepted row), incurring $0.6969 USD total ($0.1742/row).

*(Note: These figures reflect small-scale pilot observations across $N=10$ seeds. They illustrate relative token density rather than stabilized large-scale economic extrapolations.)*

---

## 6. Actionable Research Directions

This pilot clarifies that scaling synthetic data generation requires addressing benchmark construction directly:

1. **Disentangle Three Distinct Variables:**
   - **Oracle Label:** The binary security status assigned by benchmark authors.
   - **Predicate Validity:** Whether the stated vulnerability mechanism is technically defensible under source code and runtime semantics.
   - **Agent Decision:** Whether the debate/verifier swarm accepts or rejects the claim.
2. **Conduct a Systematic Predicate-Validation Audit:**
   - Before executing large-scale datagen runs on frontier models, perform an automated and manual predicate audit across the seed dataset to eliminate misleading comments and over-specified mechanism claims (as discovered in Seed 51).
3. **Preserve Deterministic Safety Invariants:**
   - Invariant enforcement (0 accepted `INV-1` logic errors, anchor normalization, verifier audits) remained intact across all stacks. The next frontier is pairing rigorous deterministic gating with verified, semantically sound predicates.
