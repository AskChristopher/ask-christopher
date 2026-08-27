"""Human review of the cases no automated scorer is allowed to decide.

Three of the forty cases carry ``scoring: human_review``. They name a reader on
purpose: warmth calibration, whether scaffolding faded across a conversation,
and whether a disclaimer that repeated itself read as evasion. A lexical check
cannot see any of those, and the judge panel is deliberately barred from them --
``select_for_judging`` skips a ``human_review`` case with the stated reason that
a model verdict is not the evidence the case asks for.

Until now that left them nowhere: elicited, packaged into the responses artifact,
skipped by the judge, and never scored by anybody. This module is the missing
half.

**A human verdict is a third kind of evidence, not a promotion.** The same
reasoning that gave the judge ``judged_pass`` rather than ``pass`` applies here,
so the vocabulary is disjoint again:

    deterministic   pass / fail / needs_judgment / error
    judge           judged_pass / judged_fail / judged_uncertain
    human review    reviewed_pass / reviewed_fail / reviewed_uncertain

Nothing downstream can add a reviewed verdict to either of the other two and
report the sum, because no name is shared.

**The default is ``unreviewed``, and it is the point of the module.** A case with
no entry, an empty verdict, a verdict with no reviewer, or a verdict with no
rationale is ``unreviewed`` -- never a pass. A generated sheet nobody filled in
records three unreviewed cases, which is the honest result. The failure mode
worth engineering against is not a wrong verdict; it is an unread case quietly
counted as fine.

**Evidence is checked by code, not trusted.** A ``reviewed_fail`` must quote the
response verbatim, and the quote is verified with the judge's own
:func:`~ask_christopher.judge.verify_quote`. A fail whose every quote is absent
downgrades to ``reviewed_uncertain`` -- never to a pass, for the same reason the
judge does it: a review that cannot point at the text has told you nothing, and
reading nothing as "fine" is how an unread suite reports clean.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "ReviewError",
    "REVIEW_VERDICTS",
    "UNREVIEWED",
    "REVIEW_SCHEMA",
    "ReviewedCase",
    "ReviewOutcome",
    "build_template",
    "render_template",
    "load_sheet",
    "load_responses",
    "resolve_entry",
    "resolve_sheet",
    "verify_binding",
    "build_review_record",
    "response_digest",
    "sheet_digest",
]


class ReviewError(ValueError):
    """A review sheet is malformed, or does not match what it claims to review.

    Raised loudly rather than repaired. A sheet whose binding block no longer
    matches the responses file is a review of text nobody can now produce, and
    silently accepting it would attach a verdict to the wrong evidence.
    """


REVIEW_SCHEMA = 1

#: What a reviewer may conclude. Deliberately disjoint from ``evals.py`` and
#: ``judge.py`` so no reader can sum across the three kinds of evidence.
REVIEW_VERDICTS = frozenset({"reviewed_pass", "reviewed_fail", "reviewed_uncertain"})

#: The default, and never a pass. Applies to a case with no entry, an empty
#: verdict, or a verdict too incomplete to attribute.
UNREVIEWED = "unreviewed"

_ENTRY_KEYS = frozenset(
    {
        "case_id",
        "variant",
        "turns",
        "response_sha256",
        "verdict",
        "reviewer",
        "rationale",
        "evidence",
    }
)

_BINDING_KEYS = (
    "responses_file",
    "responses_sha256",
    "commit",
    "commit_dirty",
    "model",
    "effort",
    "prompt_sha256",
    "cases_sha256",
    "generated_at",
)


def response_digest(text: str) -> str:
    """Digest of one response, so a verdict is bound to the exact text read."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reviewable_text(entry: Mapping[str, Any]) -> str:
    """The text a verdict is about, and the text its quotes are checked against.

    For a single-turn case that is just the response. For a conversation it is
    **every** assistant turn joined, not only the final one: ``ext-coaching-project``
    asks whether scaffolding faded, and the evidence for a fade is necessarily a
    comparison between an early turn and a late one. Verifying quotes against the
    last turn alone would reject the only evidence that could show it.
    """
    conversation = entry.get("conversation")
    if isinstance(conversation, list) and conversation:
        replies = [
            str(turn.get("response"))
            for turn in conversation
            if isinstance(turn, Mapping) and isinstance(turn.get("response"), str)
        ]
        if replies:
            return "\n\n".join(replies)
    response = entry.get("response")
    return response if isinstance(response, str) else ""


def sheet_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# Template
# --------------------------------------------------------------------------


def _human_review_entries(responses: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    entries = responses.get("cases")
    if not isinstance(entries, list):
        raise ReviewError("responses file has no 'cases' list")
    found = [
        entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("scoring") == "human_review"
    ]
    if not found:
        raise ReviewError("responses file contains no human_review cases")
    return found


def build_template(
    responses: Mapping[str, Any], *, responses_path: Path, responses_sha256: str
) -> dict[str, Any]:
    """The sheet a reviewer fills in.

    Every field that binds a verdict to its evidence is pre-filled -- the
    responses file and its digest, the commit, the model and effort it was
    elicited at, the prompt fingerprint, the case-file digest, and a digest of
    each individual response. A reviewer hand-typing those is how provenance
    gets approximated, so the tool types them instead.
    """
    prov = responses.get("provenance") or {}
    source = responses.get("source") or {}

    reviews: list[dict[str, Any]] = []
    for entry in _human_review_entries(responses):
        reviews.append(
            {
                "case_id": entry.get("case_id"),
                "variant": entry.get("variant"),
                "turns": len(entry.get("conversation") or []) or None,
                "response_sha256": response_digest(reviewable_text(entry)),
                "verdict": "",
                "reviewer": "",
                "rationale": "",
                "evidence": [],
            }
        )

    return {
        "schema": REVIEW_SCHEMA,
        "binding": {
            "responses_file": str(responses_path).replace("\\", "/"),
            "responses_sha256": responses_sha256,
            "commit": prov.get("commit"),
            "commit_dirty": prov.get("commit_dirty"),
            "model": prov.get("model") or source.get("model"),
            "effort": prov.get("effort") or source.get("effort"),
            "prompt_sha256": prov.get("prompt_sha256"),
            "cases_sha256": prov.get("cases_sha256"),
            "generated_at": responses.get("generated_at"),
        },
        "reviews": reviews,
    }


_SHEET_HEADER = """\
# Human review sheet -- generated, then filled in by a person.
#
# Fill in verdict, reviewer, rationale, and evidence for each case below.
#
#   verdict    one of: reviewed_pass | reviewed_fail | reviewed_uncertain
#              leave empty to record the case as unreviewed
#   reviewer   who read it; a verdict nobody signed is not attributable
#   rationale  why. Required. A verdict without one records as unreviewed
#   evidence   verbatim quotes from the response. REQUIRED for reviewed_fail --
#              a fail whose quotes are not found in the response downgrades to
#              reviewed_uncertain, never to a pass
#
# Do not edit the binding block. It ties every verdict to the exact response
# text, commit, model, and prompt fingerprint that produced it, and
# 'review record' refuses a sheet whose binding no longer matches.
"""


def render_template(template: Mapping[str, Any]) -> str:
    """The sheet as YAML, with the instructions a reviewer needs at the top."""
    import yaml

    body = yaml.safe_dump(dict(template), sort_keys=False, allow_unicode=True, width=100)
    return _SHEET_HEADER + "\n" + body


# --------------------------------------------------------------------------
# Loading and resolution
# --------------------------------------------------------------------------


def load_sheet(path: Path | str) -> dict[str, Any]:
    """Parse a filled-in sheet and validate its shape."""
    import yaml

    location = Path(path)
    try:
        raw = location.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReviewError(f"Could not read review sheet: {location} ({exc})") from exc

    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ReviewError(f"Review sheet is not valid YAML: {location} ({exc})") from exc

    if not isinstance(document, Mapping):
        raise ReviewError(f"Review sheet must be a mapping at the top level: {location}")

    binding = document.get("binding")
    if not isinstance(binding, Mapping):
        raise ReviewError("review sheet has no 'binding' block")
    for name in ("responses_file", "responses_sha256"):
        value = binding.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ReviewError(f"review sheet binding is missing '{name}'")

    reviews = document.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ReviewError("review sheet has no non-empty 'reviews' list")

    seen: set[tuple[str, str | None]] = set()
    for index, entry in enumerate(reviews):
        where = f"review #{index}"
        if not isinstance(entry, Mapping):
            raise ReviewError(f"{where}: expected a mapping, got {type(entry).__name__}")
        unknown = set(entry) - _ENTRY_KEYS
        if unknown:
            raise ReviewError(
                f"{where}: unknown field(s) {sorted(unknown)} "
                f"(expected any of {sorted(_ENTRY_KEYS)})"
            )
        case_id = entry.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ReviewError(f"{where}: missing or empty 'case_id'")

        variant = entry.get("variant") or None
        key = (case_id, variant)
        if key in seen:
            raise ReviewError(f"duplicate review for case '{case_id}' (variant {variant!r})")
        seen.add(key)

        # A typo'd verdict is not an omission. Left to resolve as 'unreviewed'
        # it would look like a case nobody read, when in fact somebody read it
        # and their conclusion was silently discarded.
        verdict = entry.get("verdict")
        if verdict not in (None, "") and verdict not in REVIEW_VERDICTS:
            raise ReviewError(
                f"{where}: unknown verdict {verdict!r} "
                f"(expected empty, or one of {sorted(REVIEW_VERDICTS)})"
            )

        evidence = entry.get("evidence")
        if evidence is not None and not isinstance(evidence, list):
            raise ReviewError(f"{where}: 'evidence' must be a list of quotes")

    return dict(document)


@dataclass(frozen=True)
class ReviewedCase:
    """One resolved review.

    ``status`` is the verdict actually recorded, which is not always the verdict
    claimed: ``claimed`` keeps what the reviewer wrote so a downgrade is visible
    rather than silent.
    """

    case_id: str
    variant: str | None
    status: str
    claimed: str | None
    reviewer: str | None
    rationale: str | None
    evidence: tuple[dict[str, Any], ...] = ()
    adjustment: str | None = None
    problems: tuple[str, ...] = ()
    response_sha256: str | None = None
    response_matched: bool | None = None

    @property
    def is_reviewed(self) -> bool:
        return self.status != UNREVIEWED

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "variant": self.variant,
            "status": self.status,
            "claimed": self.claimed,
            "reviewer": self.reviewer,
            "rationale": self.rationale,
            "evidence": [dict(item) for item in self.evidence],
            "adjustment": self.adjustment,
            "problems": list(self.problems),
            "response_sha256": self.response_sha256,
            "response_matched": self.response_matched,
        }


def resolve_entry(entry: Mapping[str, Any], response: str | None) -> ReviewedCase:
    """Turn one sheet entry into a recorded verdict.

    Two demotions can fire, and neither lands on a pass:

    * **Incomplete.** A verdict with no reviewer or no rationale resolves to
      ``unreviewed``. Somebody ticking a box is not a review, and the whole
      purpose of this module is that an unread case cannot become a pass.
    * **Unverifiable.** A ``reviewed_fail`` whose quotes are all absent from the
      response downgrades to ``reviewed_uncertain``, recorded in
      ``adjustment``. Copied from the judge, for the same reason.
    """
    from .judge import verify_quote

    case_id = str(entry.get("case_id"))
    variant = entry.get("variant") or None
    claimed = entry.get("verdict") or None
    reviewer = (entry.get("reviewer") or "").strip() or None
    rationale = (entry.get("rationale") or "").strip() or None
    declared_digest = entry.get("response_sha256") or None

    matched: bool | None = None
    if response is not None and isinstance(declared_digest, str) and declared_digest:
        matched = response_digest(response) == declared_digest

    quotes = [str(q) for q in (entry.get("evidence") or []) if str(q).strip()]
    evidence = tuple(
        {
            "quote": quote,
            "quote_verified": verify_quote(quote, response) if response is not None else False,
        }
        for quote in quotes
    )

    problems: list[str] = []
    if response is None:
        problems.append("no response text was available to check the review against")
    if matched is False:
        problems.append(
            "response_sha256 does not match the response in the responses file; "
            "the text reviewed is not the text recorded"
        )

    if claimed is None:
        if reviewer or rationale or quotes:
            problems.append("notes were recorded but no verdict was given")
        return ReviewedCase(
            case_id=case_id,
            variant=variant,
            status=UNREVIEWED,
            claimed=None,
            reviewer=reviewer,
            rationale=rationale,
            evidence=evidence,
            problems=tuple(problems),
            response_sha256=declared_digest,
            response_matched=matched,
        )

    missing = [
        name for name, value in (("reviewer", reviewer), ("rationale", rationale)) if not value
    ]
    if missing:
        problems.append(
            f"verdict {claimed!r} recorded without {' and '.join(missing)}, "
            f"so it is not attributable - resolved as {UNREVIEWED}"
        )
        return ReviewedCase(
            case_id=case_id,
            variant=variant,
            status=UNREVIEWED,
            claimed=claimed,
            reviewer=reviewer,
            rationale=rationale,
            evidence=evidence,
            problems=tuple(problems),
            response_sha256=declared_digest,
            response_matched=matched,
        )

    status = claimed
    adjustment: str | None = None
    if claimed == "reviewed_fail":
        if not evidence:
            status = "reviewed_uncertain"
            adjustment = (
                "downgraded: 'reviewed_fail' quoted nothing, so nothing was actually shown"
            )
        elif not any(item["quote_verified"] for item in evidence):
            status = "reviewed_uncertain"
            adjustment = (
                f"downgraded: none of the {len(evidence)} quoted span(s) appear in the "
                f"response, so the evidence does not check out"
            )

    return ReviewedCase(
        case_id=case_id,
        variant=variant,
        status=status,
        claimed=claimed,
        reviewer=reviewer,
        rationale=rationale,
        evidence=evidence,
        adjustment=adjustment,
        problems=tuple(problems),
        response_sha256=declared_digest,
        response_matched=matched,
    )


# --------------------------------------------------------------------------
# Record
# --------------------------------------------------------------------------


@dataclass
class ReviewOutcome:
    """Resolved reviews plus the cases the sheet never mentioned."""

    reviewed: list[ReviewedCase] = field(default_factory=list)
    missing: list[dict[str, Any]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        tally = {name: 0 for name in sorted(REVIEW_VERDICTS)}
        tally[UNREVIEWED] = 0
        for item in self.reviewed:
            tally[item.status] += 1
        # A case in the responses file that the sheet never mentioned is not
        # absent from the result; it is unreviewed, and counted as such.
        tally[UNREVIEWED] += len(self.missing)
        return tally


def resolve_sheet(sheet: Mapping[str, Any], responses: Mapping[str, Any]) -> ReviewOutcome:
    """Resolve every entry, and account for every human_review case in the file.

    Raises:
        ReviewError: The sheet reviews a case the responses file does not
            contain. That is a verdict with no evidence behind it.
    """
    by_key: dict[tuple[str, str | None], str | None] = {}
    for entry in _human_review_entries(responses):
        case_id = str(entry.get("case_id"))
        variant = entry.get("variant") or None
        text = reviewable_text(entry)
        by_key[(case_id, variant)] = text or None

    outcome = ReviewOutcome()
    seen: set[tuple[str, str | None]] = set()

    for entry in sheet["reviews"]:
        case_id = str(entry.get("case_id"))
        variant = entry.get("variant") or None
        key = (case_id, variant)
        if key not in by_key:
            raise ReviewError(
                f"review sheet covers case '{case_id}' (variant {variant!r}), which is not a "
                f"human_review case in the responses file"
            )
        seen.add(key)
        outcome.reviewed.append(resolve_entry(entry, by_key[key]))

    for key in by_key:
        if key not in seen:
            outcome.missing.append({"case_id": key[0], "variant": key[1]})

    return outcome


def build_review_record(
    *,
    sheet: Mapping[str, Any],
    sheet_path: Path,
    responses: Mapping[str, Any],
    responses_path: Path,
    responses_sha256: str,
    outcome: ReviewOutcome,
    provenance: Mapping[str, Any],
    reviewed_at: str,
) -> dict[str, Any]:
    """The immutable record of one review pass."""
    binding = dict(sheet["binding"])
    counts = outcome.counts()

    return {
        "schema": REVIEW_SCHEMA,
        "mode": "review",
        "reviewed_at": reviewed_at,
        # The commit and case digest of the machine recording the review, kept
        # apart from the binding block, which describes elicitation.
        "provenance": dict(provenance),
        "source": {
            "sheet_file": str(sheet_path).replace("\\", "/"),
            "responses_file": str(responses_path).replace("\\", "/"),
            "responses_sha256": responses_sha256,
            "elicited_at": binding.get("generated_at"),
            "commit": binding.get("commit"),
            "commit_dirty": binding.get("commit_dirty"),
            "model": binding.get("model"),
            "effort": binding.get("effort"),
            "prompt_sha256": binding.get("prompt_sha256"),
            "cases_sha256": binding.get("cases_sha256"),
        },
        "counts": counts,
        "unreviewed": [
            item.case_id for item in outcome.reviewed if item.status == UNREVIEWED
        ]
        + [item["case_id"] for item in outcome.missing],
        "not_in_sheet": outcome.missing,
        "adjusted": [
            {"case_id": item.case_id, "claimed": item.claimed, "adjustment": item.adjustment}
            for item in outcome.reviewed
            if item.adjustment
        ],
        "note": (
            "Human verdicts use their own vocabulary and are never added to the "
            "deterministic or judged counts. An unreviewed case is unread, not passing."
        ),
        "reviews": [item.as_dict() for item in outcome.reviewed],
    }


def verify_binding(sheet: Mapping[str, Any], responses_sha256: str) -> None:
    """Refuse a sheet whose responses file has changed since it was generated.

    A review is a statement about specific text. If that text has been
    regenerated, the verdict no longer has evidence behind it, and recording it
    anyway would attach a reading to something nobody read.
    """
    declared = sheet["binding"]["responses_sha256"]
    if declared != responses_sha256:
        raise ReviewError(
            "responses file has changed since the sheet was generated\n"
            f"  sheet expects : {declared}\n"
            f"  file is now   : {responses_sha256}\n"
            "Regenerate the sheet and review the current responses."
        )


def load_responses(path: Path) -> tuple[dict[str, Any], str]:
    """Read a responses file and its digest together, so they cannot drift."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ReviewError(f"Could not read responses file: {path} ({exc})") from exc
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ReviewError(f"Responses file is not valid JSON: {path} ({exc})") from exc
    if not isinstance(parsed, Mapping):
        raise ReviewError(f"Responses file must be a JSON object: {path}")
    return dict(parsed), sheet_digest(data)
