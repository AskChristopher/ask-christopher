"""Anthropic API client — Milestone 2 cache baseline.

Scope is deliberately narrow. This module builds one request from the assembled
prefix, sends it, and records what the provider reports about caching. There is
no conversation history, no streaming, no REPL, and no retrieval — see
``docs/decisions/0002-full-corpus-injection-is-a-baseline-not-the-architecture.md``
for why full-corpus injection is being *measured* rather than assumed correct.

The cache contract this exercises comes from ``prompts/system.md``: the prefix
is two stable segments split at breakpoint A, sent as two ``system`` content
blocks each carrying ``cache_control``. Ordinary requests hit the second
breakpoint; a corpus edit invalidates it while the behaviour layer stays warm.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ask_christopher.prompt import AssembledPrompt, build_system_prompt

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_EFFORT",
    "PRICING_USD_PER_MTOK",
    "RequestMetrics",
    "build_request",
    "ask",
]


#: Claude Opus 5. The corpus is a factual record about a real person and the
#: grounding rules are subtle, so this is not a place to economise on model.
DEFAULT_MODEL = "claude-opus-5"

#: Enough headroom for thinking plus a short answer. Thinking is **on by
#: default** on Opus 5 (omitting the parameter runs adaptive), and ``max_tokens``
#: caps thinking and response text together — a value sized for the answer alone
#: truncates mid-response.
DEFAULT_MAX_TOKENS = 2048

#: Low effort keeps the baseline cheap and output-length variance small, so the
#: measured latency reflects prefix handling rather than generation depth.
DEFAULT_EFFORT = "low"

#: Anthropic list pricing, USD per million tokens, as of 2026-07-25. Cache reads
#: bill at ~0.1x input; 5-minute-TTL cache writes at 1.25x.
#: Recorded here only so the baseline can report cost — re-check before quoting.
PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
}

_CACHE_READ_MULTIPLIER = 0.1
_CACHE_WRITE_MULTIPLIER = 1.25


@dataclass(frozen=True)
class RequestMetrics:
    """Provider-reported usage for one request, plus measured wall-clock latency.

    Only what verification needs. No response text is retained — the baseline is
    about cache behaviour, not about what the assistant said.
    """

    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    latency_seconds: float
    stop_reason: str | None
    request_id: str | None

    @property
    def total_prompt_tokens(self) -> int:
        """Full prompt size.

        ``input_tokens`` is the *uncached remainder* only, so reading it alone
        understates the prompt whenever the cache engages.
        """
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    @property
    def cache_hit(self) -> bool:
        return self.cache_read_input_tokens > 0

    @property
    def input_cost_usd(self) -> float | None:
        """Input-side cost, or ``None`` if the model is absent from the price table."""
        rates = PRICING_USD_PER_MTOK.get(self.model)
        if rates is None:
            return None
        per_token = rates["input"] / 1_000_000
        return (
            self.input_tokens * per_token
            + self.cache_creation_input_tokens * per_token * _CACHE_WRITE_MULTIPLIER
            + self.cache_read_input_tokens * per_token * _CACHE_READ_MULTIPLIER
        )

    @property
    def output_cost_usd(self) -> float | None:
        rates = PRICING_USD_PER_MTOK.get(self.model)
        if rates is None:
            return None
        return self.output_tokens * rates["output"] / 1_000_000

    @property
    def total_cost_usd(self) -> float | None:
        if self.input_cost_usd is None or self.output_cost_usd is None:
            return None
        return self.input_cost_usd + self.output_cost_usd

    def as_dict(self) -> dict[str, Any]:
        """Flat record for logging or comparison across runs."""
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "cache_hit": self.cache_hit,
            "latency_seconds": round(self.latency_seconds, 3),
            "stop_reason": self.stop_reason,
            "request_id": self.request_id,
            "input_cost_usd": self.input_cost_usd,
            "output_cost_usd": self.output_cost_usd,
            "total_cost_usd": self.total_cost_usd,
        }


def build_request(
    question: str,
    *,
    prompt: AssembledPrompt | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    effort: str = DEFAULT_EFFORT,
) -> dict[str, Any]:
    """Build the keyword arguments for ``client.messages.create``.

    Pure — no I/O, no clock, no network. Separated from :func:`ask` so the
    request shape can be asserted in tests without mocking a transport.

    The prefix is split into two ``system`` blocks at breakpoint A, each marked
    ``cache_control``. Concatenating the two block texts reproduces
    ``prompt.text`` exactly; the split expresses cache boundaries and nothing
    else. Two of the four permitted breakpoints are used.

    ``temperature``, ``top_p``, and ``top_k`` are deliberately absent — Opus 5
    rejects them with a 400. ``thinking`` is left unset, which runs adaptive
    thinking on this model.
    """
    assembled = build_system_prompt() if prompt is None else prompt
    behavior, knowledge = assembled.segments

    return {
        "model": model,
        "max_tokens": max_tokens,
        "output_config": {"effort": effort},
        "system": [
            {
                "type": "text",
                "text": behavior,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": knowledge,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "messages": [{"role": "user", "content": question}],
    }


def ask(client: Any, question: str, **kwargs: Any) -> tuple[Any, RequestMetrics]:
    """Send one request and return ``(message, metrics)``.

    ``client`` is an ``anthropic.Anthropic`` instance. It is injected rather than
    constructed here so tests can pass a stub and so credential resolution stays
    the caller's concern.
    """
    request = build_request(question, **kwargs)

    started = time.perf_counter()
    message = client.messages.create(**request)
    elapsed = time.perf_counter() - started

    return message, _extract_metrics(message, elapsed, fallback_model=request["model"])


def _extract_metrics(message: Any, elapsed: float, *, fallback_model: str) -> RequestMetrics:
    """Read usage off a response.

    Cache fields are absent or ``None`` on responses where caching did not apply,
    so each is coerced to zero rather than propagating ``None`` into arithmetic.
    """
    usage = getattr(message, "usage", None)

    def field(name: str) -> int:
        return int(getattr(usage, name, 0) or 0)

    return RequestMetrics(
        model=getattr(message, "model", None) or fallback_model,
        input_tokens=field("input_tokens"),
        output_tokens=field("output_tokens"),
        cache_creation_input_tokens=field("cache_creation_input_tokens"),
        cache_read_input_tokens=field("cache_read_input_tokens"),
        latency_seconds=elapsed,
        stop_reason=getattr(message, "stop_reason", None),
        request_id=getattr(message, "_request_id", None),
    )
