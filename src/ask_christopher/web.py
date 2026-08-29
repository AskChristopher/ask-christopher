"""A bare WSGI wrapper around :class:`ask_christopher.repl.Session`.

No web framework. cPanel's Python application runs Passenger, which wants a
WSGI callable, and the whole surface is two routes. Flask would work and would
pull six packages into a project whose ``pyproject.toml`` says it is
deliberately minimal; ``wsgiref``-shaped plumbing is about seventy lines and
adds no dependency.

**What this file does not do.** It does not build requests, assemble prompts,
choose a model, or read usage off a response. ``client.py`` and ``repl.py``
already do all of that, and Phase 1 measured their behaviour. This is transport
and policy only - parse, gate, delegate, serialise. Every Phase 1 default
(``claude-opus-5``, ``max_tokens=2048``, ``effort=low``, the two
``cache_control`` system blocks) is inherited untouched.

**The prefix is assembled once per process, not once per request.**
:func:`build_application` takes an already-assembled prompt and hands the same
object to every :class:`Session`. Re-assembling per request would still produce
identical bytes - ``tests/test_prompt.py`` pins that - but it would re-read nine
files on every call for no reason, and passing one object keeps the "assembled
once" guarantee visible rather than incidental.

**Stateless: the client holds the conversation.** History arrives in the request
body. Passenger recycles workers without warning, so server-side session state
would be lost mid-conversation; the browser is the only durable place to keep it
in this deployment. The cost of that choice is the accumulated history
re-sent as uncached input on every turn, which is the same line ``converse``
already prices.

**Not streaming.** Passenger behind Apache commonly buffers
``text/event-stream`` on shared hosting, and a prototype does not need it. A
typing indicator on the frontend covers the wait. Adding streaming later is a
change to this file and the frontend, not to anything below it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ask_christopher.prompt import AssembledPrompt, build_system_prompt
from ask_christopher.usage import GateDecision, UsageGate

__all__ = [
    "MAX_HISTORY_MESSAGES",
    "MAX_QUESTION_CHARS",
    "AppConfig",
    "build_application",
]

#: A question longer than this is refused before anything is spent. Generous for
#: a real question, tight enough that a paste-bomb cannot inflate input.
MAX_QUESTION_CHARS = 1000

#: Turns after the first re-send the whole history as uncached input, so this
#: bounds the per-request cost as well as the conversation length. Eight
#: messages is four exchanges.
MAX_HISTORY_MESSAGES = 8

_JSON = [("Content-Type", "application/json; charset=utf-8")]

#: Same-origin only. The frontend is served from the same host, so no
#: Access-Control-Allow-Origin header is emitted at all - the absence is the
#: policy, and it is stricter than any value would be.


@dataclass(frozen=True)
class AppConfig:
    """Everything the application needs, injected rather than discovered.

    ``client_factory`` is called once per request rather than held, so a
    recycled worker or a rotated credential does not leave a stale client
    behind. Constructing an ``anthropic.Anthropic`` is cheap and does no I/O.
    """

    client_factory: Callable[[], Any]
    gate: UsageGate
    prompt: AssembledPrompt
    prefix_sha256: str


def build_application(
    client_factory: Callable[[], Any],
    gate: UsageGate,
    *,
    prompt: AssembledPrompt | None = None,
) -> Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]:
    """Return a WSGI application.

    The prompt is assembled here, at build time, which for Passenger means once
    when the worker imports ``passenger_wsgi.py``.
    """
    import hashlib

    assembled = build_system_prompt() if prompt is None else prompt
    config = AppConfig(
        client_factory=client_factory,
        gate=gate,
        prompt=assembled,
        prefix_sha256=hashlib.sha256(assembled.to_bytes()).hexdigest(),
    )

    def application(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = _route(environ)

        if path == "/health" and method == "GET":
            return _respond(start_response, 200, _health(config))
        if path == "/ask" and method == "POST":
            return _ask(environ, start_response, config)
        if path in {"/health", "/ask"}:
            return _respond(start_response, 405, {"error": "method_not_allowed"})
        return _respond(start_response, 404, {"error": "not_found"})

    return application


def _route(environ: dict[str, Any]) -> str:
    """The path within the application, mount point removed.

    Passenger sets ``SCRIPT_NAME`` to the mount point and ``PATH_INFO`` to the
    remainder, so the same code serves ``/ask`` whether the app is mounted at
    the document root or under a subpath. Reading ``PATH_INFO`` alone is what
    makes the mount point a deployment detail rather than a code change.
    """
    path = environ.get("PATH_INFO", "") or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def _health(config: AppConfig) -> dict[str, Any]:
    """Liveness plus the two facts worth checking after a deploy.

    ``prefix_sha256`` is the assembled prompt's fingerprint. If it does not
    match the value pinned in ``tests/test_prompt.py``, the deployed corpus is
    not the measured corpus and no Phase 1 result describes this service.

    Calls :meth:`UsageGate.peek`, never ``check_and_consume`` - a monitor
    polling health must not spend the budget it is monitoring.
    """
    decision = config.gate.peek()
    return {
        "ok": True,
        "prefix_sha256": config.prefix_sha256,
        "usage": decision.as_dict(),
    }


def _ask(
    environ: dict[str, Any],
    start_response: Callable[..., Any],
    config: AppConfig,
) -> Iterable[bytes]:
    payload, error = _read_json(environ)
    if error is not None:
        return _respond(start_response, 400, {"error": error})

    messages, error = _validate_messages(payload)
    if error is not None:
        return _respond(start_response, 400, {"error": error})

    # Gate before the model call. Order matters: validation is free and rejects
    # junk without touching the budget, and the gate is consulted only for a
    # request that would otherwise cost money.
    decision = config.gate.check_and_consume()
    if not decision.allowed:
        return _respond(start_response, *_gate_refusal(decision))

    from ask_christopher.client import response_text
    from ask_christopher.repl import Session

    # History minus the final user turn becomes the Session's prior context;
    # send() appends the question and commits both messages on success. This is
    # the same path the REPL takes, which is the point - the transport changes,
    # the behaviour does not.
    *prior, final = messages
    session = Session(
        client=config.client_factory(),
        prompt=config.prompt,
        messages=list(prior),
    )

    try:
        turn = session.send(final["content"])
    except Exception:
        # Deliberately no exception detail: an upstream error message can carry
        # request internals, and a visitor cannot act on it. The slot stays
        # consumed - see usage.py on why a failed call is not refunded.
        return _respond(
            start_response, 502, {"error": "upstream_error", "retryable": True}
        )

    reply = turn.reply or response_text(getattr(turn, "message", None))
    return _respond(
        start_response,
        200,
        {
            "reply": reply,
            "usage": {"used": decision.used, "limit": decision.limit},
        },
    )


def _gate_refusal(decision: GateDecision) -> tuple[int, dict[str, Any]]:
    """Map a gate denial to a status the frontend can act on."""
    if decision.reason == "limit_reached":
        return 429, {"error": "daily_limit_reached", "usage": decision.as_dict()}
    # unconfigured or storage_error: the fault is the deployment's, not the
    # visitor's, and 503 says "try later" rather than "you did something wrong".
    return 503, {"error": "gate_unavailable", "reason": decision.reason}


def _read_json(environ: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        declared = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return None, "bad_content_length"

    if declared <= 0:
        return None, "empty_body"
    # Bounded read. MAX_QUESTION_CHARS plus history plus JSON overhead fits
    # comfortably; anything larger is refused without being buffered.
    if declared > 64 * 1024:
        return None, "body_too_large"

    body = environ["wsgi.input"].read(declared)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "malformed_json"

    if not isinstance(payload, dict):
        return None, "expected_object"
    return payload, None


def _validate_messages(
    payload: dict[str, Any],
) -> tuple[list[dict[str, str]], str | None]:
    """Accept only the exact shape the model call needs.

    Roles are restricted to ``user`` and ``assistant``. A client cannot inject a
    ``system`` turn, which on this model is an operator channel - accepting one
    from the browser would hand visitors the instruction layer.
    """
    raw = payload.get("messages")
    if not isinstance(raw, list) or not raw:
        return [], "messages_required"
    if len(raw) > MAX_HISTORY_MESSAGES:
        return [], "history_too_long"

    messages: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            return [], "malformed_message"
        role = entry.get("role")
        content = entry.get("content")
        if role not in {"user", "assistant"}:
            return [], "bad_role"
        if not isinstance(content, str) or not content.strip():
            return [], "empty_content"
        if len(content) > MAX_QUESTION_CHARS:
            return [], "question_too_long"
        messages.append({"role": role, "content": content})

    if messages[-1]["role"] != "user":
        return [], "last_message_must_be_user"
    return messages, None


def _respond(
    start_response: Callable[..., Any], status: int, body: dict[str, Any]
) -> Iterable[bytes]:
    encoded = json.dumps(body).encode("utf-8")
    headers = _JSON + [
        ("Content-Length", str(len(encoded))),
        # A cached answer would be served to the next visitor and would also
        # hide the usage counter from the frontend.
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
    ]
    start_response(f"{status} {_REASONS.get(status, 'Status')}", headers)
    return [encoded]


_REASONS = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    429: "Too Many Requests",
    502: "Bad Gateway",
    503: "Service Unavailable",
}
