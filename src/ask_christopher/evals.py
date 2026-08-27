"""Behavioural evaluation framework.

The assessment instrument for the assistant itself. Unit tests prove the code
runs; this measures whether the assistant is accurate, teaches, and declines
when it should — the properties the product is actually judged on.

**What this can and cannot do.** Deterministic checks are lexical: substrings,
regexes, and length. They catch a real class of failure — a dollar figure in a
pricing answer, a promise to forward a message, a refusal phrase in a general
technical explanation — and they catch it cheaply and repeatably.

They cannot prove semantic correctness or voice fidelity. A lexical check
cannot tell whether an answer is *true*, whether it taught anything, or whether
it sounds like Christopher rather than a policy document. Worse, the obvious
lexical approach is often actively wrong: a correct denial of a fabricated
credential contains the very word you would search for.

So the framework is built around one rule:

    Deterministic checks can FALSIFY a judged case. They can never CONFIRM one.

A ``model_judged`` or ``human_review`` case whose checks all pass is reported as
``needs_judgment`` — never ``pass``. Pretending otherwise would manufacture a
pass rate that measures nothing, which is worse than having no pass rate.

Model-as-judge scoring is deliberately absent from this implementation. The
result record has room for it; nothing here calls a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

__all__ = [
    "EvalCaseError",
    "SCORING_MODES",
    "CATEGORIES",
    "Checks",
    "ConversationTurn",
    "EvalCase",
    "CheckFailure",
    "TurnResult",
    "CaseResult",
    "SuiteResult",
    "default_cases_path",
    "load_cases",
    "run_checks",
    "run_case",
    "run_conversation",
    "run_suite",
]


class EvalCaseError(ValueError):
    """A case file is malformed.

    Raised loudly rather than skipping the case. A silently dropped case is a
    behaviour nobody is measuring while the suite still reports green.
    """


#: How far a case can be scored, and by what.
SCORING_MODES = frozenset({"deterministic", "model_judged", "human_review"})

CATEGORIES = frozenset(
    {"accuracy", "trap", "over_refusal", "teaching", "voice", "identity", "evidence"}
)

_CHECK_KEYS = frozenset(
    {
        "forbidden_substrings",
        "required_substrings",
        "required_any",
        "forbidden_patterns",
        "max_words",
        "min_words",
    }
)

_REQUIRED_FIELDS = ("id", "category", "prompt", "tests", "source", "scoring")

#: Every field a case may carry. Unknown keys are rejected rather than ignored:
#: a mistyped field name is a check nobody is running while the suite still
#: reports green, which is the same failure mode a dropped case would be.
_CASE_KEYS = frozenset(_REQUIRED_FIELDS) | {
    "requires",
    "prohibits",
    "pair",
    "checks",
    "multi_turn",
    "turns",
}

_TURN_KEYS = frozenset({"send", "intent", "checks"})


@dataclass(frozen=True)
class Checks:
    """Lexical assertions. Matching is case-insensitive except for regexes."""

    forbidden_substrings: tuple[str, ...] = ()
    required_substrings: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    max_words: int | None = None
    min_words: int | None = None

    def is_empty(self) -> bool:
        return not (
            self.forbidden_substrings
            or self.required_substrings
            or self.required_any
            or self.forbidden_patterns
            or self.max_words is not None
            or self.min_words is not None
        )


@dataclass(frozen=True)
class ConversationTurn:
    """One user message in an ordered conversation.

    **Only the user side is authored.** There is deliberately no field for a
    scripted assistant reply: a conversation whose history was written for the
    model tests it against words it never said. ``idn-no-repeat-disclosure`` is
    the case that makes this load-bearing — whether identity "was already
    disclosed" has to be the assistant's own doing, or the probe measures
    nothing.

    ``intent`` is prose for the human reading the transcript. A reviewer facing
    four turns needs to know which one is the probe and what the others set up.

    ``checks`` are lexical assertions on *this* turn's reply. They exist mainly
    to falsify a conversation's premise early: if turn 1 was supposed to elicit
    disclosure and did not, every later turn is measuring something else.
    """

    send: str
    intent: str | None = None
    checks: Checks = field(default_factory=Checks)


@dataclass(frozen=True)
class EvalCase:
    """One behavioural case.

    ``requires`` and ``prohibits`` are prose, not assertions — they are the
    rubric a model or a person scores against. ``checks`` is the executable
    subset, and is deliberately much smaller.

    **When ``turns`` is present it is what gets sent, and ``prompt`` is the
    case's description rather than a message.** Two of the forty cases describe
    a sequence in prose that was never sendable; ``prompt`` stays required
    because thirty-eight cases use it as the message, and changing that for all
    of them to tidy two is not worth the churn.
    """

    id: str
    category: str
    prompt: str
    tests: str
    source: str
    scoring: str
    requires: tuple[str, ...] = ()
    prohibits: tuple[str, ...] = ()
    pair: str | None = None
    checks: Checks = field(default_factory=Checks)
    #: Needs a conversation, not a prompt. Either the case describes a sequence
    #: in prose, or what it measures only becomes visible across turns. A
    #: single-turn runner must skip these and say so rather than send the prose.
    multi_turn: bool = False
    #: The ordered user messages. Required when ``multi_turn`` is set, forbidden
    #: otherwise, so a case can never be flagged as needing a conversation while
    #: carrying no conversation to run.
    turns: tuple[ConversationTurn, ...] = ()

    @property
    def is_deterministic(self) -> bool:
        return self.scoring == "deterministic"

    @property
    def has_any_checks(self) -> bool:
        """Any executable assertion, at case level or on any turn."""
        return not self.checks.is_empty() or any(not t.checks.is_empty() for t in self.turns)


@dataclass(frozen=True)
class CheckFailure:
    kind: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail}


@dataclass(frozen=True)
class TurnResult:
    """Outcome for one turn of a conversation.

    ``response`` is held for the caller that builds the readable artifact and is
    deliberately absent from :meth:`as_dict`, for the same reason
    :class:`CaseResult` never carries response text: the result record is a
    metrics series compared across runs, not a transcript archive.

    ``deterministic`` is ``pass``, ``fail``, ``no_checks``, or ``not_run`` — the
    last meaning the conversation ended before this turn was reached.
    """

    index: int
    send: str
    intent: str | None
    deterministic: str
    response: str | None = None
    failures: tuple[CheckFailure, ...] = ()
    response_words: int = 0
    response_chars: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "intent": self.intent,
            "deterministic": self.deterministic,
            "failures": [f.as_dict() for f in self.failures],
            "response_words": self.response_words,
            "response_chars": self.response_chars,
            "error": self.error,
        }


@dataclass(frozen=True)
class CaseResult:
    """Outcome for one case.

    ``status`` is one of:

    ``pass``
        Deterministic case, all checks satisfied.
    ``fail``
        A check failed. Applies regardless of scoring mode — a lexical failure
        is a real failure even on a case that also needs judgement.
    ``needs_judgment``
        Nothing falsified it, but confirming it requires a model or a person.
    ``error``
        The response function raised, or a conversation ended before its last
        turn. An unfinished conversation is never scored on the turns that did
        complete — see :func:`run_conversation`.
    """

    case_id: str
    category: str
    scoring: str
    status: str
    deterministic: str
    failures: tuple[CheckFailure, ...] = ()
    response_words: int = 0
    response_chars: int = 0
    error: str | None = None
    #: Populated only by :func:`run_conversation`. Empty for single-turn cases,
    #: which keeps every existing record byte-comparable with earlier runs.
    turns: tuple[TurnResult, ...] = ()

    @property
    def turns_completed(self) -> int:
        return sum(1 for t in self.turns if t.response is not None)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": self.case_id,
            "category": self.category,
            "scoring": self.scoring,
            "status": self.status,
            "deterministic": self.deterministic,
            "failures": [f.as_dict() for f in self.failures],
            "response_words": self.response_words,
            "response_chars": self.response_chars,
            "error": self.error,
        }
        if self.turns:
            payload["turns_planned"] = len(self.turns)
            payload["turns_completed"] = self.turns_completed
            payload["turns"] = [t.as_dict() for t in self.turns]
        return payload


@dataclass(frozen=True)
class SuiteResult:
    results: tuple[CaseResult, ...]

    def counts(self) -> dict[str, int]:
        tally = {"pass": 0, "fail": 0, "needs_judgment": 0, "error": 0}
        for result in self.results:
            tally[result.status] += 1
        return tally

    @property
    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(r for r in self.results if r.status in {"fail", "error"})

    def as_dict(self) -> dict[str, Any]:
        counts = self.counts()
        return {
            "total": len(self.results),
            "counts": counts,
            # Stated explicitly so no downstream reader computes a pass rate
            # over cases that were never actually scored.
            "scored": counts["pass"] + counts["fail"],
            "unscored": counts["needs_judgment"],
            "results": [r.as_dict() for r in self.results],
        }


def default_cases_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "evals" / "cases.yaml"


# --------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------


def load_cases(path: Path | str | None = None) -> tuple[EvalCase, ...]:
    """Parse and validate a case file.

    Raises:
        EvalCaseError: The file is unreadable, malformed, or violates any of the
            structural rules — duplicate ids, unknown scoring mode, a
            non-reciprocal pair, an uncompilable regex, or a ``deterministic``
            case with no checks.
    """
    import yaml  # imported here so the rest of the package needs no YAML parser

    location = default_cases_path() if path is None else Path(path)

    try:
        raw = location.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvalCaseError(f"Could not read case file: {location} ({exc})") from exc

    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise EvalCaseError(f"Case file is not valid YAML: {location} ({exc})") from exc

    if not isinstance(document, Mapping):
        raise EvalCaseError(f"Case file must be a mapping at the top level: {location}")

    entries = document.get("cases")
    if not isinstance(entries, list) or not entries:
        raise EvalCaseError(f"Case file has no non-empty 'cases' list: {location}")

    cases = tuple(_build_case(entry, index) for index, entry in enumerate(entries))
    _validate_suite(cases)
    return cases


def _build_case(entry: Any, index: int) -> EvalCase:
    where = f"case #{index}"
    if not isinstance(entry, Mapping):
        raise EvalCaseError(f"{where}: expected a mapping, got {type(entry).__name__}")

    case_id = entry.get("id")
    if isinstance(case_id, str) and case_id.strip():
        where = f"case '{case_id}'"

    unknown = set(entry) - _CASE_KEYS
    if unknown:
        raise EvalCaseError(
            f"{where}: unknown field(s) {sorted(unknown)} "
            f"(expected any of {sorted(_CASE_KEYS)})"
        )

    for name in _REQUIRED_FIELDS:
        value = entry.get(name)
        if not isinstance(value, str) or not value.strip():
            raise EvalCaseError(f"{where}: missing or empty required field '{name}'")

    scoring = entry["scoring"]
    if scoring not in SCORING_MODES:
        raise EvalCaseError(
            f"{where}: unknown scoring mode '{scoring}' "
            f"(expected one of {sorted(SCORING_MODES)})"
        )

    category = entry["category"]
    if category not in CATEGORIES:
        raise EvalCaseError(
            f"{where}: unknown category '{category}' (expected one of {sorted(CATEGORIES)})"
        )

    pair = entry.get("pair")
    if pair is not None and (not isinstance(pair, str) or not pair.strip()):
        raise EvalCaseError(f"{where}: 'pair' must be a non-empty string when present")

    multi_turn = entry.get("multi_turn", False)
    if not isinstance(multi_turn, bool):
        raise EvalCaseError(f"{where}: 'multi_turn' must be true or false when present")

    checks = _build_checks(entry.get("checks"), where)
    turns = _build_turns(entry.get("turns"), where)

    # A case flagged as needing a conversation but carrying none is unrunnable
    # by construction: the single-turn path skips it and the conversation path
    # has nothing to send. That is exactly the silent-gap failure this module
    # raises on elsewhere, so it raises here too.
    if multi_turn and not turns:
        raise EvalCaseError(
            f"{where}: 'multi_turn' is true but no 'turns' are defined — "
            f"nothing could run it. Add turns, or drop the multi_turn flag."
        )
    if turns and not multi_turn:
        raise EvalCaseError(
            f"{where}: 'turns' are defined but 'multi_turn' is not true — "
            f"the single-turn path would send 'prompt' and ignore them."
        )

    # A deterministic case with no checks can never fail, which would quietly
    # inflate the pass rate with cases that assert nothing.
    case = EvalCase(
        id=entry["id"],
        category=category,
        prompt=entry["prompt"],
        tests=entry["tests"],
        source=entry["source"],
        scoring=scoring,
        requires=_string_tuple(entry.get("requires"), where, "requires"),
        prohibits=_string_tuple(entry.get("prohibits"), where, "prohibits"),
        pair=pair,
        checks=checks,
        multi_turn=multi_turn,
        turns=turns,
    )
    if scoring == "deterministic" and not case.has_any_checks:
        raise EvalCaseError(
            f"{where}: scoring is 'deterministic' but no checks are defined — "
            f"the case could never fail. Add checks, or use 'model_judged'."
        )
    return case


def _build_turns(raw: Any, where: str) -> tuple[ConversationTurn, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise EvalCaseError(f"{where}: 'turns' must be a non-empty list")

    turns: list[ConversationTurn] = []
    for position, item in enumerate(raw, start=1):
        spot = f"{where}: turn {position}"
        if not isinstance(item, Mapping):
            raise EvalCaseError(f"{spot}: expected a mapping, got {type(item).__name__}")

        unknown = set(item) - _TURN_KEYS
        if unknown:
            raise EvalCaseError(
                f"{spot}: unknown field(s) {sorted(unknown)} "
                f"(expected any of {sorted(_TURN_KEYS)})"
            )

        send = item.get("send")
        if not isinstance(send, str) or not send.strip():
            raise EvalCaseError(f"{spot}: missing or empty 'send'")

        intent = item.get("intent")
        if intent is not None and (not isinstance(intent, str) or not intent.strip()):
            raise EvalCaseError(f"{spot}: 'intent' must be a non-empty string when present")

        turns.append(
            ConversationTurn(send=send, intent=intent, checks=_build_checks(item.get("checks"), spot))
        )

    return tuple(turns)


def _build_checks(raw: Any, where: str) -> Checks:
    if raw is None:
        return Checks()
    if not isinstance(raw, Mapping):
        raise EvalCaseError(f"{where}: 'checks' must be a mapping")

    unknown = set(raw) - _CHECK_KEYS
    if unknown:
        raise EvalCaseError(
            f"{where}: unknown check(s) {sorted(unknown)} "
            f"(expected any of {sorted(_CHECK_KEYS)})"
        )

    patterns = _string_tuple(raw.get("forbidden_patterns"), where, "forbidden_patterns")
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise EvalCaseError(f"{where}: forbidden_patterns entry {pattern!r} — {exc}") from exc

    groups: list[tuple[str, ...]] = []
    raw_any = raw.get("required_any")
    if raw_any is not None:
        if not isinstance(raw_any, list):
            raise EvalCaseError(f"{where}: 'required_any' must be a list of lists")
        for group in raw_any:
            if not isinstance(group, list) or not group:
                raise EvalCaseError(f"{where}: each 'required_any' group must be a non-empty list")
            groups.append(_string_tuple(group, where, "required_any"))

    max_words = _optional_positive_int(raw.get("max_words"), where, "max_words")
    min_words = _optional_positive_int(raw.get("min_words"), where, "min_words")
    if max_words is not None and min_words is not None and min_words > max_words:
        raise EvalCaseError(f"{where}: min_words ({min_words}) exceeds max_words ({max_words})")

    return Checks(
        forbidden_substrings=_string_tuple(
            raw.get("forbidden_substrings"), where, "forbidden_substrings"
        ),
        required_substrings=_string_tuple(
            raw.get("required_substrings"), where, "required_substrings"
        ),
        required_any=tuple(groups),
        forbidden_patterns=patterns,
        max_words=max_words,
        min_words=min_words,
    )


def _string_tuple(value: Any, where: str, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise EvalCaseError(f"{where}: '{name}' must be a list")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise EvalCaseError(f"{where}: '{name}' entries must be non-empty strings")
    return tuple(value)


def _optional_positive_int(value: Any, where: str, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvalCaseError(f"{where}: '{name}' must be a positive integer")
    return value


def _validate_suite(cases: tuple[EvalCase, ...]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise EvalCaseError(f"duplicate case id '{case.id}'")
        seen.add(case.id)

    by_id = {case.id: case for case in cases}
    for case in cases:
        if case.pair is None:
            continue
        if case.pair == case.id:
            raise EvalCaseError(f"case '{case.id}' is paired with itself")
        partner = by_id.get(case.pair)
        if partner is None:
            raise EvalCaseError(f"case '{case.id}' pairs with unknown case '{case.pair}'")
        # A one-way pair means one direction of a tradeoff can be deleted
        # without anything noticing the other half is now unguarded.
        if partner.pair != case.id:
            raise EvalCaseError(
                f"case '{case.id}' pairs with '{case.pair}', but "
                f"'{partner.id}' pairs with {partner.pair!r} — pairs must be reciprocal"
            )


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def run_checks(case: EvalCase, response: str) -> tuple[CheckFailure, ...]:
    """Apply a case's lexical checks. Empty result means nothing was falsified."""
    checks = case.checks
    haystack = response.lower()
    words = len(response.split())
    failures: list[CheckFailure] = []

    for needle in checks.forbidden_substrings:
        if needle.lower() in haystack:
            failures.append(CheckFailure("forbidden_substring", needle))

    for needle in checks.required_substrings:
        if needle.lower() not in haystack:
            failures.append(CheckFailure("missing_required_substring", needle))

    for group in checks.required_any:
        if not any(option.lower() in haystack for option in group):
            failures.append(CheckFailure("missing_required_any", " | ".join(group)))

    for pattern in checks.forbidden_patterns:
        if re.search(pattern, response, re.IGNORECASE | re.MULTILINE):
            failures.append(CheckFailure("forbidden_pattern", pattern))

    if checks.max_words is not None and words > checks.max_words:
        failures.append(CheckFailure("too_long", f"{words} words > max {checks.max_words}"))

    if checks.min_words is not None and words < checks.min_words:
        failures.append(CheckFailure("too_short", f"{words} words < min {checks.min_words}"))

    return tuple(failures)


def run_case(case: EvalCase, respond: Callable[[str], str]) -> CaseResult:
    """Run one case against an injected response function.

    ``respond`` maps a prompt to a response string. In production it wraps
    :func:`ask_christopher.client.ask`; in tests and offline development it is
    any callable. Nothing in this module knows about the API.
    """
    try:
        response = respond(case.prompt)
    except Exception as exc:  # noqa: BLE001 — one bad case must not halt a suite
        return CaseResult(
            case_id=case.id,
            category=case.category,
            scoring=case.scoring,
            status="error",
            deterministic="not_run",
            error=f"{type(exc).__name__}: {exc}",
        )

    if not isinstance(response, str):
        return CaseResult(
            case_id=case.id,
            category=case.category,
            scoring=case.scoring,
            status="error",
            deterministic="not_run",
            error=f"response function returned {type(response).__name__}, expected str",
        )

    failures = run_checks(case, response)

    if case.checks.is_empty():
        deterministic = "no_checks"
    elif failures:
        deterministic = "fail"
    else:
        deterministic = "pass"

    if failures:
        status = "fail"
    elif case.is_deterministic:
        status = "pass"
    else:
        # Checks passing does not confirm a judged case. See the module docstring.
        status = "needs_judgment"

    return CaseResult(
        case_id=case.id,
        category=case.category,
        scoring=case.scoring,
        status=status,
        deterministic=deterministic,
        failures=failures,
        response_words=len(response.split()),
        response_chars=len(response),
    )


def run_conversation(case: EvalCase, converse: Callable[[str], str]) -> CaseResult:
    """Run a multi-turn case as one conversation.

    ``converse`` is **stateful**: successive calls continue the same
    conversation, so the callable is expected to wrap something like
    :class:`ask_christopher.repl.Session`, which accumulates history and mutates
    it only on success. Nothing here knows about the API.

    Three rules decide the status, and the third is the one that matters:

    * Each turn's own ``checks`` are applied to that turn's reply.
    * The **case-level** checks are applied to the **final** turn only. That is
      what makes single-turn the one-turn special case of this function rather
      than a different thing, and it is what the two multi-turn cases actually
      need: ``idn-no-repeat-disclosure`` requires disclosure on turn 1 and
      prohibits it on the last, so a case-level prohibition applied to every
      turn would contradict the case.
    * **An unfinished conversation is never scored.** If any turn raises, the
      case is ``error`` and the case-level checks are not applied to whichever
      turn happened to be last. Scoring the prefix of a conversation would
      report a verdict on a probe that never ran.
    """
    if not case.turns:
        raise EvalCaseError(f"case '{case.id}': run_conversation needs 'turns'")

    turns: list[TurnResult] = []
    failures: list[CheckFailure] = []
    error: str | None = None

    for index, turn in enumerate(case.turns, start=1):
        if error is not None:
            turns.append(
                TurnResult(index=index, send=turn.send, intent=turn.intent, deterministic="not_run")
            )
            continue

        try:
            reply = converse(turn.send)
        except Exception as exc:  # noqa: BLE001 - one bad turn must not halt a suite
            error = f"turn {index}: {type(exc).__name__}: {exc}"
            turns.append(
                TurnResult(
                    index=index,
                    send=turn.send,
                    intent=turn.intent,
                    deterministic="not_run",
                    error=error,
                )
            )
            continue

        if not isinstance(reply, str):
            error = f"turn {index}: response function returned {type(reply).__name__}, expected str"
            turns.append(
                TurnResult(
                    index=index,
                    send=turn.send,
                    intent=turn.intent,
                    deterministic="not_run",
                    error=error,
                )
            )
            continue

        is_final = index == len(case.turns)
        turn_failures = list(run_checks(_as_case(case, turn.checks), reply))
        turn_deterministic = (
            "no_checks" if turn.checks.is_empty() else ("fail" if turn_failures else "pass")
        )

        # Case-level checks belong to the final turn, and only once the
        # conversation actually got there.
        if is_final:
            turn_failures.extend(run_checks(case, reply))

        failures.extend(turn_failures)
        turns.append(
            TurnResult(
                index=index,
                send=turn.send,
                intent=turn.intent,
                deterministic=turn_deterministic,
                response=reply,
                failures=tuple(turn_failures),
                response_words=len(reply.split()),
                response_chars=len(reply),
            )
        )

    final = turns[-1] if turns else None
    completed = final is not None and final.response is not None

    if not case.has_any_checks:
        deterministic = "no_checks"
    elif not completed:
        deterministic = "not_run"
    elif failures:
        deterministic = "fail"
    else:
        deterministic = "pass"

    if error is not None:
        status = "error"
    elif failures:
        status = "fail"
    elif case.is_deterministic:
        status = "pass"
    else:
        status = "needs_judgment"

    return CaseResult(
        case_id=case.id,
        category=case.category,
        scoring=case.scoring,
        status=status,
        deterministic=deterministic,
        failures=tuple(failures),
        response_words=final.response_words if completed and final else 0,
        response_chars=final.response_chars if completed and final else 0,
        error=error,
        turns=tuple(turns),
    )


def _as_case(case: EvalCase, checks: Checks) -> EvalCase:
    """``case`` with ``checks`` swapped in, so ``run_checks`` stays single-purpose."""
    from dataclasses import replace

    return replace(case, checks=checks)


def run_suite(cases: Iterable[EvalCase], respond: Callable[[str], str]) -> SuiteResult:
    """Run every case in order and collect the results."""
    return SuiteResult(results=tuple(run_case(case, respond) for case in cases))
