# 0001. Use Python for the MVP

**Status:** Accepted
**Date:** 2026-07-24

---

## Context

Ask Christopher had no implementation language when this decision was made. The repository contained documentation and a directory scaffold; `src/` was empty. Choosing a language now determines the dependency manifest, test runner, packaging layout, and hosting options, and it is expensive to reverse once code exists.

Four constraints applied:

**The MVP is small.** Milestone 1 is a terminal REPL that loads a Markdown corpus, assembles a cached system prompt, calls the Anthropic API, and streams a response. Roughly six modules. Nearly any modern language handles this comfortably — the technical requirements do not, on their own, select a winner.

**Learning is an explicit project goal.** `docs/product-vision.md` names Python as a topic Ask Christopher should teach. `README.md` lists Python under both current focus and active learning, and frames the project as part of a 90-day AI systems builder sprint. The language choice is therefore not purely technical: the code becomes teaching material, and it should be written in the language the project is committed to teaching.

**The portfolio is Python-centric.** The related repositories named in `README.md` — Document Chatbot, Kaggle work, MCP server examples, tool-calling examples, Python Foundations — are Python or Python-adjacent. Phase 3 of the roadmap connects those repositories into Ask Christopher's knowledge. A shared language lowers the cost of that integration and of moving code between projects.

**Phase 2 needs a web interface.** The vision positions Ask Christopher as the front door to ChristopherMathews.com. The MVP is a terminal application, but the milestone immediately after it is a browser-based chat embedded in a website. That is the constraint pulling in the other direction, and it is the reason this decision is not obvious.

## Decision

> We will implement Ask Christopher in Python for the MVP, using the official `anthropic` SDK and a `src/` package layout.

Tooling: `pyproject.toml` for dependencies and packaging, `pytest` for tests, `python-dotenv` for local environment loading.

This decision covers the MVP through Milestone 1. It does not commit the Phase 2 web interface to Python — see *Revisit when* below.

## Alternatives considered

**TypeScript / Node.js.** Genuinely the strongest competitor, and better than Python on the dimension that matters most after the MVP. A TypeScript backend and a browser frontend share one language, one package manager, and one set of types; frameworks like Next.js collapse the API layer and the chat UI into a single deployable, and edge hosting for that shape is mature and cheap. The `@anthropic-ai/sdk` is a first-class SDK with full feature parity — nothing about the API argues against it.

It lost on the learning goal rather than on the engineering. Choosing TypeScript would mean the flagship project in a portfolio built around learning Python is not written in Python, and the code that visitors read to learn from would be in a language the project does not otherwise teach. That is a real cost against a real benefit, and it is the closest call in this document.

**Do nothing yet — stay language-agnostic longer.** The corpus in `knowledge/` and the prompts in `prompts/` are plain Markdown and work under any runtime, so deferring was viable. Rejected because the deferral has no expiry condition. Milestone 1 needs code, and postponing the choice only moves the same decision later while blocking work now.

**Go, Rust, or another compiled language.** Both have Anthropic SDKs and would perform well. Rejected without much deliberation: the workload is I/O-bound network calls where runtime performance is irrelevant, neither language appears anywhere in the project's teaching goals or portfolio, and both raise the barrier for a visitor reading the source to learn.

## Consequences

**Easier.** Python is already the working language for the surrounding portfolio, so context-switching cost drops and code moves between projects. The `anthropic` Python SDK is well documented, and Milestone 1 needs only a small dependency set. Writing the application in a language the project teaches means `examples/` serves both the developer and the visitor from the same source.

**Harder — and this is the accepted cost.** Phase 2 will need a browser interface, and Python does not supply one. The likely shape is a small FastAPI service in front of the existing package with a separate frontend, which means two languages and two deploy targets where TypeScript would have needed one. That is more moving parts than the alternative, and it was chosen with the tradeoff understood rather than overlooked.

**Expensive to undo.** Once `src/` holds working code, switching languages means rewriting it. The mitigating factor is deliberate and structural: the corpus and prompts — the actual product — are Markdown and carry over unchanged. A language switch would cost the harness, not the work that took the most effort.

**Neutral.** Model access, prompt caching, streaming, and tool use are identical across SDKs. Nothing in the roadmap is unreachable from Python.

## Revisit when

Reopen this decision at **the start of Phase 2**, when the web interface is designed. Two outcomes are legitimate:

1. Keep Python for the core, add a thin API layer, build the frontend separately. Preserves this decision's benefits.
2. Port the harness to TypeScript for a single-language full-stack deployment. The corpus and prompts survive the move; only `src/` is rewritten.

Choose on the evidence available then — hosting constraints, how large the harness has actually grown, and whether the two-language split is causing real friction. Record the outcome as a new ADR superseding this one if the language changes.
