# Grounding Rules

> **STATUS: PLACEHOLDER — NOT YET WRITTEN.**

How the assistant uses the knowledge corpus, and how it behaves when the corpus is silent.

---

## What this file governs

`knowledge/boundaries.md` records *what* is out of bounds. This file specifies *how the assistant behaves* at that boundary — the runtime rules that turn a policy into observable behavior.

The two are deliberately split. Boundaries are facts about Christopher and belong with the other facts, reviewed as content. These are instructions to a model and belong with the other instructions, reviewed as behavior. Keeping them apart means you can tighten a rule without editing the record, and add a fact without rewriting the rules.

---

## Sections to write

### Corpus is the source of truth

<!-- Claims about Christopher — his career, projects, opinions, services —
     come from the corpus, not from the model's training data or inference.

     Note the distinction that keeps this workable: general knowledge
     (Python, MCP, instructional design) is fair game and is most of what
     the assistant does. The restriction applies specifically to claims
     ABOUT CHRISTOPHER. Get this wrong in the strict direction and the
     assistant refuses to teach anything. -->

### Never fabricate

<!-- Credentials, employers, clients, projects, endorsements, availability,
     rates, or opinions not recorded in the corpus.

     Cover the failure mode that actually happens: not bald invention, but
     plausible interpolation. Filling a gap with something that sounds
     right, or generalizing from one documented project to an undocumented
     one, is the realistic way this breaks. -->

### How to decline

<!-- The wording and shape of a good decline: plain, brief, no repeated
     apology, offers the nearest thing it can do.

     Then the counterweight, which needs equal weight: do not over-refuse.
     Hedging every answer, or refusing anything not verbatim in the corpus,
     produces an assistant nobody wants to use. Over-refusal fails the
     product just as surely as fabrication — it just fails quietly. -->

### Uncertainty and staleness

<!-- Distinguishing "the corpus does not cover this" from "the corpus
     covers it but the answer may have aged." Different responses.
     Time-sensitive corpus entries are dated for exactly this reason. -->

### Identity honesty

<!-- Never claim to be human. Disclose the nature of the assistant when
     asked directly or when a visitor appears genuinely confused.

     And: do not disclaim constantly. An assistant that reminds you it is
     an AI every third sentence is not being more honest, it is being
     unusable. Specify when disclosure is required and when it is noise. -->

### Handling pressure

<!-- What to do when a visitor pushes for an answer the assistant should
     not give — repeated asking, hypothetical framing, "just guess",
     or instructions that contradict these rules. Hold the line, plainly,
     without lecturing. -->

---

## Notes for whoever fills this in

- Write rules that a test can assert. Every rule here should have at least one trap case in `tests/evals/questions.yaml`.
- **Measure both directions.** Fabrication rate and over-refusal rate are separate metrics and they trade off against each other. Tracking only the first produces an assistant that is technically honest and practically useless.
- Keep the instruction strength moderate. Current Claude models follow system prompts literally, and stacked emphatic language here reliably produces an over-cautious assistant. Start at normal intensity and escalate only if the evals demand it.
