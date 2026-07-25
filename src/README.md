# src/

Application code. Currently empty by design — Milestone 1 is content and persona work, and the code comes after there is something to serve.

## Purpose

`src/` is the delivery mechanism. The product itself is the corpus in `knowledge/` and the behavior in `prompts/`; this directory loads them, sends them to the model, and returns the response.

That framing is worth keeping in mind, because it inverts the usual instinct. The temptation on an AI project is to build the harness first and treat the prompt as configuration. Here the prompt *is* the system, and the harness should stay small enough that rewriting it is cheap.

## Planned layout

```
src/
└── ask_christopher/
    ├── __init__.py
    ├── config.py       Model ID, effort level, environment loading
    ├── knowledge.py    Load and concatenate knowledge/*.md
    ├── prompt.py       Assemble the system prompt per prompts/system.md
    ├── client.py       Anthropic API client, streaming
    └── cli.py          Terminal REPL — the entire interface for Milestone 1
```

Six small modules with one responsibility each. If any of them grows past a couple hundred lines, something belongs somewhere else.

## Layout convention

`src/` layout, not a flat package at the repository root. The package is importable only after installation, which means tests exercise the installed package rather than accidentally importing loose files from the working directory. It catches packaging mistakes before users do.

## Design constraints

Carried from `CLAUDE.md` and the vision document:

- **Prompts and knowledge are data, not code.** Never inline persona text or biographical facts into a Python string. If a fact about Christopher appears in this directory, it has escaped review and testing.
- **The rationale is part of the deliverable.** This project is a public demonstration of AI engineering; someone will read this code to learn from it. Comment the decisions, not the syntax.
- **No secrets.** Configuration comes from the environment. `.env` is gitignored; `.env.example` documents what is required.
- **Keep it inspectable.** A reader should be able to follow a request from CLI input to assembled prompt to API call without indirection.

## Not yet decided

The language and runtime. Python is the working assumption — it matches the learning goals in `docs/product-vision.md` and the rest of the portfolio — and the layout above reflects it. The decision is not final until it is recorded in `docs/decisions/`, and the corpus and prompt files are stack-independent either way.
