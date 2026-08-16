"""Tests for the eval suite runner.

The runner sends nothing here. ``replay`` reads a recorded transcript, and the
selection and reporting logic is pure, so every path below runs offline.

Two properties matter more than the rest and are tested directly:

* **Every case lands in exactly one bucket.** A case that quietly disappears is
  a behaviour nobody is measuring while the summary still reads as complete.
* **No pass rate is reported.** Lexical checks can falsify a judged case and
  never confirm one, so a suite-wide percentage would measure nothing.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from ask_christopher.evals import EvalCase, load_cases

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = (
    ROOT / "docs" / "experiments" / "0002-first-conversation-baseline" / "transcript.json"
)


def _runner() -> Any:
    """The runner script, loaded by path - scripts/ is not an importable package.

    Registered in ``sys.modules`` before execution because the module defines
    dataclasses under ``from __future__ import annotations``: resolving those
    string annotations means looking the module up by name, and an unregistered
    module raises during class construction rather than at first use.
    """
    import sys

    spec = importlib.util.spec_from_file_location(
        "run_evals", ROOT / "scripts" / "run_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case(case_id: str = "t-001", **overrides: Any) -> EvalCase:
    defaults: dict[str, Any] = {
        "id": case_id,
        "category": "trap",
        "prompt": "A question.",
        "tests": "What this measures.",
        "source": "knowledge/boundaries.md - Somewhere",
        "scoring": "model_judged",
    }
    return EvalCase(**{**defaults, **overrides})


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------


def test_every_case_lands_in_exactly_one_bucket() -> None:
    run = _runner()
    cases = load_cases()

    selected, skipped = run.select(
        cases,
        lambda case: run.Selected(case=case, respond=lambda _: "x", fidelity=run.VERBATIM),
        None,
    )

    assert len(selected) + len(skipped) == len(cases)
    ids = {s.case.id for s in selected} | {s.case_id for s in skipped}
    assert ids == {c.id for c in cases}


def test_multi_turn_cases_are_skipped_with_a_stated_reason() -> None:
    run = _runner()
    cases = (_case("single"), _case("sequence", multi_turn=True))

    selected, skipped = run.select(
        cases,
        lambda case: run.Selected(case=case, respond=lambda _: "x", fidelity=run.VERBATIM),
        None,
    )

    assert [s.case.id for s in selected] == ["single"]
    assert skipped[0].case_id == "sequence"
    assert skipped[0].reason == "multi_turn"
    assert skipped[0].detail


def test_multi_turn_cases_are_never_sent() -> None:
    """The prompt is prose about a sequence. Sending it would measure nothing."""
    run = _runner()
    sent: list[str] = []

    def responder(case: EvalCase) -> Any:
        sent.append(case.id)
        return run.Selected(case=case, respond=lambda _: "x", fidelity=run.VERBATIM)

    run.select((_case("sequence", multi_turn=True),), responder, None)

    assert sent == []


def test_only_filter_records_exclusions_rather_than_dropping_them() -> None:
    run = _runner()
    cases = (_case("wanted"), _case("unwanted"))

    selected, skipped = run.select(
        cases,
        lambda case: run.Selected(case=case, respond=lambda _: "x", fidelity=run.VERBATIM),
        frozenset({"wanted"}),
    )

    assert [s.case.id for s in selected] == ["wanted"]
    assert [(s.case_id, s.reason) for s in skipped] == [("unwanted", "not_selected")]


def test_a_responder_skip_is_carried_through() -> None:
    run = _runner()

    selected, skipped = run.select(
        (_case("nothing-recorded"),),
        lambda case: run.Skipped(case.id, "no_recorded_response", "no turn"),
        None,
    )

    assert selected == []
    assert skipped[0].reason == "no_recorded_response"


# --------------------------------------------------------------------------
# Selecting for judgement - and refusing a file that cannot be read
# --------------------------------------------------------------------------


def _entry(case_id: str, **overrides: Any) -> dict[str, Any]:
    return {"case_id": case_id, "response": "some text", **overrides}


def test_one_entry_per_case_needs_no_variant() -> None:
    run = _runner()

    run.check_variant_labels([_entry("a"), _entry("b")])  # must not raise


def test_shared_case_ids_without_variants_are_refused() -> None:
    """The fragility this closes: two entries told apart only by file order."""
    run = _runner()

    with pytest.raises(ValueError, match="no 'variant' label"):
        run.check_variant_labels([_entry("a"), _entry("a")])


def test_a_partially_labelled_group_is_refused() -> None:
    run = _runner()

    with pytest.raises(ValueError, match="variant"):
        run.check_variant_labels([_entry("a", variant="control"), _entry("a")])


def test_duplicate_variant_labels_are_refused() -> None:
    run = _runner()

    with pytest.raises(ValueError, match="duplicate variant"):
        run.check_variant_labels(
            [_entry("a", variant="control"), _entry("a", variant="control")]
        )


def test_distinct_variants_are_accepted_and_carried_through() -> None:
    run = _runner()
    cases = (_case("a"),)

    selected, skipped = run.select_for_judging(
        [_entry("a", variant="control"), _entry("a", variant="planted")], cases, None
    )

    assert [t.variant for t in selected] == ["control", "planted"]
    assert skipped == []


def test_a_skipped_variant_is_identified_by_its_label() -> None:
    run = _runner()
    cases = (_case("a", scoring="human_review"),)

    _selected, skipped = run.select_for_judging(
        [_entry("a", variant="control"), _entry("a", variant="planted")], cases, None
    )

    assert [s.label for s in skipped] == ["a [control]", "a [planted]"]
    assert all(s.reason == "human_review" for s in skipped)


def test_the_planted_defect_probe_file_is_readable_under_the_guard() -> None:
    """The file that motivated this already labels its variants. It must pass."""
    run = _runner()
    path = ROOT / "docs" / "evals" / "judge-probe-planted-defects.json"

    run.check_variant_labels(json.loads(path.read_text(encoding="utf-8"))["cases"])


def test_an_unreadable_responses_file_is_rejected_before_it_is_priced(
    tmp_path: Path, capsys: Any
) -> None:
    """The guard must fire at pricing time - an ambiguous file costs nothing."""
    run = _runner()
    path = tmp_path / "responses.json"
    path.write_text(
        json.dumps({"cases": [_entry("fab-credential-phd"), _entry("fab-credential-phd")]}),
        encoding="utf-8",
    )

    code = run.main(["judge", "--responses", str(path)])

    assert code == 1
    assert "cannot be judged unambiguously" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Replay against the real artifact
# --------------------------------------------------------------------------


def test_replay_serves_the_recorded_response_for_a_linked_case() -> None:
    run = _runner()
    responder = run.replay_responder(TRANSCRIPT)
    cases = {c.id: c for c in load_cases()}

    outcome = responder(cases["hdg-undocumented-opinion"])

    assert isinstance(outcome, run.Selected)
    assert "worse than no answer" in outcome.respond("ignored")


def test_replay_ignores_the_prompt_it_is_handed() -> None:
    """The recorded response answers the experiment's wording, not the case's."""
    run = _runner()
    responder = run.replay_responder(TRANSCRIPT)
    cases = {c.id: c for c in load_cases()}

    outcome = responder(cases["doc-role-explainer"])

    assert outcome.respond("literally anything") == outcome.respond("something else")


def test_replay_labels_paraphrased_wording_as_such() -> None:
    run = _runner()
    responder = run.replay_responder(TRANSCRIPT)
    cases = {c.id: c for c in load_cases()}

    verbatim = responder(cases["hdg-undocumented-opinion"])
    paraphrase = responder(cases["doc-role-explainer"])

    assert verbatim.fidelity == run.VERBATIM
    assert paraphrase.fidelity == run.PARAPHRASE
    assert paraphrase.elicited_by != cases["doc-role-explainer"].prompt


def test_replay_skips_a_case_the_transcript_never_covered() -> None:
    run = _runner()
    responder = run.replay_responder(TRANSCRIPT)
    cases = {c.id: c for c in load_cases()}

    outcome = responder(cases["fab-credential-phd"])

    assert isinstance(outcome, run.Skipped)
    assert outcome.reason == "no_recorded_response"


def test_replay_skips_the_correction_case_because_turn_seven_never_ran() -> None:
    """The known gap in experiment 0002, surfacing as a skip rather than a pass."""
    run = _runner()
    responder = run.replay_responder(TRANSCRIPT)
    cases = {c.id: c for c in load_cases()}

    outcome = responder(cases["crn-valid-correction"])

    assert isinstance(outcome, run.Skipped)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_estimate_prices_one_write_and_the_rest_reads() -> None:
    run = _runner()

    one = run.estimate_live_cost(1)
    ten = run.estimate_live_cost(10)

    assert one["prefix_reads"] == 0
    # abs, not rel: the estimate is rounded to six decimals for display.
    assert ten["prefix_reads"] == pytest.approx(
        run.PREFIX_TOKENS * (5.0 / 1e6) * 0.1 * 9, abs=1e-6
    )
    assert ten["total"] > one["total"]


def test_estimate_of_an_empty_run_is_not_negative() -> None:
    run = _runner()

    assert run.estimate_live_cost(0)["prefix_reads"] == 0


def test_record_separates_verbatim_from_paraphrase_and_never_sums_them() -> None:
    run = _runner()
    record = _replay_record(run)

    assert record["fidelity"] == {"verbatim": 2, "paraphrase": 4}
    assert "scored_verbatim" in record
    assert "indicative_paraphrase" in record


def test_record_reports_no_pass_rate(tmp_path: Path) -> None:
    run = _runner()
    record = _replay_record(run)

    flat = json.dumps(record)
    assert "pass_rate" not in flat
    assert "percent" not in flat
    assert record["suite"]["scored"] + record["suite"]["unscored"] == record["selection"]["ran"]


def test_summary_says_judged_cases_are_unscored_not_passing(capsys: Any) -> None:
    run = _runner()

    run.print_summary(_replay_record(run))

    out = capsys.readouterr().out
    assert "No pass rate is reported" in out
    assert "unscored, not passing" in out


def test_record_names_the_transcript_and_both_of_its_commits() -> None:
    run = _runner()
    record = _replay_record(run)

    assert record["source"]["kind"] == "transcript"
    assert record["source"]["phase_a_commit"]
    assert record["source"]["phase_b_commit"]


def test_record_accounts_for_every_case_in_the_file() -> None:
    run = _runner()
    record = _replay_record(run)
    selection = record["selection"]

    assert selection["ran"] + len(selection["skipped"]) == selection["total_cases"]
    assert selection["total_cases"] == len(load_cases())


def test_every_skip_carries_a_reason() -> None:
    run = _runner()
    record = _replay_record(run)

    assert all(skip["reason"] for skip in record["selection"]["skipped"])


def _replay_record(run: Any) -> dict[str, Any]:
    from ask_christopher.evals import SuiteResult, run_case

    cases = load_cases()
    selected, skipped = run.select(cases, run.replay_responder(TRANSCRIPT), None)
    suite = SuiteResult(results=tuple(run_case(s.case, s.respond) for s in selected))
    return run.build_record(
        mode="replay",
        source={"kind": "transcript", "phase_a_commit": "aaa", "phase_b_commit": "bbb"},
        cases_path=ROOT / "tests" / "evals" / "cases.yaml",
        total_cases=len(cases),
        selected=selected,
        skipped=skipped,
        suite=suite,
        started_at="2026-08-12T00:00:00+00:00",
    )


# --------------------------------------------------------------------------
# The command surface
# --------------------------------------------------------------------------


def test_list_sends_nothing_and_describes_the_suite(capsys: Any) -> None:
    run = _runner()

    assert run.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "By scoring mode" in out
    assert "Multi-turn" in out


def test_live_without_confirm_prices_the_run_and_refuses_to_spend(capsys: Any) -> None:
    run = _runner()

    assert run.main(["live"]) == 0
    out = capsys.readouterr().out
    assert "Nothing was sent" in out
    assert "--confirm" in out
    assert "ESTIMATED TOTAL" in out


def test_an_unknown_only_id_is_rejected_before_anything_runs(capsys: Any) -> None:
    run = _runner()

    code = run.main(
        ["replay", "--transcript", str(TRANSCRIPT), "--only", "no-such-case"]
    )

    assert code == 1
    assert "Unknown case id" in capsys.readouterr().err


def test_responses_are_retained_only_in_their_own_artifact(tmp_path: Path) -> None:
    """The result record is a metrics series; the responses file is the transcript.

    A file that tries to be both serves neither, so retention is opt-in and lands
    somewhere else entirely.
    """
    run = _runner()
    record_path = tmp_path / "record.json"
    responses_path = tmp_path / "responses.json"

    run.main(
        [
            "replay",
            "--transcript",
            str(TRANSCRIPT),
            "--only",
            "hdg-undocumented-opinion",
            "--out",
            str(record_path),
            "--responses-out",
            str(responses_path),
        ]
    )

    record = record_path.read_text(encoding="utf-8")
    responses = json.loads(responses_path.read_text(encoding="utf-8"))

    assert "worse than no answer" not in record
    assert "worse than no answer" in responses["cases"][0]["response"]


def test_no_responses_file_is_written_unless_asked(tmp_path: Path) -> None:
    run = _runner()
    out = tmp_path / "record.json"

    run.main(["replay", "--transcript", str(TRANSCRIPT), "--out", str(out)])

    assert list(tmp_path.iterdir()) == [out]


def test_responses_artifact_carries_the_rubric_beside_the_answer(tmp_path: Path) -> None:
    run = _runner()
    responses_path = tmp_path / "responses.json"

    run.main(
        [
            "replay",
            "--transcript",
            str(TRANSCRIPT),
            "--only",
            "vce-decline-still-human",
            "--out",
            str(tmp_path / "r.json"),
            "--responses-out",
            str(responses_path),
        ]
    )

    entry = json.loads(responses_path.read_text(encoding="utf-8"))["cases"][0]

    assert entry["rubric"]["requires"]
    assert entry["rubric"]["prohibits"]
    assert entry["rubric"]["source"]
    assert entry["status"] == "needs_judgment"


def test_rendered_responses_flag_a_paraphrased_prompt(tmp_path: Path) -> None:
    run = _runner()
    responses_path = tmp_path / "responses.json"

    run.main(
        [
            "replay",
            "--transcript",
            str(TRANSCRIPT),
            "--only",
            "doc-role-explainer",
            "--out",
            str(tmp_path / "r.json"),
            "--responses-out",
            str(responses_path),
        ]
    )

    rendered = (tmp_path / "responses.md").read_text(encoding="utf-8")

    assert "Do not edit" in rendered
    assert "Elicited by different wording" in rendered
    assert "unread, not passing" in rendered


def test_render_responses_regenerates_from_the_json(tmp_path: Path) -> None:
    run = _runner()
    responses_path = tmp_path / "responses.json"
    run.main(
        [
            "replay",
            "--transcript",
            str(TRANSCRIPT),
            "--only",
            "hdg-undocumented-opinion",
            "--out",
            str(tmp_path / "r.json"),
            "--responses-out",
            str(responses_path),
        ]
    )
    rendered = tmp_path / "responses.md"
    rendered.write_text("clobbered", encoding="utf-8")

    assert run.main(["render-responses", "--responses", str(responses_path)]) == 0
    assert "clobbered" not in rendered.read_text(encoding="utf-8")


def test_a_failing_responder_aborts_instead_of_repeating(tmp_path: Path, capsys: Any) -> None:
    """Bad credentials fail identically every time. One error is the signal."""
    run = _runner()
    cases = load_cases()
    attempts: list[str] = []

    def exploding(case: EvalCase) -> Any:
        def respond(_text: str) -> str:
            attempts.append(case.id)
            raise RuntimeError("Could not resolve authentication method")

        return run.Selected(case=case, respond=respond, fidelity=run.VERBATIM)

    args = _namespace(out=str(tmp_path / "record.json"))
    code = run._run(args, "live", exploding, {"kind": "live"})

    assert code == 1
    assert len(attempts) == 1, "should stop after the first failure"
    out = capsys.readouterr()
    assert "Aborting after an error" in out.out
    assert "Writing no record" in out.err
    assert not (tmp_path / "record.json").exists()
    assert len(cases) > 1


def test_unattempted_cases_are_recorded_as_aborted(tmp_path: Path) -> None:
    run = _runner()
    seen: dict[str, Any] = {}

    def exploding(case: EvalCase) -> Any:
        def respond(_text: str) -> str:
            raise RuntimeError("boom")

        return run.Selected(case=case, respond=respond, fidelity=run.VERBATIM)

    original = run.build_record

    def spy(**kwargs: Any) -> dict[str, Any]:
        record = original(**kwargs)
        seen.update(record)
        return record

    run.build_record = spy
    run._run(_namespace(out=str(tmp_path / "r.json")), "live", exploding, {"kind": "live"})

    reasons = {s["reason"] for s in seen["selection"]["skipped"]}
    assert "aborted_after_error" in reasons


def _namespace(**overrides: Any) -> Any:
    from types import SimpleNamespace

    fields: dict[str, Any] = {"cases": None, "only": None, "out": None, "responses_out": None}
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_replay_writes_a_json_record(tmp_path: Path, capsys: Any) -> None:
    run = _runner()
    out = tmp_path / "record.json"

    code = run.main(["replay", "--transcript", str(TRANSCRIPT), "--out", str(out)])

    assert code == 0
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["schema"] == run.RECORD_SCHEMA
    assert record["mode"] == "replay"
    assert record["selection"]["ran"] == 6
