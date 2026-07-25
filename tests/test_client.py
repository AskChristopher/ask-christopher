"""Tests for request construction and metrics extraction.

**The API is mocked throughout.** This suite requires no credentials, spends no
money, and makes no network call. The live cache verification is a separate,
explicitly opt-in script — ``scripts/cache_experiment.py``.

What matters here is the request *shape*: a malformed prefix split, a stray
sampling parameter, or a missing ``cache_control`` marker would each break the
cache or the request, and none of them would be visible in a diff.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ask_christopher.client import (
    DEFAULT_EFFORT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    RequestMetrics,
    ask,
    build_request,
)
from ask_christopher.prompt import build_system_prompt

QUESTION = "What does a Senior Instructional Designer do?"


class FakeMessages:
    """Records the kwargs it was called with and returns a canned response."""

    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: Any) -> None:
        self.messages = FakeMessages(response)


def _response(
    *,
    input_tokens: int = 12,
    output_tokens: int = 40,
    cache_creation: int = 32_000,
    cache_read: int = 0,
    model: str = DEFAULT_MODEL,
) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        stop_reason="end_turn",
        _request_id="req_test_0001",
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
        ),
    )


# --------------------------------------------------------------------------
# Request shape
# --------------------------------------------------------------------------


def test_request_uses_two_system_blocks_from_the_breakpoints() -> None:
    prompt = build_system_prompt()
    request = build_request(QUESTION, prompt=prompt)

    blocks = request["system"]
    assert len(blocks) == 2
    assert [block["text"] for block in blocks] == list(prompt.segments)


def test_system_blocks_reassemble_into_the_assembled_prefix() -> None:
    """The split expresses cache boundaries — it must not alter the bytes."""
    prompt = build_system_prompt()
    request = build_request(QUESTION, prompt=prompt)

    assert "".join(block["text"] for block in request["system"]) == prompt.text


def test_both_system_blocks_carry_a_cache_breakpoint() -> None:
    request = build_request(QUESTION, prompt=build_system_prompt())

    for block in request["system"]:
        assert block["cache_control"] == {"type": "ephemeral"}


def test_breakpoint_count_is_within_the_api_limit() -> None:
    """At most four ``cache_control`` markers are permitted per request."""
    request = build_request(QUESTION, prompt=build_system_prompt())

    markers = sum(1 for block in request["system"] if "cache_control" in block)
    assert markers <= 4


def test_question_is_the_only_message_and_sits_after_the_prefix() -> None:
    request = build_request(QUESTION, prompt=build_system_prompt())

    assert request["messages"] == [{"role": "user", "content": QUESTION}]


@pytest.mark.parametrize("rejected", ["temperature", "top_p", "top_k"])
def test_sampling_parameters_are_absent(rejected: str) -> None:
    """Opus 5 rejects these with a 400 — their absence is load-bearing."""
    request = build_request(QUESTION, prompt=build_system_prompt())

    assert rejected not in request


def test_defaults_are_applied() -> None:
    request = build_request(QUESTION, prompt=build_system_prompt())

    assert request["model"] == DEFAULT_MODEL
    assert request["max_tokens"] == DEFAULT_MAX_TOKENS
    assert request["output_config"] == {"effort": DEFAULT_EFFORT}


def test_overrides_are_respected() -> None:
    request = build_request(
        QUESTION,
        prompt=build_system_prompt(),
        model="claude-sonnet-5",
        max_tokens=64,
        effort="medium",
    )

    assert request["model"] == "claude-sonnet-5"
    assert request["max_tokens"] == 64
    assert request["output_config"] == {"effort": "medium"}


def test_repeated_builds_produce_an_identical_prefix() -> None:
    """A cache read requires byte-identical system blocks across requests."""
    first = build_request(QUESTION)["system"]
    second = build_request("An entirely different question.")["system"]

    assert first == second


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------


def test_ask_sends_exactly_the_built_request() -> None:
    client = FakeClient(_response())
    ask(client, QUESTION)

    assert client.messages.calls == [build_request(QUESTION)]


def test_ask_returns_the_message_and_metrics() -> None:
    response = _response()
    client = FakeClient(response)

    message, metrics = ask(client, QUESTION)

    assert message is response
    assert isinstance(metrics, RequestMetrics)
    assert metrics.request_id == "req_test_0001"
    assert metrics.stop_reason == "end_turn"
    assert metrics.latency_seconds >= 0


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def test_first_call_records_a_cache_write_and_no_hit() -> None:
    _, metrics = ask(FakeClient(_response(cache_creation=32_000, cache_read=0)), QUESTION)

    assert metrics.cache_creation_input_tokens == 32_000
    assert metrics.cache_read_input_tokens == 0
    assert metrics.cache_hit is False


def test_second_call_records_a_cache_read_and_a_hit() -> None:
    _, metrics = ask(FakeClient(_response(cache_creation=0, cache_read=32_000)), QUESTION)

    assert metrics.cache_read_input_tokens == 32_000
    assert metrics.cache_hit is True


def test_total_prompt_tokens_sums_all_three_input_fields() -> None:
    """``input_tokens`` alone is the uncached remainder, not the prompt size."""
    _, metrics = ask(
        FakeClient(_response(input_tokens=12, cache_creation=0, cache_read=32_000)),
        QUESTION,
    )

    assert metrics.input_tokens == 12
    assert metrics.total_prompt_tokens == 32_012


def test_missing_cache_fields_coerce_to_zero() -> None:
    """Responses without caching omit these or return ``None``."""
    response = SimpleNamespace(
        model=DEFAULT_MODEL,
        stop_reason="end_turn",
        _request_id=None,
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )

    _, metrics = ask(FakeClient(response), QUESTION)

    assert metrics.cache_creation_input_tokens == 0
    assert metrics.cache_read_input_tokens == 0
    assert metrics.total_prompt_tokens == 100


def test_cache_read_is_far_cheaper_than_the_equivalent_write() -> None:
    """The whole point of the baseline, asserted on the arithmetic."""
    _, write = ask(FakeClient(_response(cache_creation=32_000, cache_read=0, output_tokens=0)), QUESTION)
    _, read = ask(FakeClient(_response(cache_creation=0, cache_read=32_000, output_tokens=0)), QUESTION)

    assert write.input_cost_usd is not None and read.input_cost_usd is not None
    assert read.input_cost_usd < write.input_cost_usd / 10


def test_cost_is_none_for_an_unpriced_model() -> None:
    _, metrics = ask(FakeClient(_response(model="some-future-model")), QUESTION)

    assert metrics.total_cost_usd is None


def test_as_dict_carries_no_response_text() -> None:
    """Only metrics and metadata are recorded — no answer content."""
    _, metrics = ask(FakeClient(_response()), QUESTION)
    record = metrics.as_dict()

    assert "content" not in record
    assert "text" not in record
    assert record["cache_creation_input_tokens"] == 32_000
