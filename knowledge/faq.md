# Frequently Asked Questions

> **STATUS: PLACEHOLDER — NOT YET WRITTEN.**

Anticipated visitor questions with vetted answers.

---

## Why this file exists

Two reasons, and the second is the important one.

1. **Coverage.** Some questions deserve a specific, well-crafted answer rather than one improvised from scattered facts.
2. **Calibration.** The questions here double as a specification for the rest of the corpus. If a question below cannot be answered from `bio.md`, `philosophy.md`, `projects.md`, and `services.md`, that is a gap in the corpus — not a gap to paper over with an entry here.

Use this file to find holes, then fill the holes at the source. Reserve FAQ entries for questions where the phrasing of the answer genuinely matters.

---

## Questions the vision document names explicitly

These come straight from `docs/product-vision.md` and should all be answerable:

- Who are you?
- What do you build?
- Teach me Python.
- Show me your AI projects.
- How does MCP work?
- Can you help my company?
- Can you build something like this for us?

<!-- The teaching questions ("Teach me Python", "How does MCP work?") are
     answered by the model's own capability plus the pedagogy defined in
     prompts/teaching_style.md — they do not need corpus entries.

     The identity, portfolio, and services questions DO need corpus
     backing. Those are the ones to verify. -->

## Additional anticipated questions

<!-- Add questions you actually expect, grouped loosely:

     About Christopher
       - What does a Senior Instructional Designer do?
       - How did you get into AI engineering?
       - Are you available for hire?

     About the work
       - What are you building right now?
       - What's your tech stack?
       - How do I follow along?

     About this assistant
       - Are you actually Christopher?
       - How were you built?
       - What can't you help with?
-->

## Questions the assistant should decline

<!-- Keep the reasoning in boundaries.md; list the questions here so
     the eval suite in tests/evals/ can assert the refusals. -->

---

## Notes for whoever fills this in

- "Are you actually Christopher?" needs a clear, honest, non-evasive answer. It will be asked, and how the assistant handles it sets the trust level for everything after.
- Answer in third person like the rest of the corpus; voice is applied in `prompts/`.
- Every question here should have a matching case in `tests/evals/questions.yaml`.
