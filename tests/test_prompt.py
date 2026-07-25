"""Tests for system prompt assembly.

``prompts/system.md`` requires four assertions of this file:

* **Byte-stability** — building the prefix twice yields identical bytes.
* **Platform stability** — the bytes do not depend on the checkout's line endings.
* **Completeness** — every corpus file appears in the assembled prompt.
* **Ordering** — sections appear in the specified sequence.

The separator tests go further and pin the exact byte layout, so a future edit
to ``prompt.py`` cannot silently change the cached prefix. A changed prefix is
not a test failure anywhere else in the suite; it is an invisible doubling of
the input bill.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ask_christopher.prompt import (
    BEHAVIOR_FILES,
    CORPUS_EXCLUDED,
    CORPUS_FILES,
    PREAMBLE,
    PromptAssemblyError,
    build_system_prompt,
    repository_root,
)

ROOT = repository_root()


def _write_tree(base: Path, *, newline: str = "\n", omit: str | None = None) -> Path:
    """Create a synthetic repository tree with known contents.

    Used instead of the real corpus wherever a test needs to control the input
    exactly — line endings, a missing file, invalid bytes.
    """
    (base / "prompts").mkdir(parents=True, exist_ok=True)
    (base / "knowledge").mkdir(parents=True, exist_ok=True)

    for filename, tag in BEHAVIOR_FILES:
        if filename == omit:
            continue
        body = f"# {tag}\n\nline one\nline two\n".replace("\n", newline)
        (base / "prompts" / filename).write_bytes(body.encode("utf-8"))

    for filename in CORPUS_FILES:
        if filename == omit:
            continue
        body = f"# {filename}\n\nfact one\nfact two\n".replace("\n", newline)
        (base / "knowledge" / filename).write_bytes(body.encode("utf-8"))

    return base


# --------------------------------------------------------------------------
# Byte-stability
# --------------------------------------------------------------------------


def test_build_is_byte_stable_within_a_process() -> None:
    assert build_system_prompt().to_bytes() == build_system_prompt().to_bytes()


def test_build_is_byte_stable_across_processes() -> None:
    """Identical repository contents produce identical bytes across runs.

    Deliberately does not pin ``PYTHONHASHSEED``. Python randomises string
    hashing per process by default, so two runs exercise different seeds — and
    any dependence on set or dict iteration order shows up here.
    """
    snippet = (
        "import hashlib;"
        "from ask_christopher.prompt import build_system_prompt;"
        "print(hashlib.sha256(build_system_prompt().to_bytes()).hexdigest())"
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    runs = [
        subprocess.run(
            [sys.executable, "-c", snippet],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for _ in range(2)
    ]

    assert runs[0] == runs[1]
    in_process = hashlib.sha256(build_system_prompt().to_bytes()).hexdigest()
    assert runs[0] == in_process


# --------------------------------------------------------------------------
# Platform stability
# --------------------------------------------------------------------------


def test_line_endings_do_not_change_the_output(tmp_path: Path) -> None:
    """The failure this repository was actually exhibiting before .gitattributes."""
    lf = _write_tree(tmp_path / "lf", newline="\n")
    crlf = _write_tree(tmp_path / "crlf", newline="\r\n")
    cr = _write_tree(tmp_path / "cr", newline="\r")

    assert build_system_prompt(lf).to_bytes() == build_system_prompt(crlf).to_bytes()
    assert build_system_prompt(lf).to_bytes() == build_system_prompt(cr).to_bytes()


def test_assembled_prompt_contains_no_carriage_returns() -> None:
    assert "\r" not in build_system_prompt().text


def test_byte_order_mark_is_stripped(tmp_path: Path) -> None:
    """A BOM would otherwise land invisibly in the middle of the prompt."""
    plain = _write_tree(tmp_path / "plain")
    bom = _write_tree(tmp_path / "bom")
    target = bom / "knowledge" / "bio.md"
    target.write_bytes(b"\xef\xbb\xbf" + target.read_bytes())

    assert build_system_prompt(plain).text == build_system_prompt(bom).text


# --------------------------------------------------------------------------
# Completeness
# --------------------------------------------------------------------------


def test_every_corpus_file_appears_in_the_prompt() -> None:
    text = build_system_prompt().text
    for filename in CORPUS_FILES:
        assert f'<document source="knowledge/{filename}">' in text


def test_every_behavior_file_appears_in_the_prompt() -> None:
    text = build_system_prompt().text
    for _, tag in BEHAVIOR_FILES:
        assert f"\n<{tag}>\n" in text
        assert f"\n</{tag}>\n" in text


def test_no_knowledge_file_is_missing_from_the_corpus_list() -> None:
    """Catches a corpus file added to the directory but not to the list.

    That is the intentional friction described in ``system.md``: a new public
    factual claim should not join the prompt by being dropped in a folder.
    """
    on_disk = {path.name for path in (ROOT / "knowledge").glob("*.md")}
    assert on_disk - CORPUS_EXCLUDED == set(CORPUS_FILES)


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


def test_preamble_comes_first() -> None:
    assert build_system_prompt().text.startswith(PREAMBLE.strip())


def test_sections_appear_in_specification_order() -> None:
    """Markers are anchored to line starts on purpose.

    The preamble names every tag as a legend, so a bare ``"<persona>"`` search
    would match the explanation rather than the section and the test would pass
    for the wrong reason.
    """
    text = build_system_prompt().text
    markers = ["\n<persona>\n", "\n<teaching_style>\n", "\n<grounding_rules>\n", "\n<knowledge>\n"]
    positions = [text.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_corpus_documents_appear_in_specification_order() -> None:
    text = build_system_prompt().text
    positions = [text.index(f'<document source="knowledge/{name}">') for name in CORPUS_FILES]
    assert positions == sorted(positions)


# --------------------------------------------------------------------------
# The byte layout itself
# --------------------------------------------------------------------------


def test_full_assembly_matches_the_specified_byte_layout(tmp_path: Path) -> None:
    """Pins the exact separators, against a tree with known contents."""
    tree = _write_tree(tmp_path)

    documents = "\n".join(
        f'<document source="knowledge/{name}">\n# {name}\n\nfact one\nfact two\n</document>\n'
        for name in CORPUS_FILES
    )
    expected = (
        PREAMBLE.strip()
        + "\n"
        + "\n<persona>\n# persona\n\nline one\nline two\n</persona>\n"
        + "\n<teaching_style>\n# teaching_style\n\nline one\nline two\n</teaching_style>\n"
        + "\n<grounding_rules>\n# grounding_rules\n\nline one\nline two\n</grounding_rules>\n"
        + "\n"
        + "<knowledge>\n"
        + documents
        + "</knowledge>\n"
    )

    assert build_system_prompt(tree).text == expected


def test_breakpoints_partition_the_text() -> None:
    assembled = build_system_prompt()
    a, b = assembled.breakpoints

    assert b == len(assembled.text)
    assert 0 < a < b
    assert "".join(assembled.segments) == assembled.text


def test_breakpoint_a_ends_the_behavior_layer() -> None:
    behavior, knowledge = build_system_prompt().segments

    assert behavior.endswith("</grounding_rules>\n\n")
    assert knowledge.startswith("<knowledge>\n")
    assert knowledge.endswith("</knowledge>\n")


# --------------------------------------------------------------------------
# Failure modes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["persona.md", "grounding_rules.md", "services.md", "boundaries.md"])
def test_missing_file_raises_and_names_the_path(tmp_path: Path, missing: str) -> None:
    tree = _write_tree(tmp_path, omit=missing)
    with pytest.raises(PromptAssemblyError, match=missing):
        build_system_prompt(tree)


def test_invalid_utf8_raises(tmp_path: Path) -> None:
    tree = _write_tree(tmp_path)
    (tree / "knowledge" / "bio.md").write_bytes(b"\xff\xfe not valid utf-8")
    with pytest.raises(PromptAssemblyError, match="not valid UTF-8"):
        build_system_prompt(tree)


def test_empty_file_raises(tmp_path: Path) -> None:
    """An empty section assembles successfully, which is why it must fail here."""
    tree = _write_tree(tmp_path)
    (tree / "prompts" / "persona.md").write_bytes(b"   \n\n  \n")
    with pytest.raises(PromptAssemblyError, match="empty"):
        build_system_prompt(tree)


def test_unreadable_directory_in_place_of_a_file_raises(tmp_path: Path) -> None:
    """A directory where a file is expected is an OSError, not FileNotFoundError."""
    tree = _write_tree(tmp_path, omit="faq.md")
    (tree / "knowledge" / "faq.md").mkdir()
    with pytest.raises(PromptAssemblyError, match="faq.md"):
        build_system_prompt(tree)
