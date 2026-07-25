# Experiment 0001 — Prompt cache baseline

**Date:** 2026-07-25, 22:40 UTC
**Commit under test:** `48d01e7` — *Implement cached API baseline and document retrieval decision*
**Motivated by:** [ADR-0002](../decisions/0002-full-corpus-injection-is-a-baseline-not-the-architecture.md)
**Raw record:** [`0001-prompt-cache-baseline.json`](0001-prompt-cache-baseline.json)

> This file reports what happened. It does not decide anything. ADR-0002 explains why the experiment exists; a future ADR will decide what to do about the result.

---

## Method

Executed from a **detached git worktree at `48d01e7`**, unmodified.

That matters because `src/ask_christopher/client.py` was refactored two commits later (`8b87cbc`) to add conversation support. The corpus and prompts are byte-identical between `48d01e7` and `HEAD`, so the prefix is the same either way — but the request-construction code is not, and the agreed protocol was to measure the reviewed artifact rather than a version adjusted afterwards.

Two sequential calls, identical prefix, identical question. Sequential rather than concurrent by necessity: a cache entry only becomes readable once the first response has begun streaming, so parallel calls would both miss and measure nothing.

### Configuration

| | |
|---|---|
| Model | `claude-opus-5` |
| `max_tokens` | 2048 |
| `effort` | `low` |
| `thinking` | unset — adaptive is the default on this model |
| Sampling params | none — rejected by this model |
| Cache breakpoints | 2 (behaviour layer, then full prefix) |
| Cache TTL | default, 5 minutes |
| SDK | `anthropic` 0.120.0 |
| Runtime | Python 3.12.10, Windows 11 |
| Question | *"What does a Senior Instructional Designer do?"* |

---

## Prefix size

| Measure | Value |
|---|---|
| Characters | 129,699 |
| UTF-8 bytes | 130,217 |
| Segment A — behaviour layer | 34,862 chars |
| Segment B — knowledge corpus | 94,837 chars |
| **Tokens, estimated before the run** | **32,554** |
| **Tokens, reported by the provider** | **40,511** |

Derived ratios: **3.214 bytes/token**, **3.202 chars/token**.

---

## Results

| | Call 1 | Call 2 |
|---|---:|---:|
| Request ID | `req_011CdPaWg8PDUYD2ofanqkKi` | `req_011CdPaX9uUceXMEGbjTinc3` |
| `cache_creation_input_tokens` | **40,511** | 0 |
| `cache_read_input_tokens` | 0 | **40,511** |
| `input_tokens` | 19 | 19 |
| Total prompt tokens | 40,530 | 40,530 |
| `output_tokens` | 343 | 374 |
| `stop_reason` | `end_turn` | `end_turn` |
| Latency | **6.709 s** | **6.820 s** |

### Cost

Applying list pricing for `claude-opus-5` — $5.00/MTok input, $25.00/MTok output, cache writes at 1.25×, cache reads at 0.1×:

| | Call 1 | Call 2 |
|---|---:|---:|
| Input | $0.253289 | $0.020351 |
| Output | $0.008575 | $0.009350 |
| **Total** | **$0.261864** | **$0.029701** |

**Input cost fell by $0.232938 — 92.0%.** Total experiment cost: **$0.291565**.

---

## Confirmed or contradicted

**Confirmed — caching works exactly as designed.**

The prediction stated before the run was a cache write on call 1 roughly equal to the prefix, a read of the same magnitude on call 2, and `input_tokens` on both showing only the uncached remainder. All three hold. The write and read are the same 40,511 tokens, and `input_tokens` is 19 on both calls — the question and nothing else. The two-breakpoint design in `prompts/system.md` engaged on the first attempt with no tuning.

**Contradicted — the token estimate was materially wrong.**

The measured prefix is **40,511 tokens against a pre-run estimate of 32,554**: the estimate was 19.6% low, and the real figure is 24.4% higher than assumed. The bytes-÷-4 heuristic does not hold for this content on this tokenizer, which runs closer to 3.21 bytes per token.

This deepens rather than changes ADR-0002's conclusion. That ADR reclassified full-corpus injection as a baseline because the corpus had already passed a ~20k-token revisit threshold at an estimated ~24k. The corpus segment is **~29,600 tokens** by proportional derivation — *derived from the character split, not separately measured* — which is roughly **1.5× the threshold**, not 1.2×.

**Not observed — no latency improvement.**

Call 2 was **111 ms slower** than call 1 despite reading 40,511 tokens from cache. This does not falsify caching; it shows the measurement cannot isolate it. End-to-end latency is dominated by generation, which is never cached, and call 2 happened to generate 31 more output tokens. The script's own output warned about this before the run.

**Isolating prefix latency would require time-to-first-token, which requires streaming, which is out of scope for the baseline.** Anyone citing these two numbers as evidence about cache latency would be misreading them.

---

## What this establishes for the retrieval decision

1. **The cost argument for caching is real and large.** 92% off input on a repeat request, break-even after two.
2. **It is also narrower than it looks.** $0.25 is the *floor* for a cold prefix, and every visitor arriving after a five-minute gap pays it — as does every visitor after any corpus edit. On a low-traffic site, cold writes may be the common case rather than the exception.
3. **The relevance argument is untouched**, and is now larger than ADR-0002 assumed. Roughly 29,600 tokens of corpus are sent to answer a question whose answer occupies one paragraph of `bio.md`.
4. **Latency remains unmeasured.** Any future claim that caching improves responsiveness needs a streaming TTFT measurement, not this record.

---

## Notes

- Both calls returned `end_turn`; neither hit `max_tokens`, so the 2048 budget was sufficient with adaptive thinking on at `low` effort.
- Response text was deliberately not retained. The baseline measures cache behaviour, not answer quality — that is Experiment 0002.
- The worktree at `48d01e7` was removed after the run.
