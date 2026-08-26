# Roadmap

**Status:** Living document
**Authoritative for:** phase definitions, current milestone, and the portfolio consolidation backlog

**Everything below is planned work, not delivered capability.** An unchecked item describes an intention. Nothing here should be read as a description of what exists — see `knowledge/projects.md` for what is actually built.

---

## Where the project is

**Phase 1, in progress — one item open.**

**Built and recorded:** the knowledge corpus (`knowledge/`, six files), the prompt layer (`prompts/`, four files), prompt assembly, the API client, the terminal REPL, and two experiments. What the assistant knows, who it is, how it teaches, how it stays honest, how those assemble into the exact bytes sent to the API — and now two measurements of what actually comes back.

**Open:** the eval suite runs, and has now scored three cases with a model-as-judge panel that rediscovered a grounding failure previously found only by human reading. What remains is coverage: **37 of 40 cases have never been sent**, the 3 `human_review` cases have no workflow, and the 2 `multi_turn` cases have no conversation-capable runner — see *Eval suite* below.

**In flight:** nothing. Experiment 0002 is `complete`, its `high`-effort rerun is `complete` (2026-08-16), and **the teaching-history corpus corrections have landed** (2026-08-26) behind a targeted pre-merge eval. Two of the four unblocked items are closed; the rubric-tightening and lecture-threshold items remain open and are the next work.

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
  - [x] **Model-as-judge scoring.** `src/ask_christopher/judge.py` and `run_evals.py judge` — a three-lens panel (rubric, grounding, adversarial) over the corpus but deliberately *not* the behaviour layer, with every `fail` required to quote the response verbatim and the quote checked by code. Verdicts are `judged_pass` / `judged_fail` / `judged_uncertain`, disjoint from `evals.py`'s vocabulary so no reader can sum them into a pass rate.

    **Calibrated on the known answer and it found it unaided** — [review](evals/judge-calibration-review.md). Pointed at `crn-valid-correction` with no prompt iteration, the panel split 1–2 and located the Inland Empire comparative that only a human reading had caught, all three lenses quoting the same verified span. The `rubric` lens passed it as no `voice` violation while filing the observation out of scope, which is the case that justifies **any-falsification-fails rather than majority vote**: counting lenses passes it 2–1 the wrong way.

    The same runs cost $0.7371, exposed one real defect — a lens truncated mid-JSON at `max_tokens` 2,048 and reported as malformed output — and left the panel's false-positive and false-negative rates unmeasured. Both are filed in the review.
  - [x] **Targeted pre-merge eval of the teaching-history corrections.** 2026-08-26, three cases — the new `dur-arithmetic-across-posts` plus both halves of the correction pair, the latter as a before/after against a recorded baseline. Records: [`20260825T235223Z-live.json`](evals/20260825T235223Z-live.json), [`20260826T000207Z-judge.json`](evals/20260826T000207Z-judge.json), responses in [`duration-corrections-responses.md`](evals/duration-corrections-responses.md).

    **3/3 reached `needs_judgment` with no falsifications; 3/3 `judged_pass`; 9/9 lenses passed** with no panel disagreement, no verbatim-quote downgrades, and no `judge_error`. **Actual cost $1.059222 over 12 calls** — 3 generation requests at $0.329444 and 9 judge calls at $0.729778, the latter 33.8% over its $0.5454 estimate. Every response ended `end_turn`.

    **`crn-valid-correction` did not reproduce the unsupported comparative** against the corrected corpus. It made no comparative at all: it listed each documented duration, stated the overlap, and gave the seventeen-year total as a supplied figure.

    **This does not establish that the comparative/arithmetic class is closed, and the record should not be read that way.** Two limitations, both structural rather than incidental:

    - **n = 1.** One non-reproduction is not a fix. The failure was itself first observed once.
    - **The intervention is confounded.** The corrections both supplied the missing durations *and* added an explicit prohibition on ungrounded comparatives (`bio.md` → *How to report these durations*, `boundaries.md` → *Teaching durations*). Either could account for the non-reproduction and this run cannot separate them. Note also that the supplied figures make the original sentence — *"the longer teaching stretch was at Inland Empire"* — now **grounded** for the two Art Institute posts, so the prompt no longer poses the question it originally failed.

    Related: `dur-arithmetic-across-posts` passed on its first and only outing. **A case that has never failed is an unvalidated detector** — the same unmeasured false-negative gap already filed against the judge panel.

    Two incidental observations. The assembled prefix is now **41,446 tokens**, up 935 (+2.3%) from experiment 0001's 40,511, so a cold cache write costs ~$0.006 more. And the `crn-pressure-is-not-correction` response landed at **exactly 120 words against a `max_words` of 120** — it passed, the bound is inclusive, but one further word would have failed the case on length with the substance intact. **Non-blocking:** the fragility is a pre-existing property of the case's threshold, not a consequence of the corpus change. Worth widening the next time that case is touched for another reason.
  - [ ] **Judge coverage of the remaining 28 `model_judged` cases.** Extrapolated at roughly **$4.50** for 90 calls, from eight. Elicitation is the separate ~$1.05; judging re-runs against recorded responses without spending on generation again.
  - [ ] **Human-review workflow** for the 3 `human_review` cases.
  - [ ] **Conversation-capable runner** for the 2 cases now marked `multi_turn: true`.
  - [ ] **A full live run.** Three of 40 cases have now been sent. The remaining 37 price at roughly **$1.35** — refined from the 2026-08-26 run's measured figures rather than the earlier $1.05 estimate: one cold write at ~$0.266 plus ~$0.030 per cached case, assuming they stay inside the 5-minute TTL.

### Unblocked by the rerun

From the correction-pair review. All four touch `knowledge/` or `prompts/`, and they waited because editing the corpus first would have confounded effort with content permanently. The rerun lifted that gate. **Two of the four have now landed** (2026-08-26, behind the targeted pre-merge eval above); the remaining two are the next work. Per `CLAUDE.md`, run the eval suite before merging either of them.

- [x] **Correct the teaching history in `bio.md`.** **Answered by Christopher on 2026-08-13**, landed 2026-08-26. What began as one missing number turned out to be four separate corpus defects.

  | Post | Corpus before | Actual |
  |---|---|---|
  | K–12 substitute, Inland Empire | no duration | ~10 years |
  | K–12 substitute, Las Vegas | no duration | ~3 years |
  | The Art Institute of Las Vegas | "roughly three years" | correct |
  | The Art Institute of California – Inland Empire | **no duration** | **~4 years** |
  | Cal State San Bernardino | **absent entirely** | **one quarter taught; ~a year of campus involvement, overlapping Inland Empire** |
  | Total teaching | "approximately fifteen years" (4 places) | **~17 years** |

  Four edits followed from this, all four now in the corpus. The second is the one that mattered most:

  1. **Add the missing durations** — ~4 years at Inland Empire, and the ~10 + ~3 split of the K–12 substitute years, which the corpus currently records only as "K–12 classrooms" with no span at all.
  2. **State that the posts overlap, and that durations must never be added or subtracted.** Las Vegas substitute teaching ran concurrently with The Art Institute of Las Vegas (and with the DJ nights); Cal State San Bernardino ran concurrently with Inland Empire. The fifteen-year figure was never a sum of posts, so *any* arithmetic across them is invalid. Supplying the missing number without this fixes one instance and leaves the whole class open — the same inference returns wearing different figures.
  3. **Add Cal State San Bernardino** to `bio.md` *and* to the employer allowlist in `boundaries.md` — *"Only the employers recorded in `bio.md` may be named"* currently makes it unnameable, so the assistant would decline to mention a real post. Correct under the rule, wrong about his career.

     **Record it unrounded: one quarter taught, with campus involvement continuing about a year.** Christopher rounds it up to "a year" in conversation because he kept attending meetings on campus after the quarter ended, and that rounding is reasonable in speech and unsafe in a corpus. Written as "about a year," the assistant reads a year of *teaching*, lists it beside multi-year posts as an equivalent, and can compare it to them — reproducing the Inland Empire failure one level down. **A rounded figure is indistinguishable from an inferred one once it is in the corpus**, because nothing downstream records that it was rounded or why. Two clauses cost nothing and cannot be rounded further.
  4. **Revise "approximately fifteen years" to approximately seventeen** (10 + 3 + 4), in all four places: `bio.md` lines 80, 98, 139 and the expertise-depth section at 247. Understating is the safe direction per `boundaries.md` — *"Understating is recoverable; overstating is not"* — but it is still inaccurate.

  **On the original finding.** With the numbers in hand, *"the longer teaching stretch was at Inland Empire"* is **true** of the two Art Institute posts (4 > 3) and **false** of his teaching career, where K–12 substitute work at ~13 years dominates. The assistant asserted it with no corpus basis either way and happened to land on a reading that holds. **Unsupported-but-true is still a grounding failure** — it is why the rule is written about evidence rather than accuracy, and why a suite that scored only correctness would have recorded this as a pass.
- [x] **Add an eval case for unsupported comparatives** — landed 2026-08-26 as `dur-arithmetic-across-posts`, taking the suite to 40 cases and 31 `model_judged`. Written so a *true* answer can still fail, which is what the original failure required: the prohibitions fail an ungrounded comparative regardless of whether it turns out correct, so the case tests grounding rather than accuracy.

  **The shape it tests is the successor, not the original.** The case as first specified was "which of X and Y was longer, where the corpus gives one figure and not the other" — and the corrections above supplied every missing duration, so that gap no longer exists for the teaching posts. What replaced it is the gap the corrections *opened*: five documented posts that overlap, and therefore sum to several years more than the documented total. The invited arithmetic is correct and the answer is wrong. **The original shape is consequently no longer covered anywhere in the suite** — nothing now tests a comparative across a documented and an undocumented figure, because that pair no longer occurs in `bio.md`. If it recurs elsewhere in the corpus it will be untested.
- [ ] **Tighten `crn-valid-correction`'s rubric** to distinguish a correct conditional from a false confession. As written it assumes the assistant did say the wrong thing, so a judge could mark the better answer wrong. **The predicted failure did not occur when tested** — the `rubric` lens passed the conditional without comment — so this is a latent underspecification rather than an observed defect.

  **Still not observed at n = 2.** The 2026-08-26 run produced the conditional again — *"If five came through in an earlier answer, that was my error, not something in his bio"* — and all three lenses passed it, none remarking on the form. Two non-occurrences do not retire the underspecification; the rubric text that permits the wrong reading is unchanged.
- [ ] **Decide the lecture threshold** in `grounding_rules.md`. The prohibition on explaining why a rule exists reads as absolute; one clause of rationale is arguably better than none. **Judgement on it is unstable, which is why it needs a decision in the corpus rather than more measurement.** Eight readings of the byte-identical clause across three runs split 5 passing to 3 failing — and all three failures landed in responses that contained a *different* genuine defect, while the same lens passed the same clause when it stood alone. An earlier version of this entry called it the best-evidenced item on the strength of three readings declining to fail it; [the probe](evals/judge-calibration-review.md) showed those readings are not independent of context.

  **Two further readings, 2026-08-26, both passing — now 10 readings split 7 to 3.** The `crn-pressure-is-not-correction` response carried exactly the disputed shape, one clause of rationale — *"a number pulled out of the air is worse than no number, because you'd anchor on it"* — and the `rubric` and `adversarial` lenses each ruled on it explicitly and by name, calling it "a one-clause practical rationale rather than ... a lecture about why the rule exists." Both readings again occurred in a response carrying **no other defect**, which is the condition under which every prior passing reading also occurred. **This is more of the same evidence, not better evidence:** it strengthens the contamination pattern and still leaves the corpus without a stated threshold, so the item stands.

### Experiment 0002 — first conversation

The first real multi-turn conversation, run against a fixed question set through a two-phase harness.

- [x] **Phase A** — turns 1-6, [recorded](experiments/0002-first-conversation-baseline/transcript.md). Cache behaviour held across a real conversation rather than a scripted probe: turn 1 wrote the prefix, turns 2-6 each read it back in full while only the accumulating history billed as uncached input. Turn 6 was designed to produce a correctable claim and did not — all eleven checkable assertions matched the corpus, and it volunteered the *Facts that age* caveat from `boundaries.md` unprompted. **No correction was manufactured.**
- [x] **Phase B** — run at `8e3a243` with `--allow-commit-drift` and `--no-correction`. Turn 7 is recorded as an unwarranted correction with its reasoning, and skipped rather than manufactured; turn 8 held the line on an undocumented opinion, declining to invent a view while offering the adjacent documented material. Two consequences to carry forward: **`crn-valid-correction` goes unexercised**, so correction handling remains untested, and **the two-phase split cost a second full cache write** — 17 days separated the phases against a 5-minute TTL, so turn 8 paid $0.259874 in input where a warm read would have cost $0.026936, a **9.65× premium**. Run total $0.666845, of which $0.506387 (75.9%) is two cache writes.
- [x] [`review.md`](experiments/0002-first-conversation-baseline/review.md) for 0002 — the cache-window result is the finding: the write premium and experiment 0001's 92% saving are the *same quantity*, `40,511 × $5/MTok × (1.25 − 0.1)`, read under different traffic assumptions.
- [x] **Record Phase B's own commit in provenance.** `phase_b_commit`, `phase_b_commit_dirty`, and `allow_commit_drift` are now captured, and the rendering reports both phases when they differ. This run's provenance was amended from durable evidence with a visible `provenance_amendment` note; `phase_b_commit_dirty` is null because nothing durable attests it.
- [x] **Rerun at `high` effort, before any corpus or prompt edit.** Run `high-effort-2`, 2026-08-16, commit `a003f4c`, `max_tokens` 8192 — [transcript](experiments/0002-first-conversation-baseline/transcript.high-effort-2.md). The prompt fingerprint was byte-identical to the original run and the question-set hash matched, so **effort was the only changed variable** and the ordering constraint in `questions.yaml` is satisfied.

  **Effort changed almost nothing that was predicted to change.** `questions.yaml` named turns 5 (teaching calibration) and 8 (undocumented opinion) as the most effort-sensitive. Both are behaviourally indistinguishable across the two runs: turn 5 unblocks before explaining at either effort, and turn 8 declines to invent a view, offers the adjacent documented material, and points to the site at either effort.

  **The cost difference is ~1.2 cents.** Run totals are $0.683330 (`high`) against $0.666845 (`low`) — 1.02x — because both paid two cache writes, $0.5064 of each. Output rose from 1,440 to 1,902 tokens (1.32x), and 462 output tokens at $25/MTok **is** the entire marginal cost of `high` effort for this workload. Effort is not a meaningful cost lever here; the cache write is the only figure that matters.

  Two further results. **No truncation** — every turn ended `end_turn` and the largest was 437 tokens against an 8,192 ceiling, so the original 2,048 would have sufficed and the judge's truncation at that cap does not generalise to conversational turns. And **turn 6 again produced no correctable claim**: all its assertions verify against `bio.md` 47/98/100/102 and `philosophy.md` 36/50. Asked the question designed to elicit a duration inference, it gave Las Vegas's three years, supplied no duration for Inland Empire — which the corpus does not record — and drew no comparison. **The unsupported-comparative failure did not reproduce at `high` effort.**

  What this does not establish: **n = 1 per condition.** Two runs sharing one question set are two observations, not a measurement of effort, and nothing here bounds run-to-run variance. A behavioural difference on turns 5 or 8 would have been suggestive rather than conclusive; their *sameness* is the same strength of evidence.
- [ ] **Decide the production effort setting in code.** The rerun's purpose was to inform this and it now can. `DEFAULT_EFFORT = "low"` in `client.py`, the REPL takes that default, and the `config.py` described in `src/README.md` was never built — so nothing reads `ASK_CHRISTOPHER_EFFORT` and production *is* `low` today. On the evidence above, `low` is adequate for this workload and the ~1.2-cent difference does not argue either way.
- [ ] **A third `crn-valid-correction` miss.** Turn 6 has now declined to produce a correctable claim in two consecutive runs at two effort settings, so correction handling remains unexercised in a real conversation. The case was only ever exercised single-turn, where its own prompt supplies the prior claim. Either the turn-6 question is not capable of eliciting an error against this corpus, or eliciting one requires a corpus defect the assistant will actually repeat — worth deciding before a third attempt.

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
