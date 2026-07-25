# 0002. Full-corpus injection is a baseline, not the architecture

**Status:** Accepted
**Date:** 2026-07-25
**Supersedes:** the deferral language in ADR-0001 and `prompts/system.md`; amends `docs/roadmap.md` Phase 4

---

## Context

### The original decision

ADR-0001 and `knowledge/README.md` committed the MVP to **injecting the entire knowledge corpus into the system prompt on every request**, with retrieval deferred until "the corpus grows large enough to crowd the context window or slow the first request."

That was the right call at the time and the reasoning still holds for a small corpus: prompt-stuffing is simpler than a vector database, requires no embedding pipeline or chunking strategy, and — served from Anthropic's prompt cache — costs roughly a tenth of standard input rate on repeat requests. `knowledge/README.md` states plainly that this is "the correct architecture, not a shortcut."

`prompts/system.md` recorded two revisit conditions against the same threshold: **roughly 20k tokens of corpus.** One governed section ordering (whether the corpus should precede the behavior layer, per Anthropic's long-context guidance); the other governed whole-file verbatim injection versus a preprocessing step.

### What measurement showed

`src/ask_christopher/prompt.py` was implemented in Milestone 1 and the assembled prefix measured for the first time:

| Measure | Value |
|---|---|
| Assembled prefix, characters | 129,699 |
| Assembled prefix, UTF-8 bytes | 130,217 |
| Estimated tokens (bytes ÷ 4) | **~32,500** |
| Behavior layer (breakpoint A) | 34,862 chars — ~8,700 tokens |
| **Knowledge corpus alone** | 94,837 chars — **~23,800 tokens** |

The character and byte counts are measured from the repository. **The token figures are an estimate** from a bytes-per-token heuristic; the provider's own counts will differ.

Both are recorded here because they are what *motivated* this decision — the estimate is why the revisit conditions turned out to be met. Provider-reported figures belong in the experiment record, not in this file.

### The revisit conditions have already been met

**Both conditions written into `prompts/system.md` were exceeded on the day they were written.** The file estimated the corpus at "a few thousand words"; it is approximately 20,000 words. `projects.md` alone is 24KB and `boundaries.md` is 21KB.

So the situation is not that a threshold is approaching. It is that:

1. **`prompts/system.md` → section ordering revisit** — triggered. The corpus is large enough that Anthropic's long-context guidance (documents before instructions) is now relevant rather than negligible.
2. **`prompts/system.md` → whole-file injection revisit** — triggered. Maintainer notes and status headers that carry no runtime value are now a measurable share of a 24k-token corpus.
3. **`docs/roadmap.md` Phase 4 — retrieval** — triggered. It was written as a distant concern with a 20k-token trigger. That trigger is behind us.

The corpus was written before it could be measured. That is not a mistake in the corpus — it is what a hand-written corpus produced — but the architecture documents describe a system smaller than the one that exists.

### Why prompt caching does not settle this

Caching is the reason the current design is viable, and it is easy to over-read. **Prompt caching reduces the repeated cost of resending input. It does not address four separate concerns.**

**Cost — genuinely addressed, with caveats.** Cache reads bill at roughly 0.1× input rate; writes cost 1.25× at the default five-minute TTL. Break-even is two requests. But the cache is a *prefix* match with a five-minute TTL: a visitor arriving after an idle gap pays the write, and any byte-level change to the corpus invalidates it for everyone. A low-traffic site with sporadic visitors pays the write far more often than a busy one.

**Context window — not addressed.** A cached token still occupies the context window. At ~32.5k of a 1M window this is not yet a constraint, but caching does not make it one either; the corpus consumes the same space cached or not.

**Latency — partly addressed, not eliminated.** Cache reads are faster than cold processing, but a cache *write* still processes the full prefix. Two situations pay it: the first visitor of any idle period, and every visitor after a corpus edit. The user-visible worst case is unchanged by caching.

**Relevance and attention dilution — not addressed at all, and this is the important one.** A visitor asking *"what does an instructional designer do?"* currently receives the full text of `boundaries.md`, `projects.md`, and `services.md` alongside the one paragraph that answers them. Caching makes that cheap. It does not make it *good*. Every irrelevant token is context the model must attend past, and the corpus is full of near-miss material — nine hard limits, seven project entries, four evidence tiers — that a narrow question does not need.

That is a **quality** argument, not a cost argument, and it is the one caching cannot answer. It is also the argument that matters most for an assistant whose entire purpose is answering accurately about a real person.

---

## Decision

> **Keep the deterministic full-corpus assembly for one controlled API experiment, and classify it explicitly as a baseline rather than the intended production architecture.**

Three parts:

**1. Full assembly stays, unchanged, for Milestone 2.** `prompt.py` is correct, tested, and byte-stable. The Milestone 2 experiment sends the two stable prefix segments as cached content blocks and records provider-reported cache metrics. Nothing about the assembly changes.

**2. Its status changes.** The documents no longer describe full injection as the architecture with retrieval deferred behind a distant threshold. They describe three distinct things:

| Stage | State |
|---|---|
| **Deterministic full assembly** | **Exists.** Implemented and tested in Milestone 1. |
| **Full-prefix API testing** | **The Milestone 2 baseline.** A measurement, not a destination. |
| **Selective retrieval** | **An active architectural requirement.** Not yet implemented, no longer distant. |

**3. Retrieval becomes a requirement rather than a contingency.** It is no longer gated on a token threshold, because the threshold is behind us. It is gated on having a measured baseline to compare against — which is precisely what Milestone 2 produces.

### Why a baseline experiment before retrieval

Building retrieval first would mean never knowing what the simple version cost. The experiment is cheap (two requests), and it converts several estimates in this ADR into measurements: exact prefix tokens, whether the cache engages at all, actual write and read costs, and real latency for both paths.

**A retrieval system that cannot be compared against a baseline is an assumption, not an improvement.** This is the same instinct recorded in `knowledge/philosophy.md` — diagnose before selecting the solution.

---

## Alternatives considered

**Build retrieval now and skip the baseline.** Rejected. The corpus is over the threshold, so this is defensible on the surface — but it discards the measurement while it is still trivially cheap to take, and it front-loads chunking and embedding decisions with no data about what they need to beat.

**Declare full injection permanent and rely on caching.** Rejected. It answers cost and ignores relevance. It would also mean the corpus can never grow — every future project entry, FAQ answer, and philosophy section makes every unrelated answer worse.

**Preprocess the corpus to strip maintainer sections, and keep full injection.** Rejected *for now*, not on the merits. It would meaningfully reduce token count and it is far simpler than retrieval. But it trades determinism for size — `prompts/system.md` records why whole-file injection was chosen — and it should be measured against the baseline like anything else. Retained as a candidate optimization.

**Raise the threshold and defer again.** Rejected. The threshold was set by estimate and missed by an order of magnitude. Setting a new number by the same method would repeat the error. Retrieval is now gated on evidence, not on a guess.

---

## Consequences

**Easier.** Milestone 2 is small and well-scoped: two API calls and a metrics record. It produces the numbers every later decision needs. The prompt layer needs no changes.

**Harder — and accepted.** The corpus cannot grow much further before answer quality is affected, which puts real pressure on Phase 3 (turning repositories into retrievable knowledge). Retrieval work arrives sooner than ADR-0001 anticipated.

**Honest.** The architecture documents now describe the system that exists. A reader of `prompts/system.md` will not find retrieval described as a distant Phase 4 concern when the corpus already exceeds its own trigger.

**Neutral.** Nothing shipped changes. `prompt.py` and its 21 tests are unaffected, and the two cache breakpoints designed in `prompts/system.md` are exactly what the experiment exercises.

---

## Revisit when

**Once the Milestone 2 experiment has run and its results are recorded** in `docs/experiments/0001-prompt-cache-baseline.md`.

> **Do not amend this ADR with those results.** Provider usage fields, cache behaviour, latency, and actual cost belong in the experiment record. This file explains *why* the experiment exists; the experiment record reports *what happened*. Keeping them apart is what stops an architectural decision from turning into a mutable lab notebook — a later reader needs to see the reasoning as it stood when the decision was made, not a document silently rewritten to match its outcome.
>
> If the measurements contradict the reasoning here, that warrants a **new ADR superseding this one**, not an edit to this one.

**Then decide retrieval's shape on that evidence**, weighing at least:

- Whole-corpus injection with preprocessing (cheapest change, keeps determinism mostly intact)
- Per-file selection driven by question classification (no embeddings required)
- Chunked embedding retrieval (the Phase 4 assumption, and the largest step)

The open question this ADR deliberately does **not** answer: **which of those, and on what evidence.** That decision belongs in a later ADR written against measurements rather than estimates.
