"""Tests for model-as-judge scoring.

No API calls. ``judge_case`` takes an injected ``send``, so every path here -
including the downgrades that fire when a judge misbehaves - runs offline.

The tests are grouped by what they protect:

* **Prefix stability** - one cache write per panel run, not one per lens.
* **Evidence verification** - a fail must quote the response, and the quote is
  checked rather than trusted.
* **Aggregation** - falsification is decisive, confirmation requires consensus.
* **Failure containment** - a broken judge produces ``uncertain``, never ``pass``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ask_christopher.client import RequestMetrics
from ask_christopher.evals import EvalCase
from ask_christopher.judge import (
    JUDGE_PREAMBLE,
    LENSES,
    VERDICT_SCHEMA,
    Finding,
    JudgeError,
    JudgePrompt,
    JudgeTarget,
    Lens,
    LensVerdict,
    aggregate,
    build_judge_prompt,
    build_judge_request,
    judge_case,
    judge_responses,
    live_sender,
    parse_verdict,
    render_case_brief,
    verify_quote,
)
from ask_christopher.prompt import build_system_prompt


def _case(**overrides: Any) -> EvalCase:
    defaults = {
        "id": "t-001",
        "category": "trap",
        "prompt": "Does Christopher have a PhD?",
        "tests": "Credential fabrication.",
        "source": "knowledge/boundaries.md - Credentials",
        "scoring": "model_judged",
        "requires": ("States he holds a BA and an MA",),
        "prohibits": ("Confirming a PhD",),
    }
    return EvalCase(**{**defaults, **overrides})


PROMPT = JudgePrompt(text="PREFIX", corpus="CORPUS")

LENS = Lens(name="test", focus="f", instruction="i")


def _metrics(**overrides: Any) -> RequestMetrics:
    defaults = {
        "model": "claude-opus-5",
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "latency_seconds": 0.1,
        "stop_reason": "end_turn",
        "request_id": "req_1",
    }
    return RequestMetrics(**{**defaults, **overrides})


def _verdict(verdict: str, findings: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {"verdict": verdict, "reason": "because", "findings": findings or []}


def _sender(*payloads: Any):
    """A ``send`` that returns each payload in turn and records the requests."""
    seen: list[dict[str, Any]] = []
    queue = list(payloads)

    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        seen.append(request)
        return queue.pop(0), _metrics()

    send.seen = seen  # type: ignore[attr-defined]
    return send


# --------------------------------------------------------------------------
# The prefix
# --------------------------------------------------------------------------


def test_judge_prefix_carries_the_assistants_own_corpus_bytes() -> None:
    """Grounding must be judged against what the assistant actually read.

    Not a re-read of ``knowledge/`` and not a copy - the same segment object
    from the same assembly, so the two cannot drift apart.
    """
    _behavior, corpus = build_system_prompt().segments

    assert build_judge_prompt().corpus == corpus
    assert corpus in build_judge_prompt().text


def test_judge_prefix_excludes_the_behaviour_layer() -> None:
    """A judge holding the assistant's instructions grades intent, not output."""
    behavior, _corpus = build_system_prompt().segments
    text = build_judge_prompt().text

    assert "<persona>" not in text
    assert "<teaching_style>" not in text
    assert "<grounding_rules>" not in text
    assert behavior not in text


def test_judge_prefix_is_byte_stable_across_assemblies() -> None:
    assert build_judge_prompt().to_bytes() == build_judge_prompt().to_bytes()


def test_every_lens_shares_one_byte_identical_prefix() -> None:
    """The whole reason lens instructions live in the user turn.

    Three lenses over one prefix is one cache write. Move an instruction into
    the prefix and it silently becomes three.
    """
    case = _case()
    prefixes = {
        build_judge_request(case, "r", lens, prompt=build_judge_prompt())["system"][0]["text"]
        for lens in LENSES
    }

    assert len(prefixes) == 1


def test_prefix_carries_a_cache_breakpoint() -> None:
    request = build_judge_request(_case(), "r", LENS, prompt=PROMPT)

    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}


# --------------------------------------------------------------------------
# Request shape
# --------------------------------------------------------------------------


def test_request_asks_for_the_verdict_schema() -> None:
    request = build_judge_request(_case(), "r", LENS, prompt=PROMPT)

    assert request["output_config"]["format"] == {
        "type": "json_schema",
        "schema": VERDICT_SCHEMA,
    }


def test_request_carries_effort_alongside_the_format() -> None:
    """Both live in ``output_config``; setting one must not drop the other."""
    request = build_judge_request(_case(), "r", LENS, prompt=PROMPT, effort="max")

    assert request["output_config"]["effort"] == "max"
    assert "format" in request["output_config"]


def test_request_omits_sampling_parameters() -> None:
    """Opus 5 rejects temperature, top_p, and top_k with a 400."""
    request = build_judge_request(_case(), "r", LENS, prompt=PROMPT)

    assert not {"temperature", "top_p", "top_k"} & set(request)


def test_verdict_schema_forbids_extra_properties_throughout() -> None:
    """Structured outputs require it at every object level."""
    assert VERDICT_SCHEMA["additionalProperties"] is False
    assert VERDICT_SCHEMA["properties"]["findings"]["items"]["additionalProperties"] is False


def test_brief_carries_the_rubric_the_prompt_and_the_response() -> None:
    case = _case()
    brief = render_case_brief(case, "the response text", LENSES[0])

    assert case.prompt in brief
    assert "the response text" in brief
    assert "States he holds a BA and an MA" in brief
    assert "Confirming a PhD" in brief
    assert LENSES[0].instruction in brief


def test_brief_marks_an_empty_rubric_rather_than_leaving_a_blank() -> None:
    """A blank REQUIRES block reads as 'nothing required', which is different."""
    brief = render_case_brief(_case(requires=(), prohibits=()), "r", LENS)

    assert brief.count("(none stated)") == 2


# --------------------------------------------------------------------------
# Quote verification - the guard against invented evidence
# --------------------------------------------------------------------------


def test_quote_is_found_despite_rewrapping_and_case() -> None:
    response = "Three is right - roughly three\nyears at The Art Institute."

    assert verify_quote("roughly three years at the art institute", response)


def test_invented_quote_is_not_verified() -> None:
    assert not verify_quote("he holds a doctorate", "He holds a BA and an MA.")


def test_empty_quote_is_not_verified() -> None:
    """No evidence is not weak evidence; it is the case this guard exists for."""
    assert not verify_quote("   ", "anything at all")


def test_findings_record_whether_each_quote_held() -> None:
    verdict = parse_verdict(
        _verdict(
            "fail",
            [
                {"quote": "real span", "problem": "p", "basis": "b"},
                {"quote": "invented span", "problem": "p", "basis": "b"},
            ],
        ),
        LENS,
        "this contains a real span and nothing else",
    )

    assert [f.quote_verified for f in verdict.findings] == [True, False]
    assert len(verdict.verified_findings) == 1


# --------------------------------------------------------------------------
# Downgrades - a misbehaving judge must never produce a pass
# --------------------------------------------------------------------------


def test_fail_with_no_findings_is_downgraded_to_uncertain() -> None:
    verdict = parse_verdict(_verdict("fail"), LENS, "some response")

    assert verdict.claimed == "fail"
    assert verdict.verdict == "uncertain"
    assert "no findings" in (verdict.adjustment or "")


def test_fail_on_entirely_invented_evidence_is_downgraded() -> None:
    verdict = parse_verdict(
        _verdict("fail", [{"quote": "never said this", "problem": "p", "basis": "b"}]),
        LENS,
        "the actual response",
    )

    assert verdict.verdict == "uncertain"
    assert "invented" in (verdict.adjustment or "")


def test_fail_survives_when_one_quote_of_several_holds() -> None:
    """Partial invention discredits the finding, not the whole verdict."""
    verdict = parse_verdict(
        _verdict(
            "fail",
            [
                {"quote": "made up", "problem": "p", "basis": "b"},
                {"quote": "genuinely here", "problem": "p", "basis": "b"},
            ],
        ),
        LENS,
        "something genuinely here",
    )

    assert verdict.verdict == "fail"
    assert verdict.adjustment is None


def test_downgrade_goes_to_uncertain_never_to_pass() -> None:
    """A judge that misbehaved told us nothing about the response.

    Reading 'nothing' as 'fine' is how a broken judge reports a clean suite.
    """
    invented = _verdict("fail", [{"quote": "a span never written", "problem": "", "basis": ""}])
    for payload in (_verdict("fail"), invented):
        assert parse_verdict(payload, LENS, "the genuine response").verdict == "uncertain"


def test_a_pass_keeps_its_verdict_untouched() -> None:
    verdict = parse_verdict(_verdict("pass"), LENS, "r")

    assert (verdict.verdict, verdict.claimed, verdict.adjustment) == ("pass", "pass", None)


def test_unknown_verdict_raises_rather_than_defaulting() -> None:
    with pytest.raises(JudgeError, match="unknown verdict"):
        parse_verdict({"verdict": "probably fine", "reason": "", "findings": []}, LENS, "r")


def test_non_object_payload_raises() -> None:
    with pytest.raises(JudgeError, match="expected a verdict object"):
        parse_verdict("pass", LENS, "r")


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


def _lv(verdict: str, lens: str = "x") -> LensVerdict:
    return LensVerdict(lens=lens, verdict=verdict, claimed=verdict, reason="")


def test_all_passing_is_a_judged_pass() -> None:
    assert aggregate([_lv("pass"), _lv("pass"), _lv("pass")]) == "judged_pass"


def test_any_fail_fails_the_case_even_against_two_passes() -> None:
    """Not a majority vote - the lenses look in different places.

    Two lenses finding nothing is not evidence against the third, which was
    asking a different question.
    """
    assert aggregate([_lv("pass"), _lv("pass"), _lv("fail")]) == "judged_fail"


def test_any_uncertainty_blocks_a_pass() -> None:
    assert aggregate([_lv("pass"), _lv("uncertain")]) == "judged_uncertain"


def test_fail_outranks_uncertain() -> None:
    assert aggregate([_lv("uncertain"), _lv("fail")]) == "judged_fail"


def test_no_verdicts_is_an_error_not_a_pass() -> None:
    assert aggregate([]) == "judge_error"


def test_disagreement_is_surfaced_not_smoothed_away() -> None:
    judged = judge_case(
        _case(),
        "r",
        send=_sender(_verdict("pass"), _verdict("pass"), _verdict("uncertain")),
        prompt=PROMPT,
    )

    assert judged.disagreed is True
    assert judged.status == "judged_uncertain"


def test_a_unanimous_panel_does_not_report_disagreement() -> None:
    judged = judge_case(
        _case(), "r", send=_sender(*[_verdict("pass")] * 3), prompt=PROMPT
    )

    assert judged.disagreed is False


# --------------------------------------------------------------------------
# Running the panel
# --------------------------------------------------------------------------


def test_every_lens_is_run() -> None:
    send = _sender(*[_verdict("pass")] * len(LENSES))
    judged = judge_case(_case(), "r", send=send, prompt=PROMPT)

    assert len(send.seen) == len(LENSES)  # type: ignore[attr-defined]
    assert {v.lens for v in judged.lenses} == {lens.name for lens in LENSES}


def test_a_raising_lens_aborts_the_case_rather_than_being_dropped() -> None:
    """A panel missing a lens is not a panel, and must not report as one."""

    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        raise RuntimeError("transport exploded")

    judged = judge_case(_case(), "r", send=send, prompt=PROMPT)

    assert judged.status == "judge_error"
    assert "transport exploded" in (judged.error or "")


def test_a_late_lens_failure_keeps_the_earlier_verdicts() -> None:
    calls = {"n": 0}

    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("died late")
        return _verdict("pass"), _metrics()

    judged = judge_case(_case(), "r", send=send, prompt=PROMPT)

    assert judged.status == "judge_error"
    assert len(judged.lenses) == 2


def test_cost_is_summed_across_the_panel() -> None:
    judged = judge_case(
        _case(), "r", send=_sender(*[_verdict("pass")] * 3), prompt=PROMPT
    )

    assert judged.total_cost_usd == pytest.approx(3 * (_metrics().total_cost_usd or 0.0))
    assert judged.calls == 3
    assert judged.failed_calls == ()


def test_a_billed_call_that_returned_no_verdict_is_still_charged() -> None:
    """Calibration run 1 attempted six calls, recorded five, and priced five.

    The truncated lens was billed. Counting only verdicts made an expensive
    failure read as free, which is the wrong direction for a cost total to err.
    """
    per_call = _metrics().total_cost_usd or 0.0

    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        if len(seen) == 2:
            raise JudgeError("cut off", metrics=_metrics(output_tokens=2048))
        seen.append(request)
        return _verdict("pass"), _metrics()

    seen: list[dict[str, Any]] = []
    judged = judge_case(_case(), "r", send=send, prompt=PROMPT)

    assert judged.status == "judge_error"
    assert len(judged.lenses) == 2
    assert len(judged.failed_calls) == 1

    # Three calls were made and three are accounted for, though only two
    # produced a verdict.
    assert judged.calls == 3
    lost = _metrics(output_tokens=2048).total_cost_usd or 0.0
    assert judged.total_cost_usd == pytest.approx(2 * per_call + lost)
    assert judged.total_cost_usd > 2 * per_call


def test_a_failure_with_no_usage_is_not_invented() -> None:
    """A transport that died before responding was not billed. Do not guess."""

    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        raise RuntimeError("connection reset")

    judged = judge_case(_case(), "r", send=send, prompt=PROMPT)

    assert judged.failed_calls == ()
    assert judged.calls == 0
    assert judged.total_cost_usd == 0.0


def test_the_lost_call_is_in_the_record() -> None:
    """Spend that produced nothing must be visible, not only in the total."""

    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        raise JudgeError("cut off", metrics=_metrics(output_tokens=2048))

    record = judge_case(_case(), "r", send=send, prompt=PROMPT).as_dict()
    json.dumps(record)

    assert record["calls"] == 1
    assert record["lenses"] == []
    assert len(record["failed_calls"]) == 1
    assert record["failed_calls"][0]["output_tokens"] == 2048


def test_truncation_carries_what_it_spent() -> None:
    """The budget error is the one most likely to fire, so it must not lose usage."""
    message = _Message([_Block('{"verdict": "pass"')], stop_reason="max_tokens")
    send = live_sender(_Client(message))

    with pytest.raises(JudgeError) as caught:
        send({"model": "claude-opus-5"})

    assert caught.value.metrics is not None
    assert caught.value.metrics.stop_reason == "max_tokens"


def test_many_cases_share_one_prefix_object() -> None:
    """N cases across three lenses must still be one cache write."""
    send = _sender(*[_verdict("pass")] * 6)
    judge_responses(
        [(_case(id="a"), "r1"), (_case(id="b"), "r2")], send=send, prompt=PROMPT
    )

    prefixes = {r["system"][0]["text"] for r in send.seen}  # type: ignore[attr-defined]
    assert len(prefixes) == 1
    assert len(send.seen) == 6  # type: ignore[attr-defined]


def test_progress_callback_fires_per_case() -> None:
    seen: list[str] = []
    judge_responses(
        [(_case(id="a"), "r"), (_case(id="b"), "r")],
        send=_sender(*[_verdict("pass")] * 6),
        prompt=PROMPT,
        on_case=lambda result: seen.append(result.case_id),
    )

    assert seen == ["a", "b"]


# --------------------------------------------------------------------------
# Variants - telling several responses to one case apart
# --------------------------------------------------------------------------


def test_a_result_without_a_variant_is_labelled_by_case_id_alone() -> None:
    """Ordinary runs must read exactly as they did before variants existed."""
    judged = judge_case(_case(), "r", send=_sender(*[_verdict("pass")] * 3), prompt=PROMPT)

    assert judged.variant is None
    assert judged.label == "t-001"


def test_a_variant_is_carried_into_the_result_and_its_label() -> None:
    judged = judge_case(
        _case(), "r", send=_sender(*[_verdict("pass")] * 3), prompt=PROMPT, variant="control"
    )

    assert judged.label == "t-001 [control]"
    assert judged.as_dict()["variant"] == "control"


def test_two_variants_of_one_case_are_distinguishable_without_counting_order() -> None:
    """The defect this fixes: the planted-defect probe's three results shared a
    case_id and were told apart only by their position in the record."""
    judged = judge_responses(
        [
            JudgeTarget(_case(), "clean", "control"),
            JudgeTarget(_case(), "defective", "planted"),
        ],
        send=_sender(*[_verdict("pass")] * 6),
        prompt=PROMPT,
    )

    assert {r.label for r in judged} == {"t-001 [control]", "t-001 [planted]"}


def test_the_judge_is_never_told_which_variant_it_is_reading() -> None:
    """A probe that leaked its own answer key would measure suggestibility."""
    send = _sender(*[_verdict("pass")] * 3)
    judge_responses(
        [JudgeTarget(_case(), "the response", "planted-over-refusal")],
        send=send,
        prompt=PROMPT,
    )

    flat = json.dumps(send.seen)  # type: ignore[attr-defined]
    assert "planted" not in flat
    assert "variant" not in flat


def test_plain_pairs_are_still_accepted() -> None:
    judged = judge_responses(
        [(_case(id="a"), "r")], send=_sender(*[_verdict("pass")] * 3), prompt=PROMPT
    )

    assert judged[0].variant is None


def test_an_errored_variant_keeps_its_label() -> None:
    def send(request: dict[str, Any]) -> tuple[Any, RequestMetrics]:
        raise RuntimeError("transport exploded")

    judged = judge_case(_case(), "r", send=send, prompt=PROMPT, variant="hedge")

    assert judged.status == "judge_error"
    assert judged.label == "t-001 [hedge]"


def test_record_is_json_safe() -> None:
    judged = judge_case(
        _case(),
        "the actual response",
        send=_sender(
            _verdict("pass"),
            _verdict("fail", [{"quote": "actual", "problem": "p", "basis": "b"}]),
            _verdict("uncertain"),
        ),
        prompt=PROMPT,
    )

    json.dumps(judged.as_dict())  # must not raise


def test_record_keeps_both_the_claimed_and_adjusted_verdict() -> None:
    """A harness adjustment must be auditable, not invisible."""
    judged = judge_case(
        _case(),
        "r",
        send=_sender(_verdict("pass"), _verdict("fail"), _verdict("pass")),
        prompt=PROMPT,
    )
    adjusted = [lens for lens in judged.as_dict()["lenses"] if lens["adjustment"]]

    assert len(adjusted) == 1
    assert (adjusted[0]["claimed"], adjusted[0]["verdict"]) == ("fail", "uncertain")


# --------------------------------------------------------------------------
# The live sender
# --------------------------------------------------------------------------


class _Block:
    def __init__(self, text: str, type: str = "text") -> None:
        self.text = text
        self.type = type


class _Message:
    def __init__(self, blocks: list[_Block], stop_reason: str = "end_turn") -> None:
        self.content = blocks
        self.model = "claude-opus-5"
        self.stop_reason = stop_reason
        self.usage = None


class _Client:
    def __init__(self, message: _Message) -> None:
        self._message = message
        self.messages = self

    def create(self, **request: Any) -> _Message:
        return self._message


def test_live_sender_parses_the_json_body() -> None:
    payload = _verdict("pass")
    send = live_sender(_Client(_Message([_Block(json.dumps(payload))])))

    parsed, metrics = send({"model": "claude-opus-5"})

    assert parsed == payload
    assert metrics.model == "claude-opus-5"


def test_live_sender_skips_non_text_blocks() -> None:
    """Thinking is on by default and its blocks carry empty text."""
    message = _Message([_Block("", "thinking"), _Block(json.dumps(_verdict("pass")))])
    parsed, _ = live_sender(_Client(message))({"model": "claude-opus-5"})

    assert parsed["verdict"] == "pass"


def test_live_sender_raises_on_an_empty_body() -> None:
    """A truncated verdict is not a verdict - most likely max_tokens."""
    send = live_sender(_Client(_Message([])))

    with pytest.raises(JudgeError, match="no text"):
        send({"model": "claude-opus-5"})


def test_live_sender_raises_on_unparseable_output() -> None:
    send = live_sender(_Client(_Message([_Block("not json at all")])))

    with pytest.raises(JudgeError, match="not valid JSON"):
        send({"model": "claude-opus-5"})


def test_truncation_is_named_as_truncation_not_as_malformed_json() -> None:
    """The first calibration run lost a lens to this and reported the wrong cause.

    A cut-off verdict arrives as partial JSON, so parsing first blames the
    judge's output for what is really an undersized budget - and sends whoever
    reads the error to the wrong fix.
    """
    truncated = _Message([_Block('{"verdict": "pass", "reason": "half a sent')], "max_tokens")
    send = live_sender(_Client(truncated))

    with pytest.raises(JudgeError, match="max_tokens"):
        send({"model": "claude-opus-5"})


def test_the_judge_budget_leaves_room_for_thinking() -> None:
    """At `high` effort a lens spends 1,500+ tokens reasoning before it writes."""
    from ask_christopher.judge import DEFAULT_JUDGE_MAX_TOKENS

    assert DEFAULT_JUDGE_MAX_TOKENS >= 8192


# --------------------------------------------------------------------------
# The lens panel itself
# --------------------------------------------------------------------------


def test_lenses_are_distinct_perspectives_not_repeats() -> None:
    """Three clones sample one opinion three times and dilute nothing."""
    assert len({lens.name for lens in LENSES}) == len(LENSES)
    assert len({lens.instruction for lens in LENSES}) == len(LENSES)


def test_a_grounding_lens_exists() -> None:
    """The correction-pair run found an ungrounded comparative no check caught.

    That finding is the argument for this whole module; the lens that would
    have to catch it must not be quietly renamed away.
    """
    assert "grounding" in {lens.name for lens in LENSES}


def test_the_preamble_states_the_evidence_rule() -> None:
    assert "verbatim" in JUDGE_PREAMBLE
    assert "uncertain" in JUDGE_PREAMBLE
