"""Eval suite runner - the entry point tests/evals/README.md listed as missing.

    python scripts/run_evals.py list
    python scripts/run_evals.py replay --transcript docs/experiments/0002-.../transcript.json
    python scripts/run_evals.py live --confirm
    python scripts/run_evals.py judge --responses docs/evals/....json --confirm

Three response sources, one scoring path. ``list`` sends nothing and reports what
the suite contains. ``replay`` scores responses an experiment already recorded.
``live`` sends the suite to the API and **costs real money**, so it prices the run
and refuses to spend without ``--confirm``.

``judge`` is a fourth command and a different thing: it scores responses that were
already elicited, using the model-as-judge panel in ``judge.py``. Elicitation and
judgement are deliberately separate steps. Sending the suite is the expensive,
non-idempotent half; judging is re-runnable against the same recorded responses as
the rubric or the panel changes, without spending a second time on generation.

Two rules govern the output, both inherited from ``evals.py``:

**Deterministic checks can falsify a judged case. They can never confirm one.**
So this runner never prints a suite-wide pass rate. Only 6 of 39 cases are
scorable by lexical checks at all; a percentage over the other 33 would be a
number that measures nothing, which is worse than no number.

**Every case lands in exactly one bucket** - ran, or skipped with a stated
reason. A case that quietly disappears is a behaviour nobody is measuring while
the summary still reads as complete.

Replay carries one caveat the record makes explicit. The experiment's wording and
a case's wording are usually not identical - only 2 of the 7 linked cases match
verbatim - so a paraphrase-sourced result is evidence about the assistant, not a
verdict on the case as written. The two are counted separately and never summed.

Judging carries the corresponding caveat. A judge verdict uses its own status
vocabulary - judged_pass, judged_fail, judged_uncertain - which is disjoint from
the deterministic pass/fail on purpose. The two are never added together, because
a lexical pass and a judged pass are not the same claim about the assistant.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ask_christopher.evals import (  # noqa: E402
    CaseResult,
    EvalCase,
    SuiteResult,
    default_cases_path,
    load_cases,
    run_case,
)

RECORD_SCHEMA = 1

#: Measured, not estimated: experiments 0001 and 0002 both reported exactly this
#: prefix. Used only to price a live run before it is authorised.
PREFIX_TOKENS = 40_511

#: List pricing for claude-opus-5, per token.
_IN, _OUT = 5.0 / 1e6, 25.0 / 1e6
_WRITE_MULTIPLIER, _READ_MULTIPLIER = 1.25, 0.1

#: Midpoint of the 151-285 output range observed across experiment 0002.
_TYPICAL_OUTPUT = 220

_NO_CREDENTIALS = """
No credentials found. A live run makes real, billed API calls.

    export ANTHROPIC_API_KEY=...     or     ant auth login
"""


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit() -> tuple[str, bool]:
    # Duplicated from first_conversation.py rather than shared through the
    # package: git plumbing is experiment tooling, and the shipped package has
    # no business knowing what a commit is.
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return run("rev-parse", "--short", "HEAD"), bool(run("status", "--porcelain"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", True


def cases_fingerprint(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Selection - the bookkeeping that stops a case disappearing
# --------------------------------------------------------------------------

VERBATIM = "verbatim"
PARAPHRASE = "paraphrase"


@dataclass(frozen=True)
class Selected:
    case: EvalCase
    respond: Callable[[str], str]
    fidelity: str
    #: Present for replay: the wording that actually elicited the response.
    elicited_by: str | None = None


@dataclass(frozen=True)
class Skipped:
    case_id: str
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"case_id": self.case_id, "reason": self.reason, "detail": self.detail}


def select(
    cases: tuple[EvalCase, ...],
    responder: Callable[[EvalCase], Selected | Skipped],
    only: frozenset[str] | None,
) -> tuple[list[Selected], list[Skipped]]:
    """Partition every case into exactly one of run or skipped."""
    selected: list[Selected] = []
    skipped: list[Skipped] = []

    for case in cases:
        if only is not None and case.id not in only:
            skipped.append(Skipped(case.id, "not_selected", "excluded by --only"))
            continue
        if case.multi_turn:
            skipped.append(
                Skipped(
                    case.id,
                    "multi_turn",
                    "needs a conversation-capable runner; a single prompt cannot measure it",
                )
            )
            continue
        outcome = responder(case)
        if isinstance(outcome, Skipped):
            skipped.append(outcome)
        else:
            selected.append(outcome)

    return selected, skipped


# --------------------------------------------------------------------------
# Response sources
# --------------------------------------------------------------------------


def replay_responder(transcript_path: Path) -> Callable[[EvalCase], Selected | Skipped]:
    """Serve responses an experiment already recorded, keyed by eval_case id.

    The link from a turn to a case lives in the experiment's ``questions.yaml``,
    not in the prompt text, because the two wordings usually differ. Fidelity is
    recorded per case so a paraphrase-sourced result is never read as a verdict
    on the case as written.
    """
    from ask_christopher.transcript import Transcript, load_question_set

    transcript = Transcript.load(transcript_path)
    questions = load_question_set(transcript_path.parent / "questions.yaml")

    recorded: dict[int, str] = {
        record.turn: record.response
        for record in transcript.turns
        if record.response is not None
    }
    asked: dict[int, str] = {
        record.turn: record.prompt for record in transcript.turns if record.prompt is not None
    }

    by_case: dict[str, tuple[str, str]] = {}
    for planned in questions.turns:
        if planned.eval_case is None or planned.turn not in recorded:
            continue
        by_case[planned.eval_case] = (recorded[planned.turn], asked[planned.turn])

    def responder(case: EvalCase) -> Selected | Skipped:
        found = by_case.get(case.id)
        if found is None:
            return Skipped(
                case.id,
                "no_recorded_response",
                f"{transcript_path.name} has no turn linked to this case",
            )
        response, asked_text = found
        fidelity = VERBATIM if asked_text.strip() == case.prompt.strip() else PARAPHRASE
        return Selected(
            case=case,
            respond=lambda _prompt, text=response: text,
            fidelity=fidelity,
            elicited_by=asked_text,
        )

    return responder


def live_responder(
    client: Any, prompt: Any, model: str, max_tokens: int, effort: str, usage: list[dict[str, Any]]
) -> Callable[[EvalCase], Selected | Skipped]:
    """Send each case as its own conversation.

    A fresh ``Session`` per case, all sharing one assembled prompt object. Fresh
    because cases are independent and history would leak one case's framing into
    the next; shared prompt because that keeps the cached prefix byte-identical,
    so only the first case pays a cache write.
    """
    from ask_christopher.repl import Session

    def responder(case: EvalCase) -> Selected | Skipped:
        def respond(text: str) -> str:
            session = Session(
                client=client, prompt=prompt, model=model, max_tokens=max_tokens, effort=effort
            )
            turn = session.send(text)
            usage.append({"case_id": case.id, **turn.metrics.as_dict()})
            return turn.reply

        return Selected(case=case, respond=respond, fidelity=VERBATIM)

    return responder


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def estimate_live_cost(case_count: int) -> dict[str, float]:
    """Price a live run. One cache write, the rest reads if they stay inside TTL."""
    write = PREFIX_TOKENS * _IN * _WRITE_MULTIPLIER
    read = PREFIX_TOKENS * _IN * _READ_MULTIPLIER
    output = case_count * _TYPICAL_OUTPUT * _OUT
    return {
        "prefix_write": round(write, 6),
        "prefix_reads": round(read * max(0, case_count - 1), 6),
        "output": round(output, 6),
        "total": round(write + read * max(0, case_count - 1) + output, 6),
    }


def build_record(
    *,
    mode: str,
    source: dict[str, Any],
    cases_path: Path,
    total_cases: int,
    selected: list[Selected],
    skipped: list[Skipped],
    suite: SuiteResult,
    started_at: str,
    extra_provenance: dict[str, Any] | None = None,
    usage: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    commit, dirty = git_commit()
    fidelity = {
        VERBATIM: sum(1 for s in selected if s.fidelity == VERBATIM),
        PARAPHRASE: sum(1 for s in selected if s.fidelity == PARAPHRASE),
    }
    by_id = {s.case.id: s for s in selected}

    scored_verbatim = 0
    indicative_paraphrase = 0
    for result in suite.results:
        if result.status not in {"pass", "fail"}:
            continue
        if by_id[result.case_id].fidelity == VERBATIM:
            scored_verbatim += 1
        else:
            indicative_paraphrase += 1

    record: dict[str, Any] = {
        "schema": RECORD_SCHEMA,
        "mode": mode,
        "started_at": started_at,
        "finished_at": utc_now(),
        "provenance": {
            "commit": commit,
            "commit_dirty": dirty,
            "cases_file": _repo_relative(cases_path),
            "cases_sha256": cases_fingerprint(cases_path),
            "python": sys.version.split()[0],
            **(extra_provenance or {}),
        },
        "source": source,
        "selection": {
            "total_cases": total_cases,
            "ran": len(selected),
            "skipped": [s.as_dict() for s in skipped],
        },
        "fidelity": fidelity,
        # Kept apart from the suite counts on purpose. A paraphrase-sourced
        # result is evidence about the assistant, not a verdict on the case.
        "scored_verbatim": scored_verbatim,
        "indicative_paraphrase": indicative_paraphrase,
        "suite": suite.as_dict(),
        "judgment_required": [
            r.case_id for r in suite.results if r.status == "needs_judgment"
        ],
    }
    if usage:
        record["usage"] = {
            "requests": len(usage),
            "total_cost_usd": round(sum(u.get("total_cost_usd") or 0 for u in usage), 6),
            "output_tokens": sum(u.get("output_tokens") or 0 for u in usage),
            "per_case": usage,
        }
    return record


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def print_summary(record: dict[str, Any]) -> None:
    counts = record["suite"]["counts"]
    selection = record["selection"]
    fidelity = record["fidelity"]

    print("")
    print(f"Cases in file      : {selection['total_cases']}")
    print(f"Ran                : {selection['ran']}"
          f"  (verbatim {fidelity[VERBATIM]}, paraphrase {fidelity[PARAPHRASE]})")
    print(f"Skipped            : {len(selection['skipped'])}")
    for skip in selection["skipped"]:
        print(f"  - {skip['case_id']:34} {skip['reason']}")

    print("")
    print(f"Falsified (fail)   : {counts['fail']}")
    print(f"Errors             : {counts['error']}")
    print(f"Scored pass        : {counts['pass']}  (deterministic cases only)")
    print(f"Needs judgment     : {counts['needs_judgment']}")
    print("")
    print(f"  scored verbatim         : {record['scored_verbatim']}")
    print(f"  indicative (paraphrase) : {record['indicative_paraphrase']}")

    if counts["fail"] or counts["error"]:
        print("\nFailures:")
        for result in record["suite"]["results"]:
            if result["status"] not in {"fail", "error"}:
                continue
            print(f"  {result['case_id']} [{result['status']}]")
            if result["error"]:
                print(f"      {result['error']}")
            for failure in result["failures"]:
                print(f"      {failure['kind']}: {failure['detail']}")

    usage = record.get("usage")
    if usage:
        print(f"\nSpent: ${usage['total_cost_usd']:.4f} over {usage['requests']} requests")

    # The one sentence that must survive being skimmed.
    print(
        "\nNo pass rate is reported. Lexical checks can falsify a judged case and "
        "never confirm one,\nso the "
        f"{counts['needs_judgment']} judged cases above are unscored, not passing."
    )


def build_responses(
    *,
    mode: str,
    record: dict[str, Any],
    selected: list[Selected],
    captured: dict[str, dict[str, str]],
    suite: SuiteResult,
) -> dict[str, Any]:
    """The judgement packet: rubric and answer side by side, for a human to read.

    Deliberately a separate artifact. The result record retains no response text,
    because it exists to be compared across runs rather than read - and a file
    that is both a metrics series and a transcript archive ends up serving
    neither. Retention here is opt-in per run, via ``--responses-out``.
    """
    by_id = {s.case.id: s for s in selected}
    status = {r.case_id: r for r in suite.results}

    entries: list[dict[str, Any]] = []
    for case_id, text in captured.items():
        item = by_id[case_id]
        result = status[case_id]
        entries.append(
            {
                "case_id": case_id,
                "category": item.case.category,
                "scoring": item.case.scoring,
                "status": result.status,
                "deterministic": result.deterministic,
                "failures": [f.as_dict() for f in result.failures],
                "fidelity": item.fidelity,
                "rubric": {
                    "tests": item.case.tests,
                    "requires": list(item.case.requires),
                    "prohibits": list(item.case.prohibits),
                    "source": item.case.source,
                },
                "case_prompt": item.case.prompt,
                "prompt_sent": text["prompt_sent"],
                "elicited_by": item.elicited_by,
                "response": text["response"],
                "response_words": result.response_words,
            }
        )

    return {
        "schema": RECORD_SCHEMA,
        "mode": mode,
        "generated_at": utc_now(),
        "provenance": record["provenance"],
        "source": record["source"],
        "note": (
            "Rubric and response for human judgement. Deterministic checks can "
            "falsify a judged case and never confirm one, so a status of "
            "needs_judgment here means exactly that: unread, not passing."
        ),
        "cases": entries,
    }


def render_responses(data: dict[str, Any]) -> str:
    """Readable rendering. Generated from the JSON, never hand-edited."""
    prov = data["provenance"]
    lines = [
        "# Eval responses for judgement",
        "",
        "> **Generated from the JSON. Do not edit.**",
        "> Regenerate with `python scripts/run_evals.py render-responses --responses <file>`.",
        "",
        f"**Mode:** `{data['mode']}`  ",
        f"**Generated:** {data['generated_at']}  ",
        f"**Commit:** `{prov.get('commit')}`"
        f"{' (dirty)' if prov.get('commit_dirty') else ''}  ",
        # Live runs carry the configuration in provenance; a replay inherits it
        # from the transcript it is replaying.
        f"**Model:** `{prov.get('model') or data['source'].get('model', 'n/a')}` "
        f"(effort `{prov.get('effort') or data['source'].get('effort', 'n/a')}`)  ",
        f"**Cases:** {len(data['cases'])}",
        "",
        f"> {data['note']}",
        "",
        "---",
        "",
    ]

    for entry in data["cases"]:
        lines += [
            f"## `{entry['case_id']}` - {entry['status']}",
            "",
            f"*{entry['rubric']['tests']}*",
            "",
            f"**Source:** {entry['rubric']['source']}  ",
            f"**Scoring:** `{entry['scoring']}` | "
            f"**checks:** `{entry['deterministic']}` | "
            f"**words:** {entry['response_words']}",
            "",
            "**Requires**",
            "",
        ]
        lines += [f"- {item}" for item in entry["rubric"]["requires"]] or ["- (none stated)"]
        lines += ["", "**Prohibits**", ""]
        lines += [f"- {item}" for item in entry["rubric"]["prohibits"]] or ["- (none stated)"]

        if entry["failures"]:
            lines += ["", "**Failed checks**", ""]
            lines += [f"- `{f['kind']}`: {f['detail']}" for f in entry["failures"]]

        lines += ["", "**Prompt**", "", "```text", entry["prompt_sent"], "```", ""]
        if entry["fidelity"] != VERBATIM:
            lines += [
                f"> Elicited by different wording than the case specifies. "
                f"Case prompt: `{entry['case_prompt']}`",
                "",
            ]
        lines += ["**Response**", "", "```text", entry["response"], "```", "", "---", ""]

    return "\n".join(lines) + "\n"


def write_responses(data: dict[str, Any], out: Path) -> tuple[Path, Path]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rendered = out.with_suffix(".md")
    rendered.write_text(render_responses(data), encoding="utf-8")
    return out, rendered


def write_record(record: dict[str, Any], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return out


def default_out(mode: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "docs" / "evals" / f"{stamp}-{mode}.json"


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    by_scoring: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for case in cases:
        by_scoring[case.scoring] = by_scoring.get(case.scoring, 0) + 1
        by_category[case.category] = by_category.get(case.category, 0) + 1

    print(f"{len(cases)} cases in {args.cases or default_cases_path().name}\n")
    print("By scoring mode:")
    for name in sorted(by_scoring):
        print(f"  {name:16} {by_scoring[name]:3}")
    print("\nBy category:")
    for name in sorted(by_category):
        print(f"  {name:16} {by_category[name]:3}")

    multi = [c.id for c in cases if c.multi_turn]
    unchecked = [c.id for c in cases if c.checks.is_empty()]
    print(f"\nMulti-turn (a single-turn runner must skip): {len(multi)}")
    for case_id in multi:
        print(f"  {case_id}")
    print(f"\nNo executable checks - judgement only: {len(unchecked)}")
    print(f"Lexically scorable: {len(cases) - len(unchecked)}")
    return 0


def _run(
    args: argparse.Namespace,
    mode: str,
    responder: Callable[[EvalCase], Selected | Skipped],
    source: dict[str, Any],
    extra_provenance: dict[str, Any] | None = None,
    usage: list[dict[str, Any]] | None = None,
) -> int:
    started_at = utc_now()
    cases_path = Path(args.cases) if args.cases else default_cases_path()
    cases = load_cases(cases_path)
    only = frozenset(i.strip() for i in args.only.split(",")) if args.only else None

    if only is not None:
        unknown = only - {c.id for c in cases}
        if unknown:
            print(f"Unknown case id(s): {sorted(unknown)}", file=sys.stderr)
            return 1

    selected, skipped = select(cases, responder, only)
    if not selected:
        print("Nothing to run - every case was skipped.", file=sys.stderr)
        for skip in skipped:
            print(f"  - {skip.case_id}: {skip.reason}", file=sys.stderr)
        return 1

    total_selected = len(selected)

    responses_out = getattr(args, "responses_out", None)
    captured: dict[str, dict[str, str]] = {}

    results: list[CaseResult] = []
    for index, item in enumerate(selected, start=1):
        marker = "" if item.fidelity == VERBATIM else " (paraphrase)"
        print(f"[{index}/{total_selected}] {item.case.id}{marker} ... ", end="", flush=True)

        respond = item.respond
        if responses_out:
            # Wrapped here rather than inside run_case, so evals.py keeps its
            # guarantee that a result record carries no response text.
            def respond(text: str, _id: str = item.case.id, _inner: Any = item.respond) -> str:
                reply = _inner(text)
                captured[_id] = {"prompt_sent": text, "response": reply}
                return reply

        result = run_case(item.case, respond)
        results.append(result)
        print(result.status)

        # Abort rather than repeat. A response function that fails once almost
        # always fails identically for every remaining case - bad credentials, a
        # wrong model name, no network - and a record of N identical errors is
        # noise wearing the shape of data. Cases already sent are kept.
        if result.status == "error":
            remaining = selected[index:]
            print(f"\nAborting after an error. {len(remaining)} case(s) not attempted.")
            print(f"  {result.error}")
            skipped.extend(
                Skipped(later.case.id, "aborted_after_error", f"run stopped at {item.case.id}")
                for later in remaining
            )
            selected = selected[:index]
            break

    suite = SuiteResult(results=tuple(results))
    record = build_record(
        mode=mode,
        source=source,
        cases_path=cases_path,
        total_cases=len(cases),
        selected=selected,
        skipped=skipped,
        suite=suite,
        started_at=started_at,
        extra_provenance=extra_provenance,
        usage=usage,
    )
    print_summary(record)

    # An all-error run measured nothing. Writing a record for it would put a file
    # in the results series that looks like a datapoint and is not one.
    if all(r.status == "error" for r in results):
        print("\nNo case produced a response. Writing no record.", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else default_out(mode)
    print(f"\nRecord: {write_record(record, out)}")

    if responses_out:
        data = build_responses(
            mode=mode, record=record, selected=selected, captured=captured, suite=suite
        )
        written, rendered = write_responses(data, Path(responses_out))
        print(f"Responses: {written}\nRendered:  {rendered}")

    return 1 if suite.failures else 0


# --------------------------------------------------------------------------
# Judging - scoring already-elicited responses with the model-as-judge panel
# --------------------------------------------------------------------------


def estimate_judge_cost(prefix_tokens: int, case_count: int, lens_count: int) -> dict[str, float]:
    """Price a judge run. One cache write, the rest reads inside the TTL.

    ``prefix_tokens`` is estimated by character ratio against the 40,511 the
    assistant prefix measured in experiments 0001 and 0002 - the judge prefix has
    never itself been measured, so this is an estimate and the record says so.
    """
    calls = case_count * lens_count
    write = prefix_tokens * _IN * _WRITE_MULTIPLIER
    reads = prefix_tokens * _IN * _READ_MULTIPLIER * max(0, calls - 1)
    # The case brief - rubric, prompt, response - sits after the breakpoint and
    # bills uncached on every call.
    brief = calls * _JUDGE_BRIEF_TOKENS * _IN
    output = calls * _JUDGE_OUTPUT_TOKENS * _OUT
    return {
        "calls": calls,
        "prefix_tokens_estimated": prefix_tokens,
        "prefix_write": round(write, 6),
        "prefix_reads": round(reads, 6),
        "briefs": round(brief, 6),
        "output": round(output, 6),
        "total": round(write + reads + brief + output, 6),
    }


#: Rubric plus prompt plus a typical response. Rounded up from the two recorded
#: correction-pair responses, which ran 80 and 101 words.
_JUDGE_BRIEF_TOKENS = 700

#: A verdict plus its reasoning. Thinking runs at `high` effort and bills here.
_JUDGE_OUTPUT_TOKENS = 900


def _judge_prefix_tokens(judge_prompt: Any, assistant_chars: int) -> int:
    """Scale the measured assistant prefix by character ratio. An estimate."""
    if assistant_chars <= 0:
        return PREFIX_TOKENS
    return int(PREFIX_TOKENS * len(judge_prompt.text) / assistant_chars)


def load_responses(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"{path} is not a responses file (no 'cases' key)")
    return data


def select_for_judging(
    entries: list[dict[str, Any]],
    cases: tuple[EvalCase, ...],
    only: frozenset[str] | None,
) -> tuple[list[tuple[EvalCase, str]], list[Skipped]]:
    """Pair each recorded response with its case. Every entry lands in one bucket.

    Cases are taken from the current ``cases.yaml`` rather than from the rubric
    snapshot inside the responses file, so a rubric that has been tightened since
    the response was recorded is the rubric actually applied. The two fingerprints
    are compared in the record so that substitution is visible rather than silent.
    """
    by_id = {case.id: case for case in cases}
    selected: list[tuple[EvalCase, str]] = []
    skipped: list[Skipped] = []

    for entry in entries:
        case_id = entry.get("case_id", "")
        if only is not None and case_id not in only:
            skipped.append(Skipped(case_id, "not_selected", "excluded by --only"))
            continue

        case = by_id.get(case_id)
        if case is None:
            skipped.append(
                Skipped(case_id, "case_not_in_suite", "recorded response has no matching case")
            )
            continue

        # A model judge must not stand in for the reader those cases name.
        if case.scoring == "human_review":
            skipped.append(
                Skipped(
                    case_id,
                    "human_review",
                    "scoring is human_review; a model verdict is not the evidence this case asks for",
                )
            )
            continue

        response = entry.get("response")
        if not isinstance(response, str) or not response.strip():
            skipped.append(Skipped(case_id, "no_response_text", "entry carries no response"))
            continue

        selected.append((case, response))

    return selected, skipped


def build_judgment_record(
    *,
    responses_path: Path,
    responses: dict[str, Any],
    cases_path: Path,
    judged: tuple[Any, ...],
    skipped: list[Skipped],
    started_at: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    commit, dirty = git_commit()
    counts: dict[str, int] = {}
    for result in judged:
        counts[result.status] = counts.get(result.status, 0) + 1

    current_fingerprint = cases_fingerprint(cases_path)
    recorded_fingerprint = responses.get("provenance", {}).get("cases_sha256")

    return {
        "schema": RECORD_SCHEMA,
        "mode": "judge",
        "started_at": started_at,
        "finished_at": utc_now(),
        "provenance": {
            "commit": commit,
            "commit_dirty": dirty,
            "cases_file": _repo_relative(cases_path),
            "cases_sha256": current_fingerprint,
            "python": sys.version.split()[0],
            **provenance,
        },
        "source": {
            "kind": "responses",
            "path": _repo_relative(responses_path),
            "generated_at": responses.get("generated_at"),
            "elicited_mode": responses.get("mode"),
            "elicited_commit": responses.get("provenance", {}).get("commit"),
            "elicited_model": responses.get("provenance", {}).get("model"),
            "elicited_effort": responses.get("provenance", {}).get("effort"),
            # If these differ, the rubric applied is not the rubric in force when
            # the response was elicited. That is usually intended and never silent.
            "cases_sha256_at_elicitation": recorded_fingerprint,
            "cases_changed_since_elicitation": recorded_fingerprint != current_fingerprint,
        },
        "selection": {
            "responses_in_file": len(responses.get("cases", [])),
            "judged": len(judged),
            "skipped": [s.as_dict() for s in skipped],
        },
        "counts": counts,
        # Kept apart from any deterministic tally. A judged pass and a lexical
        # pass are different claims and must never be summed into one rate.
        "disagreed": [r.case_id for r in judged if r.disagreed],
        "adjusted": [
            {"case_id": r.case_id, "lens": lens.lens, "adjustment": lens.adjustment}
            for r in judged
            for lens in r.lenses
            if lens.adjustment
        ],
        "results": [r.as_dict() for r in judged],
        "usage": {
            # Billed calls, not verdicts returned. A lens that died after the
            # response arrived cost money and produced nothing; counting only
            # verdicts made run 1's truncated lens look free.
            "calls": sum(r.calls for r in judged),
            "verdicts": sum(len(r.lenses) for r in judged),
            "failed_calls": sum(len(r.failed_calls) for r in judged),
            "total_cost_usd": round(sum(r.total_cost_usd for r in judged), 6),
        },
    }


def print_judgment_summary(record: dict[str, Any]) -> None:
    counts = record["counts"]
    selection = record["selection"]

    print("")
    print(f"Responses in file  : {selection['responses_in_file']}")
    print(f"Judged             : {selection['judged']}")
    print(f"Skipped            : {len(selection['skipped'])}")
    for skip in selection["skipped"]:
        print(f"  - {skip['case_id']:34} {skip['reason']}")

    print("")
    for status in ("judged_pass", "judged_fail", "judged_uncertain", "judge_error"):
        print(f"{status:19}: {counts.get(status, 0)}")

    if record["disagreed"]:
        print(f"\nPanel split on {len(record['disagreed'])} case(s):")
        for case_id in record["disagreed"]:
            print(f"  - {case_id}")

    if record["adjusted"]:
        print(f"\nHarness downgrades ({len(record['adjusted'])}):")
        for item in record["adjusted"]:
            print(f"  - {item['case_id']} [{item['lens']}] {item['adjustment']}")

    # Printed here, not only written to the record. An all-error run writes no
    # record at all, so leaving the cause in the file alone means the one run
    # that most needs a diagnosis is the one that prints none.
    errored = [r for r in record["results"] if r["error"]]
    if errored:
        print(f"\nErrors ({len(errored)}):")
        for result in errored:
            print(f"  - {result['case_id']}: {result['error']}")

    for result in record["results"]:
        if result["status"] != "judged_fail":
            continue
        print(f"\n{result['case_id']} - judged_fail")
        for lens in result["lenses"]:
            if lens["verdict"] != "fail":
                continue
            print(f"  [{lens['lens']}] {lens['reason']}")
            for finding in lens["findings"]:
                mark = "" if finding["quote_verified"] else "  (QUOTE NOT FOUND)"
                print(f"      \"{finding['quote'][:100]}\"{mark}")
                print(f"        {finding['problem']}")

    usage = record.get("usage") or {}
    if usage.get("total_cost_usd"):
        print(f"\nSpent: ${usage['total_cost_usd']:.4f} over {usage['calls']} judge calls")
        if usage.get("failed_calls"):
            print(
                f"  {usage['failed_calls']} of those returned no verdict and were "
                f"still billed."
            )

    print(
        "\nJudged verdicts use their own vocabulary and are never added to the "
        "deterministic\ncounts. A judged_pass is one panel's reading, not a "
        "measurement - see docs/evals/README.md."
    )


def cmd_judge(args: argparse.Namespace) -> int:
    started_at = utc_now()
    from ask_christopher.judge import (
        LENSES,
        build_judge_prompt,
        judge_responses,
        live_sender,
    )
    from ask_christopher.prompt import build_system_prompt

    responses_path = Path(args.responses)
    responses = load_responses(responses_path)
    cases_path = Path(args.cases) if args.cases else default_cases_path()
    cases = load_cases(cases_path)
    only = frozenset(i.strip() for i in args.only.split(",")) if args.only else None

    selected, skipped = select_for_judging(responses["cases"], cases, only)
    if not selected:
        print("Nothing to judge - every recorded response was skipped.", file=sys.stderr)
        for skip in skipped:
            print(f"  - {skip.case_id}: {skip.reason}", file=sys.stderr)
        return 1

    judge_prompt = build_judge_prompt()
    prefix_tokens = _judge_prefix_tokens(judge_prompt, len(build_system_prompt().text))
    estimate = estimate_judge_cost(prefix_tokens, len(selected), len(LENSES))

    if not args.confirm:
        print(f"A judge run would score {len(selected)} response(s) "
              f"across {len(LENSES)} lenses.\n")
        print(f"  lenses                    {', '.join(lens.name for lens in LENSES)}")
        print(f"  calls                     {int(estimate['calls'])}")
        print(f"  prefix (estimated)        ~{prefix_tokens:,} tokens")
        print("")
        print(f"  prefix write (first call) ${estimate['prefix_write']:.4f}")
        print(f"  prefix reads (remainder)  ${estimate['prefix_reads']:.4f}")
        print(f"  case briefs (uncached)    ${estimate['briefs']:.4f}")
        print(f"  output (est. {_JUDGE_OUTPUT_TOKENS}/call)   ${estimate['output']:.4f}")
        print(f"  ESTIMATED TOTAL           ${estimate['total']:.4f}")
        print("\nThe prefix size is estimated by character ratio against the 40,511")
        print("tokens measured in experiment 0001, not measured directly.")
        print("\nNothing was sent. Re-run with --confirm to authorise the spend.")
        return 0

    try:
        import anthropic
    except ModuleNotFoundError:
        print("The `anthropic` package is not installed.  pip install anthropic", file=sys.stderr)
        return 1

    client = anthropic.Anthropic(max_retries=0)
    if not (getattr(client, "api_key", None) or getattr(client, "auth_token", None)):
        print(_NO_CREDENTIALS, file=sys.stderr)
        return 1

    total = len(selected)
    index = {"n": 0}

    def report(result: Any) -> None:
        index["n"] += 1
        print(f"[{index['n']}/{total}] {result.case_id} ... {result.status}")

    judged = judge_responses(
        selected,
        send=live_sender(client, model=args.model),
        prompt=judge_prompt,
        on_case=report,
        model=args.model,
        effort=args.effort,
    )

    record = build_judgment_record(
        responses_path=responses_path,
        responses=responses,
        cases_path=cases_path,
        judged=judged,
        skipped=skipped,
        started_at=started_at,
        provenance={
            "model": args.model,
            "effort": args.effort,
            "lenses": [lens.name for lens in LENSES],
            "judge_prompt_sha256": _sha256(judge_prompt.to_bytes()),
            "anthropic_sdk": anthropic.__version__,
            "max_retries": 0,
            "estimate_usd": estimate["total"],
        },
    )
    print_judgment_summary(record)

    if all(r.status == "judge_error" for r in judged):
        print("\nNo case produced a verdict. Writing no record.", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else default_out("judge")
    print(f"\nRecord: {write_record(record, out)}")

    return 1 if any(r.status in {"judged_fail", "judge_error"} for r in judged) else 0


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def cmd_render_responses(args: argparse.Namespace) -> int:
    path = Path(args.responses)
    data = json.loads(path.read_text(encoding="utf-8"))
    rendered = path.with_suffix(".md")
    rendered.write_text(render_responses(data), encoding="utf-8")
    print(f"Rendered: {rendered}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    transcript_path = Path(args.transcript)
    from ask_christopher.transcript import Transcript

    transcript = Transcript.load(transcript_path)
    source = {
        "kind": "transcript",
        "path": _repo_relative(transcript_path),
        "run_id": transcript.run_id,
        "status": transcript.status,
        "phase_a_commit": transcript.provenance.get("commit"),
        "phase_b_commit": transcript.provenance.get("phase_b_commit"),
        "model": transcript.provenance.get("model"),
        "effort": transcript.provenance.get("effort"),
    }
    return _run(args, "replay", replay_responder(transcript_path), source)


def cmd_live(args: argparse.Namespace) -> int:
    from ask_christopher.prompt import build_system_prompt
    from ask_christopher.transcript import prompt_fingerprint

    cases_path = Path(args.cases) if args.cases else default_cases_path()
    cases = load_cases(cases_path)
    only = frozenset(i.strip() for i in args.only.split(",")) if args.only else None
    would_run = [
        c for c in cases if not c.multi_turn and (only is None or c.id in only)
    ]
    estimate = estimate_live_cost(len(would_run))

    if not args.confirm:
        print(f"A live run would send {len(would_run)} of {len(cases)} cases.\n")
        print(f"  prefix write (first case) ${estimate['prefix_write']:.4f}")
        print(f"  prefix reads (remainder)  ${estimate['prefix_reads']:.4f}")
        print(f"  output (est. {_TYPICAL_OUTPUT}/case)    ${estimate['output']:.4f}")
        print(f"  ESTIMATED TOTAL           ${estimate['total']:.4f}")
        print("\nEstimate assumes every case after the first lands inside the 5-minute")
        print("cache TTL. A slow or interrupted run pays more than this.")
        print("\nNothing was sent. Re-run with --confirm to authorise the spend.")
        return 0

    try:
        import anthropic
    except ModuleNotFoundError:
        print("The `anthropic` package is not installed.  pip install anthropic", file=sys.stderr)
        return 1

    client = anthropic.Anthropic(max_retries=0)

    # Checked before the loop, not at the first request. Constructing the client
    # succeeds with no credentials - the failure surfaces per request, which
    # would otherwise write a record whose every case failed identically.
    if not (getattr(client, "api_key", None) or getattr(client, "auth_token", None)):
        print(_NO_CREDENTIALS, file=sys.stderr)
        return 1

    prompt = build_system_prompt()
    usage: list[dict[str, Any]] = []
    source = {"kind": "live", "estimate_usd": estimate["total"]}
    extra = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "effort": args.effort,
        "prompt_sha256": prompt_fingerprint(prompt),
        "anthropic_sdk": anthropic.__version__,
        "max_retries": 0,
    }
    responder = live_responder(
        client, prompt, args.model, args.max_tokens, args.effort, usage
    )
    return _run(args, "live", responder, source, extra_provenance=extra, usage=usage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run-evals",
        description="Run the behavioural eval suite. Reports what was scored and what was not.",
    )
    parser.add_argument("--cases", help="path to a case file (default: tests/evals/cases.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="describe the suite; sends nothing")
    listing.set_defaults(func=cmd_list)

    responses_help = "also write rubric-and-response pairs here, for human judgement"

    replay = sub.add_parser("replay", help="score responses already recorded by an experiment")
    replay.add_argument("--transcript", required=True, help="path to a transcript.json")
    replay.add_argument("--only", help="comma-separated case ids")
    replay.add_argument("--out", help="where to write the JSON record")
    replay.add_argument("--responses-out", help=responses_help)
    replay.set_defaults(func=cmd_replay)

    rendering = sub.add_parser("render-responses", help="regenerate the Markdown from the JSON")
    rendering.add_argument("--responses", required=True, help="path to a responses JSON file")
    rendering.set_defaults(func=cmd_render_responses)

    live = sub.add_parser("live", help="send the suite to the API; costs money")
    live.add_argument("--confirm", action="store_true", help="authorise the spend")
    live.add_argument("--only", help="comma-separated case ids")
    live.add_argument("--out", help="where to write the JSON record")
    live.add_argument("--responses-out", help=responses_help)
    live.add_argument("--model", default="claude-opus-5")
    live.add_argument("--max-tokens", type=int, default=2048)
    live.add_argument("--effort", default="low")
    live.set_defaults(func=cmd_live)

    judging = sub.add_parser(
        "judge", help="score already-recorded responses with the judge panel; costs money"
    )
    judging.add_argument("--responses", required=True, help="path to a responses JSON file")
    judging.add_argument("--confirm", action="store_true", help="authorise the spend")
    judging.add_argument("--only", help="comma-separated case ids")
    judging.add_argument("--out", help="where to write the JSON record")
    judging.add_argument("--model", default="claude-opus-5")
    # Judging is the half of the suite that catches what lexical checks cannot.
    # Eliciting at low effort keeps a baseline cheap; scoring at low effort would
    # just add a second unreliable reader.
    judging.add_argument("--effort", default="high")
    judging.set_defaults(func=cmd_judge)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
