# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

**Phase 1 — grounded persona — is in progress.** `docs/roadmap.md` is authoritative for phase definitions and the current milestone; check it before planning work, and update it when a milestone lands.

What exists and is committed:

- `knowledge/` — the runtime corpus the model reads: bio, philosophy, projects, services, FAQ, boundaries
- `prompts/` — persona, teaching style, grounding rules, and `system.md`, the assembly specification
- `src/ask_christopher/` — prompt assembly, API client, terminal REPL, experiment transcript, eval framework
- `tests/` — full unit suite plus `tests/evals/cases.yaml`, 39 behavioural cases
- `docs/decisions/` — two ADRs; `docs/experiments/` — two recorded experiments

### Stack

Python ≥ 3.12, the `anthropic` SDK, and `pyyaml`. Tests run on pytest.

`pyproject.toml` is deliberately minimal — runtime dependencies and pytest configuration, nothing else. There is **no build backend, linter, formatter, or CI**, because nothing yet needs to build or publish the package. Don't add one incidentally; that's its own decision.

ADR-0001 scopes the Python choice to **Milestone 1 only**. It explicitly does not commit the web interface, which reopens the question at the start of Phase 2.

## Commands

```bash
python -m pytest -q                              # whole suite, offline, no credentials, ~2s
python scripts/run_evals.py list                 # describe the eval suite, send nothing
python scripts/run_evals.py replay --transcript docs/experiments/.../transcript.json
python scripts/run_evals.py live                 # price a live eval run, send nothing
python scripts/run_evals.py live --confirm       # send it (live API)
python -m ask_christopher.repl [--diagnostics]   # interactive session (live API)
python scripts/cache_experiment.py               # experiment 0001 (live API)
python scripts/first_conversation.py phase-a     # experiment 0002, turns 1-6
python scripts/first_conversation.py phase-b     # turns 7-8, after reviewing turn 6
python scripts/first_conversation.py render      # regenerate transcript.md from JSON
```

Anything touching the API needs `ANTHROPIC_API_KEY` — copy `.env.example` to `.env`. **Live runs cost real money and are not idempotent.** Never fire one to "check that it works"; the unit suite covers correctness offline, and every live script is designed to be run deliberately, once, and recorded.

## What is being built

Ask Christopher is the AI-powered front door to ChristopherMathews.com: a conversational assistant that acts as a digital representation of Christopher Mathews, a Senior Instructional Designer. It is explicitly **not a generic chatbot**. Read `docs/product-vision.md` before making product or architecture decisions — it is the authoritative spec.

Five core capabilities the system is meant to grow into (from the vision doc):

1. Answer questions about Christopher — bio, philosophy, career, projects
2. Explore the portfolio — every public repo becomes retrievable knowledge, connected into one story
3. Teach skills — AI engineering, Python, GitHub, APIs, MCP, tool calling, prompt engineering, instructional design
4. Coach visitors through building projects — explain decisions, not just emit code
5. Surface consulting/training services — education first, sales second

## Design constraints that should shape code

These come from the vision doc and should be treated as requirements, not aspirations:

- **Teaching over answering.** Output that solves a problem without leaving the user more capable misses the point. This applies to generated content and to system prompts written into `prompts/`.
- **Explain decisions.** When the assistant produces code or artifacts, the rationale is part of the deliverable.
- **Honest and human-centered.** The assistant speaks as a representation of a real person — it should not fabricate credentials, projects, or claims about Christopher's work. Ground portfolio answers in actual repository content.
- Guiding principle: *Technology Enhances. People Create.*

## Invariants — break these and the failure is silent

**The assembled system prefix must be byte-identical on every request.** One varying byte disables Anthropic's prompt cache and bills every request at full input rate, with no error and no symptom other than the cost. This is why `prompt.py` uses binary reads, explicit file lists, and normalisation before concatenation, and why the REPL assembles the prefix once in `Session.__init__` and passes the same object to every turn. `tests/test_prompt.py` guards it — if a change there fails, the change is wrong, not the test.

**`prompts/system.md` is the specification; `prompt.py` implements it.** If they disagree, argue with the specification first.

**Console-producing source must be pure ASCII.** Non-ASCII output mangles on the Windows code page, including em dashes reaching the terminal via `--help`. `tests/test_repl.py` asserts this across all three console-producing files. Markdown may use whatever typography it likes; anything printed may not.

**Experiment transcripts are immutable.** `transcript.json` is the source of truth and `transcript.md` is generated from it — never hand-edit the Markdown. A recorded run is amended by starting a new run id, not by editing the artifact.

**Evals: deterministic checks can falsify a judged case. They can never confirm one.** A `model_judged` case whose lexical checks all pass reports `needs_judgment`, never `pass`. Read `tests/evals/README.md` before trusting any number out of that suite.

## Working conventions

- **ADRs** (`docs/decisions/`) record significant, hard-to-reverse choices — one per file, from `TEMPLATE.md`. An ADR decides; it is amended by a later ADR rather than rewritten.
- **Experiments** (`docs/experiments/`) report what happened and decide nothing. Keep the raw JSON alongside the prose. Record what was *not* observed, and why the measurement can't support a claim, as carefully as the result.
- **Run the eval suite before merging any change to `prompts/` or `knowledge/`.** Those are the changes that alter behaviour, and reading the diff will not reveal that a warmer persona quietly loosened a grounding rule. Code-only changes rarely need it.
- **`docs/` is for humans; `knowledge/` is for the model.** Mixing them means the assistant either misses documentation it needs or quotes internal design notes at visitors.
- Commit directly to `main` — no feature branches in this repo. Commit, don't push, unless asked.

## Directory intent

| Path | Contents |
|---|---|
| `src/ask_christopher/` | Application code |
| `prompts/` | System prompts, persona, and the assembly spec — a first-class asset, not scratch files |
| `knowledge/` | The corpus injected into the prefix at runtime |
| `docs/` | Vision, roadmap, ADRs, experiment records |
| `scripts/` | Deliberate, recorded live-API runs |
| `tests/` | Unit suite and the behavioural eval cases |
| `config/`, `examples/`, `assets/` | README only so far — intent, not content |
