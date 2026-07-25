"""Terminal REPL - the smallest interactive session.

Two layers, deliberately separated so the conversation behaviour can be tested
without credentials or a terminal:

:class:`Session`
    Owns history and sends requests. No printing, no reading, no ``input()``.
:func:`run`
    The loop. Reads, writes, and formats errors. Takes its I/O as arguments.

One design constraint governs the whole file: **the two cached system blocks
must stay byte-identical for the entire session.** The prefix is assembled once
in :meth:`Session.__init__` and the same object is passed to every turn.
Conversation history lives in the message list and never touches the prefix -
a single varying byte there would make every turn pay a fresh cache write.

Out of scope on purpose: retrieval, persistence, tools, streaming, and any rich
terminal UI.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from ask_christopher.client import (
    DEFAULT_EFFORT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    RequestMetrics,
    ask_conversation,
    response_text,
)
from ask_christopher.prompt import AssembledPrompt, build_system_prompt

__all__ = [
    "EXIT_COMMANDS",
    "Turn",
    "Session",
    "describe_error",
    "format_diagnostics",
    "run",
    "main",
]

EXIT_COMMANDS = frozenset({"exit", "quit"})

# ASCII only. Windows consoles default to a code page that mangles em dashes
# and angle quotes into replacement characters, and this is a Windows project.
_BANNER = "Ask Christopher - type 'exit' or 'quit' to leave."
_INPUT_PROMPT = "\nyou > "


@dataclass(frozen=True)
class Turn:
    """One completed exchange."""

    reply: str
    metrics: RequestMetrics


@dataclass
class Session:
    """Conversation state and transport. No terminal I/O.

    ``client`` is injected, so a stub exercises every path here offline.
    """

    client: Any
    # Assembled exactly once, at construction. The lambda defers the name
    # lookup to call time rather than binding at class definition, which keeps
    # the "assembled once" guarantee observable in tests.
    prompt: AssembledPrompt = field(default_factory=lambda: build_system_prompt())
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    effort: str = DEFAULT_EFFORT
    messages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def turn_count(self) -> int:
        """Completed exchanges. Two messages per turn."""
        return len(self.messages) // 2

    def build_request(self, user_text: str) -> dict[str, Any]:
        """The request that :meth:`send` would issue for ``user_text``.

        Exposed so the request shape - including prefix stability across turns -
        can be asserted without sending anything.
        """
        from ask_christopher.client import build_conversation_request

        return build_conversation_request(
            self._candidate(user_text),
            prompt=self.prompt,
            model=self.model,
            max_tokens=self.max_tokens,
            effort=self.effort,
        )

    def send(self, user_text: str) -> Turn:
        """Send one turn and commit both messages to history.

        **History is only mutated on success.** The user turn is appended to a
        candidate list, and ``self.messages`` is replaced only after a reply
        comes back. A failed request therefore leaves the conversation exactly
        as it was - retrying does not stack duplicate user turns, and the next
        successful turn is not sent against a history containing a question the
        assistant never answered.
        """
        candidate = self._candidate(user_text)

        message, metrics = ask_conversation(
            self.client,
            candidate,
            prompt=self.prompt,
            model=self.model,
            max_tokens=self.max_tokens,
            effort=self.effort,
        )

        reply = response_text(message)
        self.messages = [*candidate, {"role": "assistant", "content": reply}]
        return Turn(reply=reply, metrics=metrics)

    def _candidate(self, user_text: str) -> list[dict[str, Any]]:
        return [*self.messages, {"role": "user", "content": user_text}]


def describe_error(exc: BaseException) -> str:
    """Plain-language description of a transport failure.

    Duck-typed rather than matched against SDK exception classes, so the REPL's
    error handling stays testable without constructing real SDK errors.
    """
    name = type(exc).__name__
    text = str(exc)

    if isinstance(exc, TypeError) and "authentication method" in text:
        return (
            "No credentials found. Set ANTHROPIC_API_KEY in your environment, "
            "or run `ant auth login`, then start again."
        )
    if "Authentication" in name:
        return "Credentials were found but rejected. Check the key is current."
    if "PermissionDenied" in name or "Forbidden" in name:
        return "Those credentials lack access to this model."
    if "APIConnection" in name or isinstance(exc, ConnectionError):
        return "Could not reach the API. Check your network connection."
    if "RateLimit" in name:
        return "Rate limited. Wait a moment and try again."

    status = getattr(exc, "status_code", None)
    if status is not None:
        detail = getattr(exc, "message", None) or text
        return f"The API returned an error ({status}): {detail}"

    return f"Something went wrong ({name}): {text}"


def format_diagnostics(metrics: RequestMetrics) -> str:
    """One-line metrics summary. Only shown when diagnostics are enabled."""
    cache = (
        f"cache read {metrics.cache_read_input_tokens:,}"
        if metrics.cache_hit
        else f"cache write {metrics.cache_creation_input_tokens:,}"
    )
    parts = [
        f"prompt {metrics.total_prompt_tokens:,}",
        cache,
        f"output {metrics.output_tokens:,}",
        f"{metrics.latency_seconds:.2f}s",
    ]
    if metrics.total_cost_usd is not None:
        parts.append(f"${metrics.total_cost_usd:.4f}")
    return "  [" + " | ".join(parts) + "]"


def run(
    session: Session,
    *,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
    diagnostics: bool = False,
    banner: bool = True,
) -> int:
    """Drive an interactive session. Returns a process exit code.

    ``read`` and ``write`` are injected so the loop can be exercised offline.
    ``read`` should raise ``EOFError`` at end of input, which ``input()`` does.

    Output is the reply and nothing else unless ``diagnostics`` is set.
    """
    if banner:
        write(_BANNER)

    while True:
        try:
            user_text = read(_INPUT_PROMPT)
        except (EOFError, KeyboardInterrupt):
            write("")
            return 0

        stripped = user_text.strip()
        if not stripped:
            continue
        if stripped.lower() in EXIT_COMMANDS:
            return 0

        try:
            turn = session.send(stripped)
        except Exception as exc:  # noqa: BLE001 - surfaced in plain language, session survives
            write(f"\n{describe_error(exc)}")
            continue

        write(f"\n{turn.reply}")
        if diagnostics:
            write(format_diagnostics(turn.metrics))


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``python -m ask_christopher.repl [--diagnostics]``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="ask-christopher",
        description="Interactive session with the Ask Christopher assistant.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="show token, cache, latency, and cost metrics after each response",
    )
    args = parser.parse_args(argv)

    try:
        import anthropic
    except ModuleNotFoundError:
        print("The `anthropic` package is not installed.  pip install anthropic", file=sys.stderr)
        return 1

    # Assembled once, here, so the cached prefix is identical for every turn.
    session = Session(client=anthropic.Anthropic())
    return run(session, diagnostics=args.diagnostics)


if __name__ == "__main__":
    raise SystemExit(main())
