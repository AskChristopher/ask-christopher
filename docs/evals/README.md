# docs/evals/

**Status:** Living record
**Authoritative for:** eval run history

Result records from the behavioural eval suite, one JSON file per run, kept over time rather than overwritten.

## Why keep them

A single run tells you almost nothing. A gradual decline in teaching quality across ten prompt revisions is invisible in any one result and obvious in a trend — and prompt edits are exactly the changes that alter behaviour while leaving the diff looking harmless.

Two rates in particular must be tracked **separately**: fabrication and over-refusal. They trade against each other. An assistant that never fabricates because it never answers scores perfectly on one and is useless.

## Producing a record

```bash
python scripts/run_evals.py list                      # describe the suite, send nothing
python scripts/run_evals.py replay --transcript ...   # score responses already recorded
python scripts/run_evals.py live                      # price a live run, send nothing
python scripts/run_evals.py live --confirm            # send it; costs money
python scripts/run_evals.py converse                  # price a conversation run, send nothing
python scripts/run_evals.py converse --confirm        # send it; costs money
python scripts/run_evals.py judge --responses ...     # price a judge run, send nothing
python scripts/run_evals.py judge --responses ... --confirm   # send it; costs money
python scripts/run_evals.py review-template --responses ...   # emit a human review sheet
python scripts/run_evals.py review-record --sheet ...         # validate and record a filled-in sheet
```

`--out` overrides the destination; the default is `docs/evals/<UTC timestamp>-<mode>.json`.

Only `live`, `converse --confirm`, and `judge --confirm` cost money. The review commands never call a model.

**Elicitation and judgement are separate steps on purpose.** Sending the suite is the expensive, non-idempotent half; judging re-runs against the same recorded responses as a rubric or a lens changes, without paying for generation twice.

## Reading a record

| Field | Meaning |
|---|---|
| `mode` | `replay`, `live`, `converse`, `judge`, or `review` |
| `provenance` | Commit, tree cleanliness, case-file hash; live runs add model, effort, and prompt hash |
| `source` | For replay, which transcript and both of its commits |
| `selection` | `total_cases`, `ran`, and every skip with a reason |
| `fidelity` | How many prompts were verbatim vs. paraphrased |
| `scored_verbatim` / `indicative_paraphrase` | Kept apart on purpose — see below |
| `suite` | Per-case status, deterministic verdict, failed checks, response length |
| `judgment_required` | Cases nothing falsified and nothing can confirm |
| `usage` | Live runs only: per-case tokens, latency, cost |

**No response text is retained.** These are for comparison across runs, not a transcript archive — the transcript is the archive.

## Three things a record deliberately does not contain

**A pass rate.** Only 6 of 40 cases carry enough executable checks to be scored lexically. A percentage over the other 34 would be a number that measures nothing, which is worse than no number. `scored` and `unscored` are reported separately so nobody can compute one by accident.

**A `pass` on a judged case.** A `model_judged` or `human_review` case whose lexical checks all pass is recorded as `needs_judgment`. Deterministic checks can *falsify* a judged case. They can never confirm one.

**A merged fidelity count.** In `replay` mode the response was elicited by the experiment's wording, which usually differs from the case's — only 2 of the 7 linked cases match verbatim. A paraphrase-sourced result is evidence about the assistant, not a verdict on the case as written, so the two are counted separately and never summed.

## Skips are part of the result

Every case in the file appears either in `ran` or in `selection.skipped` with a reason:

| Reason | Meaning |
|---|---|
| `multi_turn` | Needs a conversation; a single prompt cannot measure it. Run these with `converse` |
| `single_turn` | `converse` only — the mirror skip; this case is not a conversation |
| `no_recorded_response` | Replay only — the transcript has no turn linked to this case |
| `not_selected` | Excluded by `--only` |
| `human_review` | Judge only — scoring is `human_review`; a model verdict is not the evidence this case asks for |

A silently dropped case is a behaviour nobody is measuring while the summary still reads as complete. The counts are asserted to add up in `tests/test_run_evals.py`.

`converse` and `live` are exact mirrors: every case one runs, the other skips. Between them the 40 cases are partitioned, never double-counted.

## Reading a judge record

`mode: judge` records have a different shape, because they score responses rather than elicit them.

| Field | Meaning |
|---|---|
| `source` | The responses file, and the commit, model, and effort it was **elicited** at — not the judge's |
| `source.cases_changed_since_elicitation` | Whether the rubric applied is the rubric in force when the response was recorded |
| `provenance.judge_prompt_sha256` | The judge prefix. Two runs sharing it are the same panel |
| `counts` | `judged_pass` / `judged_fail` / `judged_uncertain` / `judge_error` |
| `disagreed` | Cases where the lenses reached different verdicts — **the signal to read the case yourself** |
| `adjusted` | Cases where the harness downgraded a verdict whose evidence did not check out |

**A `fail` must quote the response verbatim, and the quote is verified in code.** A `fail` with no findings, or whose every quote is absent from the response, downgrades to `judged_uncertain` — never to a pass. A judge that misbehaved has told you nothing, and reading nothing as "fine" is how a broken judge reports a clean suite.

**Verdicts are not aggregated by majority.** The lenses ask different questions, so two of them finding nothing is not evidence against the third, which was looking elsewhere. Any falsification fails the case; any uncertainty leaves it uncertain; a pass needs all three. [The calibration review](judge-calibration-review.md) records the case that justifies this — majority vote passes it 2–1 the wrong way.

**Findings within one verdict are not independent.** In a `judged_fail`, the finding that drove the verdict is the trustworthy one; the others may be accretion. Measured, not assumed: a borderline clause was passed five times and failed three, on byte-identical text, and **every failure occurred in a response that contained a different, genuine defect.** Once a lens has found something real, it convicts on marginal items it otherwise excuses. So a borderline item's only clean reading is one where nothing else in the response failed — and conversely, a `judged_pass` is stronger evidence than it looks, since it comes from lenses demonstrably willing to convict when primed.

## Reading a review record

`mode: review` records carry a human's reading of the three `human_review` cases. The vocabulary is `reviewed_pass` / `reviewed_fail` / `reviewed_uncertain` / `unreviewed` — disjoint from both the deterministic and judged sets, for the same reason those two are disjoint from each other.

| Field | Meaning |
|---|---|
| `source` | The sheet, the responses file and its hash, and the commit, model, and effort the responses were **elicited** at |
| `provenance` | The commit that recorded the review — kept apart from `source`, which describes elicitation |
| `counts` | `reviewed_pass` / `reviewed_fail` / `reviewed_uncertain` / `unreviewed` |
| `unreviewed` | Cases nobody read, **including cases absent from the sheet entirely** |
| `not_in_sheet` | Cases the responses file contained and the sheet omitted |
| `adjusted` | Verdicts the harness downgraded, with what was claimed and why |
| `reviews` | Per-case verdict, reviewer, rationale, and each quote with its `quote_verified` flag |

**`unreviewed` is the default and a non-zero exit.** A missing entry, an empty verdict, a verdict with no reviewer, or a verdict with no rationale all record as `unreviewed` — never a pass. A `reviewed_fail`, by contrast, is a finding rather than a malfunction and exits clean. The gate is on cases nobody read, not on cases that failed.

**A `reviewed_fail` must quote the response verbatim,** checked with the judge's own `verify_quote`. A fail with no evidence, or whose every quote is absent, downgrades to `reviewed_uncertain` — never to a pass.

**The sheet is bound to the exact text reviewed.** `binding.responses_sha256` plus a per-response digest means editing the responses file after generating the sheet makes `review-record` refuse it outright, rather than attaching a verdict to text nobody read.

## The v1 baseline

Every scoring path exists — deterministic, judged, human, single-turn and conversational — and as of 2026-08-29 **every one of the 40 cases carries a final outcome**. The checkpoint is [`v1-baseline-review.md`](v1-baseline-review.md): what was measured, how the judge record was verified, and the two-case failure map.

Read that document before comparing any later run against "the baseline", because it also records what the baseline cannot support.

## Still missing

Coverage is closed. Calibration and trend are not.

- **Trend.** Each of the 40 cases has been scored exactly once, and one run is the thing this directory exists to say almost nothing about
- **A false-positive and false-negative rate for the panel.** It has found the defects it was pointed at, across a calibration probe and one baseline case. That is still not a detection rate — see the review's *What this does not establish*
- **Independent attestation for single-lens findings.** `cli-presupposition`'s second finding was raised by one lens, in a response that already carried another defect — exactly the contamination condition described above, and unresolved
- **An isolated effort variable.** The baseline elicited at `low` effort and judged at `high`. No run separates the two
