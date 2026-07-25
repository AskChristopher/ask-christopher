# Architecture Decision Records

A short, dated, immutable record of each significant technical decision — what was chosen, what was rejected, and why.

## Purpose

Six months from now, the reasoning behind a choice will have evaporated even though the choice itself remains in the code. An ADR captures the reasoning at the moment it was fresh. It converts "this is how it works" into "this is why it works this way, and here is what we knowingly gave up."

For this project the practice does double duty. Ask Christopher is a public demonstration of AI engineering, and its guiding constraint is that *the rationale is part of the deliverable*. These records are that rationale, made durable and readable by anyone who clones the repository.

## When to write one

Write an ADR when a decision is **significant and expensive to reverse**:

- Choosing a language, framework, or hosting platform
- Choosing a model, or a strategy for selecting between models
- Deciding to prompt-stuff the knowledge corpus rather than retrieve it
- Deciding how the assistant refuses to answer
- Anything you would otherwise have to re-litigate in a future conversation

Do **not** write one for reversible, low-stakes choices — file naming, a helper function's signature, formatting. Those belong in code review or a commit message.

## How to write one

1. Copy `TEMPLATE.md`.
2. Name it `NNNN-short-title.md`, numbered sequentially from `0001`.
3. Fill it in and commit it alongside the change it describes.

## Immutability

**ADRs are append-only.** Never edit a decision after it is accepted and merged. If circumstances change, write a *new* ADR that supersedes the old one, and add a line at the top of the old one pointing to its replacement. The value of the record is that it shows what was known and believed at the time — editing it retroactively destroys exactly that.

## Index

| # | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-use-python-for-the-mvp.md) | Use Python for the MVP | Accepted | 2026-07-24 |
