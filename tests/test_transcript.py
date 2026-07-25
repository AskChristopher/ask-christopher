"""Tests for the two-phase transcript harness.

The load-bearing test is :func:`test_reconstructed_history_matches_a_continuous_session`
— everything else in the two-phase design rests on the claim that rebuilding the
message list from the stored transcript is equivalent to never having stopped.
That claim is asserted here rather than assumed, at the level that matters: the
exact request dict the API would receive.

No API calls. No credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ask_christopher.client import DEFAULT_MODEL, build_conversation_request
from ask_christopher.repl import Session
from ask_christopher.transcript import (
    AWAITING_CORRECTION,
    COMPLETE,
    FAILED,
    Transcript,
    TranscriptError,
    TurnRecord,
    load_question_set,
    prompt_fingerprint,
    reconstruct_messages,
    render_markdown,
)

REPLIES = [
    "Reply one.",
    "Reply two,\nwith a newline and  double  spaces.",
    "Reply three.",
    "Reply four.",
    "Reply five — with punctuation & symbols <>.",
    "Reply six: he has been there nearly eight years.",
]

PROMPTS = [
    "Q1",
    "Q2 with\ttabs",
    "Q3",
    "Q4",
    "Q5\n\nmulti-line\n  indented\n",
    "Q6",
]


class FakeClient:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        outer = self

        class _Messages:
            def create(self, **kwargs: Any) -> Any:
                outer.calls.append(kwargs)
                text = outer.replies.pop(0) if outer.replies else "ok"
                return SimpleNamespace(
                    model=DEFAULT_MODEL,
                    stop_reason="end_turn",
                    _request_id="req_x",
                    content=[SimpleNamespace(type="text", text=text)],
                    usage=SimpleNamespace(
                        input_tokens=9,
                        output_tokens=11,
                        cache_creation_input_tokens=0,
                        cache_read_input_tokens=40_511,
                    ),
                )

        self.messages = _Messages()


@pytest.fixture(scope="module")
def prompt() -> Any:
    from ask_christopher.prompt import build_system_prompt

    return build_system_prompt()


def _six_turn_transcript(prompt: Any) -> tuple[Transcript, Session]:
    """Run six turns through a real Session and mirror them into a transcript."""
    session = Session(client=FakeClient(REPLIES), prompt=prompt)
    transcript = Transcript(
        run_id="test",
        status=AWAITING_CORRECTION,
        provenance={
            "commit": "abc1234",
            "prompt_sha256": prompt_fingerprint(prompt),
            "model": DEFAULT_MODEL,
            "max_tokens": 2048,
            "effort": "low",
        },
        question_set={"version": 1, "sha256": "deadbeef"},
    )
    for i, text in enumerate(PROMPTS, start=1):
        transcript.record_prompt(i, "planned", f"q{i}", text)
        turn = session.send(text)
        transcript.record_response(i, turn.reply, turn.metrics.as_dict())
    return transcript, session


# --------------------------------------------------------------------------
# The equivalence claim
# --------------------------------------------------------------------------


def test_reconstructed_history_matches_a_continuous_session(prompt: Any) -> None:
    """Phase B's rebuilt history must equal what a never-stopped Session holds."""
    transcript, session = _six_turn_transcript(prompt)

    assert reconstruct_messages(transcript.turns) == session.messages


def test_reconstructed_request_is_byte_for_byte_identical(prompt: Any) -> None:
    """Equivalence at the level that matters — the dict handed to the SDK."""
    transcript, session = _six_turn_transcript(prompt)
    next_question = "Turn seven."

    continuous = build_conversation_request(
        [*session.messages, {"role": "user", "content": next_question}], prompt=prompt
    )
    resumed = Session(
        client=FakeClient([]), prompt=prompt, messages=reconstruct_messages(transcript.turns)
    ).build_request(next_question)

    assert resumed == continuous
    assert json.dumps(resumed, sort_keys=True) == json.dumps(continuous, sort_keys=True)


def test_reconstruction_survives_a_json_round_trip(prompt: Any, tmp_path: Path) -> None:
    """The transcript is the source of truth, so equivalence must hold after reload."""
    transcript, session = _six_turn_transcript(prompt)
    path = tmp_path / "transcript.json"
    transcript.save(path)

    assert reconstruct_messages(Transcript.load(path).turns) == session.messages


def test_reconstruction_preserves_whitespace_exactly(prompt: Any, tmp_path: Path) -> None:
    """No strip, no normalisation — a transformed turn is a different experiment."""
    transcript, _ = _six_turn_transcript(prompt)
    path = tmp_path / "t.json"
    transcript.save(path)

    messages = reconstruct_messages(Transcript.load(path).turns)
    assert messages[8]["content"] == "Q5\n\nmulti-line\n  indented\n"
    assert messages[3]["content"] == "Reply two,\nwith a newline and  double  spaces."


def test_incomplete_turns_are_excluded_from_history(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)
    transcript.record_prompt(7, "correction", "q7", "a correction")

    assert len(reconstruct_messages(transcript.turns)) == 12


def test_history_is_ordered_by_turn_not_insertion(prompt: Any) -> None:
    transcript, session = _six_turn_transcript(prompt)
    transcript.turns.reverse()

    assert reconstruct_messages(transcript.turns) == session.messages


# --------------------------------------------------------------------------
# Immutability
# --------------------------------------------------------------------------


def test_a_turn_cannot_be_recorded_twice(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)

    with pytest.raises(TranscriptError, match="already recorded"):
        transcript.record_prompt(3, "planned", "q3", "different text")


def test_a_response_cannot_be_overwritten(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)

    with pytest.raises(TranscriptError, match="already has a response"):
        transcript.record_response(3, "a different answer", {})


def test_a_response_needs_a_recorded_prompt_first(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)

    with pytest.raises(TranscriptError, match="no recorded prompt"):
        transcript.record_response(7, "answer", {})


# --------------------------------------------------------------------------
# Partial results and failure
# --------------------------------------------------------------------------


def test_prompt_is_persisted_before_the_response_exists(tmp_path: Path) -> None:
    """A crash between send and reply must still leave the prompt on record."""
    transcript = Transcript("r", AWAITING_CORRECTION, {}, {})
    transcript.record_prompt(1, "planned", "q1", "asked but never answered")
    path = tmp_path / "t.json"
    transcript.save(path)

    reloaded = Transcript.load(path)
    assert reloaded.turns[0].prompt == "asked but never answered"
    assert reloaded.turns[0].response is None
    assert reloaded.turns[0].completed is False


def test_a_failure_preserves_earlier_turns(prompt: Any, tmp_path: Path) -> None:
    transcript, _ = _six_turn_transcript(prompt)
    transcript.record_prompt(7, "correction", "q7", "correction text")
    transcript.record_failure(7, "APIStatusError: 529")
    path = tmp_path / "t.json"
    transcript.save(path)

    reloaded = Transcript.load(path)
    assert reloaded.status == FAILED
    assert len(reloaded.completed_turns) == 6
    assert reloaded.turns[6].error == "APIStatusError: 529"
    assert reconstruct_messages(reloaded.turns) == reconstruct_messages(transcript.turns)


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path: Path) -> None:
    transcript = Transcript("r", AWAITING_CORRECTION, {}, {})
    path = tmp_path / "t.json"
    transcript.save(path)

    assert path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def test_round_trip_preserves_every_field(prompt: Any, tmp_path: Path) -> None:
    transcript, _ = _six_turn_transcript(prompt)
    transcript.correction_review = {"warranted": False, "reason": "accurate"}
    path = tmp_path / "t.json"
    transcript.save(path)

    assert Transcript.load(path).as_dict() == transcript.as_dict()


def test_load_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(TranscriptError, match="not valid JSON"):
        Transcript.load(path)


def test_load_rejects_a_missing_field(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"run_id": "r", "status": "x"}), encoding="utf-8")

    with pytest.raises(TranscriptError, match="missing field 'provenance'"):
        Transcript.load(path)


def test_load_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(TranscriptError, match="Could not read"):
        Transcript.load(tmp_path / "absent.json")


# --------------------------------------------------------------------------
# Question set
# --------------------------------------------------------------------------


def test_real_question_set_loads_with_eight_turns() -> None:
    questions = load_question_set()

    assert [t.turn for t in questions.turns] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert len(questions.phase("a")) == 6
    assert len(questions.phase("b")) == 2


def test_turn_seven_has_no_prescripted_prompt() -> None:
    """The correction must respond to what was actually said."""
    seven = load_question_set().by_turn(7)

    assert seven.prompt is None
    assert seven.supplied_at_phase_b is True


def test_turn_eight_uses_the_eval_case_wording_verbatim() -> None:
    """So the raw artifact feeds the eval harness without reinterpretation."""
    from ask_christopher.evals import load_cases

    eight = load_question_set().by_turn(8)
    case = next(c for c in load_cases() if c.id == "hdg-undocumented-opinion")

    assert eight.prompt == case.prompt
    assert eight.eval_case == case.id


def test_question_set_hash_changes_when_the_file_changes(tmp_path: Path) -> None:
    body = "version: 1\nturns:\n  - {id: a, turn: 1, phase: a, prompt: x}\n"
    first = tmp_path / "q1.yaml"
    first.write_text(body, encoding="utf-8")
    second = tmp_path / "q2.yaml"
    second.write_text(body + "# a comment changes nothing semantically\n", encoding="utf-8")

    assert load_question_set(first).sha256 != load_question_set(second).sha256


def test_out_of_order_turns_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "q.yaml"
    path.write_text(
        "version: 1\nturns:\n"
        "  - {id: b, turn: 2, phase: a, prompt: x}\n"
        "  - {id: a, turn: 1, phase: a, prompt: y}\n",
        encoding="utf-8",
    )

    with pytest.raises(TranscriptError, match="ascending order"):
        load_question_set(path)


def test_referenced_eval_cases_all_exist() -> None:
    from ask_christopher.evals import load_cases

    known = {c.id for c in load_cases()}
    for planned in load_question_set().turns:
        if planned.eval_case:
            assert planned.eval_case in known, planned.id


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def test_markdown_is_generated_from_the_json(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)
    rendered = render_markdown(transcript)

    assert "Do not edit" in rendered
    for text in PROMPTS:
        assert text.strip().splitlines()[0] in rendered
    for reply in REPLIES:
        assert reply.splitlines()[0] in rendered


def test_markdown_separates_the_correction_review_from_the_turns(prompt: Any) -> None:
    """Human judgement is metadata, not a model turn."""
    transcript, _ = _six_turn_transcript(prompt)
    transcript.correction_review = {
        "warranted": False,
        "reason": "turn 6 was accurate",
        "decided_at": "2026-07-25T00:00:00+00:00",
    }
    rendered = render_markdown(transcript)

    assert "Correction review" in rendered
    assert "Human judgement, recorded as metadata" in rendered
    assert "turn 6 was accurate" in rendered


def test_markdown_marks_a_failed_turn(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)
    transcript.record_prompt(7, "correction", "q7", "c")
    transcript.record_failure(7, "APIConnectionError: dns")
    rendered = render_markdown(transcript)

    assert "**FAILED**" in rendered
    assert "APIConnectionError: dns" in rendered


def test_markdown_reports_cache_reads_and_writes_distinctly(prompt: Any) -> None:
    transcript, _ = _six_turn_transcript(prompt)
    rendered = render_markdown(transcript)

    assert "cache read 40,511" in rendered


# --------------------------------------------------------------------------
# Phase B guards, exercised through the script
# --------------------------------------------------------------------------


def _script_verify(transcript: Transcript, prompt: Any, **overrides: Any) -> list[str]:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "first_conversation", root / "scripts" / "first_conversation.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    fields: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "max_tokens": 2048,
        "effort": "low",
        "allow_commit_drift": False,
        "_model_supplied": False,
        "_max_tokens_supplied": False,
        "_effort_supplied": False,
    }
    fields.update(overrides)
    args = SimpleNamespace(**fields)
    questions = load_question_set()
    return module._verify(transcript, questions, prompt, transcript.provenance["commit"], args)


def _valid_transcript(prompt: Any) -> Transcript:
    transcript, _ = _six_turn_transcript(prompt)
    questions = load_question_set()
    transcript.question_set = questions.as_dict()
    transcript.provenance["prompt_sha256"] = prompt_fingerprint(prompt)
    return transcript


def test_a_valid_partial_transcript_passes_verification(prompt: Any) -> None:
    assert _script_verify(_valid_transcript(prompt), prompt) == []


def test_phase_b_refuses_a_completed_transcript(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)
    transcript.status = COMPLETE

    assert any("already marked complete" in p for p in _script_verify(transcript, prompt))


def test_phase_b_refuses_a_failed_transcript(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)
    transcript.status = FAILED

    assert any("marked failed" in p for p in _script_verify(transcript, prompt))


def test_phase_b_refuses_a_changed_prompt_hash(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)
    transcript.provenance["prompt_sha256"] = "0" * 64

    assert any("assembled prompt changed" in p for p in _script_verify(transcript, prompt))


def test_phase_b_refuses_a_changed_question_set(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)
    transcript.question_set["sha256"] = "0" * 64

    assert any("question set changed" in p for p in _script_verify(transcript, prompt))


def test_phase_b_refuses_a_model_mismatch_when_explicitly_requested(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)

    problems = _script_verify(transcript, prompt, model="claude-sonnet-5", _model_supplied=True)
    assert any("model differs" in p for p in problems)


def test_phase_b_ignores_defaults_that_were_not_explicitly_passed(prompt: Any) -> None:
    """Otherwise an unrelated default change would fake a mismatch."""
    transcript = _valid_transcript(prompt)
    transcript.provenance["effort"] = "medium"

    assert _script_verify(transcript, prompt) == []


def test_phase_b_refuses_an_incomplete_phase_a(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)
    transcript.turns = transcript.turns[:4]

    assert any("phase A incomplete" in p for p in _script_verify(transcript, prompt))


def test_phase_b_refuses_when_turn_seven_already_exists(prompt: Any) -> None:
    transcript = _valid_transcript(prompt)
    transcript.record_prompt(7, "correction", "q7", "already done")

    assert any("already present" in p for p in _script_verify(transcript, prompt))
