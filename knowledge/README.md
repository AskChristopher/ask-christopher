# knowledge/

The factual corpus the assistant is allowed to speak from. Everything here is loaded into the model's context and treated as ground truth about a real person.

## Purpose

Ask Christopher is a digital representation of Christopher Mathews, not a generic chatbot. The difference between those two things is entirely this directory. Without it, the assistant has a voice and no facts, and will invent a career to fill the gap.

The vision document states the constraint directly: the assistant *should not fabricate credentials, projects, or claims*. This directory is how that constraint is enforced in practice. The assistant answers from the corpus, and declines when the corpus is silent.

## ⚠️ Everything here is a public factual claim

Treat these files with the care of a résumé, not a scratchpad.

- **Write only what is true.** No aspirational credentials, no rounded-up titles, no projects that are still ideas.
- **Prefer omission to approximation.** A gap the assistant declines to fill costs nothing. A confident wrong answer about your professional background is expensive and hard to unwind.
- **Assume it will be quoted.** A visitor may screenshot any sentence here, attributed to you.
- **This repository is public.** Nothing private, nothing about clients without permission, no contact details you don't want scraped.

## Files

| File | Contents | Serves |
|---|---|---|
| `bio.md` | Career, roles, background, verifiable credentials | Capability 1 |
| `philosophy.md` | Teaching philosophy, beliefs about technology and learning | Capability 1 |
| `projects.md` | Real projects: what, why, what was learned | Capability 2 |
| `services.md` | Consulting, training, engagement models | Capability 5 |
| `faq.md` | Anticipated visitor questions and their answers | All |
| `boundaries.md` | What the assistant must **not** claim, and how to decline | All |

`boundaries.md` is not optional. Stating what is out of bounds is as load-bearing as stating what is true — it is what turns "I don't have that information" from an accident into a designed behavior.

## Conventions

- Markdown. Plain prose beats clever formatting; the reader is a language model.
- **Short files over one long file.** Easier to review, easier to update, easier to reason about what changed.
- Write in third person ("Christopher is…"). The persona layer in `prompts/` handles voice; this layer handles facts. Keeping them separate means you can revise the voice without touching the record, and vice versa.
- Date anything time-sensitive explicitly ("As of July 2026, …") so the assistant can qualify it rather than assert a stale fact as current.
- No instructions to the model here. Behavioral guidance belongs in `prompts/`; mixing the two makes both harder to change.

## Size and retrieval

The whole corpus is loaded into the system prompt and served from Anthropic's prompt cache, so re-reading it each turn costs roughly a tenth of normal input rate. At a few thousand words this is cheaper and far simpler than a vector database.

Revisit that when the corpus grows large enough to crowd the context window or slow the first request — see the roadmap's Phase 4. Until then, prompt-stuffing is the correct architecture, not a shortcut.
