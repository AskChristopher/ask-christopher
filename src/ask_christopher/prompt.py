"""System prompt assembly.

Implements the specification in ``prompts/system.md``. That file decides the
arrangement; this module carries it out. If the two disagree, argue with the
specification first.

The contract this module exists to keep: **the assembled prefix must be
byte-identical on every request and on every platform.** A single varying byte
silently disables Anthropic's prompt cache and bills every request at full
input rate, with no error and no symptom other than the cost. Everything here
that looks fussy — binary reads, explicit file lists, normalisation before
concatenation — is in service of that.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "PromptAssemblyError",
    "AssembledPrompt",
    "build_system_prompt",
    "PREAMBLE",
    "BEHAVIOR_FILES",
    "CORPUS_FILES",
    "CORPUS_EXCLUDED",
    "repository_root",
]


# --------------------------------------------------------------------------
# Specification constants
# --------------------------------------------------------------------------

#: Role and precedence. Written inline rather than loaded, because it describes
#: how the loaded files relate to each other. Kept at normal instruction
#: strength: this is the most-read text in the prompt and the easiest place to
#: accidentally produce an over-cautious assistant.
PREAMBLE = """\
You are Ask Christopher, the assistant on Christopher Mathews' website.

This prompt contains two kinds of content, and they are not read the same way.

Instructions to follow:
  <persona>          who you are and how you sound
  <teaching_style>   how you teach rather than merely answer
  <grounding_rules>  how you use the corpus, and how you decline

Reference material to draw on, quote, and treat as the source of truth about
Christopher:
  <knowledge>        the factual corpus

Some corpus documents are written in an imperative voice and state rules about
what you may say. Those rules apply. The distinction above is about where
content comes from, not about whether it binds you.

Where guidance conflicts:
  1. grounding_rules outranks everything.
  2. teaching_style outranks persona.
  3. persona governs whatever the first two do not decide.
  4. On matters of fact, knowledge outranks all three.
  5. boundaries.md is never overridden."""

#: Behaviour layer, in assembly order. Each entry is (filename, xml tag).
BEHAVIOR_FILES: tuple[tuple[str, str], ...] = (
    ("persona.md", "persona"),
    ("teaching_style.md", "teaching_style"),
    ("grounding_rules.md", "grounding_rules"),
)

#: The corpus, in assembly order.
#:
#: Hardcoded on purpose. Directory iteration order varies across platforms and
#: filesystems, and a corpus that concatenates differently on Windows and Linux
#: is a cache miss on every request in one of the two. Adding a file to
#: ``knowledge/`` requires adding it here; that friction is intentional, since
#: corpus files are public factual claims.
CORPUS_FILES: tuple[str, ...] = (
    "bio.md",
    "philosophy.md",
    "projects.md",
    "services.md",
    "faq.md",
    "boundaries.md",
)

#: Files that live in ``knowledge/`` but are not corpus. Documentation for
#: maintainers, not material for the model.
CORPUS_EXCLUDED: frozenset[str] = frozenset({"README.md"})

_PROMPTS_DIR = "prompts"
_KNOWLEDGE_DIR = "knowledge"


class PromptAssemblyError(RuntimeError):
    """A required prompt or corpus file is missing, unreadable, or empty.

    Raised rather than skipping silently. A prompt assembled from a partial
    corpus would still work, which is precisely why it must fail loudly.
    """


@dataclass(frozen=True)
class AssembledPrompt:
    """The assembled cache prefix and its cache-breakpoint offsets.

    ``breakpoints`` holds character offsets into :attr:`text`:

    * ``breakpoints[0]`` — breakpoint A, the end of the behaviour layer.
    * ``breakpoints[1]`` — breakpoint B, the end of the full prefix. Always
      equal to ``len(text)``.

    Ordinary requests hit B. A corpus edit invalidates B but still hits A, so
    the behaviour layer stays warm. That is the reason the behaviour files are
    assembled first.
    """

    text: str
    breakpoints: tuple[int, int]

    @property
    def segments(self) -> tuple[str, str]:
        """The two cacheable segments, in order. Concatenate to :attr:`text`."""
        a, b = self.breakpoints
        return self.text[:a], self.text[a:b]

    def to_bytes(self) -> bytes:
        """UTF-8 encoding of the prefix. The contract is about these bytes."""
        return self.text.encode("utf-8")


def repository_root() -> Path:
    """Locate the repository root from this module's own position.

    Derived from ``__file__`` rather than the working directory or an
    environment variable, both of which would make assembly depend on how the
    process was launched.
    """
    return Path(__file__).resolve().parents[2]


def build_system_prompt(root: Path | None = None) -> AssembledPrompt:
    """Assemble the cached system-prompt prefix.

    Deterministic: identical repository contents produce identical bytes, on
    every platform and in every process. Performs no I/O beyond reading the
    files listed in :data:`BEHAVIOR_FILES` and :data:`CORPUS_FILES`, and reads
    no clock, environment, or network.

    Args:
        root: Repository root. Defaults to :func:`repository_root`. Overridable
            so tests can assemble from a synthetic tree.

    Returns:
        The assembled prefix and its breakpoint offsets.

    Raises:
        PromptAssemblyError: A required file is missing, unreadable, not valid
            UTF-8, or empty.
    """
    base = repository_root() if root is None else Path(root)

    blocks = [PREAMBLE.strip() + "\n"]
    for filename, tag in BEHAVIOR_FILES:
        content = _read_normalized(base / _PROMPTS_DIR / filename)
        blocks.append(f"<{tag}>\n{content}\n</{tag}>\n")

    # Trailing "\n" closes the behaviour layer with a blank line, so the
    # knowledge block starts cleanly at breakpoint A.
    behavior = "\n".join(blocks) + "\n"

    documents = []
    for filename in CORPUS_FILES:
        content = _read_normalized(base / _KNOWLEDGE_DIR / filename)
        source = f"{_KNOWLEDGE_DIR}/{filename}"
        documents.append(f'<document source="{source}">\n{content}\n</document>\n')

    knowledge = "<knowledge>\n" + "\n".join(documents) + "</knowledge>\n"

    text = behavior + knowledge
    return AssembledPrompt(text=text, breakpoints=(len(behavior), len(text)))


def _read_normalized(path: Path) -> str:
    """Read a file as UTF-8 and normalise it for deterministic concatenation.

    Read as bytes rather than text so the platform's newline translation cannot
    reach the result. ``utf-8-sig`` drops a byte-order mark if one is present,
    which would otherwise land invisibly in the middle of the prompt.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise PromptAssemblyError(
            f"Required file is missing: {path}. "
            f"Every file listed in prompt.py must exist; assembly does not skip."
        ) from exc
    except OSError as exc:
        raise PromptAssemblyError(f"Could not read required file: {path} ({exc})") from exc

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PromptAssemblyError(f"Required file is not valid UTF-8: {path} ({exc})") from exc

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise PromptAssemblyError(
            f"Required file is empty: {path}. "
            f"An empty section would assemble successfully and teach the model nothing."
        )
    return normalized
