"""Tests for the human-review workflow.

The whole module exists to stop one failure: an unread case quietly counted as
a pass. So the tests that matter most are the ones asserting that every
incomplete, unattributable, or unevidenced path lands on something *other* than
``reviewed_pass``.

No API calls. Nothing here reads a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ask_christopher.review import (
    REVIEW_VERDICTS,
    UNREVIEWED,
    ReviewError,
    build_review_record,
    build_template,
    load_responses,
    load_sheet,
    render_template,
    resolve_entry,
    resolve_sheet,
    response_digest,
    reviewable_text,
    verify_binding,
)


def _responses(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": 1,
        "mode": "live",
        "generated_at": "2026-08-26T00:00:00+00:00",
        "provenance": {
            "commit": "04b1c3c",
            "commit_dirty": False,
            "model": "claude-opus-5",
            "effort": "low",
            "prompt_sha256": "f" * 64,
            "cases_sha256": "a" * 64,
        },
        "source": {"kind": "live"},
        "cases": [
            {
                "case_id": "vce-warmth",
                "scoring": "human_review",
                "status": "needs_judgment",
                "response": "That feeling is common, and it is usually wrong.",
            },
            {
                "case_id": "acc-no-preamble",
                "scoring": "model_judged",
                "status": "needs_judgment",
                "response": "Two degrees from Cal Poly Pomona.",
            },
        ],
    }
    data.update(overrides)
    return data


def _conversation_entry() -> dict[str, Any]:
    return {
        "case_id": "ext-coaching-project",
        "scoring": "human_review",
        "status": "needs_judgment",
        "response": "Point at the shape you already wrote.",
        "conversation": [
            {"index": 1, "send": "one", "response": "Here is a whole scaffold."},
            {"index": 2, "send": "two", "response": "Point at the shape you already wrote."},
        ],
    }


def _write_responses(tmp_path: Path, data: dict[str, Any]) -> tuple[Path, str]:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _, digest = load_responses(path)
    return path, digest


def _sheet(tmp_path: Path, template: dict[str, Any]) -> Path:
    path = tmp_path / "sheet.yaml"
    path.write_text(render_template(template), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------


def test_review_verdicts_are_disjoint_from_every_other_scorer() -> None:
    """A human verdict is a third kind of evidence, not a promotion.

    Nothing downstream can add a reviewed verdict into a deterministic or judged
    count, because the two vocabularies share no name.
    """
    from ask_christopher.evals import SuiteResult

    deterministic = set(SuiteResult(results=()).counts())
    assert REVIEW_VERDICTS.isdisjoint(deterministic)
    assert UNREVIEWED not in deterministic
    assert REVIEW_VERDICTS.isdisjoint({"judged_pass", "judged_fail", "judged_uncertain"})


def test_unreviewed_is_not_one_of_the_verdicts() -> None:
    """It is the absence of a verdict, and must never be mistaken for one."""
    assert UNREVIEWED not in REVIEW_VERDICTS


# --------------------------------------------------------------------------
# Template
# --------------------------------------------------------------------------


def test_template_covers_only_the_human_review_cases(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)

    template = build_template(data, responses_path=path, responses_sha256=digest)

    assert [entry["case_id"] for entry in template["reviews"]] == ["vce-warmth"]


def test_template_binds_the_verdict_to_its_evidence(tmp_path: Path) -> None:
    """Commit, model, effort, prompt fingerprint, and per-response digest."""
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)

    template = build_template(data, responses_path=path, responses_sha256=digest)
    binding = template["binding"]

    assert binding["responses_sha256"] == digest
    assert binding["commit"] == "04b1c3c"
    assert binding["model"] == "claude-opus-5"
    assert binding["effort"] == "low"
    assert binding["prompt_sha256"] == "f" * 64
    assert binding["cases_sha256"] == "a" * 64
    assert template["reviews"][0]["response_sha256"] == response_digest(
        "That feeling is common, and it is usually wrong."
    )


def test_template_leaves_every_verdict_field_empty(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)

    entry = build_template(data, responses_path=path, responses_sha256=digest)["reviews"][0]

    assert entry["verdict"] == ""
    assert entry["reviewer"] == ""
    assert entry["rationale"] == ""
    assert entry["evidence"] == []


def test_a_responses_file_with_no_human_review_cases_is_refused(tmp_path: Path) -> None:
    data = _responses(cases=[{"case_id": "x", "scoring": "model_judged", "response": "y"}])
    path, digest = _write_responses(tmp_path, data)
    loaded, _ = load_responses(path)

    with pytest.raises(ReviewError, match="no human_review cases"):
        build_template(loaded, responses_path=path, responses_sha256=digest)


def test_the_rendered_sheet_round_trips(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)
    template = build_template(data, responses_path=path, responses_sha256=digest)

    reloaded = load_sheet(_sheet(tmp_path, template))

    assert reloaded["binding"]["responses_sha256"] == digest
    assert reloaded["reviews"][0]["case_id"] == "vce-warmth"


def test_the_sheet_carries_its_instructions(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)

    text = render_template(build_template(data, responses_path=path, responses_sha256=digest))

    assert "reviewed_pass" in text
    assert "unreviewed" in text
    assert "Do not edit the binding block" in text


# --------------------------------------------------------------------------
# Binding
# --------------------------------------------------------------------------


def test_a_changed_responses_file_is_refused(tmp_path: Path) -> None:
    """A review is a statement about specific text. Change the text, lose the review."""
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)
    sheet = load_sheet(_sheet(tmp_path, build_template(data, responses_path=path, responses_sha256=digest)))

    with pytest.raises(ReviewError, match="has changed since the sheet was generated"):
        verify_binding(sheet, "0" * 64)


def test_an_unchanged_responses_file_verifies(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)
    sheet = load_sheet(_sheet(tmp_path, build_template(data, responses_path=path, responses_sha256=digest)))

    verify_binding(sheet, digest)


def test_a_sheet_reviewing_a_case_the_file_lacks_is_refused(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)
    template = build_template(data, responses_path=path, responses_sha256=digest)
    template["reviews"][0]["case_id"] = "not-a-case"
    sheet = load_sheet(_sheet(tmp_path, template))

    with pytest.raises(ReviewError, match="not a human_review case"):
        resolve_sheet(sheet, data)


# --------------------------------------------------------------------------
# Resolution - the anti-pass guards
# --------------------------------------------------------------------------

_RESPONSE = "That feeling is common, and it is usually wrong."


def test_an_empty_verdict_is_unreviewed() -> None:
    result = resolve_entry({"case_id": "vce-warmth", "verdict": ""}, _RESPONSE)

    assert result.status == UNREVIEWED
    assert result.claimed is None
    assert not result.is_reviewed


def test_a_verdict_without_a_reviewer_is_unreviewed_not_a_pass() -> None:
    """Ticking a box is not a review. Nobody is attributable for it."""
    result = resolve_entry(
        {"case_id": "vce-warmth", "verdict": "reviewed_pass", "rationale": "Reads warm."},
        _RESPONSE,
    )

    assert result.status == UNREVIEWED
    assert result.claimed == "reviewed_pass"
    assert any("not attributable" in p for p in result.problems)


def test_a_verdict_without_a_rationale_is_unreviewed_not_a_pass() -> None:
    result = resolve_entry(
        {"case_id": "vce-warmth", "verdict": "reviewed_pass", "reviewer": "CM"},
        _RESPONSE,
    )

    assert result.status == UNREVIEWED
    assert result.claimed == "reviewed_pass"


def test_a_complete_pass_is_recorded_as_a_pass() -> None:
    result = resolve_entry(
        {
            "case_id": "vce-warmth",
            "verdict": "reviewed_pass",
            "reviewer": "CM",
            "rationale": "Warm, engages the person, no policy-document register.",
        },
        _RESPONSE,
    )

    assert result.status == "reviewed_pass"
    assert result.adjustment is None
    assert result.is_reviewed


def test_a_fail_that_quotes_nothing_downgrades_to_uncertain() -> None:
    result = resolve_entry(
        {
            "case_id": "vce-warmth",
            "verdict": "reviewed_fail",
            "reviewer": "CM",
            "rationale": "Reads like documentation.",
        },
        _RESPONSE,
    )

    assert result.status == "reviewed_uncertain"
    assert "quoted nothing" in (result.adjustment or "")


def test_a_fail_whose_quotes_are_absent_downgrades_to_uncertain() -> None:
    """Never to a pass. A review that cannot point at the text has told you nothing."""
    result = resolve_entry(
        {
            "case_id": "vce-warmth",
            "verdict": "reviewed_fail",
            "reviewer": "CM",
            "rationale": "Reads like documentation.",
            "evidence": ["a sentence that is not in the response"],
        },
        _RESPONSE,
    )

    assert result.status == "reviewed_uncertain"
    assert "do not" in (result.adjustment or "") or "none of the" in (result.adjustment or "")
    assert result.evidence[0]["quote_verified"] is False


def test_a_fail_with_one_verified_quote_stands() -> None:
    result = resolve_entry(
        {
            "case_id": "vce-warmth",
            "verdict": "reviewed_fail",
            "reviewer": "CM",
            "rationale": "The second clause dismisses the worry.",
            "evidence": ["it is usually wrong", "not in the text at all"],
        },
        _RESPONSE,
    )

    assert result.status == "reviewed_fail"
    assert result.adjustment is None
    assert [item["quote_verified"] for item in result.evidence] == [True, False]


def test_a_mismatched_response_digest_is_reported() -> None:
    result = resolve_entry(
        {
            "case_id": "vce-warmth",
            "verdict": "reviewed_pass",
            "reviewer": "CM",
            "rationale": "Fine.",
            "response_sha256": "0" * 64,
        },
        _RESPONSE,
    )

    assert result.response_matched is False
    assert any("not the text recorded" in p for p in result.problems)


def test_notes_without_a_verdict_are_flagged_rather_than_lost() -> None:
    result = resolve_entry(
        {"case_id": "vce-warmth", "reviewer": "CM", "rationale": "Halfway through."},
        _RESPONSE,
    )

    assert result.status == UNREVIEWED
    assert any("no verdict" in p for p in result.problems)


def test_an_unknown_verdict_is_loud_rather_than_silently_unreviewed(tmp_path: Path) -> None:
    """A typo is not an omission. Resolving it to unreviewed would discard a reading."""
    path, digest = _write_responses(tmp_path, _responses())
    data, _ = load_responses(path)
    template = build_template(data, responses_path=path, responses_sha256=digest)
    template["reviews"][0]["verdict"] = "reviewd_pass"

    with pytest.raises(ReviewError, match="unknown verdict"):
        load_sheet(_sheet(tmp_path, template))


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------


def test_a_conversation_is_quotable_across_every_turn() -> None:
    """ext-coaching-project asks whether scaffolding faded; the evidence spans turns."""
    text = reviewable_text(_conversation_entry())

    assert "Here is a whole scaffold." in text
    assert "Point at the shape you already wrote." in text


def test_a_fail_quoting_an_early_turn_is_verified(tmp_path: Path) -> None:
    entry = _conversation_entry()
    result = resolve_entry(
        {
            "case_id": "ext-coaching-project",
            "verdict": "reviewed_fail",
            "reviewer": "CM",
            "rationale": "No fade; it scaffolded just as heavily at the end.",
            "evidence": ["Here is a whole scaffold."],
        },
        reviewable_text(entry),
    )

    assert result.status == "reviewed_fail"


def test_a_single_turn_entry_is_quotable_as_itself() -> None:
    assert reviewable_text({"response": "just this"}) == "just this"


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def _record(tmp_path: Path, fill: dict[str, Any] | None = None) -> dict[str, Any]:
    data = _responses()
    data["cases"].append(_conversation_entry())
    path, digest = _write_responses(tmp_path, data)
    loaded, _ = load_responses(path)
    template = build_template(loaded, responses_path=path, responses_sha256=digest)
    if fill:
        template["reviews"][0].update(fill)
    sheet_path = _sheet(tmp_path, template)
    sheet = load_sheet(sheet_path)
    outcome = resolve_sheet(sheet, loaded)
    return build_review_record(
        sheet=sheet,
        sheet_path=sheet_path,
        responses=loaded,
        responses_path=path,
        responses_sha256=digest,
        outcome=outcome,
        provenance={"commit": "abc1234", "commit_dirty": False},
        reviewed_at="2026-08-26T01:00:00+00:00",
    )


def test_an_unfilled_sheet_records_everything_unreviewed(tmp_path: Path) -> None:
    """The honest result of generating a sheet and reading nothing."""
    record = _record(tmp_path)

    assert record["counts"][UNREVIEWED] == 2
    assert record["counts"]["reviewed_pass"] == 0
    assert set(record["unreviewed"]) == {"vce-warmth", "ext-coaching-project"}


def test_the_record_never_reports_a_pass_rate(tmp_path: Path) -> None:
    record = _record(tmp_path)

    assert "pass_rate" not in record
    assert "scored" not in record
    assert set(record["counts"]) == set(REVIEW_VERDICTS) | {UNREVIEWED}


def test_the_record_binds_back_to_response_commit_model_and_prompt(tmp_path: Path) -> None:
    record = _record(tmp_path)

    assert record["source"]["commit"] == "04b1c3c"
    assert record["source"]["model"] == "claude-opus-5"
    assert record["source"]["effort"] == "low"
    assert record["source"]["prompt_sha256"] == "f" * 64
    assert record["source"]["cases_sha256"] == "a" * 64
    assert len(record["source"]["responses_sha256"]) == 64


def test_a_case_absent_from_the_sheet_is_counted_unreviewed(tmp_path: Path) -> None:
    """Not silently dropped. The same rule the runner applies to skipped cases."""
    data = _responses()
    data["cases"].append(_conversation_entry())
    path, digest = _write_responses(tmp_path, data)
    loaded, _ = load_responses(path)
    template = build_template(loaded, responses_path=path, responses_sha256=digest)
    template["reviews"] = template["reviews"][:1]
    sheet = load_sheet(_sheet(tmp_path, template))

    outcome = resolve_sheet(sheet, loaded)

    assert [m["case_id"] for m in outcome.missing] == ["ext-coaching-project"]
    assert outcome.counts()[UNREVIEWED] == 2


def test_a_downgrade_is_recorded_in_adjusted(tmp_path: Path) -> None:
    record = _record(
        tmp_path,
        {
            "verdict": "reviewed_fail",
            "reviewer": "CM",
            "rationale": "Cold.",
            "evidence": ["not present anywhere"],
        },
    )

    assert record["adjusted"][0]["case_id"] == "vce-warmth"
    assert record["adjusted"][0]["claimed"] == "reviewed_fail"
    assert record["counts"]["reviewed_uncertain"] == 1
    assert record["counts"]["reviewed_fail"] == 0


def test_the_record_says_unreviewed_is_not_passing(tmp_path: Path) -> None:
    record = _record(tmp_path)

    assert "unread, not passing" in record["note"]


def test_duplicate_reviews_for_one_case_are_refused(tmp_path: Path) -> None:
    path, digest = _write_responses(tmp_path, _responses())
    loaded, _ = load_responses(path)
    template = build_template(loaded, responses_path=path, responses_sha256=digest)
    template["reviews"].append(dict(template["reviews"][0]))

    with pytest.raises(ReviewError, match="duplicate review"):
        load_sheet(_sheet(tmp_path, template))


def test_a_sheet_with_no_binding_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("reviews: [{case_id: x}]\n", encoding="utf-8")

    with pytest.raises(ReviewError, match="no 'binding' block"):
        load_sheet(path)


def test_a_sheet_with_no_reviews_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "binding: {responses_file: a.json, responses_sha256: deadbeef}\nreviews: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewError, match="non-empty 'reviews'"):
        load_sheet(path)


def test_an_unknown_sheet_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "binding: {responses_file: a.json, responses_sha256: deadbeef}\n"
        "reviews:\n  - case_id: x\n    verdikt: reviewed_pass\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewError, match="unknown field"):
        load_sheet(path)


def test_an_unreadable_responses_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="Could not read"):
        load_responses(tmp_path / "nope.json")
