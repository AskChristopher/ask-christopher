# 0003. Lower the supported Python floor to 3.11

**Status:** Accepted
**Date:** 2026-08-29

---

## Context

Phase 1 is complete and Phase 2 needs somewhere to run. The hosting account is GoDaddy Web Hosting Deluxe: cPanel, File Manager, FTP, Node.js apps, Python web applications, and an existing WordPress installation on `christophermathews.com` as the primary domain.

**cPanel's Python application selector offers 3.11.15 as its newest version. 3.12 is not available.** `pyproject.toml` declared `requires-python = ">=3.12"`, so the project as specified could not be deployed to the host that was already paid for.

The declared floor turned out to be undefended. [ADR-0001](0001-use-python-for-the-mvp.md) chose Python over TypeScript on learning-goal and portfolio grounds and **never mentions a minor version**. No code comment, no test, and no dependency asked for 3.12. It reads as the newest version available when the file was written.

An audit of all 21 Python files in `src/`, `tests/`, and `scripts/` found no use of 3.12:

- Every file parses as valid 3.11 syntax under `ast.parse(..., feature_version=(3, 11))`, with the guard first proven to reject PEP 695 constructs.
- No PEP 695 generics or `type` aliases. No PEP 701 f-strings — every f-string was walked with the 3.12 tokenizer looking for same-quote reuse and backslashes in replacement fields, and none appear.
- No 3.12 standard library: no `itertools.batched`, `typing.override`, `TypeAliasType`, `Path.walk`, `sys.monitoring`, `math.sumprod`, `delete_on_close`, `onexc=`, or `walk_up`.
- The names imported from `typing` are `Any`, `Callable`, `IO`, `Iterable`, `Mapping`, `MutableMapping`, `Sequence` — all predate 3.9. Dates use `timezone.utc`, not the 3.11-added `datetime.UTC` alias.
- 20 of 21 files carry `from __future__ import annotations`, which is what makes the modern annotation style safe on an older interpreter. The exception, `src/ask_christopher/__init__.py`, carries no annotations.

The dependency tree does not ask for it either. Read from installed metadata: `anthropic` 0.120.0 is `>=3.9`, `PyYAML` 6.0.3 is `>=3.8`, `pytest` 9.1.1 is `>=3.10`, `pydantic` 2.13.4 is `>=3.9`. **The strictest floor anywhere in the tree is `>=3.10`.**

One risk was real enough to test rather than reason about. The load-bearing invariant in this project is that the assembled system prefix is byte-identical on every request, and `docs/evals/` binds recorded verdicts to `prompt_sha256`. A cross-version difference in those bytes would not break caching — each server caches whatever prefix it sends — but it would mean every Phase 1 artifact described a prefix the deployed service no longer produces. Silent, and exactly the class of failure the invariant exists to prevent.

Assembly is a binary read, a `utf-8-sig` decode, CRLF and CR folded to LF, `.strip()`, and concatenation in the order of two hardcoded tuples. There is no globbing, no `sorted()`, and **no `unicodedata.normalize`** — which matters, because 3.11 ships Unicode 14.0 and 3.12 ships Unicode 15.0. The one remaining vector was `.strip()`, whose behaviour follows `str.isspace()` and therefore the Unicode database; the assembled text contains no whitespace beyond space, tab, and newline, so that vector is moot.

Verified rather than assumed, on an isolated managed CPython 3.11.15 in a clean virtual environment with dependencies installed from scratch: the full offline suite passes, and the prefix reproduces at **134,403 bytes** with SHA-256 **`63f3b4c3d9bdc93616976b3a33b3770fce6f8fda3ef5675ace264db93198e655`** — byte-identical to the fingerprint recorded in the Phase 1 `v1c` review binding.

## Decision

> We will support Python 3.11 as the deployment floor. `requires-python` becomes `>=3.11`, and a regression test pins the assembled prefix's byte length and SHA-256 so that a cross-version or accidental change to those bytes fails a test instead of failing silently.

Development continues on whatever version is newest locally. The floor describes what deployment must satisfy, not what anyone must develop on.

## Alternatives considered

**Keep `>=3.12` and host the backend elsewhere.** Genuinely viable, and it has one real advantage: the runtime would then be a choice rather than a constraint imposed by a hosting plan, and a platform like Render or Fly gives better control over process lifecycle and streaming than shared hosting behind Passenger. It lost on cost-to-benefit. It buys a second host, a second deploy pipeline, cross-origin configuration, and a second place the `ANTHROPIC_API_KEY` has to live — all to preserve a floor that no ADR defended, no code needed, and no dependency required. Defending an accident with permanent infrastructure is the wrong trade. It also adds exactly the moving parts ADR-0001 already named as the accepted cost of choosing Python.

**Lower the floor to `>=3.10`.** The dependency tree permits it — the strictest floor in the whole tree is `>=3.10` — and it would widen compatibility for free. Rejected because it is untested. Claiming support for a version nobody has run the suite on is a promise the repository cannot keep, and the only version that needed unblocking was 3.11.

**Port the backend to Node so the cPanel Node selector could run it.** Attractive on one axis: it would collapse the frontend and backend into one language and one deploy target, which is the argument TypeScript nearly won ADR-0001 on. Rejected because it would re-implement `prompt.py` in a language where `tests/test_prompt.py` guards nothing. The byte-identical prefix is the project's most load-bearing invariant, and Phase 1 spent real measurement establishing behaviour on top of it. Rewriting that untested, to satisfy a version constraint that turned out to be imaginary, is the largest available mistake here.

**Change nothing and defer deployment.** Rejected: the constraint is two lines of metadata and the audit found nothing to fix. There is no engineering reason to wait.

## Consequences

**Easier.** The backend can run on hosting that is already paid for, alongside the static frontend, on one host with one bill and no cross-origin configuration. The change is two lines of metadata plus one test; no production code moved.

**Harder — and accepted knowingly.** Three costs:

- **The pinned fingerprint test is deliberate friction.** Any intentional edit to `prompts/` or `knowledge/` will fail it, and the constant must be updated in the same commit. That is the point: the corpus should not change without someone noticing that the cached prefix and every artifact bound to it changed too. It converts an invisible event into a required decision.
- **The floor is now a real constraint on future code.** Writing 3.12-only syntax becomes a deployment break rather than a preference. Nothing enforces this automatically — there is no CI, by choice — so it rests on this document and the `CLAUDE.md` stack note.
- **This does not make shared hosting a good place to run the service.** Passenger commonly buffers `text/event-stream`, app processes idle out, and `pydantic_core` and `jiter` need `cp311` manylinux wheels to install without a build toolchain. None of those are version questions and none are settled by this ADR.

**Expensive to undo.** Very little. Raising the floor again is a one-line edit; the cost would be losing this hosting option, which is the situation that produced the decision.

**Not changed by this decision.** No prompt, corpus, eval case, dependency, or model setting moved. The prefix is byte-identical, so every Phase 1 measurement carries over unchanged — which is what the fingerprint check establishes rather than asserts.

## Revisit when

- **cPanel offers 3.12 or newer**, and something in the code has a concrete reason to need it. Availability alone is not a reason; that is how the 3.12 floor arrived in the first place.
- **The backend moves off shared hosting** — because Passenger buffering, process idling, or the per-visitor cost of the ~41,800-token prefix made it untenable. The floor becomes a free choice again at that point.
- **A dependency raises its own floor above 3.11.** The tree's strictest requirement is `>=3.10` today; the first package to demand more forces this open.
