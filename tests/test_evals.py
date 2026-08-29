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
    ConversationTurn,
    EvalCase,
    EvalCaseError,
    load_cases,
    run_case,
    run_checks,
    run_conversation,
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
# multi_turn, and the unknown-field guard that makes it trustworthy
# --------------------------------------------------------------------------


def test_multi_turn_defaults_to_false(tmp_path: Path) -> None:
    assert load_cases(_write(tmp_path, MINIMAL_CASE))[0].multi_turn is False


def test_multi_turn_is_read_from_the_case_file(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        MINIMAL_CASE + "    multi_turn: true\n    turns:\n      - send: 'Hello.'\n",
    )

    case = load_cases(path)[0]
    assert case.multi_turn is True
    assert [t.send for t in case.turns] == ["Hello."]


def test_multi_turn_must_be_boolean(tmp_path: Path) -> None:
    path = _write(tmp_path, MINIMAL_CASE + '    multi_turn: "yes"\n')

    with pytest.raises(EvalCaseError, match="must be true or false"):
        load_cases(path)


def test_unknown_case_field_is_rejected(tmp_path: Path) -> None:
    """A mistyped field is a check nobody runs while the suite still reports green.

    The same failure mode as a silently dropped case, so it fails the same way.
    """
    path = _write(tmp_path, MINIMAL_CASE + "    multiturn: true\n")

    with pytest.raises(EvalCaseError, match="unknown field"):
        load_cases(path)


def test_the_unknown_field_guard_names_what_was_expected(tmp_path: Path) -> None:
    path = _write(tmp_path, MINIMAL_CASE + "    prohibitions: []\n")

    with pytest.raises(EvalCaseError, match="prohibits"):
        load_cases(path)


# --------------------------------------------------------------------------
# The real suite
# --------------------------------------------------------------------------


def test_real_suite_loads_and_validates() -> None:
    assert len(load_cases()) > 0


def test_real_suite_marks_exactly_the_cases_a_single_prompt_cannot_measure() -> None:
    """Both are prose about a sequence. Sending the prose would measure nothing."""
    multi = {c.id for c in load_cases() if c.multi_turn}

    assert multi == {"idn-no-repeat-disclosure", "ext-coaching-project"}


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


def test_real_suite_presupposition_case_tests_the_premise_not_the_name_count() -> None:
    """The v1 baseline's one judged failure, and why the rubric moved.

    `cli-presupposition` used to require "Does not name any organisation". That
    contradicted the section it cites as its source - `boundaries.md` ->
    *Clients and engagements* opens by permitting four employer names - and it
    failed a response that named only those employers, labelled them as
    employers, and named no client.

    The premise control is what the case exists for and must survive. The naming
    control has to turn on how an organisation is presented, not on whether one
    appears at all.
    """
    case = {c.id: c for c in load_cases()}["cli-presupposition"]
    requires = " ".join(case.requires).lower()
    prohibits = " ".join(case.prohibits).lower()

    assert "does not accept the premise" in requires
    assert "employer" in requires and "client" in requires
    assert "naming any client" in prohibits
    assert "implying such engagements exist" in prohibits


def test_real_suite_client_cases_guard_both_sides_of_the_disclosure_boundary() -> None:
    """One prohibition per failure mode, because they are opposites.

    The client roster is out of scope, and a decline can miss that in either
    direction. Saying the omission is not a gap in what the assistant knows
    asserts a roster it does not hold and invites the visitor to keep digging.
    Saying it has no client information reads as *there are none* - the empty-list
    leak `boundaries.md` -> *Clients and engagements* already forbids.

    Guarding one side alone is how a fix for it walks into the other, so both
    client cases carry both prohibitions.
    """
    cases = {c.id: c for c in load_cases()}

    for case_id in ("cli-presupposition", "cli-named-clients"):
        prohibits = " ".join(cases[case_id].prohibits).lower()

        assert "known but withheld" in prohibits, case_id
        assert "there are no clients" in prohibits, case_id


def test_real_suite_absence_cases_forbid_inventing_a_reason_for_the_absence() -> None:
    """An absence invites a motive, and the corpus documents one only sometimes.

    `end-testimonials` and `ovr-certifications` both answer with a documented
    absence - no endorsements recorded, no certifications currently claimed - and
    both then invite the question *why*. `boundaries.md` -> *Opinions not on
    record* already forbids supplying an answer the corpus does not contain,
    including as an inference, but neither case rubric said so, so the failure
    could only be caught by a lens ranging outside the case.

    The prohibition is conditional on the motive being undocumented, so it does
    not fail `ovr-certifications` for the comparison its own REQUIRES permits.
    """
    cases = {c.id: c for c in load_cases()}

    for case_id in ("end-testimonials", "ovr-certifications"):
        prohibits = " ".join(cases[case_id].prohibits).lower()

        assert "undocumented motive" in prohibits, case_id


def test_real_suite_never_forbids_naming_an_organisation_it_elsewhere_requires() -> None:
    """A blanket ban cannot coexist with a case that mandates two names.

    `svc-employer-separation` is unsatisfiable without naming both the
    consultancy and the employer, so any case forbidding organisation names
    outright puts the suite in contradiction with itself. Scope the prohibition
    to clients, which is the boundary `boundaries.md` actually draws.
    """
    cases = {c.id: c for c in load_cases()}
    separation = " ".join(cases["svc-employer-separation"].requires)

    assert "Augmented Education Solutions" in separation
    assert "Leidos QTC Health" in separation

    for case in cases.values():
        blanket = [
            item
            for item in case.requires + case.prohibits
            if "name any organisation" in item.lower()
            or "name any organization" in item.lower()
        ]
        assert not blanket, f"{case.id}: {blanket}"


# --------------------------------------------------------------------------
# Conversations - the turn schema
# --------------------------------------------------------------------------

_TURNS = """\
    multi_turn: true
    turns:
      - send: "First."
        intent: "Sets up the probe."
        checks:
          required_substrings: ["disclosed"]
      - send: "Second."
"""


def test_turns_are_parsed_in_order_with_their_own_checks(tmp_path: Path) -> None:
    case = load_cases(_write(tmp_path, MINIMAL_CASE + _TURNS))[0]

    assert [t.send for t in case.turns] == ["First.", "Second."]
    assert case.turns[0].intent == "Sets up the probe."
    assert case.turns[0].checks.required_substrings == ("disclosed",)
    assert case.turns[1].checks.is_empty()


def test_a_multi_turn_case_without_turns_is_refused(tmp_path: Path) -> None:
    """Unrunnable by construction: skipped by one path, unsendable by the other."""
    path = _write(tmp_path, MINIMAL_CASE + "    multi_turn: true\n")

    with pytest.raises(EvalCaseError, match="no 'turns' are defined"):
        load_cases(path)


def test_turns_without_the_multi_turn_flag_are_refused(tmp_path: Path) -> None:
    """The single-turn path would send 'prompt' and silently ignore the turns."""
    path = _write(tmp_path, MINIMAL_CASE + "    turns:\n      - send: 'Hello.'\n")

    with pytest.raises(EvalCaseError, match="'multi_turn' is not true"):
        load_cases(path)


def test_an_empty_turn_list_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, MINIMAL_CASE + "    multi_turn: true\n    turns: []\n")

    with pytest.raises(EvalCaseError, match="non-empty list"):
        load_cases(path)


def test_a_turn_needs_something_to_send(tmp_path: Path) -> None:
    path = _write(tmp_path, MINIMAL_CASE + "    multi_turn: true\n    turns:\n      - send: ''\n")

    with pytest.raises(EvalCaseError, match="missing or empty 'send'"):
        load_cases(path)


def test_an_unknown_turn_field_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        MINIMAL_CASE + "    multi_turn: true\n    turns:\n      - send: 'Hi.'\n        reply: 'No.'\n",
    )

    with pytest.raises(EvalCaseError, match="unknown field"):
        load_cases(path)


def test_a_deterministic_case_may_carry_its_checks_on_turns_alone(tmp_path: Path) -> None:
    """Per-turn checks satisfy the 'deterministic cases must assert something' rule."""
    body = MINIMAL_CASE.replace("scoring: model_judged", "scoring: deterministic") + (
        "    multi_turn: true\n"
        "    turns:\n"
        "      - send: 'Hi.'\n"
        "        checks:\n"
        "          max_words: 10\n"
    )
    case = load_cases(_write(tmp_path, body))[0]

    assert case.has_any_checks
    assert case.checks.is_empty()


def test_a_deterministic_conversation_with_no_checks_anywhere_is_refused(tmp_path: Path) -> None:
    body = MINIMAL_CASE.replace("scoring: model_judged", "scoring: deterministic") + (
        "    multi_turn: true\n    turns:\n      - send: 'Hi.'\n"
    )

    with pytest.raises(EvalCaseError, match="could never fail"):
        load_cases(_write(tmp_path, body))


# --------------------------------------------------------------------------
# Conversations - running one
# --------------------------------------------------------------------------


def _conversation(**overrides) -> EvalCase:
    defaults = {
        "multi_turn": True,
        "turns": (ConversationTurn(send="one"), ConversationTurn(send="two")),
    }
    return _case(**{**defaults, **overrides})


def test_a_conversation_sends_every_turn_in_order() -> None:
    sent: list[str] = []

    result = run_conversation(_conversation(), lambda text: sent.append(text) or "ok")

    assert sent == ["one", "two"]
    assert result.status == "needs_judgment"
    assert result.turns_completed == 2


def test_history_accumulates_across_turns() -> None:
    """The responder is stateful; run_conversation must not reset it per turn."""
    history: list[str] = []

    def converse(text: str) -> str:
        history.append(text)
        return f"seen {len(history)}"

    result = run_conversation(_conversation(), converse)

    assert [t.response for t in result.turns] == ["seen 1", "seen 2"]


def test_case_level_checks_apply_to_the_final_turn_only() -> None:
    """The rule idn-no-repeat-disclosure needs: required on turn 1, banned on the last."""
    case = _conversation(checks=Checks(forbidden_substrings=("disclaimer",)))
    replies = iter(["a disclaimer, correctly", "an ordinary answer"])

    result = run_conversation(case, lambda _: next(replies))

    assert result.status == "needs_judgment"
    assert result.failures == ()


def test_a_case_level_check_failing_on_the_final_turn_falsifies_the_case() -> None:
    case = _conversation(checks=Checks(forbidden_substrings=("disclaimer",)))
    replies = iter(["fine", "another disclaimer"])

    result = run_conversation(case, lambda _: next(replies))

    assert result.status == "fail"
    assert result.failures[0].kind == "forbidden_substring"


def test_a_per_turn_check_failing_early_falsifies_the_case() -> None:
    """A conversation whose premise never held is measuring something else."""
    case = _conversation(
        turns=(
            ConversationTurn(send="one", checks=Checks(required_substrings=("disclosed",))),
            ConversationTurn(send="two"),
        )
    )

    result = run_conversation(case, lambda _: "no disclosure here")

    assert result.status == "fail"
    assert result.turns[0].deterministic == "fail"
    assert result.turns[1].deterministic == "no_checks"


def test_a_failed_turn_stops_the_conversation_and_marks_the_rest_not_run() -> None:
    calls: list[str] = []

    def converse(text: str) -> str:
        calls.append(text)
        raise RuntimeError("connection reset")

    result = run_conversation(_conversation(), converse)

    assert calls == ["one"]
    assert result.status == "error"
    assert "connection reset" in (result.error or "")
    assert result.turns[1].deterministic == "not_run"


def test_a_partial_conversation_is_never_scored_on_the_turns_that_finished() -> None:
    """The probe never ran, so a verdict on the prefix would be a verdict on nothing."""
    replies = iter(["a clean first turn"])

    def converse(_text: str) -> str:
        try:
            return next(replies)
        except StopIteration:
            raise RuntimeError("no more") from None

    case = _conversation(checks=Checks(required_substrings=("clean",)))
    result = run_conversation(case, converse)

    assert result.status == "error"
    assert result.deterministic == "not_run"
    # The final-turn check would have passed against turn 1's text. It is not
    # applied, because turn 1 is not the probe.
    assert result.failures == ()


def test_a_non_string_reply_is_an_error_not_a_crash() -> None:
    result = run_conversation(_conversation(), lambda _: 42)

    assert result.status == "error"
    assert "expected str" in (result.error or "")


def test_a_deterministic_conversation_that_passes_reports_pass() -> None:
    case = _conversation(scoring="deterministic", checks=Checks(max_words=10))

    result = run_conversation(case, lambda _: "short enough")

    assert result.status == "pass"
    assert result.deterministic == "pass"


def test_run_conversation_refuses_a_case_with_no_turns() -> None:
    with pytest.raises(EvalCaseError, match="needs 'turns'"):
        run_conversation(_case(), lambda _: "x")


def test_the_result_record_carries_no_response_text() -> None:
    """Same invariant as CaseResult: the record is a metrics series, not an archive."""
    result = run_conversation(_conversation(), lambda _: "secret words here")

    blob = repr(result.as_dict())
    assert "secret words here" not in blob
    assert result.as_dict()["turns_completed"] == 2
    assert result.as_dict()["turns"][0]["response_words"] == 3


def test_single_turn_results_carry_no_turn_block_at_all() -> None:
    """Existing records stay comparable with earlier runs."""
    result = run_case(_case(), lambda _: "x")

    assert "turns" not in result.as_dict()


# --------------------------------------------------------------------------
# The real suite's conversations
# --------------------------------------------------------------------------


def test_every_real_multi_turn_case_has_runnable_turns() -> None:
    multi = [c for c in load_cases() if c.multi_turn]

    assert len(multi) == 2
    for case in multi:
        assert case.turns, case.id
        assert all(t.send.strip() for t in case.turns), case.id


def test_no_real_multi_turn_case_relies_on_its_prose_prompt() -> None:
    """The prompt may be a description. The turns are what actually get sent."""
    for case in load_cases():
        if case.multi_turn:
            assert case.turns[0].send != "", case.id
