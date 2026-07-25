# Teaching Style

> **STATUS: PLACEHOLDER — NOT YET WRITTEN.**

The pedagogy. This file is what makes Ask Christopher an instructional designer's assistant rather than a general-purpose one.

---

## The constraint this file implements

From `CLAUDE.md`, stated as a requirement rather than an aspiration:

> **Teaching over answering.** Output that solves a problem without leaving the user more capable misses the point.
>
> **Explain decisions.** When the assistant produces code or artifacts, the rationale is part of the deliverable.

Nearly every AI assistant will answer the question. Very few leave the person able to answer it themselves next time. That gap is the product, and this file is where it gets specified.

---

## Sections to write

### Teaching over answering

<!-- What this means concretely, turn by turn. When a visitor asks for a
     working snippet, what exactly does the assistant add — and where does
     it stop? There is a real failure mode on this side too: an assistant
     that lectures when someone needed one line is not teaching, it is
     obstructing. Define the line. -->

### Explaining decisions

<!-- Every non-trivial artifact carries its reasoning: why this approach,
     what was rejected, what tradeoff was accepted.

     Specify the shape. A sentence of rationale inline? A short note after
     the code? Something else? Consistency here is what makes it feel
     designed rather than chatty. -->

### Learning by building

<!-- The vision emphasizes projects over tutorials. How does that change a
     response? Probably: shipping something small and working, then
     extending it — rather than covering theory before anything runs. -->

### Coaching through a project

<!-- Capability 4: walking someone through building an assistant, a Python
     app, an MCP server. What does the assistant do at each step, and what
     does it deliberately leave for the visitor to do?

     If it writes the entire project, the visitor learned nothing. If it
     writes none of it, they are stuck. Define the split. -->

### Calibrating to the learner

<!-- Reading level of expertise from how someone asks, and adjusting depth
     without either condescending or losing them. Include what to do when
     the signal is ambiguous. -->

### Scaffolding and next steps

<!-- Standard instructional design: what does the visitor do next, and how
     does the assistant hand off so they can keep going alone? -->

---

## Notes for whoever fills this in

- This is the file where your professional expertise is the differentiator. Most people building AI products have no background in how people actually learn; you do. Be specific enough that the difference is visible in the output.
- Make each instruction observable. "Teach effectively" cannot be evaluated. "When producing code, state why this approach over the obvious alternative" can be — and `tests/evals/` can assert it.
- Name the over-correction explicitly. An assistant that turns every exchange into a lesson is its own failure, and without a stated limit it is the likely outcome of a file full of teaching instructions.
