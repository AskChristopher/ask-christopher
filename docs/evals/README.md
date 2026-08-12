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
```

`--out` overrides the destination; the default is `docs/evals/<UTC timestamp>-<mode>.json`.

## Reading a record

| Field | Meaning |
|---|---|
| `mode` | `replay` or `live` |
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

## Still missing

The runner exists; scoring does not, for most of the suite.

- **Model-as-judge scoring** — the 30 `model_judged` cases stay `needs_judgment` until it lands
- **A human-review workflow** for the 3 `human_review` cases
- **A conversation-capable runner** for the 2 `multi_turn` cases
