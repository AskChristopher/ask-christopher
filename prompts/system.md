# System Prompt Assembly

> **STATUS: PLACEHOLDER — NOT YET WRITTEN.**

The entry point. Defines how the persona, pedagogy, grounding rules, and knowledge corpus combine into the system prompt sent with every request.

---

## Why assembly is specified here rather than in code

The exact bytes of the system prompt determine both the assistant's behavior and whether the prompt cache works. Leaving that arrangement implicit in application code means the most important artifact in the product is only visible by reading a function and mentally concatenating strings.

Specifying it here makes the assembled prompt reviewable as a document. `src/ask_christopher/prompt.py` implements this file; it does not decide it.

---

## Sections to write

### Assembly order

<!-- The concatenation order, and the reason for it. Proposed:

       1. prompts/persona.md          — who is speaking
       2. prompts/teaching_style.md   — how it behaves
       3. prompts/grounding_rules.md  — honesty constraints
       4. knowledge/*.md              — the factual corpus
       5. [cache breakpoint]
       6. conversation history        — volatile, never cached as prefix

     Stable content first, volatile content last. That ordering is what
     makes the cache work; it is not stylistic. -->

### Section delimiters

<!-- How each file is wrapped so the model can tell instructions from
     facts. Markdown headers or XML-style tags both work; pick one and
     apply it consistently. Without clear delimiters, corpus content can
     read as instruction, and vice versa. -->

### Corpus injection

<!-- Which knowledge files load, in what order, and whether the order is
     fixed or derived from the directory listing.

     Fix it explicitly. Directory iteration order can vary across
     platforms, and a corpus that concatenates differently on Windows and
     Linux is a cache miss on every request in one of the two — with no
     visible symptom other than the bill. -->

### Precedence

<!-- What wins when instructions conflict. Grounding rules should outrank
     persona: if being honest requires a blunter answer than the voice
     would normally give, honesty wins. State this explicitly rather than
     hoping the ordering implies it. -->

### Cache breakpoint

<!-- Where the prompt-cache boundary sits, and the invariant it depends on:
     everything before it must be byte-identical on every request.

     No timestamps, no session identifiers, no per-visitor content, no
     randomness anywhere in the prefix. A single varying byte silently
     disables caching and multiplies input cost with no error message. -->

### Conversation framing

<!-- Any per-conversation context that goes AFTER the breakpoint —
     the opening turn, or a note that the visitor arrived from
     ChristopherMathews.com. -->

---

## Notes for whoever fills this in

- Treat this as the specification and `src/ask_christopher/prompt.py` as its implementation. If they disagree, this file is what needs to be argued with first.
- `tests/test_prompt.py` should assert that the assembled prefix is byte-stable across repeated builds. That test is what keeps the cache working after a refactor nobody thought was risky.
- When the assembled prompt changes, re-run `tests/evals/`. Reordering sections changes behavior more than it looks like it should.
