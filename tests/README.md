# tests/

Automated verification for both the code and the assistant's behavior.

## Two kinds of testing, and why they are separate

An AI application has a testing problem that ordinary software does not. Some of it is deterministic and testable the usual way — does the corpus load, is the prompt assembled in the right order. The rest is the part that actually matters to users, and it is non-deterministic: does the assistant answer accurately, teach rather than dump answers, and decline when it should.

Both are tested here, using different tools, and conflating them helps neither.

| Directory | Kind | Deterministic? | Runs on |
|---|---|---|---|
| `tests/*.py` | Unit tests | Yes | Every commit — fast, free, no API calls |
| `tests/evals/` | Behavioral evaluations | No | Before merging prompt or corpus changes — costs API tokens |

## Unit tests

Standard, fast, offline. Planned coverage:

- `test_knowledge.py` — every expected corpus file exists and loads; no placeholder markers survive into a release build
- `test_prompt.py` — sections assemble in the order `prompts/system.md` specifies, and **the cached prefix is byte-identical across repeated builds**
- `test_config.py` — environment loading, defaults, and a clear error when `ANTHROPIC_API_KEY` is absent

The byte-stability assertion in `test_prompt.py` deserves its own mention. Prompt caching only works if the prefix never varies, and a cache miss produces no error — just a silently larger bill. That failure is invisible without a test watching for it.

## Behavioral evaluations

See `evals/README.md`. Briefly: a fixed question set with expected behavior, including deliberate honesty traps, run against the real model whenever the prompts or corpus change.

This is the instructional-design instinct applied to the system itself. You would not claim a course works without assessing whether learners learned; the same standard applies to claiming the assistant is accurate.

## Conventions

- `pytest`, assuming the Python decision holds.
- Unit tests must not call the Anthropic API. Anything requiring the network belongs in `evals/`.
- A test should fail for exactly one reason, and its name should say what that reason is.
- Fixtures use small purpose-built content, never the real corpus — otherwise editing `bio.md` breaks unrelated tests.

## Running

*(Commands to be added once tooling exists. `CLAUDE.md` should be updated at the same time — it currently notes that no test runner is configured.)*
