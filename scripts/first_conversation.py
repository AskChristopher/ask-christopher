"""Experiment 0002 - first conversation baseline, two-phase harness.

    python scripts/first_conversation.py phase-a
    python scripts/first_conversation.py phase-b --correction-file correction.txt
    python scripts/first_conversation.py phase-b --no-correction --reason "turn 6 accurate"
    python scripts/first_conversation.py render

**Opt-in. Makes real, billed API calls.** Phase A sends six turns; Phase B sends
one or two more.

Phase A stops after turn 6 because turn 7 must correct whatever the assistant
actually said, and pre-scripting that would test a strawman. Phase B reloads the
partial transcript, verifies the tree has not moved underneath it, and resumes.

The SDK's automatic retry is **disabled** (``max_retries=0``). A failed turn is
recorded as a failure; it must never become a second identical request that
quietly appears in the record as one.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ask_christopher.client import (  # noqa: E402
    DEFAULT_EFFORT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
)
from ask_christopher.prompt import build_system_prompt  # noqa: E402
from ask_christopher.repl import Session  # noqa: E402
from ask_christopher.transcript import (  # noqa: E402
    AWAITING_CORRECTION,
    COMPLETE,
    FAILED,
    PhaseATurns,
    Transcript,
    TranscriptError,
    experiment_dir,
    load_question_set,
    prompt_fingerprint,
    reconstruct_messages,
    render_markdown,
    utc_now,
)

_NO_CREDENTIALS = """
No credentials found. This script makes real, billed API calls.

    export ANTHROPIC_API_KEY=...     or     ant auth login
"""


def transcript_path(run_id: str | None) -> Path:
    name = "transcript.json" if run_id is None else f"transcript.{run_id}.json"
    return experiment_dir() / name


def git_commit() -> tuple[str, bool]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return run("rev-parse", "--short", "HEAD"), bool(run("status", "--porcelain"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", True


def build_client() -> Any:
    import anthropic

    # Retries off: a failure must be recorded, never silently repeated.
    return anthropic.Anthropic(max_retries=0)


def _sdk_version() -> str:
    import anthropic

    return anthropic.__version__


# --------------------------------------------------------------------------
# Phase A
# --------------------------------------------------------------------------


def phase_a(args: argparse.Namespace) -> int:
    path = transcript_path(args.run_id)
    if path.exists():
        print(
            f"Refusing to overwrite {path.name}.\n"
            f"Supply --run-id NEW to start a separate run.",
            file=sys.stderr,
        )
        return 1

    questions = load_question_set()
    prompt = build_system_prompt()
    commit, dirty = git_commit()

    if dirty and not args.allow_dirty:
        print(
            "Working tree is dirty. A transcript recorded against uncommitted\n"
            "changes cannot be reproduced. Commit first, or pass --allow-dirty.",
            file=sys.stderr,
        )
        return 1

    transcript = Transcript(
        run_id=args.run_id or "default",
        status=AWAITING_CORRECTION,
        provenance={
            "commit": commit,
            "commit_dirty": dirty,
            "prompt_sha256": prompt_fingerprint(prompt),
            "prompt_chars": len(prompt.text),
            "prompt_bytes": len(prompt.to_bytes()),
            "model": args.model,
            "max_tokens": args.max_tokens,
            "effort": args.effort,
            "thinking": "unset (adaptive default)",
            "max_retries": 0,
            "anthropic_sdk": _sdk_version(),
            "python": sys.version.split()[0],
            "started_at": utc_now(),
        },
        question_set=questions.as_dict(),
    )
    transcript.note("phase_a_started")

    session = Session(
        client=build_client(),
        prompt=prompt,
        model=args.model,
        max_tokens=args.max_tokens,
        effort=args.effort,
    )

    print(f"Phase A - {len(PhaseATurns)} turns, commit {commit}")
    print(f"Prefix: {len(prompt.to_bytes()):,} bytes, sha256 {transcript.provenance['prompt_sha256'][:12]}...\n")

    for planned in questions.phase("a"):
        assert planned.prompt is not None
        # Recorded and flushed to disk *before* the request leaves.
        transcript.record_prompt(planned.turn, "planned", planned.id, planned.prompt)
        transcript.save(path)

        print(f"[{planned.turn}/8] {planned.id} ... ", end="", flush=True)
        try:
            turn = session.send(planned.prompt)
        except Exception as exc:  # noqa: BLE001 - recorded, not retried
            transcript.record_failure(planned.turn, f"{type(exc).__name__}: {exc}")
            transcript.note("phase_a_failed")
            transcript.save(path)
            print("FAILED")
            print(f"\n{_explain(exc)}", file=sys.stderr)
            print(f"Partial transcript preserved at {path}", file=sys.stderr)
            return 1

        transcript.record_response(planned.turn, turn.reply, turn.metrics.as_dict())
        transcript.save(path)
        m = turn.metrics
        cache = f"read {m.cache_read_input_tokens:,}" if m.cache_hit else f"write {m.cache_creation_input_tokens:,}"
        print(f"ok  ({m.output_tokens} out, cache {cache}, {m.latency_seconds:.1f}s)")

    transcript.provenance["prefix_tokens_measured"] = _measured_prefix_tokens(transcript)
    transcript.note("phase_a_completed")
    transcript.save(path)

    print(f"\nPhase A complete. Status: {transcript.status}")
    print(f"Transcript: {path}")
    print("\nNext: read turn 6, decide whether a correction is warranted, then run")
    print("  phase-b --correction-file <file>   (or --no-correction --reason ...)")
    return 0


def _measured_prefix_tokens(transcript: Transcript) -> int | None:
    for record in transcript.turns:
        if record.metrics:
            created = record.metrics.get("cache_creation_input_tokens") or 0
            read = record.metrics.get("cache_read_input_tokens") or 0
            if created or read:
                return created or read
    return None


# --------------------------------------------------------------------------
# Phase B
# --------------------------------------------------------------------------


def phase_b(args: argparse.Namespace) -> int:
    path = transcript_path(args.run_id)
    try:
        transcript = Transcript.load(path)
    except TranscriptError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    questions = load_question_set()
    prompt = build_system_prompt()
    commit, dirty = git_commit()

    problems = _verify(transcript, questions, prompt, commit, args)
    if problems:
        print("Refusing to continue - the run does not match the current tree:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("\nStart a new run rather than amending this one.", file=sys.stderr)
        return 1

    correction_text: str | None = None
    if args.no_correction:
        review = {"warranted": False, "reason": args.reason, "decided_at": utc_now()}
    else:
        correction_text = _read_correction(args)
        if correction_text is None:
            return 1
        review = {"warranted": True, "reason": args.reason, "decided_at": utc_now()}
    transcript.correction_review = review

    # Reconstructed from the immutable record - no live object spans the gap.
    session = Session(
        client=build_client(),
        prompt=prompt,
        model=transcript.provenance["model"],
        max_tokens=transcript.provenance["max_tokens"],
        effort=transcript.provenance["effort"],
        messages=reconstruct_messages(transcript.turns),
    )
    print(f"Phase B - resuming with {session.turn_count} prior turns reconstructed")

    pending: list[tuple[int, str, str | None, str]] = []
    if correction_text is not None:
        pending.append((7, "correction", "q7-correction", correction_text))
    else:
        print("  turn 7 skipped - no correction warranted")
    q8 = questions.by_turn(8)
    assert q8.prompt is not None
    pending.append((8, "planned", q8.id, q8.prompt))

    transcript.note("phase_b_started")
    transcript.save(path)

    for number, kind, question_id, text in pending:
        transcript.record_prompt(number, kind, question_id, text)
        transcript.save(path)

        print(f"[{number}/8] {question_id} ... ", end="", flush=True)
        try:
            turn = session.send(text)
        except Exception as exc:  # noqa: BLE001
            transcript.record_failure(number, f"{type(exc).__name__}: {exc}")
            transcript.note("phase_b_failed")
            transcript.save(path)
            print("FAILED")
            print(f"\n{_explain(exc)}", file=sys.stderr)
            print(f"Partial transcript preserved at {path}", file=sys.stderr)
            return 1

        transcript.record_response(number, turn.reply, turn.metrics.as_dict())
        transcript.save(path)
        print(f"ok  ({turn.metrics.output_tokens} out, {turn.metrics.latency_seconds:.1f}s)")

    transcript.status = COMPLETE
    transcript.provenance["completed_at"] = utc_now()
    transcript.note("phase_b_completed")
    transcript.save(path)

    md = _render(transcript, args.run_id)
    print(f"\nComplete. Transcript: {path}\nRendered: {md}")
    return 0


def _verify(
    transcript: Transcript,
    questions: Any,
    prompt: Any,
    commit: str,
    args: argparse.Namespace,
) -> list[str]:
    problems: list[str] = []
    prov = transcript.provenance

    if transcript.status == COMPLETE:
        problems.append("transcript is already marked complete")
    elif transcript.status == FAILED:
        problems.append("transcript is marked failed - a failed run is not resumable")
    elif transcript.status != AWAITING_CORRECTION:
        problems.append(f"unexpected status '{transcript.status}'")

    if prov.get("commit") != commit and not args.allow_commit_drift:
        problems.append(f"commit moved: recorded {prov.get('commit')}, now {commit}")

    current_prompt_hash = prompt_fingerprint(prompt)
    if prov.get("prompt_sha256") != current_prompt_hash:
        problems.append(
            f"assembled prompt changed: recorded {str(prov.get('prompt_sha256'))[:12]}..., "
            f"now {current_prompt_hash[:12]}..."
        )

    if transcript.question_set.get("sha256") != questions.sha256:
        problems.append("question set changed since the run started")
    if transcript.question_set.get("version") != questions.version:
        problems.append("question-set version changed since the run started")

    for name, expected in (
        ("model", args.model),
        ("max_tokens", args.max_tokens),
        ("effort", args.effort),
    ):
        if args_supplied(args, name) and prov.get(name) != expected:
            problems.append(f"{name} differs: recorded {prov.get(name)}, requested {expected}")

    done = {t.turn for t in transcript.completed_turns}
    missing = [n for n in PhaseATurns if n not in done]
    if missing:
        problems.append(f"phase A incomplete - turns {missing} have no response")
    if any(t.turn in (7, 8) for t in transcript.turns):
        problems.append("turns 7 or 8 already present - earlier turns are immutable")

    return problems


def args_supplied(args: argparse.Namespace, name: str) -> bool:
    return getattr(args, f"_{name}_supplied", False)


def _read_correction(args: argparse.Namespace) -> str | None:
    if args.correction_file:
        try:
            # Recorded verbatim apart from newline normalisation, so a CRLF
            # checkout does not silently alter the submitted user turn.
            text = Path(args.correction_file).read_text(encoding="utf-8").replace("\r\n", "\n")
        except OSError as exc:
            print(f"Could not read correction file: {exc}", file=sys.stderr)
            return None
    elif args.correction:
        text = args.correction
    else:
        print(
            "Supply the correction with --correction-file / --correction,\n"
            "or pass --no-correction --reason '...' if turn 6 was accurate.",
            file=sys.stderr,
        )
        return None

    if not text.strip():
        print("Correction text is empty.", file=sys.stderr)
        return None
    return text


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------


def _render(transcript: Transcript, run_id: str | None) -> Path:
    name = "transcript.md" if run_id is None else f"transcript.{run_id}.md"
    target = experiment_dir() / name
    target.write_text(render_markdown(transcript), encoding="utf-8", newline="\n")
    return target


def render_only(args: argparse.Namespace) -> int:
    try:
        transcript = Transcript.load(transcript_path(args.run_id))
    except TranscriptError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Rendered: {_render(transcript, args.run_id)}")
    return 0


def _explain(exc: BaseException) -> str:
    from ask_christopher.repl import describe_error

    if isinstance(exc, TypeError) and "authentication method" in str(exc):
        return _NO_CREDENTIALS
    return describe_error(exc)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="first_conversation",
        description="Experiment 0002 - two-phase first-conversation transcript.",
    )
    parser.add_argument("--run-id", help="separate run; required to avoid overwriting")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("phase-a", help="send turns 1-6 and stop")
    a.add_argument("--model", default=DEFAULT_MODEL)
    a.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    a.add_argument("--effort", default=DEFAULT_EFFORT)
    a.add_argument("--allow-dirty", action="store_true", help="record against an uncommitted tree")
    a.set_defaults(func=phase_a)

    b = sub.add_parser("phase-b", help="supply the correction and send turns 7-8")
    b.add_argument("--correction-file", help="file containing the correction, recorded verbatim")
    b.add_argument("--correction", help="correction text inline")
    b.add_argument("--no-correction", action="store_true", help="turn 6 was accurate")
    b.add_argument("--reason", default="", help="why a correction is or is not warranted")
    b.add_argument("--model", default=DEFAULT_MODEL)
    b.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    b.add_argument("--effort", default=DEFAULT_EFFORT)
    b.add_argument("--allow-commit-drift", action="store_true")
    b.set_defaults(func=phase_b)

    r = sub.add_parser("render", help="regenerate the Markdown from the JSON")
    r.set_defaults(func=render_only)

    args = parser.parse_args(argv)

    # Only treat model/max_tokens/effort as constraints in phase B when the
    # caller actually passed them; otherwise defaults would fake a mismatch.
    raw = argv if argv is not None else sys.argv[1:]
    for name, flag in (("model", "--model"), ("max_tokens", "--max-tokens"), ("effort", "--effort")):
        setattr(args, f"_{name}_supplied", flag in raw)

    if getattr(args, "no_correction", False) and not args.reason:
        print("--no-correction requires --reason explaining why turn 6 was accurate.", file=sys.stderr)
        return 1

    try:
        import anthropic  # noqa: F401
    except ModuleNotFoundError:
        if args.command != "render":
            print("The `anthropic` package is not installed.", file=sys.stderr)
            return 1

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
