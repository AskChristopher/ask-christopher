# tests/evals/

Behavioral evaluation suite. The assessment instrument for the assistant itself.

## Purpose

Unit tests prove the code runs. They say nothing about whether the assistant is accurate, teaches well, or declines when it should — and those are the properties the product is actually judged on.

This suite is how Milestone 1 gets an exit criterion instead of a feeling. It is also the regression check that makes prompt iteration safe: a persona edit intended to warm up the voice can quietly loosen a grounding rule, and reading the diff will not reveal it.

## Why an eval suite belongs in an instructional design project

You would not ship a course and call it effective because it felt effective. You would define the outcomes, build an assessment, and measure. The same discipline applies here, and the parallel is exact — the questions below are the assessment, the corpus and prompts are the instruction, and the pass rate is the evidence.

## Structure

```
evals/
├── README.md
├── questions.example.yaml   Template showing the case format
└── questions.yaml           The real suite (to be written)
```

## What to cover

Four categories, each measuring a distinct failure mode:

**1. Accuracy** — questions answerable from the corpus. Does it get them right?
Covers: the questions named in `docs/product-vision.md`, everything in `knowledge/faq.md`.

**2. Honesty traps** — questions with a plausible wrong answer available. *The most important category.*
Credentials Christopher does not hold. Employers he has not worked for. Projects that do not exist. Rates and availability. If the assistant answers any of these, the product has failed at its core constraint regardless of how well it performs elsewhere.

**3. Teaching quality** — does it leave the visitor more capable, or just supply the answer?
Hard to score automatically; a rubric plus periodic human review is the realistic approach. Do not skip it because it is inconvenient to measure — it is the entire differentiator.

**4. Over-refusal** — general questions it *should* answer confidently.
"Teach me Python." "How does MCP work?" An assistant that refuses these has over-corrected on grounding, and this category is what catches it. Fabrication and over-refusal trade off against each other; measuring only one guarantees drifting into the other.

## Running the suite

Run it before merging any change to `prompts/` or `knowledge/` — those are the changes that alter behavior. Code-only changes rarely need it.

The suite calls the real API and costs tokens. It is small; the cost is negligible next to shipping an assistant that misstates your credentials.

*(A runner script will live at `scripts/run_evals.*` once the stack is decided.)*

## Recording results

Keep results over time, not just the latest pass or fail. A gradual decline in teaching quality across ten prompt revisions is invisible in any single run and obvious in a trend.
