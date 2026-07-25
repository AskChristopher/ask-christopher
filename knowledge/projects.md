# Projects

> **STATUS: WRITTEN.** All seven repositories interviewed, July 2026.
> Several entries describe work that exists **off GitHub** — see *Portfolio
> state* for how the assistant must handle that. Re-audit after the
> consolidation milestone lands.

The portfolio, written so the assistant can explain *why* each project exists — not just list them.

---

## How to write an entry

The vision asks the assistant to answer questions like *"Show me your best project"*, *"Why did you build this?"*, and *"What did you learn?"*, and to **connect the projects into one coherent story**. A bare list of repository names cannot do that. Each entry needs the reasoning behind the work.

Use this shape for every project:

```
### Project Name

**Status:** see status vocabulary below
**Evidence:** see evidence vocabulary below
**Repository:** https://github.com/AskChristopher/...

**What it is** — one or two sentences, plain language, no jargon.
**Why it exists** — the problem or question that prompted it.
**How it works** — technologies and approach.
**What was learned** — including what went wrong. Most valuable field.
**How it connects** — its relationship to the other projects.
```

### Status vocabulary

The original template assumed a repository's contents reflect its progress. That assumption does not hold here, so status is stated in three precise terms:

| Status | Meaning |
|---|---|
| **Active** | Being built now, and the repository reflects the work. |
| **In progress** | Real, substantial work exists. The repository does **not** yet reflect it. |
| **Planned** | Design or scope is defined. No implementation yet, anywhere. |

Never blur *In progress* into *Planned*, and never blur it into *Active*. It is its own state and it is the one most likely to be described inaccurately.

### Evidence vocabulary

Status describes **how built** a project is. Evidence describes **how much of it a visitor can independently verify.** These are separate axes, and collapsing them into one is how a corpus starts quietly overstating itself.

| Evidence | Meaning |
|---|---|
| **Public repository** | Committed to GitHub. A visitor can click through and read it. |
| **Public elsewhere** | Publicly documented outside GitHub — a published notebook, article, or demo. Verifiable, but not from the repository. |
| **Deliberately private** | Work exists and is intentionally unpublished for a stated, legitimate reason. **A choice, not a gap** — see below. |
| **Described only** | Christopher's own account of work he has done. Real, but no public artifact exists yet, and no particular reason it hasn't been published. |

> **The standard this corpus holds itself to: a public claim should be supported by a public artifact wherever practical. Where it is not yet, the assistant says so.**

**The assistant must not overstate how much publicly available evidence exists.** Presenting unpublished work as though a visitor could go and look at it is the quiet form of overclaiming — and it is the form most likely to be checked, because the visitor is already on GitHub when they hear it.

### Distinguish a gap from a choice

*Described only* and *deliberately private* are indistinguishable from outside the repository and completely different in meaning.

**Unpublished work invites the question "why not?". Withheld work answers it.** Where there is a legitimate reason something is not public — an active competition, a confidentiality obligation, work that is not ready — **the assistant states the reason as part of the answer, and does not apologize for the choice.**

A stated reason is stronger than an artifact-shaped silence. It is also falsifiable, which is what makes it honest: a reason that is temporary comes with a point at which it expires, and this file records that point.

---

## Portfolio state, as of July 2026

Of the seven public repositories:

- **Two are active, with the work in the public repository** — the AI Systems Builder Sprint, with roughly twenty implemented pattern modules, and Ask Christopher, this repository. *Evidence: public repository.*
- **Two are in progress, with the work outside GitHub** — the BioHub cell-tracking project, in Kaggle notebooks, and the voice assistant, built with ElevenLabs. **Their evidence situations are different and must not be merged:** the Kaggle work is *deliberately private* during an active competition, while the voice assistant is simply *not yet published.* One is a choice with a stated reason; the other is a gap.
- **Three are planned** — document-chatbot, mcp-server, and tool-calling-examples. Designs are defined; nothing is built, so there is nothing to verify.

### The off-GitHub problem, and the rule for handling it

Much of Christopher's sprint work has happened in Kaggle, Claude Code, local development environments, and documentation rather than in committed GitHub repositories. **Consolidating that work into the public repositories is an explicit next milestone.** Until it lands, the repositories understate the work.

This creates a failure mode in both directions, so the rule is explicit:

> **When describing work that is not in a public repository, the assistant states two things: what has actually been built, and where the evidence for it currently stands.**

Saying only the first invites a visitor to click through to a repository containing one file and conclude the assistant was overselling — which costs more trust than the original understatement would have. Saying only the second denies real work. **Both halves, every time.**

The evidence half is not a hedge or an apology. It is a factual statement about where something can be found, and it is what keeps the corpus and the public record honest with each other while they are out of step.

### What the repositories currently contain

As of this writing, the five non-active repositories each contain a single file: a copy of the GitHub profile README. It is a general introduction to Christopher, not a description of the project. **The assistant must not treat a repository's README as evidence of what that project is** — for five of seven, the README says nothing about the project it sits in.

A named repository is not a finished project. Describing an empty repo as though it were built is the same category of error as claiming an unearned credential.

---

## How the projects fit together

The vision asks the assistant to connect the projects into one story. It has one, and the shape is worth stating directly:

**Ask Christopher is the centerpiece and the integration point.** Everything else either feeds it or deliberately stands apart from it.

- **AI Systems Builder Sprint** — the foundation. Where each pattern is learned in isolation before it is combined.
- **document-chatbot** — the retrieval platform. Ask Christopher becomes one deployment of it.
- **mcp-server** — the service layer. Ask Christopher will consume knowledge from it rather than embedding it.
- **voice-assistant** — an alternate interface onto the same knowledge.
- **tool-calling-examples** — the teaching output, aimed outward at other developers rather than inward at his own learning.
- **biohub-cell-tracking** — deliberately outside this story. See its entry.

There is an architectural pattern in the first four: **each one moves a capability *out* of Ask Christopher and into something reusable.** Christopher is building components rather than one monolithic application, which is why the portfolio holds together as a system instead of reading as a list of unrelated experiments.

---

## Entries

### Ask Christopher

**Status:** Active
**Evidence:** Public repository
**Repository:** https://github.com/AskChristopher/ask-christopher

**What it is**

The AI-powered front door to ChristopherMathews.com — a conversational assistant acting as a digital representation of Christopher, helping visitors explore his work, learn skills, build projects, and discover services.

**It has become the centerpiece of everything he is building.**

**Why it exists**

So that visitors can experience Christopher's teaching style through conversation rather than by reading an About page, and so that his knowledge and philosophy remain available even when he is not.

**How it works**

Python, using the Anthropic API. As of July 2026 the project is in Milestone 1 — building a grounded persona: a hand-written knowledge corpus, a system prompt encoding voice and pedagogy, and an evaluation suite that tests both accuracy and honest refusal. Retrieval is deliberately deferred until the corpus outgrows the context window; the reasoning is recorded in `docs/decisions/`.

**What was learned**

The central lesson of the first phase:

> **The corpus is more valuable than the model.**

Christopher has spent considerably more time on knowledge architecture, documentation, boundaries, and product vision than on application code — and he now believes that was the correct sequencing rather than a delay.

The reasoning: **if the knowledge is well organized and grounded, models, frameworks, and interfaces can all be replaced without losing the value of the system.** The corpus is the durable asset. The model is a component, and components get swapped.

This lesson has an instructional design fingerprint on it. Diagnosing the problem before selecting the solution is the first habit described in `philosophy.md` → *On instructional design*, and it is what produced a knowledge architecture before a line of application code. The discipline transferred intact.

**How it connects**

The integration point for the whole portfolio. It is where patterns proven in the AI Systems Builder Sprint are combined into a complete system, and where document-chatbot, mcp-server, and voice-assistant are each expected to plug in as they are built.

---

### AI Systems Builder Sprint

**Status:** Active
**Evidence:** Public repository
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

The sprint is the **technical foundation behind Ask Christopher.** The division of labor is deliberate: the sprint is where Christopher learns the individual building blocks in isolation; Ask Christopher is where they come together into a complete system.

Note the distinction from `tool-calling-examples`, which covers overlapping technical ground for a different reason. The sprint is a **learning journal, written for his own understanding**. That repository is a **curated reference, written for other developers.** Different audiences, different quality bars, different purposes.

---

### document-chatbot

**Status:** Planned — design defined, not yet built
**Evidence:** None — nothing built to verify
**Repository:** https://github.com/AskChristopher/document-chatbot

**What it is**

A reusable, document-grounded RAG platform. **Not a feature of Ask Christopher** — a general system that can ingest arbitrary document collections, generate embeddings, retrieve relevant context, cite its sources, and work across multiple LLM providers.

**Why it exists**

The capability is general, so building it inside one application would waste it. As a platform, it can serve any corpus for any purpose.

**How it works**

*Planned architecture:* document ingestion, embedding generation, retrieval, source citation, and multi-provider LLM support. Nothing is implemented yet.

**What was learned**

*Pending — nothing has been built.*

**How it connects**

**Ask Christopher will eventually be one deployment of this platform**, using Christopher's own corpus as its document collection. That inverts the obvious relationship: the chatbot is not a spin-off of Ask Christopher, Ask Christopher becomes an instance of it.

It also inherits directly from the sprint's RAG, embeddings, and document question-answering modules.

---

### mcp-server

**Status:** Planned — design defined, not yet built
**Evidence:** None — nothing built to verify
**Repository:** https://github.com/AskChristopher/mcp-server

**What it is**

A Model Context Protocol server exposing Christopher's own tools and knowledge to any MCP-capable client.

**Why it exists**

To make his knowledge available as a *service* rather than as content embedded inside a single application.

**How it works**

*Planned scope.* Initially it will provide access to his document corpus, project metadata, instructional design assets, and learning journals. Nothing is implemented yet.

**What was learned**

*Pending — nothing has been built.*

**How it connects**

**Long term, Ask Christopher is expected to consume services from this MCP server rather than embedding everything directly in the application.** That is the same decoupling move document-chatbot makes for retrieval, applied to tools and knowledge access.

Together the two projects describe the intended end state: Ask Christopher as a thin, well-designed interface over reusable services, rather than a monolith that happens to know things.

---

### tool-calling-examples

**Status:** Planned — scope defined, not yet built
**Evidence:** None — nothing built to verify
**Repository:** https://github.com/AskChristopher/tool-calling-examples

**What it is**

A curated collection of **production-quality reference implementations** for developers. Planned coverage includes function calling, MCP, OpenAI, Anthropic, Microsoft Graph, Gmail, Google Calendar, GitHub, vector search, and structured outputs.

**Why it exists**

**This is not the sprint, and the difference is the point.** The AI Systems Builder Sprint is a learning journal — its audience is Christopher's own understanding, and its artifacts are learning artifacts. This repository is aimed outward, at developers looking for practical reference implementations they can actually use.

Same technical territory, different audience and a different quality bar. The assistant should draw that distinction plainly when someone asks why both exist.

**How it works**

*Planned.* Nothing is implemented yet.

**What was learned**

*Pending — nothing has been built.*

**How it connects**

The teaching output of the portfolio, and the most direct expression of the *teaching over answering* principle in a repository rather than in conversation. It is what the sprint's private learning becomes once it is polished for someone else's use.

---

### voice-assistant

**Status:** In progress
**Evidence:** Described only — no public artifact yet
**Repository:** https://github.com/AskChristopher/voice-assistant

> **The build is real; the public evidence is not there yet.** This is the entry most at risk of being overstated. The repository contains one file, and there is currently nothing a visitor can look at to confirm the work — it rests on Christopher's own account.
>
> The assistant describes what was built **and** says the documentation has not been published yet. Never imply a visitor can go and see it.

**What it is**

A voice assistant, with the core already built. Christopher has implemented it using **ElevenLabs** and created custom voices for it.

**Why it exists**

To make his knowledge reachable by speaking rather than typing — the voice interface named in the vision's ecosystem diagram and listed in `services.md` under emerging capabilities.

**How it works**

Built with ElevenLabs, including custom voices. The repository is planned to document the architecture, the integrations, and the lessons learned once the work is consolidated there.

**What was learned**

*Pending consolidation. The build exists; the write-up does not yet.*

**How it connects**

**The long-term goal is integration with Ask Christopher**, so visitors can interact with the same knowledge base by voice instead of text only. It is an alternate interface onto the corpus rather than a separate product — the same decoupling pattern as document-chatbot and mcp-server, applied to input and output.

---

### biohub-cell-tracking

**Status:** In progress — competition active
**Evidence:** Deliberately private until the competition concludes
**Repository:** https://github.com/AskChristopher/biohub-cell-tracking

> **The notebooks are intentionally unpublished, and the reason is part of the answer.** This is the canonical framing:
>
> *Christopher is actively participating in the BioHub Cell Tracking competition. The detailed notebooks and implementation are intentionally private until the competition concludes, after which he plans to publish and document the work publicly.*
>
> Give the reason plainly and without apology. Withholding an approach during an active competition is ordinary competitive practice, and explaining it is more credible than either hiding the project or hinting at unseen work.

**What it is**

Christopher's entry in the **Biohub Cell Tracking During Development** Kaggle competition. The work is well underway: extensive exploration of the competition data, data analysis, graph features, ranking models, and supporting notebooks.

**Why it exists**

**To demonstrate that he can learn advanced machine learning techniques well outside his instructional design background.** Competition machine learning is genuinely unlike anything else in the portfolio, which is exactly what makes it evidence.

**How it works**

Kaggle notebooks covering data analysis, graph feature engineering, and ranking models. These are private while the competition runs.

**After the competition concludes,** Christopher plans to organize his Kaggle profile, publish the notebooks, document the complete project, and link the public Kaggle work from the portfolio and from Ask Christopher. GitHub is intended to become the permanent, documented home for a cleaned and organized version of the work.

**What was learned**

*Pending publication. The work is substantial and ongoing; the write-up waits on the competition, not on the effort.*

**How it connects**

**It doesn't — and that is the honest answer.** This project has nothing to do with instructional design, AI assistants, or the Ask Christopher architecture, and the assistant should say so plainly rather than manufacturing a link.

Its role in the portfolio is different in kind: the other projects show depth in a direction Christopher was already heading. This one shows **range** — the ability to enter an unfamiliar technical domain and do serious work in it. A portfolio where every project reinforces the same story proves less about learning capacity than one that includes a genuine departure.

---

## Closing the evidence gap — backlog

The corpus currently describes more than the public record supports. That is honestly labeled, but the labels are a stopgap, not the goal. **The fix is to publish the artifacts, not to keep qualifying the claims.**

**Available now:**

| # | Task | Closes |
|---|---|---|
| 1 | **Publish the ElevenLabs documentation** — voice process, goals, architecture, lessons learned. | Moves voice-assistant off *described only* — the only entry with no reason for its gap. Also supplies its missing *What was learned*. |
| 2 | **Consolidate remaining sprint work** from Claude Code and local environments into the public repositories. | Closes the general gap described above. |

**Blocked on the BioHub competition concluding** — not a delay, a deliberate hold:

| # | Task | Closes |
|---|---|---|
| 3 | Organize the Kaggle profile. | — |
| 4 | Publish the BioHub notebooks. | Moves biohub to *public elsewhere*. |
| 5 | Document the complete project. | Supplies biohub's *What was learned*. |
| 6 | Link the public Kaggle work from the portfolio and from Ask Christopher. | Moves biohub to *public repository*. |

**Item 1 is the one that matters most**, because the voice assistant is now the only project asserted without either public evidence or a reason for its absence. Everything else in this file is either verifiable or explained.

When these land, the corpus and the public evidence align, and most of the qualifying language in this file can be deleted. **That deletion is the success condition.**

*This backlog belongs in `docs/roadmap.md` once that file exists — it is planned but not yet written. It sits here for now because it is inseparable from the entries it governs.*

---

## Notes for maintainers

- **Re-audit after the consolidation milestone.** Four entries above are dated by the gap between what exists and what GitHub shows. When work lands in the repositories, both status and evidence change, and the caveats come out.
- **Status and evidence are independent.** A project can be substantially built with no public evidence, which is exactly the voice assistant's situation. Never infer one from the other.
- **The three *Planned* entries have no *What was learned* field**, because nothing has been built. Leave them empty rather than filling them with intentions. That field is the most valuable one precisely because it cannot be written in advance.
- `tests/evals/questions.yaml` needs a case for each evidence tier, and the two in-progress projects need **different** assertions:
  - *Voice assistant* — the answer must contain both the ElevenLabs work and the not-yet-published caveat. One without the other fails in opposite directions.
  - *BioHub* — the answer must contain the competition reason. An answer that says only "it isn't public" is factually true and still wrong, because it reads as a gap when it is a choice.
  - A trap case worth adding: asking to see the BioHub notebooks should produce the reason and the post-competition plan, **not** a refusal and not an implication that they can be found somewhere.
- The five non-active repositories currently contain a copy of the profile README rather than a project description. If that changes, this file should not silently start trusting READMEs — update it deliberately.
