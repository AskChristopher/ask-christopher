# Projects

> **STATUS: IN PROGRESS.** One full entry written. Remaining repositories are
> recorded factually but await interview.

The portfolio, written so the assistant can explain *why* each project exists — not just list them.

---

## How to write an entry

The vision asks the assistant to answer questions like *"Show me your best project"*, *"Why did you build this?"*, and *"What did you learn?"*, and to **connect the projects into one coherent story**. A bare list of repository names cannot do that. Each entry needs the reasoning behind the work.

Use this shape for every project:

```
### Project Name

**Status:** Active | Paused | Complete | Concept
**Repository:** https://github.com/AskChristopher/...

**What it is** — one or two sentences, plain language, no jargon.
**Why it exists** — the problem or question that prompted it.
**How it works** — technologies and approach.
**What was learned** — including what went wrong. Most valuable field.
**How it connects** — its relationship to the other projects.
```

---

## Portfolio state, as of July 2026

Honesty about the current state matters more than a long list. Of the public repositories:

- **One is substantial** — the AI Systems Builder Sprint, with roughly twenty implemented pattern modules.
- **One is in active development** — Ask Christopher, this repository.
- **Five are early-stage** — created and named, currently containing only a README.

The assistant should represent this accurately. A named repository is not a finished project, and describing one as though it were is the same category of error as claiming an unearned credential. When asked about an early-stage repository, the honest answer is that it exists, it is planned, and it is not yet built.

---

## Entries

### AI Systems Builder Sprint

**Status:** Active
**Repository:** https://github.com/AskChristopher/ai-systems-builder-sprint

**What it is**

Christopher's public learning laboratory. It began as a structured 90-day challenge to move from being an AI *user* to someone capable of designing and building AI systems. Rather than taking notes from courses, he set out to build a working example of every important concept he learned.

The repository does several jobs at once:

- A public learning journal documenting his progress
- A reference library of AI engineering patterns
- A collection of runnable Python examples
- A foundation for future AI projects
- A portfolio showing how his understanding has evolved over time

The goal was never a single application. It was to understand the building blocks well enough to combine them confidently into future systems.

**Why it exists**

Christopher recognized that AI was changing both software development and instructional design, and he wanted to understand how these systems actually work — not just how to use them. The sprint gave him a structured way to learn consistently while documenting everything he built.

The curriculum draws on several sources: Anthropic's AI Engineering courses, Claude Code, Python practice, API documentation, Kaggle competitions, personal experimentation, and real-world projects that required learning new concepts.

The deliberate choice was to avoid copying tutorials. The standard he set was to understand each pattern well enough to **explain it, modify it, and reuse it** later.

**How it works**

Each module isolates one important AI engineering concept into a small, understandable example, rather than building one large application up front. Patterns covered include:

Retrieval-Augmented Generation (RAG) · agents · multi-agent systems · MCP · function calling · structured outputs · embeddings · memory · evaluation · streaming · guardrails · document question answering

The repository is designed as a reference to revisit at the start of a new project. Accompanying notes capture ideas, observations, implementation details, and lessons learned during study and experimentation.

**What was learned**

The biggest lesson: **modern AI applications are not built from one breakthrough — they are built by combining many relatively simple patterns.**

Early on, embeddings, RAG, MCP, evaluation, and agent workflows seemed like unrelated topics. As the sprint progressed, it became clear they are modular building blocks that compose to solve increasingly complex problems.

A second lesson: **documentation alone is rarely enough.** Christopher understands concepts far more deeply after implementing them himself — making mistakes, debugging them, and adapting them to his own projects.

The sprint reinforced a teaching philosophy he developed long before AI: *people learn best by building, practicing, and solving real problems rather than simply consuming information.* Studying AI engineering became direct evidence for a conviction he had formed in classrooms two decades earlier.

**How it connects**

The sprint is the **technical foundation behind Ask Christopher.** Many of the concepts explored there — RAG, MCP, agents, evaluation, memory, structured outputs, document retrieval, prompt engineering — are expected to become components of Ask Christopher.

The division of labor is deliberate: the sprint is where Christopher learns the individual building blocks in isolation; Ask Christopher is where they come together into a complete system. Each experiment can be understood on its own before it is integrated into something larger.

The two projects inform each other continuously. The sprint develops technical capability; Ask Christopher supplies the real-world application that gives that capability purpose.

---

### Ask Christopher

**Status:** Active development
**Repository:** https://github.com/AskChristopher/ask-christopher

*(Factual summary from project documentation. Awaiting interview for the
"what was learned" content.)*

**What it is**

The AI-powered front door to ChristopherMathews.com — a conversational assistant acting as a digital representation of Christopher, helping visitors explore his work, learn skills, build projects, and discover services.

**Why it exists**

So that visitors can experience Christopher's teaching style through conversation rather than by reading an About page, and so that his knowledge and philosophy remain available even when he is not.

**How it works**

Python, using the Anthropic API. As of July 2026 the project is in Milestone 1 — building a grounded persona: a hand-written knowledge corpus, a system prompt encoding voice and pedagogy, and an evaluation suite that tests both accuracy and honest refusal. Retrieval is deliberately deferred until the corpus outgrows the context window.

**How it connects**

The integration point for the whole portfolio. It is where patterns proven in the AI Systems Builder Sprint are combined into a complete system, and Phase 3 of its roadmap turns the other repositories into retrievable knowledge.

---

### Early-stage repositories

These public repositories exist and are named, but **currently contain only a README with no implementation.** They are recorded here so the assistant can describe their state accurately rather than either inventing detail or staying silent about repositories a visitor can plainly see.

| Repository | State |
|---|---|
| [document-chatbot](https://github.com/AskChristopher/document-chatbot) | Concept — README only |
| [mcp-server](https://github.com/AskChristopher/mcp-server) | Concept — README only on GitHub |
| [tool-calling-examples](https://github.com/AskChristopher/tool-calling-examples) | Concept — README only |
| [biohub-cell-tracking](https://github.com/AskChristopher/biohub-cell-tracking) | Concept — README only |
| [voice-assistant](https://github.com/AskChristopher/voice-assistant) | Concept — README only |

**When asked about any of these**, the assistant should say plainly that the project is planned but not yet built, and can point to the AI Systems Builder Sprint where the relevant patterns are being developed. It must not describe features, architecture, or progress that does not exist.

*Each will get a full entry once there is something to describe.*
