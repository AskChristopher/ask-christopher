# Roadmap

**Status:** Living document
**Authoritative for:** phase definitions, current milestone, and the portfolio consolidation backlog

**Everything below is planned work, not delivered capability.** An unchecked item describes an intention. Nothing here should be read as a description of what exists — see `knowledge/projects.md` for what is actually built.

---

## Where the project is

**Phase 1, in progress.**

**Specified and complete:** the knowledge corpus (`knowledge/`, six files) and the prompt layer (`prompts/`, four files). What the assistant knows, who it is, how it teaches, how it stays honest, and how those assemble into the exact bytes sent to the API.

**Not built:** everything in `src/`, and the eval suite.

---

## Phase 1 — Grounded persona

Milestone 1, from ADR-0001: a terminal REPL that loads the Markdown corpus, assembles a cached system prompt, calls the Anthropic API, and streams a response.

- [x] Knowledge corpus — `knowledge/`
- [x] Prompt layer — persona, teaching style, grounding rules, assembly spec
- [x] Prompt assembly — `src/ask_christopher/prompt.py`, with byte-stability tests
- [ ] **Milestone 2 — cache baseline.** Two identical requests through the two stable prefix segments; record provider-reported cache metrics, tokens, latency, and cost. No conversation history, streaming, REPL, or retrieval.
- [ ] Terminal REPL
- [ ] Eval suite — `tests/evals/`, measuring accuracy *and* honest refusal in both directions

ADR-0001 deferred retrieval to Phase 4. **ADR-0002 amends that** — the corpus already exceeds the threshold, so full injection is now classified as a baseline and retrieval as an active requirement.

## Phase 2 — Web interface

Browser-based chat embedded in ChristopherMathews.com. The likely shape is a small FastAPI service in front of the existing package, with a separate frontend.

**Reopen ADR-0001 at the start of this phase.** The Python decision is scoped to Milestone 1 and explicitly does not commit the web interface.

## Phase 3 — Portfolio knowledge

Turn the other public repositories into retrievable knowledge, so the assistant answers from repository content directly rather than from hand-written summaries in `projects.md`.

Depends on the consolidation backlog below — there is little to retrieve until the work is actually published.

## Phase 4 — Selective retrieval

> ⚠️ **No longer a distant concern.** This phase was written with a ~20k-token trigger. The corpus measured **~24k tokens** (assembled prefix ~32.5k) the first time `prompt.py` ran, so the trigger is behind us. **Selective retrieval is an active architectural requirement, not a contingency** — see `docs/decisions/0002-full-corpus-injection-is-a-baseline-not-the-architecture.md`.

Three stages, deliberately distinguished:

| Stage | State |
|---|---|
| **Deterministic full assembly** | **Exists** — `src/ask_christopher/prompt.py`, Milestone 1 |
| **Full-prefix API testing** | **The Milestone 2 baseline** — a measurement, not a destination |
| **Selective retrieval** | **Required, not yet implemented** |

Prompt caching makes full injection *cheap*; it does not make it *right*. Caching addresses repeated input cost. It does not address context-window occupancy, first-request and post-edit latency, or — most importantly — **relevance and attention dilution**: a visitor asking what an instructional designer does currently receives the whole of `boundaries.md` and `projects.md` alongside the paragraph that answers them.

Retrieval is now gated on **having a measured baseline to compare against**, which is what Milestone 2 produces — not on a token threshold. Candidate shapes, to be chosen on evidence in a later ADR:

- Whole-corpus injection with a preprocessing step (smallest change; trades determinism for size)
- Per-file selection driven by question classification (no embeddings required)
- Chunked embedding retrieval (the original Phase 4 assumption; the largest step)

---

## Portfolio consolidation backlog

Moved here from `knowledge/projects.md`, which is corpus rather than planning. Closes the gap between what Christopher has built and what the public repositories show — see `projects.md` → *Evidence vocabulary*.

**Available now**

1. **Publish the ElevenLabs documentation** — voice process, goals, architecture, lessons learned. Moves voice-assistant off *described only*, which is currently the only project asserted with neither public evidence nor a stated reason for its absence. Also supplies its missing *What was learned*.
2. **Consolidate remaining sprint work** from Claude Code and local environments into the public repositories.

**Blocked on the BioHub competition concluding** — a deliberate hold, not a delay

3. Organize the Kaggle profile.
4. Publish the BioHub notebooks.
5. Document the complete project.
6. Link the public Kaggle work from the portfolio and from Ask Christopher.

When these land, the corpus and the public evidence align and most of the qualifying language in `projects.md` can be deleted. **That deletion is the success condition.**

### Related open item

The Kaggle profile URL is deliberately absent from the corpus: it contains Christopher's email prefix, and publishing it would undo the decision to keep the address out of `services.md`. Resolve during item 3.
