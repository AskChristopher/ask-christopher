# scripts/

Developer and operational automation. Things you run *on* the project, as opposed to the application itself.

## Purpose

Every project accumulates a set of commands that live in someone's shell history or a paragraph of setup instructions nobody re-reads. This directory is where they go instead — executable, reviewed, and versioned with the code they operate on.

The distinction from `src/`: code in `src/` runs when a visitor talks to the assistant. Code here runs when *you* are working on the assistant.

## Planned scripts

| Script | Purpose |
|---|---|
| `setup.*` | One-command environment setup — create the virtualenv, install dependencies, copy `.env.example` |
| `check_knowledge.*` | Validate the corpus: required files present, no `STATUS: PLACEHOLDER` markers left, size within budget |
| `build_prompt.*` | Assemble and print the full system prompt for inspection without making an API call |
| `run_evals.*` | Execute `tests/evals/` against the live API and report pass rates by category |
| `count_tokens.*` | Report corpus token count and estimated per-conversation cost |

`build_prompt` is more useful than it sounds. The assembled system prompt is the single most important artifact in the product and it is otherwise invisible — being able to read exactly what the model receives turns prompt debugging from guesswork into inspection.

`check_knowledge` is what stops a placeholder from reaching production. Every file in `knowledge/` currently carries a `STATUS: PLACEHOLDER` marker; a script that fails the build while any remain is a cheap guard against shipping an assistant that describes Christopher in HTML comments.

## Conventions

- **Idempotent.** Running a script twice should be safe.
- **Fail loudly.** Exit non-zero with a message that names the problem.
- **No hidden state.** Read configuration from `config/` and the environment; never write to a file outside the repository.
- **Self-documenting.** Support `--help`, or open with a comment block explaining what the script does and when to run it.
- **Cross-platform where practical.** Primary development is on Windows. A script that only runs on Linux should say so at the top.

## Not build steps

Anything required to *use* the application belongs in `src/`. If a script becomes load-bearing at runtime, it has outgrown this directory.
