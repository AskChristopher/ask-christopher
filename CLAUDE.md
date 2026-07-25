# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This is a greenfield repository. As of this writing it contains only documentation:

- `README.md` — public-facing project overview
- `docs/product-vision.md` — the North Star product vision
- `assets/`, `prompts/`, `src/` — created but empty

There is **no build system, dependency manifest, test runner, linter, or CI configuration yet**, and the directory is not yet a git repository. Do not assume a stack (Python vs. Node, framework, package manager) — ask before scaffolding one, and update this file with the real build/test/lint commands once tooling exists.

## What is being built

Ask Christopher is the AI-powered front door to ChristopherMathews.com: a conversational assistant that acts as a digital representation of Christopher Mathews, a Senior Instructional Designer. It is explicitly **not a generic chatbot**. Read `docs/product-vision.md` before making product or architecture decisions — it is the authoritative spec.

Five core capabilities the system is meant to grow into (from the vision doc):

1. Answer questions about Christopher — bio, philosophy, career, projects
2. Explore the portfolio — every public repo becomes retrievable knowledge, connected into one story
3. Teach skills — AI engineering, Python, GitHub, APIs, MCP, tool calling, prompt engineering, instructional design
4. Coach visitors through building projects — explain decisions, not just emit code
5. Surface consulting/training services — education first, sales second

Planned technical surface area per the README: chat assistant, document Q&A (RAG), personal knowledge base, voice interface, MCP server integrations, tool-calling examples, automation workflows.

## Design constraints that should shape code

These come from the vision doc and should be treated as requirements, not aspirations:

- **Teaching over answering.** Output that solves a problem without leaving the user more capable misses the point. This applies to generated content and to system prompts written into `prompts/`.
- **Explain decisions.** When the assistant produces code or artifacts, the rationale is part of the deliverable.
- **Honest and human-centered.** The assistant speaks as a representation of a real person — it should not fabricate credentials, projects, or claims about Christopher's work. Ground portfolio answers in actual repository content.
- Guiding principle: *Technology Enhances. People Create.*

## Directory intent

- `src/` — application code
- `prompts/` — system prompts, persona definitions, and prompt templates (a first-class asset here, not scratch files)
- `docs/` — vision and design documentation
- `assets/` — static media
