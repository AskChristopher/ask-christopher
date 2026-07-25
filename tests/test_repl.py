"""Tests for the interactive session.

No credentials and no terminal. The client is a stub and the loop's ``read`` and
``write`` are injected, which is the whole reason :class:`Session` holds no I/O.

The load-bearing assertion is prefix stability: the two cached system blocks
must be byte-identical on every turn, or each turn silently pays a fresh cache
write. Nothing else in the suite would notice that.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ask_christopher import repl as repl_module
from ask_christopher.client import DEFAULT_MODEL
from ask_christopher.repl import (
    EXIT_COMMANDS,
    Session,
    describe_error,
    format_diagnostics,
    run,
)


class FakeMessages:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        text = self.replies.pop(0) if self.replies else "ok"
        return SimpleNamespace(
            model=DEFAULT_MODEL,
            stop_reason="end_turn",
            _request_id="req_x",
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=20,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=32_000,
            ),
        )


class FakeClient:
    def __init__(self, replies: list[str] | None = None) -> None:
        self.messages = FakeMessages(replies or [])


class ExplodingClient:
    """Fails a fixed number of times, then succeeds."""

    def __init__(self, failures: int = 1, exc: Exception | None = None) -> None:
        self.remaining = failures
        self.exc = exc or RuntimeError("transport down")
        outer = self

        class _Messages:
            def create(self, **kwargs: Any) -> Any:
                if outer.remaining > 0:
                    outer.remaining -= 1
                    raise outer.exc
                return SimpleNamespace(
                    model=DEFAULT_MODEL,
                    stop_reason="end_turn",
                    _request_id="req_x",
                    content=[SimpleNamespace(type="text", text="recovered")],
                    usage=SimpleNamespace(
                        input_tokens=1,
                        output_tokens=1,
                        cache_creation_input_tokens=0,
                        cache_read_input_tokens=0,
                    ),
                )

        self.messages = _Messages()


def _session(replies: list[str] | None = None) -> Session:
    return Session(client=FakeClient(replies))


class ScriptedInput:
    """Replays lines, then raises EOFError like ``input()`` does."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = list(lines)
        self.prompts: list[str] = []

    def __call__(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


# --------------------------------------------------------------------------
# Initial request shape
# --------------------------------------------------------------------------


def test_initial_request_has_one_user_message() -> None:
    request = _session().build_request("hello")

    assert request["messages"] == [{"role": "user", "content": "hello"}]


def test_initial_request_carries_the_two_cached_system_blocks() -> None:
    request = _session().build_request("hello")

    assert len(request["system"]) == 2
    for block in request["system"]:
        assert block["cache_control"] == {"type": "ephemeral"}


def test_initial_request_uses_the_configured_model_and_effort() -> None:
    session = Session(client=FakeClient(), model="claude-sonnet-5", effort="medium")
    request = session.build_request("hello")

    assert request["model"] == "claude-sonnet-5"
    assert request["output_config"] == {"effort": "medium"}


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------


def test_a_turn_appends_user_then_assistant() -> None:
    session = _session(["first reply"])
    turn = session.send("first question")

    assert turn.reply == "first reply"
    assert session.messages == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first reply"},
    ]


def test_history_accumulates_in_order() -> None:
    session = _session(["a1", "a2", "a3"])
    for q in ("q1", "q2", "q3"):
        session.send(q)

    assert [m["content"] for m in session.messages] == ["q1", "a1", "q2", "a2", "q3", "a3"]
    assert [m["role"] for m in session.messages] == ["user", "assistant"] * 3
    assert session.turn_count == 3


def test_later_requests_include_the_whole_prior_conversation() -> None:
    session = _session(["a1", "a2"])
    session.send("q1")
    session.send("q2")

    sent = session.client.messages.calls[-1]["messages"]
    assert [m["content"] for m in sent] == ["q1", "a1", "q2"]


def test_history_is_sent_in_messages_not_folded_into_the_prefix() -> None:
    session = _session(["a1", "a2"])
    session.send("a distinctive first question")
    session.send("q2")

    system_text = "".join(b["text"] for b in session.client.messages.calls[-1]["system"])
    assert "a distinctive first question" not in system_text


# --------------------------------------------------------------------------
# The cache constraint
# --------------------------------------------------------------------------


def test_system_blocks_are_byte_identical_across_turns() -> None:
    """A single varying byte here makes every turn pay a fresh cache write."""
    session = _session(["a1", "a2", "a3"])
    for q in ("q1", "q2", "q3"):
        session.send(q)

    prefixes = [call["system"] for call in session.client.messages.calls]
    assert len(prefixes) == 3
    assert all(p == prefixes[0] for p in prefixes)


def test_prompt_is_assembled_once_per_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-assembling per turn would be wasted work and risks prefix drift."""
    real = repl_module.build_system_prompt
    calls = {"n": 0}

    def counting() -> Any:
        calls["n"] += 1
        return real()

    monkeypatch.setattr(repl_module, "build_system_prompt", counting)

    session = Session(client=FakeClient(["a1", "a2", "a3"]))
    for q in ("q1", "q2", "q3"):
        session.send(q)

    assert calls["n"] == 1


def test_supplied_prompt_is_not_reassembled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Also guards the fallback inside client.build_conversation_request.

    If the session ever failed to pass ``prompt=``, that function would quietly
    assemble its own — same bytes today, but an independent assembly is exactly
    the drift the cache constraint forbids.
    """
    from ask_christopher import client as client_module
    from ask_christopher.prompt import build_system_prompt

    prompt = build_system_prompt()

    def forbidden() -> Any:
        pytest.fail("prompt must not be reassembled once the session owns one")

    monkeypatch.setattr(repl_module, "build_system_prompt", forbidden)
    monkeypatch.setattr(client_module, "build_system_prompt", forbidden)

    session = Session(client=FakeClient(["a1", "a2"]), prompt=prompt)
    session.build_request("peek")
    session.send("q1")
    session.send("q2")

    assert session.turn_count == 2
    assert session.prompt is prompt


# --------------------------------------------------------------------------
# Failure does not corrupt history
# --------------------------------------------------------------------------


def test_a_failed_request_leaves_history_untouched() -> None:
    session = Session(client=ExplodingClient(failures=1))

    with pytest.raises(RuntimeError):
        session.send("q1")

    assert session.messages == []
    assert session.turn_count == 0


def test_a_failure_mid_conversation_preserves_earlier_turns() -> None:
    session = _session(["a1"])
    session.send("q1")
    before = list(session.messages)

    session.client.messages.create = lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        session.send("q2")

    assert session.messages == before


def test_retrying_after_a_failure_does_not_duplicate_the_user_turn() -> None:
    session = Session(client=ExplodingClient(failures=1))

    with pytest.raises(RuntimeError):
        session.send("q1")
    session.send("q1")

    assert [m["content"] for m in session.messages] == ["q1", "recovered"]


# --------------------------------------------------------------------------
# Loop control
# --------------------------------------------------------------------------


@pytest.mark.parametrize("command", sorted(EXIT_COMMANDS))
def test_exit_commands_end_the_loop(command: str) -> None:
    session = _session(["never sent"])
    code = run(session, read=ScriptedInput([command]), write=lambda _: None, banner=False)

    assert code == 0
    assert session.client.messages.calls == []


@pytest.mark.parametrize("command", ["EXIT", "Quit", "  exit  "])
def test_exit_commands_tolerate_case_and_whitespace(command: str) -> None:
    session = _session()
    assert run(session, read=ScriptedInput([command]), write=lambda _: None, banner=False) == 0
    assert session.client.messages.calls == []


def test_eof_ends_the_loop_cleanly() -> None:
    session = _session()
    code = run(session, read=ScriptedInput([]), write=lambda _: None, banner=False)

    assert code == 0


def test_keyboard_interrupt_ends_the_loop_cleanly() -> None:
    def interrupt(_: str) -> str:
        raise KeyboardInterrupt

    assert run(_session(), read=interrupt, write=lambda _: None, banner=False) == 0


def test_blank_input_is_skipped_without_sending() -> None:
    session = _session(["a1"])
    written: list[str] = []
    run(session, read=ScriptedInput(["", "   ", "q1"]), write=written.append, banner=False)

    assert len(session.client.messages.calls) == 1
    assert "a1" in "\n".join(written)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def test_default_output_is_the_reply_with_no_debug_noise() -> None:
    written: list[str] = []
    run(_session(["the reply"]), read=ScriptedInput(["q1"]), write=written.append, banner=False)

    body = "\n".join(written)
    assert "the reply" in body
    for noise in ("cache", "tokens", "latency", "req_x", "$", "prompt "):
        assert noise not in body


def test_diagnostics_flag_adds_a_metrics_line() -> None:
    written: list[str] = []
    run(
        _session(["the reply"]),
        read=ScriptedInput(["q1"]),
        write=written.append,
        diagnostics=True,
        banner=False,
    )

    body = "\n".join(written)
    assert "the reply" in body
    assert "cache read" in body
    assert "output" in body


def test_diagnostics_line_reports_a_write_when_the_cache_misses() -> None:
    from ask_christopher.client import RequestMetrics

    miss = RequestMetrics(
        model=DEFAULT_MODEL,
        input_tokens=5,
        output_tokens=7,
        cache_creation_input_tokens=32_000,
        cache_read_input_tokens=0,
        latency_seconds=1.5,
        stop_reason="end_turn",
        request_id=None,
    )

    line = format_diagnostics(miss)
    assert "cache write 32,000" in line
    assert "cache read" not in line


def test_banner_is_shown_by_default_and_suppressible() -> None:
    shown: list[str] = []
    run(_session(), read=ScriptedInput(["exit"]), write=shown.append)
    assert any("exit" in line for line in shown)

    hidden: list[str] = []
    run(_session(), read=ScriptedInput(["exit"]), write=hidden.append, banner=False)
    assert hidden == []


# --------------------------------------------------------------------------
# Error surfacing
# --------------------------------------------------------------------------


def test_missing_credentials_get_a_plain_language_message() -> None:
    exc = TypeError("Could not resolve authentication method. Expected one of api_key...")

    described = describe_error(exc)
    assert "No credentials found" in described
    assert "ANTHROPIC_API_KEY" in described


def test_rejected_credentials_are_distinguished_from_absent_ones() -> None:
    class AuthenticationError(Exception):
        pass

    assert "rejected" in describe_error(AuthenticationError("401"))


def test_connection_failure_is_described_plainly() -> None:
    class APIConnectionError(Exception):
        pass

    assert "Could not reach the API" in describe_error(APIConnectionError("dns"))


def test_api_status_error_reports_the_status_code() -> None:
    exc = RuntimeError("overloaded")
    exc.status_code = 529  # type: ignore[attr-defined]

    assert "529" in describe_error(exc)


def test_unknown_error_still_produces_a_readable_line() -> None:
    assert "Something went wrong" in describe_error(ValueError("weird"))


def test_loop_survives_a_failed_turn_and_continues() -> None:
    session = Session(client=ExplodingClient(failures=1))
    written: list[str] = []

    code = run(
        session,
        read=ScriptedInput(["q1", "q1"]),
        write=written.append,
        banner=False,
    )

    body = "\n".join(written)
    assert code == 0
    assert "Something went wrong" in body
    assert "recovered" in body
    assert session.turn_count == 1


@pytest.mark.parametrize(
    "relative",
    [
        "src/ask_christopher/repl.py",
        "scripts/cache_experiment.py",
        "scripts/first_conversation.py",
    ],
)
def test_console_producing_sources_are_pure_ascii(relative: str) -> None:
    """Windows consoles mangle non-ASCII into replacement characters.

    Enforced over the whole file rather than over printed strings only, because
    deciding which literal reaches a terminal is a judgement call that has
    already been got wrong twice — an em dash in an argparse ``description=``
    reaches the console via ``--help``.
    """
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / relative
    text = path.read_text(encoding="utf-8")
    offenders = sorted({c for c in text if not c.isascii()})

    assert not offenders, f"{relative} contains non-ASCII: {offenders}"


def test_no_traceback_leaks_into_output_on_failure() -> None:
    written: list[str] = []
    run(
        Session(client=ExplodingClient(failures=1)),
        read=ScriptedInput(["q1"]),
        write=written.append,
        banner=False,
    )

    body = "\n".join(written)
    assert "Traceback" not in body
    assert "File \"" not in body
