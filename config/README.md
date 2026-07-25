# config/

Non-secret application configuration, kept out of source code.

## Purpose

Settings change for different reasons than code does, and often by different people. Model selection, reasoning effort, and response limits are the knobs you turn while tuning behavior — they should be adjustable without editing Python, and reviewable as a diff that shows what actually changed.

## Configuration vs. secrets

The split matters and is easy to get wrong:

| | Lives in | Committed? |
|---|---|---|
| **Configuration** — model ID, effort level, max tokens, feature flags | `config/` | Yes |
| **Secrets** — API keys, tokens, anything that grants access | `.env` (gitignored) | **Never** |

`.env.example` at the repository root documents which secrets are required, with placeholder values. It is committed; the real `.env` is not. `.gitignore` already enforces this.

The reason for the split, stated plainly: this repository is public. A committed key is a key that must be rotated immediately, and public-repository scanners find them within minutes.

## Precedence

Later sources override earlier ones:

1. Defaults in code
2. Files in `config/`
3. Environment variables
4. Command-line arguments

Environment variables outrank config files so deployment can override without a code change; CLI arguments outrank everything so a one-off experiment doesn't require editing anything.

## Planned contents

| File | Purpose |
|---|---|
| `model.toml` | Model ID, effort level, `max_tokens`, streaming |
| `app.toml` | Corpus paths, prompt assembly order, logging |

Format is undecided pending the language choice — TOML if Python, since it needs no dependency on 3.11+.

## Conventions

- **Comment every setting.** State what it does and what the tradeoff is. A configuration file is documentation that happens to execute.
- **Reference the reasoning.** Where a value came from a real decision — the model choice especially — link the relevant ADR in `docs/decisions/` rather than re-arguing it in a comment.
- **No secrets, ever.** Not even commented out, not even a truncated example. Reviewers skim; a key-shaped string in a committed file gets treated as live.

## Not yet decided

The model default. Claude Opus 5 is the working assumption for quality; Haiku 4.5 is roughly a fifth of the cost if traffic makes that matter. With the corpus served from the prompt cache, per-conversation cost is low enough that this should be decided on measurements rather than in advance — and recorded in `docs/decisions/` when it is.
