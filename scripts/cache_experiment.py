"""Milestone 2 baseline — live cache verification.

**Opt-in. Requires credentials and spends money.** Not part of the test suite:
``pytest`` must stay runnable with no API key and no cost, so the live check
lives here instead of behind a marker.

    python scripts/cache_experiment.py

Sends the same scripted question twice, sequentially, through an identical
cached prefix, and reports what the provider says about each call.

Two mechanics make sequential execution necessary rather than merely tidy:

* A cache entry only becomes readable once the first response has begun
  streaming, so two concurrent requests would both miss and the experiment
  would measure nothing.
* The default cache TTL is five minutes. The second call must land inside it.

What this measures is a **baseline**, not an endorsement of full-corpus
injection — see ``docs/decisions/0002-full-corpus-injection-is-a-baseline-not-the-architecture.md``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ask_christopher.client import RequestMetrics, ask  # noqa: E402
from ask_christopher.prompt import build_system_prompt  # noqa: E402

QUESTION = "What does a Senior Instructional Designer do?"

_NO_CREDENTIALS = """
No credentials found. This script makes real, billed API calls.

Set one of:
    export ANTHROPIC_API_KEY=...        (or set it in your shell profile)
    ant auth login                      (stores a profile the SDK reads automatically)

Then re-run:
    python scripts/cache_experiment.py
"""


def _print_metrics(label: str, metrics: RequestMetrics) -> None:
    print(f"\n--- {label} ---")
    print(f"  request id       : {metrics.request_id}")
    print(f"  model            : {metrics.model}")
    print(f"  stop reason      : {metrics.stop_reason}")
    print(f"  input tokens     : {metrics.input_tokens:,}   (uncached remainder only)")
    print(f"  cache creation   : {metrics.cache_creation_input_tokens:,}")
    print(f"  cache read       : {metrics.cache_read_input_tokens:,}")
    print(f"  total prompt     : {metrics.total_prompt_tokens:,}")
    print(f"  output tokens    : {metrics.output_tokens:,}")
    print(f"  cache hit        : {metrics.cache_hit}")
    print(f"  latency          : {metrics.latency_seconds:.3f}s")
    if metrics.total_cost_usd is not None:
        print(f"  input cost       : ${metrics.input_cost_usd:.6f}")
        print(f"  output cost      : ${metrics.output_cost_usd:.6f}")
        print(f"  total cost       : ${metrics.total_cost_usd:.6f}")


def main() -> int:
    try:
        import anthropic
    except ModuleNotFoundError:
        print("The `anthropic` package is not installed.  pip install anthropic", file=sys.stderr)
        return 1

    prompt = build_system_prompt()
    behavior, knowledge = prompt.segments
    print("Assembled prefix")
    print(f"  characters : {len(prompt.text):,}")
    print(f"  utf-8 bytes: {len(prompt.to_bytes()):,}")
    print(f"  segment A  : {len(behavior):,} chars  (behaviour layer)")
    print(f"  segment B  : {len(knowledge):,} chars  (knowledge corpus)")
    print(f"\nQuestion: {QUESTION}")

    client = anthropic.Anthropic()

    try:
        _, first = ask(client, QUESTION, prompt=prompt)
        _, second = ask(client, QUESTION, prompt=prompt)
    except TypeError as exc:
        # Raised at request-build time when no credential resolves at all — the
        # constructor succeeds regardless, so this surfaces here rather than above.
        if "authentication method" not in str(exc):
            raise
        print(_NO_CREDENTIALS, file=sys.stderr)
        return 1
    except anthropic.AuthenticationError:
        # A credential was found and rejected — a different problem from having none.
        print("\nCredentials were found but rejected (401). Check the key is current.", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as exc:
        print(f"\nAPI error {exc.status_code}: {exc.message}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("\nCould not reach the API. Check network connectivity.", file=sys.stderr)
        return 1

    _print_metrics("call 1 (expect cache write)", first)
    _print_metrics("call 2 (expect cache read)", second)

    print("\n--- comparison ---")
    if not second.cache_hit:
        print("  NO CACHE READ on the second call.")
        print("  The prefix is byte-stable (tests/test_prompt.py asserts it), so suspect")
        print("  the TTL, the minimum cacheable length, or a change between calls.")
    else:
        print(f"  cached prefix    : {second.cache_read_input_tokens:,} tokens")
        if first.input_cost_usd is not None and second.input_cost_usd is not None:
            saved = first.input_cost_usd - second.input_cost_usd
            pct = saved / first.input_cost_usd * 100 if first.input_cost_usd else 0.0
            print(f"  input cost call 1: ${first.input_cost_usd:.6f}")
            print(f"  input cost call 2: ${second.input_cost_usd:.6f}")
            print(f"  saved per repeat : ${saved:.6f}  ({pct:.1f}% of input cost)")
        delta = first.latency_seconds - second.latency_seconds
        print(f"  latency delta    : {delta:+.3f}s  (call 1 minus call 2)")
        print("  Note: latency is end-to-end and includes generation, which is not")
        print("  cached. Prefix handling is only part of what this number covers.")

    print("\n--- machine-readable ---")
    print(json.dumps({"first": first.as_dict(), "second": second.as_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
