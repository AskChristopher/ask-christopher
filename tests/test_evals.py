"""Tests for the evaluation framework.

Two things are under test and they are easy to confuse:

* **The framework** — loading, validating, and scoring. Tested with synthetic
  cases written inline, so editing the real suite never breaks these.
* **The real suite** — that ``tests/evals/cases.yaml`` is well-formed and
  structurally sound. A handful of tests at the end cover that.

No API calls. The runner takes an injected response function precisely so the
framework can be exercised offline.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ask_christopher.evals import (
    CATEGORIES,
    SCORING_MODES,
    Checks,
    EvalCase,
    EvalCaseError,
    load_cases,
    run_case,
    run_checks,
    run_suite,
)

MINIMAL_CASE = """\
cases:
  - id: t-001
    category: trap
    prompt: "A question."
    tests: "What this measures."
    source: "knowledge/boundaries.md — Somewhere"
    scoring: model_judged
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "cases.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _case(**overrides) -> EvalCase:
    defaults = {
        "id": "t-001",
        "category": "trap",
        "prompt": "A question.",
        "tests": "What this measures.",
        "source": "knowledge/boundaries.md — Somewhere",
        "scoring": "model_judged",
    }
    return EvalCase(**{**defaults, **overrides})


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def test_loads_a_minimal_case(tmp_path: Path) -> None:
    cases = load_cases(_write(tmp_path, MINIMAL_CASE))

    assert len(cases) == 1
    assert cases[0].id == "t-001"
    assert cases[0].checks.is_empty()


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="Could not read"):
        load_cases(tmp_path / "absent.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="not valid YAML"):
        load_cases(_write(tmp_path, "cases: [unclosed\n"))


def test_empty_case_list_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="no non-empty 'cases' list"):
        load_cases(_write(tmp_path, "cases: []\n"))


def test_top_level_list_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="mapping at the top level"):
        load_cases(_write(tmp_path, "- id: t-001\n"))


# --------------------------------------------------------------------------
# Malformed cases
# --------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["id", "category", "prompt", "tests", "source", "scoring"])
def test_missing_required_field_raises(tmp_path: Path, missing: str) -> None:
    """Built from a dict rather than by stripping lines.

    Line-stripping would delete the ``- `` list marker along with ``id:`` and
    produce a YAML error instead of the validation error under test.
    """
    import yaml

    case = {
        "id": "t-001",
        "category": "trap",
        "prompt": "A question.",
        "tests": "What this measures.",
        "source": "knowledge/boundaries.md — Somewhere",
        "scoring": "model_judged",
    }
    del case[missing]
    body = yaml.safe_dump({"cases": [case]}, allow_unicode=True)

    with pytest.raises(EvalCaseError, match=f"required field '{missing}'"):
        load_cases(_write(tmp_path, body))


def test_empty_required_field_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="required field 'prompt'"):
        load_cases(_write(tmp_path, MINIMAL_CASE.replace('"A question."', '""')))


def test_unknown_scoring_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="unknown scoring mode 'vibes'"):
        load_cases(_write(tmp_path, MINIMAL_CASE.replace("model_judged", "vibes")))


def test_unknown_category_raises(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="unknown category 'misc'"):
        load_cases(_write(tmp_path, MINIMAL_CASE.replace("category: trap", "category: misc")))


def test_duplicate_ids_raise(tmp_path: Path) -> None:
    with pytest.raises(EvalCaseError, match="duplicate case id 't-001'"):
        load_cases(_write(tmp_path, MINIMAL_CASE + MINIMAL_CASE.replace("cases:\n", "")))


def test_unknown_check_key_raises(tmp_path: Path) -> None:
    body = MINIMAL_CASE + "    checks:\n      forbidden_words: [nope]\n"
    with pytest.raises(EvalCaseError, match="unknown check"):
        load_cases(_write(tmp_path, body))


def test_uncompilable_regex_raises(tmp_path: Path) -> None:
    body = MINIMAL_CASE + "    checks:\n      forbidden_patterns: ['([unclosed']\n"
    with pytest.raises(EvalCaseError, match="forbidden_patterns"):
        load_cases(_write(tmp_path, body))


def test_negative_word_limit_raises(tmp_path: Path) -> None:
    body = MINIMAL_CASE + "    checks:\n      max_words: -5\n"
    with pytest.raises(EvalCaseError, match="'max_words' must be a positive integer"):
        load_cases(_write(tmp_path, body))


def test_min_exceeding_max_raises(tmp_path: Path) -> None:
    body = MINIMAL_CASE + "    checks:\n      max_words: 10\n      min_words: 50\n"
    with pytest.raises(EvalCaseError, match="min_words .* exceeds max_words"):
        load_cases(_write(tmp_path, body))


def test_deterministic_case_without_checks_raises(tmp_path: Path) -> None:
    """A deterministic case with no checks could never fail — a silent free pass."""
    with pytest.raises(EvalCaseError, match="could never fail"):
        load_cases(_write(tmp_path, MINIMAL_CASE.replace("model_judged", "deterministic")))


# --------------------------------------------------------------------------
# Pairing
# --------------------------------------------------------------------------


def test_pair_to_unknown_case_raises(tmp_path: Path) -> None:
    body = MINIMAL_CASE + "    pair: t-999\n"
    with pytest.raises(EvalCaseError, match="pairs with unknown case 't-999'"):
        load_cases(_write(tmp_path, body))


def test_self_pair_raises(tmp_path: Path) -> None:
    body = MINIMAL_CASE + "    pair: t-001\n"
    with pytest.raises(EvalCaseError, match="paired with itself"):
        load_cases(_write(tmp_path, body))


def test_one_way_pair_raises(tmp_path: Path) -> None:
    """Both halves must point at each other, or one can be deleted unnoticed."""
    body = """\
    cases:
      - id: t-001
        category: trap
        prompt: "A."
        tests: "x"
        source: "s"
        scoring: model_judged
        pair: t-002
      - id: t-002
        category: over_refusal
        prompt: "B."
        tests: "y"
        source: "s"
        scoring: model_judged
    """
    with pytest.raises(EvalCaseError, match="pairs must be reciprocal"):
        load_cases(_write(tmp_path, body))


def test_reciprocal_pair_loads(tmp_path: Path) -> None:
    body = """\
    cases:
      - id: t-001
        category: trap
        prompt: "A."
        tests: "x"
        source: "s"
        scoring: model_judged
        pair: t-002
      - id: t-002
        category: over_refusal
        prompt: "B."
        tests: "y"
        source: "s"
        scoring: model_judged
        pair: t-001
    """
    assert len(load_cases(_write(tmp_path, body))) == 2


# --------------------------------------------------------------------------
# Deterministic checks
# --------------------------------------------------------------------------


def test_forbidden_substring_is_case_insensitive() -> None:
    case = _case(checks=Checks(forbidden_substrings=("Great question",)))
    failures = run_checks(case, "GREAT QUESTION — here you go.")

    assert [f.kind for f in failures] == ["forbidden_substring"]


def test_required_substring_missing_is_reported() -> None:
    case = _case(checks=Checks(required_substrings=("ChristopherMathews.com",)))

    assert run_checks(case, "Reach out through his website.")
    assert not run_checks(case, "Reach him at christophermathews.com anytime.")


def test_required_any_needs_one_of_the_group() -> None:
    case = _case(checks=Checks(required_any=(("dict comprehension", "{"),)))

    assert not run_checks(case, "Use a dict comprehension.")
    assert not run_checks(case, "Write {k: v for k, v in pairs}.")
    assert run_checks(case, "Use a loop instead.")


def test_forbidden_pattern_catches_a_currency_figure() -> None:
    case = _case(checks=Checks(forbidden_patterns=(r"\$\s?\d",)))

    assert run_checks(case, "Roughly $150 per hour.")
    assert not run_checks(case, "Pricing depends on scope and is discussed directly.")


def test_word_limits_are_enforced_in_both_directions() -> None:
    case = _case(checks=Checks(max_words=3, min_words=2))

    assert [f.kind for f in run_checks(case, "one two three four")] == ["too_long"]
    assert [f.kind for f in run_checks(case, "one")] == ["too_short"]
    assert not run_checks(case, "one two")


def test_all_failing_checks_are_reported_not_just_the_first() -> None:
    case = _case(
        checks=Checks(
            forbidden_substrings=("nope",),
            required_substrings=("yes",),
            max_words=2,
        )
    )
    failures = run_checks(case, "nope nope nope nope")

    assert len(failures) == 3


def test_no_checks_means_nothing_falsified() -> None:
    assert run_checks(_case(), "literally anything at all") == ()


# --------------------------------------------------------------------------
# Scoring semantics — the integrity of the framework
# --------------------------------------------------------------------------


def test_deterministic_case_passing_its_checks_passes() -> None:
    case = _case(scoring="deterministic", checks=Checks(max_words=10))
    result = run_case(case, lambda _: "short enough")

    assert result.status == "pass"
    assert result.deterministic == "pass"


def test_judged_case_passing_its_checks_is_not_a_pass() -> None:
    """The core rule: checks falsify judged cases, they never confirm them."""
    case = _case(scoring="model_judged", checks=Checks(max_words=10))
    result = run_case(case, lambda _: "short enough")

    assert result.deterministic == "pass"
    assert result.status == "needs_judgment"


def test_judged_case_with_no_checks_is_not_a_pass() -> None:
    result = run_case(_case(scoring="human_review"), lambda _: "anything")

    assert result.deterministic == "no_checks"
    assert result.status == "needs_judgment"


def test_a_failed_check_fails_a_judged_case() -> None:
    """A lexical failure is real even when full scoring needs judgement."""
    case = _case(scoring="model_judged", checks=Checks(forbidden_patterns=(r"\$\s?\d",)))
    result = run_case(case, lambda _: "About $200 an hour.")

    assert result.status == "fail"
    assert result.failures[0].kind == "forbidden_pattern"


def test_response_function_raising_is_recorded_not_propagated() -> None:
    def boom(_: str) -> str:
        raise RuntimeError("transport exploded")

    result = run_case(_case(), boom)

    assert result.status == "error"
    assert result.deterministic == "not_run"
    assert "transport exploded" in (result.error or "")


def test_non_string_response_is_an_error() -> None:
    result = run_case(_case(), lambda _: None)  # type: ignore[arg-type,return-value]

    assert result.status == "error"
    assert "expected str" in (result.error or "")


def test_runner_passes_the_prompt_to_the_response_function() -> None:
    seen: list[str] = []
    run_case(_case(prompt="the exact prompt"), lambda p: seen.append(p) or "ok")  # type: ignore[func-returns-value]

    assert seen == ["the exact prompt"]


# --------------------------------------------------------------------------
# Suite results
# --------------------------------------------------------------------------


def test_suite_counts_each_status() -> None:
    cases = [
        _case(id="a", scoring="deterministic", checks=Checks(max_words=10)),
        _case(id="b", scoring="deterministic", checks=Checks(max_words=1)),
        _case(id="c", scoring="model_judged"),
    ]
    suite = run_suite(cases, lambda _: "two words")

    assert suite.counts() == {"pass": 1, "fail": 1, "needs_judgment": 1, "error": 0}


def test_suite_record_separates_scored_from_unscored() -> None:
    """A pass rate must not be computed over cases nobody scored."""
    cases = [
        _case(id="a", scoring="deterministic", checks=Checks(max_words=10)),
        _case(id="b", scoring="human_review"),
    ]
    record = run_suite(cases, lambda _: "fine").as_dict()

    assert record["total"] == 2
    assert record["scored"] == 1
    assert record["unscored"] == 1


def test_suite_failures_include_errors() -> None:
    def boom(prompt: str) -> str:
        if prompt == "b":
            raise RuntimeError("x")
        return "ok"

    suite = run_suite([_case(id="a", prompt="a"), _case(id="b", prompt="b")], boom)

    assert {r.case_id for r in suite.failures} == {"b"}


def test_result_record_is_json_safe() -> None:
    import json

    suite = run_suite([_case(scoring="deterministic", checks=Checks(max_words=1))], lambda _: "a b")
    json.dumps(suite.as_dict())  # must not raise


def test_result_record_carries_no_response_text() -> None:
    """Only metrics and metadata are recorded, matching the client's baseline."""
    record = run_case(_case(), lambda _: "a secret-ish answer").as_dict()

    assert "response" not in record
    assert "text" not in record
    assert record["response_words"] == 3


# --------------------------------------------------------------------------
# The real suite
# --------------------------------------------------------------------------


def test_real_suite_loads_and_validates() -> None:
    assert len(load_cases()) > 0


def test_real_suite_ids_are_unique_and_stable_looking() -> None:
    cases = load_cases()
    ids = [c.id for c in cases]

    assert len(ids) == len(set(ids))
    assert all(c.id.replace("-", "").isalnum() for c in cases)


def test_real_suite_every_case_cites_a_source() -> None:
    """A case without a traceable source is one somebody invented."""
    for case in load_cases():
        assert "/" in case.source or "—" in case.source, case.id


def test_real_suite_categories_and_scoring_are_known() -> None:
    for case in load_cases():
        assert case.category in CATEGORIES
        assert case.scoring in SCORING_MODES


def test_real_suite_guards_both_directions_of_the_core_tradeoff() -> None:
    categories = {c.category for c in load_cases()}

    assert "trap" in categories
    assert "over_refusal" in categories


def test_real_suite_pairs_are_reciprocal() -> None:
    """Enforced by the loader; asserted here so the intent is visible."""
    cases = {c.id: c for c in load_cases()}
    paired = [c for c in cases.values() if c.pair]

    assert paired
    for case in paired:
        assert cases[case.pair].pair == case.id


def test_real_suite_deterministic_cases_all_carry_checks() -> None:
    for case in load_cases():
        if case.is_deterministic:
            assert not case.checks.is_empty(), case.id
