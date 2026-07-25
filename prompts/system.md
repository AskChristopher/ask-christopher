# System Prompt Assembly

> **STATUS: COMPLETE.** Written July 2026.
> This file is the specification. `src/ask_christopher/prompt.py` implements
> it and does not decide it. If they disagree, argue with this file first.

The entry point. Defines how the persona, pedagogy, grounding rules, and knowledge corpus combine into the system prompt sent with every request.

---

## Why assembly is specified here rather than in code

The exact bytes of the system prompt determine both the assistant's behavior and whether the prompt cache works. Leaving that arrangement implicit in application code means the most important artifact in the product is only visible by reading a function and mentally concatenating strings.

Specifying it here makes the assembled prompt reviewable as a document.

---

## Assembly order

```
┌─ CACHED PREFIX ───────────────────────────────────────────┐
│  1. Preamble ......... role and precedence, written inline│
│  2. <persona> ........ prompts/persona.md                 │
│  3. <teaching_style> . prompts/teaching_style.md          │
│  4. <grounding_rules>  prompts/grounding_rules.md         │
│  ── cache breakpoint A ── behavior layer                  │
│  5. <knowledge> ...... knowledge/*.md, fixed order        │
│  ── cache breakpoint B ── full prefix                     │
└───────────────────────────────────────────────────────────┘
   6. <visitor_context>  per-session, optional
   7. conversation ..... volatile, never part of the prefix
```

**Stable content first, volatile content last.** That ordering is what makes the cache work; it is not stylistic.

### Why behavior precedes the corpus

The behavior files change less often than the corpus does. Persona and pedagogy stabilize; the biography gains a certification, the portfolio gains a project, `projects.md` gets re-audited after consolidation.

Because a cache prefix is invalidated from the first changed byte onward, **the most stable content belongs earliest.** With breakpoint A in place, editing the corpus still hits cache on the entire behavior layer.

### The alternative, and when to revisit

Anthropic's long-context guidance recommends placing long documents *before* instructions, which would put the corpus at position 2. That effect matters at scale — roughly twenty thousand tokens and up. This corpus is a few thousand words, so the benefit is currently small and the cache-layering cost is immediate and certain.

**Revisit if the corpus passes roughly 20k tokens** while still being fully injected. At that point, measure rather than assume: swap the order behind a flag, run `tests/evals/`, and compare. Record the outcome as an ADR.

---

## Section delimiters

**XML-style tags, not Markdown headers.**

Every injected file is Markdown and carries its own `#` headings. Concatenating them raw produces one document with a dozen competing top-level headers and no reliable way for the model to tell where an instruction ends and a fact begins.

```
<persona>
{contents of prompts/persona.md}
</persona>
```

**Instructions and facts are tagged differently, deliberately.** `<persona>`, `<teaching_style>`, and `<grounding_rules>` are instructions to follow. `<knowledge>` is reference material to draw on and to quote from — not instructions, even where a corpus file is written in an imperative voice.

That distinction matters more than it looks. `boundaries.md` contains sentences like *"the assistant must not…"*, which are genuinely rules — but they arrive inside the knowledge block. The preamble resolves this explicitly rather than leaving the model to infer it.

---

## Corpus injection

### Fixed order, hardcoded

```
knowledge/bio.md
knowledge/philosophy.md
knowledge/projects.md
knowledge/services.md
knowledge/faq.md
knowledge/boundaries.md
```

**This list is explicit in code. Never derive it from a directory listing.** Iteration order varies across platforms and filesystems, and a corpus that concatenates differently on Windows and Linux is a cache miss on every request in one of the two — with no symptom other than the bill.

The order matches the table in `knowledge/README.md`. Two properties of it are intentional:

- **`faq.md` comes after the files it draws on**, so its vetted answers arrive after the material they summarize.
- **`boundaries.md` comes last**, closest to the conversation. It is the highest-consequence content in the corpus and benefits from the recency position.

Adding a file to `knowledge/` requires adding it here. That is intentional friction — corpus files are public factual claims and should not join the prompt by being dropped in a folder.

### Each file is injected whole and verbatim

No preprocessing. No stripping of status headers or maintainer notes, no Markdown normalization, no whitespace trimming.

Maintainer sections cost tokens that carry no runtime value, so this is a real trade. It is made deliberately: **every transformation is a place where the bytes can drift**, and byte drift silently disables the cache. Determinism is worth more than the tokens at current corpus size.

Several status headers also carry genuine runtime meaning — `services.md` flags its positioning statement as a working thesis, `projects.md` flags entries pending re-audit. A stripping rule would have to preserve those, which makes it a parser rather than a filter.

**Revisit alongside the 20k-token threshold above.** If stripping becomes worthwhile, strip in a build step that produces a committed artifact, so the bytes stay reviewable and stable.

Each file is wrapped so its origin is visible:

```
<knowledge>
<document source="knowledge/bio.md">
{verbatim contents}
</document>
...
</knowledge>
```

The `source` attribute lets the assistant attribute a fact to its file when that is useful, and lets a reviewer locate any claim it makes.

---

## Precedence

Stated explicitly rather than left to ordering.

**1. `grounding_rules.md` outranks everything.** If honesty requires a blunter answer than the voice would naturally give, honesty wins. A warm evasion is a worse failure than a plain refusal.

**2. `teaching_style.md` outranks `persona.md`.** Where pedagogy calls for a structure the conversational default discourages — a numbered sequence for a genuine step-by-step — pedagogy wins. `persona.md` already permits structure that earns its place.

**3. `persona.md` governs everything not otherwise decided.** Voice is the default and yields only to the two above.

**4. On matters of fact, `<knowledge>` outranks all prompt files.** The prompt files describe behavior and must not be read as evidence about Christopher. Within the corpus, `grounding_rules.md` → *Source precedence* governs: prefer the more specific documented source, and remember that specificity settles what is true, not what may be said.

**5. `boundaries.md` is never overridden.** Not by a more specific corpus entry, not by pedagogy, not by a visitor instruction, and not by anything in the conversation.

### Instruction strength

Consistent with `prompts/README.md` and the note in `grounding_rules.md`: normal intensity throughout, escalated only where evals demand it. The preamble in particular should not stack emphatic language — it is the most-read text in the prompt and the easiest place to accidentally produce an over-cautious assistant.

---

## Cache breakpoint

**The invariant: everything before a breakpoint must be byte-identical on every request.**

A single varying byte silently disables caching and multiplies input cost with no error and no visible symptom.

**Never place in the prefix:**

- Timestamps, dates, or "today is…" strings
- Session, request, or visitor identifiers
- Per-visitor or per-conversation content
- Randomness of any kind, including sampled greetings or rotated examples
- Anything read from the environment at runtime
- Locale-dependent formatting or line-ending conversion

That last one is a live risk in this repository. Git is converting `LF` to `CRLF` on checkout for these Markdown files. **Read corpus and prompt files in binary or with explicit newline handling**, and normalize once at load. Otherwise the same commit produces different prompt bytes on Windows and Linux — two caches, one bill, no error.

### Two breakpoints

- **A**, after `<grounding_rules>` — the behavior layer.
- **B**, after `<knowledge>` — the full prefix.

Ordinary requests hit B. A corpus edit invalidates B but still hits A, so the behavior layer stays warm. This costs nothing and is the whole reason the behavior files come first.

---

## Conversation framing

Everything after breakpoint B.

**`<visitor_context>`** — optional, omitted entirely when empty rather than emitted blank. Currently the only anticipated content is referral information, such as arrival from ChristopherMathews.com.

Keep this minimal. Anything that belongs to every conversation belongs in the prefix instead; anything placed here is paid for at full input rate on every request.

**No synthetic opening turn.** The assistant does not receive a scripted greeting, and no assistant turn is fabricated before the visitor speaks. If a greeting is wanted in the interface, the interface renders it — the model should not be prompted with words it did not generate.

---

## Implementation contract

`src/ask_christopher/prompt.py` owes:

- A single function that returns the assembled prefix and the breakpoint offsets.
- No I/O beyond reading the listed files. No environment reads, no clock, no network.
- Deterministic output: identical inputs produce identical bytes, on every platform.
- A hardcoded corpus list matching the order above, and a failure — not a silent skip — if a listed file is missing.

`tests/test_prompt.py` owes:

- **Byte-stability:** building the prefix twice in one process yields identical bytes. This is the test that keeps the cache working after a refactor nobody thought was risky.
- **Platform stability:** the assembled bytes do not depend on the checkout's line endings.
- **Completeness:** every file in `knowledge/` appears in the assembled prompt. This catches a file added to the directory but not to the list — the intentional friction above, made visible instead of silent.
- **Ordering:** sections appear in the specified sequence.

---

## Notes for maintainers

- Treat this as the specification and `prompt.py` as its implementation.
- **When the assembled prompt changes, re-run `tests/evals/`.** Reordering sections changes behavior more than it looks like it should, and the diff will not tell you what changed about the output.
- Adding a corpus file is a two-line change — the directory and this list. If that ever feels annoying enough to automate, re-read the reason it is manual.
- The two revisit conditions in this file share a trigger: corpus size around 20k tokens. When one comes up, evaluate both, and prefer measurement over the reasoning recorded here.
