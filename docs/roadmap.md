# Roadmap

**Status:** Living document
**Authoritative for:** phase definitions, current milestone, and the portfolio consolidation backlog

**Everything below is planned work, not delivered capability.** An unchecked item describes an intention. Nothing here should be read as a description of what exists — see `knowledge/projects.md` for what is actually built.

---

## Where the project is

**Phase 1, in progress — one item open.**

**Built and recorded:** the knowledge corpus (`knowledge/`, six files), the prompt layer (`prompts/`, four files), prompt assembly, the API client, the terminal REPL, and two experiments. What the assistant knows, who it is, how it teaches, how it stays honest, how those assemble into the exact bytes sent to the API — and now two measurements of what actually comes back.

**Open:** the eval suite is a framework with 39 cases and **has never been run against real model output.** That is the remaining Phase 1 item. Scoring the 30 `model_judged` cases needs a judge that does not exist yet, and there is no entry point to run the suite live — see *Eval suite* below.

**In flight:** experiment 0002 is `complete` as of 2026-08-12. Its `review.md` and the production-effort rerun are the open items.

---

## Phase 1 — Grounded persona

Milestone 1, from ADR-0001: a terminal REPL that loads the Markdown corpus, assembles a cached system prompt, calls the Anthropic API, and streams a response.

- [x] Knowledge corpus — `knowledge/`
- [x] Prompt layer — persona, teaching style, grounding rules, assembly spec
- [x] Prompt assembly — `src/ask_christopher/prompt.py`, with byte-stability tests
- [x] **Milestone 2 — cache baseline.** Recorded as [experiment 0001](experiments/0001-prompt-cache-baseline.md). Caching confirmed on the first attempt with no tuning: 40,511 tokens written then read back, input cost down 92.0%. It also contradicted the pre-run token estimate by 19.6% and observed *no* latency improvement — the measurement cannot isolate that, which the record says explicitly.
- [x] Terminal REPL — `src/ask_christopher/repl.py`, `Session` separated from the loop so conversation behaviour is testable without credentials or a terminal
- [ ] **Eval suite — the open item, now partly closed.** `tests/evals/cases.yaml` holds 39 cases across the seven categories, with eight tradeoffs guarded in both directions, and `src/ask_christopher/evals.py` scores them against any injected response function.
  - [x] **Runner** — `scripts/run_evals.py`, with `list`, `replay`, and `live`. Every case lands in `ran` or in `skipped` with a stated reason, records go to `docs/evals/`, and no suite-wide pass rate is ever reported. A live run is priced and refuses to spend without `--confirm`.
  - [x] **First replay** — experiment 0002's transcript scored through the suite. 6 of 39 cases covered, **nothing falsified and nothing confirmed**: 2 had checks that passed, 4 carry no executable checks at all. That is the honest ceiling of lexical scoring, measured rather than argued.
  - [x] **Correction pair, judged.** Both halves run single-turn for $0.2833 and judged to pass — [review](evals/correction-pair-review.md). `crn-valid-correction` supplies the prior claim in its own prompt, so it never needed a conversation. **It also produced the first real grounding failure the suite has caught:** an unsupported comparative — *"the longer teaching stretch was at Inland Empire"* — where `bio.md` gives a duration for one post and none for the other. Both lexical checks passed; only a human reading caught it.
  - [ ] **Model-as-judge scoring.** The 30 `model_judged` cases stay `needs_judgment` until this exists. This is now the single largest gap between "the suite runs" and "the suite measures anything" — and the correction-pair finding is the argument for it: word counts and a `$`-pattern cannot see an ungrounded claim.
  - [ ] **Human-review workflow** for the 3 `human_review` cases.
  - [ ] **Conversation-capable runner** for the 2 cases now marked `multi_turn: true`.
  - [ ] **A full live run.** Two of 39 cases have now been sent. The rest are priced at roughly $1.05, assuming they stay inside the cache TTL.

### Queued behind the production-effort rerun

From the correction-pair review. All four touch `knowledge/` or `prompts/`, so they wait — editing the corpus first would confound effort with content permanently.

- [ ] **Decide the Inland Empire duration.** If it is known, `bio.md` should state it and the ungrounded comparative becomes a documented fact. If it is not, the assistant must stop ranking the two posts.
- [ ] **Add an eval case for unsupported comparatives** — "which of X and Y was longer" where the corpus gives one figure and not the other. Nothing in the current 39 tests this shape, and it catches a true-*sounding* inference rather than an invented fact.
- [ ] **Tighten `crn-valid-correction`'s rubric** to distinguish a correct conditional from a false confession. As written it assumes the assistant did say the wrong thing, so a judge could mark the better answer wrong.
- [ ] **Decide the lecture threshold** in `grounding_rules.md`. The prohibition on explaining why a rule exists reads as absolute; one clause of rationale is arguably better than none.

### Experiment 0002 — first conversation

The first real multi-turn conversation, run against a fixed question set through a two-phase harness.

- [x] **Phase A** — turns 1-6, [recorded](experiments/0002-first-conversation-baseline/transcript.md). Cache behaviour held across a real conversation rather than a scripted probe: turn 1 wrote the prefix, turns 2-6 each read it back in full while only the accumulating history billed as uncached input. Turn 6 was designed to produce a correctable claim and did not — all eleven checkable assertions matched the corpus, and it volunteered the *Facts that age* caveat from `boundaries.md` unprompted. **No correction was manufactured.**
- [x] **Phase B** — run at `8e3a243` with `--allow-commit-drift` and `--no-correction`. Turn 7 is recorded as an unwarranted correction with its reasoning, and skipped rather than manufactured; turn 8 held the line on an undocumented opinion, declining to invent a view while offering the adjacent documented material. Two consequences to carry forward: **`crn-valid-correction` goes unexercised**, so correction handling remains untested, and **the two-phase split cost a second full cache write** — 17 days separated the phases against a 5-minute TTL, so turn 8 paid $0.259874 in input where a warm read would have cost $0.026936, a **9.65× premium**. Run total $0.666845, of which $0.506387 (75.9%) is two cache writes.
- [x] [`review.md`](experiments/0002-first-conversation-baseline/review.md) for 0002 — the cache-window result is the finding: the write premium and experiment 0001's 92% saving are the *same quantity*, `40,511 × $5/MTok × (1.25 − 0.1)`, read under different traffic assumptions.
- [x] **Record Phase B's own commit in provenance.** `phase_b_commit`, `phase_b_commit_dirty`, and `allow_commit_drift` are now captured, and the rendering reports both phases when they differ. This run's provenance was amended from durable evidence with a visible `provenance_amendment` note; `phase_b_commit_dirty` is null because nothing durable attests it.
- [ ] **Rerun the same fixed question set at production effort, before any corpus or prompt edit.** Both experiments ran at `low` effort to avoid measuring two changes at once. Editing content first permanently confounds effort with content — this ordering constraint is recorded inside the hashed `questions.yaml` for that reason.

ADR-0001 deferred retrieval to Phase 4. **ADR-0002 amends that** — the corpus already exceeds the threshold, so full injection is now classified as a baseline and retrieval as an active requirement.

## Phase 2 — Web interface

Browser-based chat embedded in ChristopherMathews.com. The likely shape is a small FastAPI service in front of the existing package, with a separate frontend.

**Reopen ADR-0001 at the start of this phase.** The Python decision is scoped to Milestone 1 and explicitly does not commit the web interface.

## Phase 3 — Portfolio knowledge

Turn the other public repositories into retrievable knowledge, so the assistant answers from repository content directly rather than from hand-written summaries in `projects.md`.

Depends on the consolidation backlog below — there is little to retrieve until the work is actually published.

## Phase 4 — Selective retrieval

> ⚠️ **No longer a distant concern.** This phase was written with a ~20k-token trigger. The estimate at the time was ~24k for the corpus and ~32.5k for the assembled prefix; **experiment 0001 measured the prefix at 40,511 tokens**, making the estimate 19.6% low and the corpus segment roughly **1.5x** the revisit threshold rather than 1.2x. **Selective retrieval is an active architectural requirement, not a contingency** — see `docs/decisions/0002-full-corpus-injection-is-a-baseline-not-the-architecture.md`.

Three stages, deliberately distinguished:

| Stage | State |
|---|---|
| **Deterministic full assembly** | **Exists** — `src/ask_christopher/prompt.py`, Milestone 1 |
| **Full-prefix API testing** | **Done** — measured twice: experiment 0001 (single probe) and 0002 (multi-turn) |
| **Selective retrieval** | **Required, not yet implemented** |

The gate is now open. Retrieval was waiting on a measured baseline to compare against, and there are two. The next move in this phase is an ADR choosing a shape on that evidence.

Prompt caching makes full injection *cheap*; it does not make it *right*. Caching addresses repeated input cost. It does not address context-window occupancy, first-request and post-edit latency, or — most importantly — **relevance and attention dilution**: a visitor asking what an instructional designer does currently receives the whole of `boundaries.md` and `projects.md` alongside the paragraph that answers them.

Retrieval was gated on **having a measured baseline to compare against** — not on a token threshold. Milestone 2 produced it. Candidate shapes, to be chosen on evidence in that ADR:

- Whole-corpus injection with a preprocessing step (smallest change; trades determinism for size)
- Per-file selection driven by question classification (no embeddings required)
- Chunked embedding retrieval (the original Phase 4 assumption; the largest step)

---

## Portfolio consolidation backlog

Moved here from `knowledge/projects.md`, which is corpus rather than planning. Closes the gap between what Christopher has built and what the public repositories show — see `projects.md` → *Evidence vocabulary*.

**Available now**

1. **Publish the ElevenLabs documentation** — voice process, goals, architecture, lessons learned. Moves voice-assistant off *described only*, which is currently the only project asserted with neither public evidence nor a stated reason for its absence. Also supplies its missing *What was learned*.
2. **Consolidate remaining sprint work** from Claude Code and local environments into the public repositories.

**Blocked on the BioHub competition concluding** — a deliberate hold, not a delay

3. Organize the Kaggle profile.
4. Publish the BioHub notebooks.
5. Document the complete project.
6. Link the public Kaggle work from the portfolio and from Ask Christopher.

When these land, the corpus and the public evidence align and most of the qualifying language in `projects.md` can be deleted. **That deletion is the success condition.**

### Related open item

The Kaggle profile URL is deliberately absent from the corpus: it contains Christopher's email prefix, and publishing it would undo the decision to keep the address out of `services.md`. Resolve during item 3.
