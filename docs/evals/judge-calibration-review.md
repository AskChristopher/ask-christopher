# Judge calibration — the panel's first two live runs

**Status:** Complete
**Authoritative for:** what the model-as-judge panel has been observed to do, and what it has not
**Runs:** 2026-08-13, `e30f451` (dirty), `claude-opus-5`, effort `high`, 3 lenses, 9 calls attempted, **$0.7371 recorded**
**Records:** [`judge-calibration.json`](judge-calibration.json) · [`judge-calibration-run2.json`](judge-calibration-run2.json)
**Judged material:** [`correction-pair-responses.json`](correction-pair-responses.json), elicited 2026-08-12 at `d52cfa4`, effort `low`

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

## Cost, measured

| | Run 1 | Run 2 |
|---|---|---|
| Calls recorded | 5 | 3 |
| Recorded cost | $0.39951 | $0.337618 |
| Estimate | $0.419786 | $0.296566 |
| Estimate error | 5.1% high | 12.2% low |
| Of which one cache write | $0.19393 (48.5%) | $0.19404 (57.5%) |

The judge prefix is **30,497 tokens** — preamble plus corpus, against the assistant's measured 40,511 for the full prefix. Excluding the behaviour layer is a correctness decision, not an economy, but it costs about a quarter less per write.

**Experiment 0002's cache-window finding reproduced here without being looked for.** The two runs sat 8.75 hours apart against a 5-minute TTL, so each paid a full write, and over half of run 2's total is that one write. Within a warm window the marginal cost of a lens call is small: the six warm calls across both runs averaged **$0.0476**, against $0.2289 and $0.2225 for the two cold ones.

Extrapolating to the 30 `model_judged` cases at three lenses — 90 calls, one write, the rest warm — gives roughly **$4.50**, about 4× the ~$1.05 priced for elicitation. **That is an extrapolation from eight calls, not a measurement**, and it assumes sequential execution keeps every call inside the TTL. It also assumes the panel's output length on the correction pair is representative, which two cases cannot establish.

## What this does not establish

- **No case was promoted to `pass`.** `judged_pass` is a distinct status by construction, disjoint from `evals.py`'s vocabulary so the two can never be summed. Run 2 produced a judged verdict on `crn-pressure-is-not-correction`; the suite's deterministic view of it is unchanged.
- **n = 1 per lens per case.** Nothing here characterises the panel's stability. Re-running the same response through the same lens is the cheapest missing measurement and has not been done.
- **The false-positive rate is unmeasured, and the false-negative rate more so.** No response known to be clean was fed in to see whether a lens invents a defect, and no response with a *planted* defect was used to measure what the panel misses. Run 1 caught the one flaw it was pointed at; that is one true positive, not a detection rate.
- **This is calibration on a known answer.** The panel was not tuned to reach it — first run, no iteration, prefix hash unchanged into run 2 — which is the strongest form of the claim the setup can support, and it is still not a test on unseen material.
- **Excluding the behaviour layer from the judge prefix remains an untested design claim.** No A/B was run against a judge holding the persona and grounding instructions, so the argument that such a judge grades intent rather than output is reasoning, not evidence.
- **Both runs judged `low`-effort responses with a `high`-effort judge.** Neither says anything about the production-effort responses the rerun will produce.
- **`commit_dirty: true` on both runs.** `e30f451` does not attest the code that ran — the judge was uncommitted at the time. `judge_prompt_sha256` does attest the prefix, and `cases_sha256` matches the fingerprint recorded at elicitation, so the rubric applied is the rubric that was in force.

## Filed

1. **The lost call's spend is not in the record.** Run 1 attempted six calls and `usage.calls` reports five; the truncated lens is absent from the cost total, which is therefore an understatement of roughly $0.07. **A failed call is billed and should be recorded as spent** — the current shape makes an expensive failure look free.
2. **Repeat-sampling measurement** — same response, same lens, n ≥ 3 — before the panel is trusted on cases with no human reading behind them.
3. **A planted-defect case**, to put a number on what the panel misses rather than only on what it catches.
4. **The lecture threshold in `grounding_rules.md`** now has three independent readings behind it and should be decided rather than left contestable. It stays queued behind the production-effort rerun with the other `prompts/` and `knowledge/` edits.
