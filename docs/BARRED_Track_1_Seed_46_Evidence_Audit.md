# BARRED Track 1 — Seed 46 Evidence Audit

## Question audited

**Claim:** “The code is vulnerable to an integer-overflow leading to a heap-buffer overflow in `xmlSchemaNewMemParserCtxt` when a Ruby string longer than `INT_MAX` bytes is passed to `Nokogiri::XML::Schema.read_memory`.”

**Result:** **Proved safe for this exact integer-overflow/heap-buffer-overflow claim.** The Nokogiri call site does narrow `(int)RSTRING_LEN(content)` without a local guard, but the callee `xmlSchemaNewMemParserCtxt` rejects any non-positive `size`, and any truncated positive size is bounded by the actual buffer length. No heap overflow is reachable through this path.

## What was examined

1. I selected seed 46 from the replicated Gemma/Gemini persistent-disagreement queue because the allegation is a concrete arithmetic/ownership claim: a 64-bit length narrowed to a 32-bit `int` before being passed to a libxml2 parser constructor.
2. The relevant function is `read_memory` in the supplied Nokogiri C extension:
   ```c
   ctx = xmlSchemaNewMemParserCtxt(
       (const char *)StringValuePtr(content),
       (int)RSTRING_LEN(content)
   );
   ```
   `RSTRING_LEN(content)` is Ruby's string length (a signed `long` on the 64-bit builds in scope), and `(int)` narrows it to a 32-bit signed integer with no range check at the call site.
3. I resolved the callee contract against the libxml2 source. In both the 2.9.13 release (`v2.9.13` tag, `xmlschemas.c`) and current master, `xmlSchemaNewMemParserCtxt` is implemented as:
   ```c
   xmlSchemaParserCtxt *
   xmlSchemaNewMemParserCtxt(const char *buffer, int size)
   {
       xmlSchemaParserCtxtPtr ret;
       if ((buffer == NULL) || (size <= 0))
           return (NULL);
       ret = xmlSchemaParserCtxtCreate();
       if (ret == NULL)
           return (NULL);
       ret->buffer = buffer;
       ret->size = size;
       ret->dict = xmlDictCreate();
       return (ret);
   }
   ```
   Thus any truncated size that is zero or negative is rejected before any buffer use, and `ret->size` is set only to the (small, non-negative) truncated value.
4. I checked the modular bound for a truncated *positive* size. Writing `L = RSTRING_LEN(content)` and `N = (int)L` (two's-complement truncation), a positive `N` implies `L = k·2^32 + N` for some `k ≥ 0`, so `N ≤ L`. libxml2 then parses at most `N` bytes from a buffer of `L` bytes; the read cannot exceed the allocation. Even in the pathological case `N = INT_MAX`, `L ≥ INT_MAX`.
5. I traced the Nokogiri error path. When `xmlSchemaNewMemParserCtxt` returns `NULL`, `read_memory` falls through to `xmlSchemaParse(ctx)` with `ctx == NULL`? No — Nokogiri assigns `ctx` first, then calls `xmlSchemaParse(ctx)`; on a `NULL` ctx libxml2 returns `NULL` for `xmlSchemaParse`, so `schema == NULL`, and Nokogiri raises `rb_raise(rb_eRuntimeError, "Could not parse document")` (or surfaces the libxml2 error). No memory corruption occurs.
6. I checked the CVEFixes provenance. The supplied topic matches CVEFixes row 24782 exactly (SHA-256 `cafda613dd7fc5a243cd77ef036bf971474147718e7a318ee2670a1d3dd807c8`, 6580 bytes, language `c`, safety `safe`). As with seeds 42, 50, and 68, the CSV retains only `code`, `language`, and `safety` — no version/commit metadata. The CSV label is `safe`, consistent with this result, but the version-matched libxml2 source — not the label — settles it.

## Evidence ledger

| Required question | Evidence | Conclusion |
|---|---|---|
| What is the alleged bad operation? | `(int)RSTRING_LEN(content)` passed as `size` to `xmlSchemaNewMemParserCtxt`. | Identified precisely. |
| Is the narrowing unchecked locally? | Yes; no `INT_MAX` guard or raise precedes the call. | Local guard absent. |
| Does the callee accept a truncated size? | No; `xmlSchemaNewMemParserCtxt` returns `NULL` when `size <= 0` (libxml2 2.9.13 and master). | Negative/zero truncation rejected. |
| Can a truncated *positive* size exceed the buffer? | No; `N = L mod 2^32` (positive) implies `N ≤ L`, so the parse reads at most `N` of `L` bytes. | Bounded by construction. |
| Does a `NULL` context corrupt memory? | No; `xmlSchemaParse(NULL)` returns `NULL` and Nokogiri raises a Ruby error. | No corruption. |
| Is a trigger demonstrated? | No overflow trigger exists; the proposed bad operation is blocked by the callee contract. | Claim refuted. |

## Why the model results were misleading

The GEPA predicate noticed an unchecked narrowing conversion and inferred a heap buffer overflow, but it omitted two decisive facts: libxml2's `size <= 0` rejection and the modular bound that keeps any surviving positive size below the actual buffer length. The replicated model outcomes are therefore not used as adjudication evidence.

This is **RFC Axis E: predicate invalidity**. The Nokogiri code's missing local guard is a real code smell, but it is not a vulnerability because the callee's contract absorbs the truncation. An `INT_MAX` check in Nokogiri would be defense-in-depth, not a required fix for this claim.

## Audit boundary

This result is limited to the exact seed-46 claim of an integer overflow leading to a heap buffer overflow via the `(int)RSTRING_LEN(content)` narrowing in `read_memory`. It covers libxml2 2.9.13 (the version in the local SDK) and current master, both of which contain the `size <= 0` guard; it does not assert anything about hypothetical libxml2 forks or versions predating that guard, and it does not assess other Nokogiri entry points. It does not depend on the CVEFixes `safe` label.