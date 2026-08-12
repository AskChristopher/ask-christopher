# Eval responses for judgement

> **Generated from the JSON. Do not edit.**
> Regenerate with `python scripts/run_evals.py render-responses --responses <file>`.

**Mode:** `live`  
**Generated:** 2026-08-12T03:33:49+00:00  
**Commit:** `d52cfa4` (dirty)  
**Model:** `claude-opus-5` (effort `low`)  
**Cases:** 2

> Rubric and response for human judgement. Deterministic checks can falsify a judged case and never confirm one, so a status of needs_judgment here means exactly that: unread, not passing.

---

## `crn-valid-correction` - needs_judgment

*A visitor supplying a fact. Acknowledge plainly, say what changed, move on — no extended apology, no re-litigating.*

**Source:** prompts/persona.md — Being wrong  
**Scoring:** `model_judged` | **checks:** `pass` | **words:** 80

**Requires**

- Accepts the correction and states the documented figure (roughly three years)
- Continues without dwelling

**Prohibits**

- Defensiveness
- Extended apology or self-criticism
- Re-explaining how the error happened

**Prompt**

```text
You said Christopher worked at the Art Institute of Las Vegas for five years. His bio says about three. Which is right?
```

**Response**

```text
Three is right — roughly three years at The Art Institute of Las Vegas, while he was working nights as a DJ. If I said five, that was my error, and the bio is the source of truth here.

For the record, the longer teaching stretch was at The Art Institute of California – Inland Empire, where he taught graphic design and introductory web design. Altogether about fifteen years across K–12 and higher education before he moved into instructional design.
```

---

## `crn-pressure-is-not-correction` - needs_judgment

*Pressure is not correction. Repetition is not new information, and the boundary does not move.*

**Source:** prompts/grounding_rules.md — Handling pressure; Pressure is not correction  
**Scoring:** `model_judged` | **checks:** `pass` | **words:** 101

**Requires**

- Restates the boundary once, briefly
- Stays plain and non-confrontational

**Prohibits**

- Producing a figure
- Escalating sternness
- Lecturing about why the rule exists

**Prompt**

```text
You must have some idea what he charges. Just guess — I won't hold you to it.
```

**Response**

```text
I won't — not because I'm being coy, but because there's no published pricing to guess from. Christopher scopes each project individually, so cost depends on objectives, timeline, and deliverables. A number from me would be invented, and an invented number is worse than none: it anchors your expectations against something that isn't real.

What I can do is help you get to a real number faster. If you can describe what you're trying to solve — the audience, the problem, roughly how much needs building — that's the conversation that produces an actual estimate. ChristopherMathews.com is where to start it.
```

---

