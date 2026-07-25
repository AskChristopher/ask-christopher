# prompts/

Persona definition, behavioral rules, and prompt templates. These are source files, not scratch notes.

## Purpose

If `knowledge/` is *what the assistant knows*, `prompts/` is *who it is and how it behaves*. Together they are the product; the code in `src/` is the delivery mechanism.

This separation is deliberate and worth preserving. Facts and behavior change on different schedules and for different reasons — you might rewrite the voice a dozen times while the biography stays fixed, or add three new projects without touching the pedagogy. Interleaving them means every edit risks the other, and it makes the prompt cache harder to reason about.

## Files

Assembled in this order:

| Order | File | Defines |
|---|---|---|
| 1 | `persona.md` | Identity and voice — who is speaking |
| 2 | `teaching_style.md` | Pedagogy — how the assistant teaches rather than just answers |
| 3 | `grounding_rules.md` | Honesty behavior — how it uses the corpus and how it declines |
| 4 | `system.md` | Assembly order, precedence, and how the corpus is injected |

`system.md` is the entry point. It defines how the other three combine and where `knowledge/` is spliced in, so that the assembled prompt is explicit and reviewable rather than an artifact of code.

## Conventions

- **Markdown, written for a model.** Plain declarative prose. Skip clever formatting; it buys nothing here.
- **Behavior only — no facts.** Anything factual about Christopher belongs in `knowledge/`. A biographical detail that leaks into a prompt file is a fact that lives outside the corpus, outside review, and outside the eval suite.
- **Instructions must be testable.** "Explain the reasoning behind any code you produce" can be checked. "Be helpful and insightful" cannot. Prefer the first kind; the eval suite can only assert against behavior you have actually specified.
- **Version deliberately.** Prompt changes shift product behavior as much as code changes do. Commit them separately from unrelated work, describe the intended behavioral change in the message, and re-run `tests/evals/` before merging.

## Caution: instruction strength

Recent Claude models follow system prompts closely and literally. Prompts written to overcome an older model's reluctance tend to *overtrigger* — `CRITICAL: YOU MUST ALWAYS…` produces an assistant that does the thing constantly and inappropriately.

Write the instruction you actually mean, at normal intensity, and escalate only if the eval suite shows you need to. If a behavior is misfiring, the first thing to try is softening the language, not adding another rule on top.

## Prompt caching

The assembled system prompt — these files plus the entire knowledge corpus — is stable across requests, which makes it an ideal cache prefix. Cached reads bill at roughly a tenth of standard input rate.

That only holds if the prefix is **byte-identical every time**. Anything volatile placed ahead of the cache breakpoint — a timestamp, a session ID, a random greeting — silently invalidates the cache on every request and quietly multiplies cost. Keep dynamic content after the breakpoint, and assert the assembled prefix is stable in `tests/test_prompt.py`.
