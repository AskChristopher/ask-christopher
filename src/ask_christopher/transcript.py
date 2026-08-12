"""Two-phase conversation transcript — Experiment 0002.

The first real conversation is an experiment, not an editing session, so the
artifact has to be trustworthy on its own terms. That drives three properties:

**Immutability.** ``transcript.json`` is the source of truth. The Markdown
rendering is generated from it, never hand-edited. Phase A refuses to overwrite
an existing transcript without an explicit new run id.

**Provenance.** Every run records the commit, a hash of the assembled prompt,
the model configuration, and a hash of the question set. Phase B re-derives all
four and refuses to continue if any has moved. A transcript that spans two
different prefixes is not one experiment.

**Resumability without silent mutation.** Phase A stops after turn 6 because
turn 7 is a correction of whatever the assistant actually said, which cannot be
pre-scripted. Phase B reconstructs the message list from the stored turns rather
than holding a live object across the gap.

That reconstruction is the one place this design could go wrong, so it is tested
directly: the rebuilt history must be byte-for-byte identical to what a
continuously held :class:`~ask_christopher.repl.Session` produces after the same
six turns. The API is stateless — continuity is the ordered message list and
nothing else — so equivalence is achievable, but it is asserted rather than
assumed.

Nothing here retries. The SDK's default retry is disabled by the caller so a
failed turn is recorded as a failure instead of quietly becoming a second
identical request.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "TranscriptError",
    "AWAITING_CORRECTION",
    "COMPLETE",
    "FAILED",
    "PhaseATurns",
    "PlannedTurn",
    "QuestionSet",
    "TurnRecord",
    "Transcript",
    "experiment_dir",
    "load_question_set",
    "prompt_fingerprint",
    "reconstruct_messages",
    "render_markdown",
    "utc_now",
]


class TranscriptError(RuntimeError):
    """The transcript is missing, malformed, or does not match the current tree."""


AWAITING_CORRECTION = "awaiting_correction"
COMPLETE = "complete"
FAILED = "failed"

#: Turns Phase A is responsible for. Phase B owns 7 and 8.
PhaseATurns = (1, 2, 3, 4, 5, 6)

_EXPERIMENT = "0002-first-conversation-baseline"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def experiment_dir(root: Path | None = None) -> Path:
    base = Path(__file__).resolve().parents[2] if root is None else Path(root)
    return base / "docs" / "experiments" / _EXPERIMENT


# --------------------------------------------------------------------------
# Question set
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedTurn:
    id: str
    turn: int
    phase: str
    prompt: str | None
    intent: str
    eval_case: str | None
    supplied_at_phase_b: bool = False


@dataclass(frozen=True)
class QuestionSet:
    version: int
    turns: tuple[PlannedTurn, ...]
    sha256: str

    def phase(self, phase: str) -> tuple[PlannedTurn, ...]:
        return tuple(t for t in self.turns if t.phase == phase)

    def by_turn(self, number: int) -> PlannedTurn:
        for planned in self.turns:
            if planned.turn == number:
                return planned
        raise TranscriptError(f"question set has no turn {number}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sha256": self.sha256,
            "turns": [
                {"id": t.id, "turn": t.turn, "phase": t.phase, "eval_case": t.eval_case}
                for t in self.turns
            ],
        }


def load_question_set(path: Path | str | None = None) -> QuestionSet:
    """Load and hash the planned prompts.

    The hash covers the raw bytes, so any edit — including one that leaves the
    prompts unchanged — invalidates a run in progress. That is intentional: an
    experiment whose plan moved underneath it is not the experiment recorded.
    """
    import yaml

    location = experiment_dir() / "questions.yaml" if path is None else Path(path)
    try:
        raw = location.read_bytes()
    except OSError as exc:
        raise TranscriptError(f"Could not read question set: {location} ({exc})") from exc

    try:
        document = yaml.safe_load(raw.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise TranscriptError(f"Question set is not valid UTF-8 YAML: {location} ({exc})") from exc

    if not isinstance(document, Mapping) or "turns" not in document:
        raise TranscriptError(f"Question set must be a mapping with a 'turns' list: {location}")

    turns: list[PlannedTurn] = []
    for entry in document["turns"]:
        if not isinstance(entry, Mapping):
            raise TranscriptError("each question-set entry must be a mapping")
        turns.append(
            PlannedTurn(
                id=str(entry["id"]),
                turn=int(entry["turn"]),
                phase=str(entry["phase"]),
                prompt=entry.get("prompt"),
                intent=str(entry.get("intent", "")),
                eval_case=entry.get("eval_case"),
                supplied_at_phase_b=bool(entry.get("supplied_at_phase_b", False)),
            )
        )

    numbers = [t.turn for t in turns]
    if numbers != sorted(numbers) or len(set(numbers)) != len(numbers):
        raise TranscriptError("question-set turns must be unique and in ascending order")

    return QuestionSet(
        version=int(document.get("version", 0)),
        turns=tuple(turns),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def prompt_fingerprint(assembled: Any) -> str:
    """SHA-256 of the assembled prefix bytes."""
    return hashlib.sha256(assembled.to_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Transcript
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnRecord:
    """One exchange. ``prompt`` is recorded before the request is sent."""

    turn: int
    kind: str  # "planned" | "correction"
    question_id: str | None
    prompt: str
    prompt_recorded_at: str
    response: str | None = None
    responded_at: str | None = None
    metrics: dict[str, Any] | None = None
    error: str | None = None

    @property
    def completed(self) -> bool:
        return self.response is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "kind": self.kind,
            "question_id": self.question_id,
            "prompt": self.prompt,
            "prompt_recorded_at": self.prompt_recorded_at,
            "response": self.response,
            "responded_at": self.responded_at,
            "metrics": self.metrics,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TurnRecord":
        try:
            return cls(
                turn=int(data["turn"]),
                kind=str(data["kind"]),
                question_id=data.get("question_id"),
                prompt=data["prompt"],
                prompt_recorded_at=str(data["prompt_recorded_at"]),
                response=data.get("response"),
                responded_at=data.get("responded_at"),
                metrics=data.get("metrics"),
                error=data.get("error"),
            )
        except KeyError as exc:
            raise TranscriptError(f"turn record missing field {exc}") from exc


@dataclass
class Transcript:
    """The immutable record. Written after every prompt and every response."""

    run_id: str
    status: str
    provenance: dict[str, Any]
    question_set: dict[str, Any]
    turns: list[TurnRecord] = field(default_factory=list)
    correction_review: dict[str, Any] | None = None
    events: list[dict[str, str]] = field(default_factory=list)
    experiment: str = _EXPERIMENT

    # -- lifecycle ------------------------------------------------------

    def note(self, event: str) -> None:
        self.events.append({"at": utc_now(), "event": event})

    def record_prompt(self, turn: int, kind: str, question_id: str | None, prompt: str) -> None:
        if any(t.turn == turn for t in self.turns):
            raise TranscriptError(f"turn {turn} already recorded — earlier turns are immutable")
        self.turns.append(
            TurnRecord(
                turn=turn,
                kind=kind,
                question_id=question_id,
                prompt=prompt,
                prompt_recorded_at=utc_now(),
            )
        )

    def record_response(self, turn: int, response: str, metrics: Mapping[str, Any]) -> None:
        index = self._index(turn)
        if self.turns[index].completed:
            raise TranscriptError(f"turn {turn} already has a response — turns are immutable")
        self.turns[index] = replace(
            self.turns[index],
            response=response,
            responded_at=utc_now(),
            metrics=dict(metrics),
        )

    def record_failure(self, turn: int, error: str) -> None:
        index = self._index(turn)
        self.turns[index] = replace(self.turns[index], error=error, responded_at=utc_now())
        self.status = FAILED

    def _index(self, turn: int) -> int:
        for i, record in enumerate(self.turns):
            if record.turn == turn:
                return i
        raise TranscriptError(f"turn {turn} has no recorded prompt")

    @property
    def completed_turns(self) -> tuple[TurnRecord, ...]:
        return tuple(t for t in self.turns if t.completed)

    # -- serialisation --------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment,
            "run_id": self.run_id,
            "status": self.status,
            "provenance": self.provenance,
            "question_set": self.question_set,
            "correction_review": self.correction_review,
            "turns": [t.as_dict() for t in self.turns],
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Transcript":
        for required in ("run_id", "status", "provenance", "question_set", "turns"):
            if required not in data:
                raise TranscriptError(f"transcript missing field '{required}'")
        return cls(
            run_id=str(data["run_id"]),
            status=str(data["status"]),
            provenance=dict(data["provenance"]),
            question_set=dict(data["question_set"]),
            turns=[TurnRecord.from_dict(t) for t in data["turns"]],
            correction_review=data.get("correction_review"),
            events=list(data.get("events", [])),
            experiment=str(data.get("experiment", _EXPERIMENT)),
        )

    def save(self, path: Path) -> None:
        """Atomic write — a crash mid-save must not truncate the record."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        payload = json.dumps(self.as_dict(), indent=2, ensure_ascii=False) + "\n"
        temp.write_text(payload, encoding="utf-8", newline="\n")
        temp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Transcript":
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise TranscriptError(f"Could not read transcript: {path} ({exc})") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TranscriptError(f"Transcript is not valid JSON: {path} ({exc})") from exc
        if not isinstance(data, Mapping):
            raise TranscriptError(f"Transcript must be a JSON object: {path}")
        return cls.from_dict(data)


# --------------------------------------------------------------------------
# History reconstruction
# --------------------------------------------------------------------------


def reconstruct_messages(turns: Iterable[TurnRecord]) -> list[dict[str, str]]:
    """Rebuild the alternating message list from completed turns.

    No transformation of any kind — no strip, no normalisation, no re-encoding.
    The stored prompt and response strings are placed into the message list
    exactly as recorded, which is what makes Phase B equivalent to a session
    that never stopped.
    """
    messages: list[dict[str, str]] = []
    for record in sorted(turns, key=lambda t: t.turn):
        if not record.completed:
            continue
        messages.append({"role": "user", "content": record.prompt})
        messages.append({"role": "assistant", "content": record.response})  # type: ignore[arg-type]
    return messages


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _commit_lines(prov: dict[str, Any]) -> list[str]:
    """One commit field cannot describe a two-phase run.

    Phase B can legitimately run at a later revision — the substantive guard is
    the re-derived prompt hash, not the commit. Reporting only Phase A's commit
    makes the artifact look like it was recorded in one sitting at one revision,
    which is the gap this exists to close.
    """
    phase_a = prov.get("commit", "?")
    phase_b = prov.get("phase_b_commit")
    if phase_b is None:
        return [f"**Commit:** `{phase_a}`  "]
    if phase_b == phase_a:
        return [f"**Commit:** `{phase_a}` — both phases  "]
    drift = " — recorded with `--allow-commit-drift`" if prov.get("allow_commit_drift") else ""
    return [
        f"**Commit (Phase A):** `{phase_a}`  ",
        f"**Commit (Phase B):** `{phase_b}`{drift}  ",
    ]


def render_markdown(transcript: Transcript) -> str:
    """Readable rendering. Generated from the JSON, never hand-edited."""
    prov = transcript.provenance
    lines: list[str] = [
        "# Experiment 0002 — first conversation baseline",
        "",
        "> **Generated from `transcript.json`. Do not edit.**",
        "> Regenerate with `python scripts/first_conversation.py render`.",
        "",
        f"**Run id:** `{transcript.run_id}`  ",
        f"**Status:** `{transcript.status}`  ",
        *_commit_lines(prov),
        f"**Model:** `{prov.get('model', '?')}` "
        f"(max_tokens {prov.get('max_tokens', '?')}, effort `{prov.get('effort', '?')}`)  ",
        f"**Prompt SHA-256:** `{prov.get('prompt_sha256', '?')}`  ",
        f"**Prefix tokens (measured):** {_fmt(prov.get('prefix_tokens_measured'))}",
        "",
    ]

    # Surfaced rather than buried: a reader must not mistake a value added
    # afterwards for one the harness captured while the run was happening.
    amendment = prov.get("provenance_amendment")
    if amendment:
        lines += [f"> ⚠️ **Provenance amended after the run.** {amendment}", ""]

    lines += ["---", ""]

    review = transcript.correction_review
    if review is not None:
        lines += [
            "## Correction review",
            "",
            "*Human judgement, recorded as metadata. Not part of the raw model transcript.*",
            "",
            f"- **Correction warranted:** {review.get('warranted')}",
            f"- **Reason:** {review.get('reason', '—')}",
            f"- **Decided at:** {review.get('decided_at', '—')}",
            "",
            "---",
            "",
        ]

    for record in sorted(transcript.turns, key=lambda t: t.turn):
        label = "correction" if record.kind == "correction" else record.question_id or ""
        lines.append(f"## Turn {record.turn}" + (f" — `{label}`" if label else ""))
        lines += ["", "**Prompt**", "", "```text", record.prompt.rstrip("\n"), "```", ""]

        if record.error:
            lines += ["**FAILED**", "", "```text", record.error, "```", ""]
        elif record.response is not None:
            lines += ["**Response**", "", "```text", record.response.rstrip("\n"), "```", ""]
            lines.append(_metrics_line(record.metrics))
            lines.append("")
        else:
            lines += ["*No response recorded.*", ""]

        lines += ["---", ""]

    return "\n".join(lines).rstrip("\n") + "\n"


def _metrics_line(metrics: Mapping[str, Any] | None) -> str:
    if not metrics:
        return "*No metrics recorded.*"
    cache = (
        f"cache read {_fmt(metrics.get('cache_read_input_tokens'))}"
        if metrics.get("cache_hit")
        else f"cache write {_fmt(metrics.get('cache_creation_input_tokens'))}"
    )
    parts = [
        f"prompt {_fmt(metrics.get('total_prompt_tokens'))}",
        cache,
        f"output {_fmt(metrics.get('output_tokens'))}",
        f"{metrics.get('latency_seconds', '?')}s",
    ]
    cost = metrics.get("total_cost_usd")
    if isinstance(cost, (int, float)):
        parts.append(f"${cost:.4f}")
    return "`" + " | ".join(parts) + "`"


def _fmt(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)
