# docs/

Design documentation, specifications, and the record of decisions behind Ask Christopher.

## Purpose

This directory answers **"why is it built this way?"** — the question that source code cannot answer on its own. It is the counterpart to `src/`, which answers "what does it do?"

This matters more than usual for this project. One of its stated design constraints is *explain decisions, don't just produce output*. A repository that teaches through its own structure has to model that constraint at the repository level, not only in what the assistant says at runtime.

## What lives here

| Path | Contents |
|---|---|
| `product-vision.md` | The North Star. Authoritative for product and architecture questions. |
| `decisions/` | Architecture Decision Records — one file per significant, hard-to-reverse choice. |
| `roadmap.md` | Phased development plan, current milestone, and the portfolio consolidation backlog. |
| `architecture.md` | *(planned)* System diagram and component responsibilities, written once components exist. |

## What does not live here

- **API keys, credentials, or private notes.** This repository is public.
- **Auto-generated documentation.** If a tool can produce it from source, let the tool produce it.
- **Content the assistant reads at runtime.** That belongs in `knowledge/`. The distinction matters: `docs/` is written for humans reading the repository; `knowledge/` is written for the model reading the corpus. Mixing them means the assistant either misses documentation it needs or quotes internal design notes at visitors.

## Conventions

- Markdown, `kebab-case.md` filenames.
- Every document opens with its status and what it is authoritative for.
- Prefer updating an existing document over adding a near-duplicate.
