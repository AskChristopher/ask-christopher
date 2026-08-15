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
python scripts/run_evals.py judge --responses ...     # price a judge run, send nothing
python scripts/run_evals.py judge --responses ... --confirm   # send it; costs money
```

`--out` overrides the destination; the default is `docs/evals/<UTC timestamp>-<mode>.json`.

**Elicitation and judgement are separate steps on purpose.** Sending the suite is the expensive, non-idempotent half; judging re-runs against the same recorded responses as a rubric or a lens changes, without paying for generation twice.

## Reading a record

| Field | Meaning |
|---|---|
| `mode` | `replay`, `live`, or `judge` |
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

**A pass rate.** Only 6 of 39 cases carry enough executable checks to be scored lexically. A percentage over the other 33 would be a number that measures nothing, which is worse than no number. `scored` and `unscored` are reported separately so nobody can compute one by accident.

**A `pass` on a judged case.** A `model_judged` or `human_review` case whose lexical checks all pass is recorded as `needs_judgment`. Deterministic checks can *falsify* a judged case. They can never confirm one.

**A merged fidelity count.** In `replay` mode the response was elicited by the experiment's wording, which usually differs from the case's — only 2 of the 7 linked cases match verbatim. A paraphrase-sourced result is evidence about the assistant, not a verdict on the case as written, so the two are counted separately and never summed.

## Skips are part of the result

Every case in the file appears either in `ran` or in `selection.skipped` with a reason:

| Reason | Meaning |
|---|---|
| `multi_turn` | Needs a conversation; a single prompt cannot measure it |
| `no_recorded_response` | Replay only — the transcript has no turn linked to this case |
| `not_selected` | Excluded by `--only` |

A silently dropped case is a behaviour nobody is measuring while the summary still reads as complete. The counts are asserted to add up in `tests/test_run_evals.py`.

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

## Still missing

- **Coverage.** 37 of 39 cases have never been sent; two have been judged
- **A human-review workflow** for the 3 `human_review` cases
- **A conversation-capable runner** for the 2 `multi_turn` cases
- **A false-positive and false-negative rate for the panel.** It has caught the one defect it was pointed at. That is not a detection rate — see the review's *What this does not establish*
