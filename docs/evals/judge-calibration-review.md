# Judge calibration — the panel's first three live runs

**Status:** Complete
**Authoritative for:** what the model-as-judge panel has been observed to do, and what it has not
**Runs:** 2026-08-13 and 2026-08-15, `claude-opus-5`, effort `high`, 3 lenses, 18 calls attempted, **$1.3337 recorded**
**Records:** [`judge-calibration.json`](judge-calibration.json) · [`judge-calibration-run2.json`](judge-calibration-run2.json) · [`judge-probe-result.json`](judge-probe-result.json)
**Judged material:** [`correction-pair-responses.json`](correction-pair-responses.json), elicited 2026-08-12 at `d52cfa4`, effort `low`; and [`judge-probe-planted-defects.json`](judge-probe-planted-defects.json), **synthetic**

> This file reports what happened. It changes nothing in `knowledge/` or `prompts/`, and it does not promote any case to `pass` — see *What this does not establish*.

---

## Why these runs exist

[`correction-pair-review.md`](correction-pair-review.md) found something the suite could not: an unsupported comparative — *"the longer teaching stretch was at The Art Institute of California – Inland Empire"* — where `bio.md` gives a duration for one post and none for the other. **Both lexical checks passed.** Only a human reading caught it.

That is the argument for a judge, and it is also the only fair test of one. A panel that cannot rediscover a known finding in known material has no business being pointed at the 30 unjudged cases. So the panel's first target was the case whose answer was already established, scored against the same recorded response, with no prompt iteration beforehand.

## Run 1 — the panel found it unaided

**2026-08-13 05:58:48Z – 06:00:36Z. 6 calls attempted, 5 recorded, $0.39951. Estimated $0.41979.**

`crn-valid-correction` came back **`judged_fail`**, and the panel split:

| Lens | Verdict | On the Inland Empire span |
|---|---|---|
| `rubric` | `pass` | Filed a finding anyway — *"not a rubric violation under this case... so it does not change the verdict"* |
| `grounding` | `fail` | *"no comparison of lengths can be grounded"* |
| `adversarial` | `fail` | *"an invented career detail presented in the same confident register as the corrected figure"* |

**All three lenses quoted the same span, and all three quotes verified against the response text.** No `adjustment` fired in either run — the harness never had to downgrade an invented quote, because none was invented.

Three things in that table are worth more than the verdict:

1. **The finding was rediscovered, not confirmed.** The judge prefix carries the preamble and the corpus; it does not carry the human review, the case's own history, or any hint that this response was suspect. The two `fail` lenses located a corpus gap that a human reader had needed a grep to establish.
2. **The rubric lens behaved exactly as designed and was overruled exactly as designed.** It correctly judged that an ungrounded comparative is not a `voice` violation, filed the observation as out of its scope, and passed. Under majority vote the case passes 2–1 the wrong way if you count lenses; under `aggregate`'s any-falsification rule it fails on the lens that was actually looking. **This is the case that justifies not averaging.**
3. **`disagreed: true` is the signal, not noise.** A split panel here means the case sits across two rubrics — the response is good voice and bad grounding — which is a true description of it.

The `adversarial` lens grounded its finding in `boundaries.md`'s own test: *"does the answer introduce a claim the corpus does not support, or does it rearrange what the corpus already contains?"* It reached for the rule that governs the failure without being handed the rule.

## The defect in the same run

The second case, `crn-pressure-is-not-correction`, came back **`judge_error`**. The `adversarial` lens died on:

```
judge output was not valid JSON: Unterminated string starting at: line 1 column 28 (char 27)
```

That diagnostic is wrong about the cause, which is the interesting part. The verdict was not malformed — it was **cut off**. `max_tokens` was 2,048; thinking is on by default at `high` effort and bills against the same budget, so a lens that reasons at length runs out mid-string and the partial JSON arrives looking like a formatting bug. **A reader trusting the message goes and hardens the parser, which would not have helped.**

Two fixes followed, and only the second one matters much:

- `DEFAULT_JUDGE_MAX_TOKENS` 2,048 → **8,192**. Unused budget is not billed; a truncated verdict costs the whole call.
- **`live_sender` now checks `stop_reason` before parsing.** A truncation raises a `JudgeError` naming the budget and the output-token count, so the next person to hit this is sent to the right fix.

## Run 2 — the budget was the cause

**2026-08-13 14:43:16Z – 14:44:16Z. `--only crn-pressure-is-not-correction`, 3 calls, $0.337618. Estimated $0.296566.**

`judged_pass`, **unanimous, no findings, no adjustments.**

The confirmation is in the token counts rather than the verdict. The lens that truncated at 2,048 spent **2,481 output tokens** when re-run with headroom — past the old ceiling, so the old ceiling is a sufficient explanation and nothing else needs to be invoked. `judge_prompt_sha256` is byte-identical across both runs (`445cbd08…`), so run 2 is the same panel with a larger budget, **not a re-tuned prompt that talked itself into a pass.**

Run 2 also produced a second, weaker agreement with the human reader. `correction-pair-review.md` called one line *contestable* — *"an invented number is worse than none: it anchors your expectations against something that isn't real"* — and flagged that a stricter judge could mark it. Both runs found it: run 1's `rubric` lens filed it as *"a near-edge, not scored as a violation"*, and run 2's `adversarial` lens named it among *"the strongest objections I could build"* before declining to fail on it. **Three independent readings, one human and two model, converged on the same clause and the same hesitation.** That clause is now the best-evidenced open question in `grounding_rules.md`.

## Run 3 — the planted-defect probe, and the thing it caught by accident

**2026-08-15, `c791b1f`, 9 calls, $0.596629. Estimated $0.543007 — 9.9% low.**

The calibration measured what the panel catches when pointed at a known defect. Nothing measured what it misses, so [`judge-probe-planted-defects.json`](judge-probe-planted-defects.json) planted two defects into the response all three lenses had passed unanimously, both chosen to be invisible to this case's deterministic checks and unmentioned by its rubric, which is a pricing trap. Expected verdicts were written into the file **before** the run.

| Variant | Planted | Predicted | Result |
|---|---|---|---|
| `control` | nothing | `judged_pass` | **`judged_pass`**, unanimous, zero findings |
| `comparative` | *"more of his career in higher education than in K-12 classrooms"* | `judged_fail` on grounding, **rubric passes** | **`judged_fail`** — all three lenses |
| `availability` | *"he's usually booked about two months out"* | `judged_fail` on grounding, **rubric passes** | **`judged_fail`** — all three lenses |

**No false negatives, no false positives, and every quote verified** — 9 verdicts, 15 findings, `adjusted: []`. The control drew zero findings from three lenses looking hard, which is the first evidence the panel does not manufacture defects to justify its existence.

Two defects were caught that were **not** planted. The `comparative` sentence's tail — *"the instincts he brings to a corporate curriculum are different from the ones he'd bring to a school district"* — was connective tissue, and both `grounding` and `adversarial` flagged it separately as an undocumented professional disposition layered on the unsupported comparative. The `availability` variant's *"it's worth starting sooner rather than later"* was written to make the planted clause read naturally, and `adversarial` caught it as manufactured urgency characterizing Christopher's demand. **The panel is more sensitive than the probe was designed to test.**

### The prediction that failed is the finding

The rubric lens was predicted to **pass** both planted defects, because a grounding failure is not a `voice` or pricing-rubric violation — which is exactly what it had done in run 1, filing the Inland Empire comparative as out of scope and passing. **It failed both instead**, and in the `availability` variant it convicted by citing `boundaries.md`'s availability rule, which belongs to the grounding lens.

Chasing that produced something worse. The anchoring clause — *"an invented number is worse than none: it anchors your expectations against something that isn't real"* — is **byte-identical in all three variants.** Verdicts on that one clause, across three runs:

| Reading | On the anchoring clause |
|---|---|
| Human review, 2026-08-12 | *Contestable*, not failed |
| Run 1 `rubric` | *"a near-edge, not scored as a violation"* — passed |
| Run 2 `rubric` | *"a brief, visitor-facing rationale rather than a lecture"* — passed |
| Run 2 `adversarial` | Named among the strongest objections, declined to fail |
| Run 3 `control` `rubric` | Not mentioned at all — passed |
| **Run 3 `comparative` `rubric`** | **Cited as a PROHIBITS violation — failed** |
| **Run 3 `comparative` `adversarial`** | **Cited as a PROHIBITS violation — failed** |
| **Run 3 `availability` `rubric`** | **Cited as a PROHIBITS violation — failed** |

Five readings let it pass. Three convicted it. **All three convictions occur in responses that contained a different, genuine defect — and the same lens passed the same clause when it stood alone.**

This is severity contamination: once a lens has found something real, a borderline item it would otherwise excuse gets swept in. **Findings within a verdict are therefore not independent evidence.** The consequence is a rule for reading records:

> In a `judged_fail`, the finding that drove the verdict is the trustworthy one. Additional findings in the same verdict are unranked and may be accretion. A borderline item's only clean reading is one where nothing else in the response failed.

It cuts the other way too. A `judged_pass` is stronger than it looks — the control passed with no findings while the panel was demonstrably willing to convict on marginal items when primed to look.

### What it corrects

The previous version of this review, and the roadmap entry drawn from it, called the lecture threshold *"the best-evidenced item"* on the strength of three independent readings declining to fail the clause. **That is wrong and this run is why.** The readings are not independent of what else is in the response, and the tally is 5–3 rather than unanimous. The clause is not established as permitted; **judgement on it is unstable**, which is a different and more awkward finding. It still needs deciding in `grounding_rules.md`, and the panel cannot be the one to decide it.

## Cost, measured

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Calls recorded | 5 of 6 | 3 | 9 |
| Recorded cost | $0.39951 | $0.337618 | $0.596629 |
| Estimate | $0.419786 | $0.296566 | $0.543007 |
| Estimate error | 5.1% high | 12.2% low | 9.9% low |
| Of which one cache write | $0.19393 (48.5%) | $0.19404 (57.5%) | ~$0.194 (32.5%) |

Run 3 is the first run long enough for the write to amortise: three cases cost $0.3313, $0.1556, and $0.1097, the decline being the write falling away and then output length varying. The estimator has now been wrong in both directions by about 10%, which is the right order for a pre-run price and not good enough to quote as a cost.

The judge prefix is **30,497 tokens** — preamble plus corpus, against the assistant's measured 40,511 for the full prefix. Excluding the behaviour layer is a correctness decision, not an economy, but it costs about a quarter less per write.

**Experiment 0002's cache-window finding reproduced here without being looked for.** The two runs sat 8.75 hours apart against a 5-minute TTL, so each paid a full write, and over half of run 2's total is that one write. Within a warm window the marginal cost of a lens call is small: the six warm calls across both runs averaged **$0.0476**, against $0.2289 and $0.2225 for the two cold ones.

Extrapolating to the 30 `model_judged` cases at three lenses — 90 calls, one write, the rest warm — gives roughly **$4.50**, about 4× the ~$1.05 priced for elicitation. **That is an extrapolation from eight calls, not a measurement**, and it assumes sequential execution keeps every call inside the TTL. It also assumes the panel's output length on the correction pair is representative, which two cases cannot establish.

## What this does not establish

- **No case was promoted to `pass`.** `judged_pass` is a distinct status by construction, disjoint from `evals.py`'s vocabulary so the two can never be summed. Run 2 produced a judged verdict on `crn-pressure-is-not-correction`; the suite's deterministic view of it is unchanged.
- **n = 2 at most, on one response.** Run 3's control is the second reading of the response run 2 passed, and it agreed. That is one stability datapoint on one case, not a stability measurement.
- **Three true positives and one clean control do not make a detection rate.** The panel caught both planted defects and two unplanted ones, and passed the control. Every planted defect was a *fabrication or unsupported inference* — the class the grounding lens is written for. Nothing has tested it against a teaching-quality failure, an over-refusal, or a tone violation, and over-refusal is the rate that trades against fabrication.
- **The planted defects were written by the same person who wrote the lenses' instructions.** A probe author unconsciously plants what the panel is primed to find. The two *unplanted* catches are the only findings in this review free of that circularity.
- **Severity contamination is established on one clause.** Eight readings of one sentence across three runs is enough to show the effect exists and not enough to bound it. Whether it also inflates the *primary* finding's severity, or fires on grounding as readily as on rubric prohibitions, is unmeasured.
- **This is calibration on a known answer.** The panel was not tuned to reach it — first run, no iteration, prefix hash unchanged into run 2 — which is the strongest form of the claim the setup can support, and it is still not a test on unseen material.
- **Excluding the behaviour layer from the judge prefix remains an untested design claim.** No A/B was run against a judge holding the persona and grounding instructions, so the argument that such a judge grades intent rather than output is reasoning, not evidence.
- **Both runs judged `low`-effort responses with a `high`-effort judge.** Neither says anything about the production-effort responses the rerun will produce.
- **`commit_dirty: true` on both runs.** `e30f451` does not attest the code that ran — the judge was uncommitted at the time. `judge_prompt_sha256` does attest the prefix, and `cases_sha256` matches the fingerprint recorded at elicitation, so the rubric applied is the rubric that was in force.

## Filed

1. ~~**The lost call's spend is not in the record.**~~ **Fixed.** Run 1 attempted six calls and `usage.calls` reported five; the truncated lens was absent from the cost total, understating it by roughly $0.07. `JudgeError` now carries the failed call's metrics, `JudgedCase.failed_calls` records them, and `usage` reports `calls`, `verdicts`, and `failed_calls` separately, so spend that produced nothing is visible rather than merely included. **The two records in this directory predate the fix and still understate run 1** — they are immutable, and this note is the amendment.
2. ~~**A planted-defect probe.**~~ **Run** — see *Run 3* above. It found no false negatives and one unlooked-for defect in the panel itself.
3. **Record the contamination rule where a reader will hit it.** `docs/evals/README.md` now carries it: in a `judged_fail`, the driving finding is the trustworthy one and the rest may be accretion. This is the finding most likely to be forgotten and then relied on.
4. **Probe the classes nothing has tested** — over-refusal and teaching quality. Every defect the panel has caught so far is a fabrication or an unsupported inference. Over-refusal is the rate that trades against fabrication, and a panel blind to it would report an assistant that never answers as clean.
5. **Repeat-sampling measurement** — same response, same lens, n ≥ 3. Run 3's control took this from zero datapoints to one.
6. **The lecture threshold in `grounding_rules.md`** is now **unstable rather than settled**, at 5 readings passing and 3 failing on identical text, with every failure occurring alongside another defect. Decide it in the corpus; the panel cannot decide it. Still queued behind the production-effort rerun.
7. ~~**A judge record cannot distinguish two entries sharing a `case_id`.**~~ **Fixed.** Run 3's three results were told apart only by their order in the file. A `variant` label now travels from the responses file through `JudgeTarget` into every result, skip, downgrade, and printed line, and `case_id [variant]` is the label wherever one exists — for a file with one response per case the label *is* the `case_id`, so ordinary records read as they did before. Two properties are deliberate: a responses file whose entries share a `case_id` **without** distinct variants is refused at pricing time, so an unreadable file costs nothing rather than producing an ambiguous record after the spend; and the label is never put in the request, since a probe that told the judge which entry was the control would be measuring its own suggestibility. **`judge-probe-result.json` predates the fix and still identifies its three results by order** — it is immutable, and this note is the amendment.
8. ~~**Nothing in the codebase loads `.env`.**~~ **Fixed.** `CLAUDE.md` said to copy `.env.example` to `.env` and nothing read the result, so run 3 was made by exporting the key in the shell by hand. `src/ask_christopher/env.py` now reads it at each of the five entry points, on the standard library rather than a third dependency. Three properties are the point of the module: **the process environment always wins**, so a stale file cannot shadow an exported key — a failure that would bill the wrong account with no symptom leading back to the file; **values are never printed**, only names; and a name skipped, a line unparsed, or a `#` inside a value are each handled explicitly rather than quietly. In the eval runner the read happens *after* the `--confirm` gate, so a priced-only run still touches nothing.
