"""Tests for `.env` loading.

The module handles a secret and mutates process-wide state, so the tests worth
having are about what it refuses to do: overwrite an exported value, print a
value, or fail quietly on a line it could not read.

``environ`` is injected into every case here. Nothing in this file touches the
real ``os.environ``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from ask_christopher.env import (
    ENV_FILENAME,
    EnvLoad,
    load_env,
    load_env_reporting,
    parse_env,
)

KEY = "ANTHROPIC_API_KEY"
SECRET = "sk-ant-do-not-print-me"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ENV_FILENAME
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_a_plain_assignment_is_read() -> None:
    values, malformed = parse_env(f"{KEY}={SECRET}\n")

    assert values == {KEY: SECRET}
    assert malformed == ()


@pytest.mark.parametrize(
    "line",
    [
        f"{KEY}={SECRET}",
        f"  {KEY} = {SECRET}  ",
        f'{KEY}="{SECRET}"',
        f"{KEY}='{SECRET}'",
        f"export {KEY}={SECRET}",
    ],
)
def test_the_shapes_a_hand_written_file_actually_takes(line: str) -> None:
    values, _ = parse_env(line + "\n")

    assert values == {KEY: SECRET}


def test_blank_lines_and_comments_are_ignored() -> None:
    values, malformed = parse_env(
        f"# Ask Christopher\n\n   \n# {KEY}=commented-out\n{KEY}={SECRET}\n"
    )

    assert values == {KEY: SECRET}
    assert malformed == ()


def test_a_hash_inside_a_value_is_kept() -> None:
    """Truncating a secret at a '#' would fail authentication with no clue why."""
    values, _ = parse_env(f"{KEY}=sk-ant-abc#def\n")

    assert values == {KEY: "sk-ant-abc#def"}


def test_an_unmatched_quote_is_left_alone() -> None:
    values, _ = parse_env(f"{KEY}=\"{SECRET}\n")

    assert values == {KEY: f'"{SECRET}'}


def test_an_empty_value_is_a_value_not_an_error() -> None:
    values, malformed = parse_env("ASK_CHRISTOPHER_DEBUG=\n")

    assert values == {"ASK_CHRISTOPHER_DEBUG": ""}
    assert malformed == ()


def test_unparseable_lines_are_reported_by_number() -> None:
    values, malformed = parse_env(f"{KEY}={SECRET}\nthis is not an assignment\n=novalue\n")

    assert values == {KEY: SECRET}
    assert malformed == (2, 3)


def test_a_later_assignment_wins_as_a_shell_would_read_it() -> None:
    values, _ = parse_env(f"{KEY}=first\n{KEY}=second\n")

    assert values == {KEY: "second"}


# --------------------------------------------------------------------------
# Loading - the environment wins
# --------------------------------------------------------------------------


def test_a_name_the_environment_does_not_define_is_set(tmp_path: Path) -> None:
    environ: dict[str, str] = {}

    result = load_env(_write(tmp_path, f"{KEY}={SECRET}\n"), environ=environ)

    assert environ == {KEY: SECRET}
    assert result.loaded == (KEY,)
    assert result.already_set == ()


def test_an_exported_value_is_never_overwritten(tmp_path: Path) -> None:
    """A stale file must not shadow the key you just exported - the resulting
    failure gives no symptom pointing back at the file."""
    environ = {KEY: "exported-by-hand"}

    result = load_env(_write(tmp_path, f"{KEY}={SECRET}\n"), environ=environ)

    assert environ[KEY] == "exported-by-hand"
    assert result.loaded == ()
    assert result.already_set == (KEY,)


def test_a_name_present_but_empty_still_counts_as_set(tmp_path: Path) -> None:
    """Presence decides, not truthiness. One rule is predictable; two are not."""
    environ = {KEY: ""}

    load_env(_write(tmp_path, f"{KEY}={SECRET}\n"), environ=environ)

    assert environ[KEY] == ""


def test_a_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """Exporting the key and keeping no .env at all is a supported setup."""
    environ: dict[str, str] = {}

    result = load_env(tmp_path / ENV_FILENAME, environ=environ)

    assert result.exists is False
    assert result.loaded == ()
    assert environ == {}


def test_the_optional_settings_load_too(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    path = _write(tmp_path, f"{KEY}={SECRET}\nASK_CHRISTOPHER_EFFORT=high\n")

    load_env(path, environ=environ)

    assert environ["ASK_CHRISTOPHER_EFFORT"] == "high"


def test_the_shipped_example_file_parses(tmp_path: Path) -> None:
    """.env.example is what a reader copies. If it does not parse, the
    documented setup is broken in a new way."""
    example = Path(__file__).resolve().parents[1] / ".env.example"
    values, malformed = parse_env(example.read_text(encoding="utf-8"))

    assert malformed == ()
    assert KEY in values


# --------------------------------------------------------------------------
# Reporting - names, never values
# --------------------------------------------------------------------------


def test_no_value_ever_appears_in_the_notice() -> None:
    result = EnvLoad(
        path=Path(ENV_FILENAME),
        exists=True,
        loaded=(KEY,),
        already_set=("ASK_CHRISTOPHER_MODEL",),
        malformed=(4,),
    )

    notice = result.notice or ""
    assert SECRET not in notice
    assert KEY in notice
    assert "ASK_CHRISTOPHER_MODEL" in notice
    assert "4" in notice


def test_nothing_is_said_when_there_is_nothing_to_report() -> None:
    assert EnvLoad(path=Path(ENV_FILENAME), exists=False).notice is None
    assert EnvLoad(path=Path(ENV_FILENAME), exists=True).notice is None


def test_a_malformed_line_is_announced_even_though_the_load_succeeded(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, f"{KEY}={SECRET}\ngarbage\n")
    stream = io.StringIO()

    load_env_reporting(path, stream=stream, environ={})

    written = stream.getvalue()
    assert "could not parse" in written
    assert SECRET not in written


def test_the_notice_is_ascii(tmp_path: Path) -> None:
    """It reaches a Windows console."""
    path = _write(tmp_path, f"{KEY}={SECRET}\ngarbage\n")
    stream = io.StringIO()

    load_env_reporting(path, stream=stream, environ={})

    assert stream.getvalue().isascii()


def test_a_silent_load_writes_nothing(tmp_path: Path) -> None:
    stream = io.StringIO()

    load_env_reporting(tmp_path / ENV_FILENAME, stream=stream, environ={})

    assert stream.getvalue() == ""


def test_reporting_defaults_to_the_real_environment_without_touching_it(
    tmp_path: Path,
) -> None:
    """The entry points call it with no arguments; that path must reach
    os.environ. Asserted against a name nothing else uses, and removed after."""
    import os

    name = "ASK_CHRISTOPHER_ENV_LOAD_PROBE"
    assert name not in os.environ
    path = _write(tmp_path, f"{name}=1\n")

    try:
        load_env_reporting(path, stream=io.StringIO())
        assert os.environ[name] == "1"
    finally:
        os.environ.pop(name, None)
