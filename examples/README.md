# examples/

Small, runnable programs demonstrating how to use and extend Ask Christopher.

## Purpose

Two audiences, and the second one is the reason this directory ranks alongside the others rather than being an afterthought.

**For you:** a place to try an idea end to end before it becomes a feature. Examples are cheap to write and cheap to delete.

**For visitors:** teaching material. Ask Christopher's stated purpose is to teach AI engineering, and its own repository is the first thing a curious visitor will read. A directory of small, working, commented programs — *this is how you assemble a cached system prompt; this is what a streaming chat loop looks like* — teaches more effectively than any explanation the assistant could generate about itself.

That makes this directory part of the product's mission, not just developer convenience. The vision says every project becomes another capability; this is where the project explains itself.

## Planned examples

| Example | Demonstrates |
|---|---|
| `minimal_chat.*` | The smallest working call — client, message, response |
| `with_knowledge.*` | Loading the corpus and grounding an answer in it |
| `prompt_caching.*` | Cache breakpoint placement, with before/after token accounting |
| `streaming.*` | Streaming responses to a terminal |
| `honesty_check.*` | Asking an out-of-corpus question and showing the decline behavior |

`prompt_caching` is worth writing carefully. It is the single most cost-relevant technique in the project, the effect is measurable rather than theoretical, and printing `cache_read_input_tokens` before and after makes the concept concrete in a way prose does not.

## Conventions

- **Each example runs standalone.** One file, one concept, executable directly. Do not build a shared example framework — the moment an example needs a helper module, it stops being a teaching artifact.
- **Comment the reasoning.** Per `CLAUDE.md`: the rationale is part of the deliverable. Explain *why* the cache breakpoint sits where it does, not just that it exists.
- **Keep them working.** A broken example teaches the wrong thing and costs credibility. If an API change breaks one, fix it or remove it.
- **No secrets.** Read the key from the environment, exactly as the application does.
- **Short.** Past roughly a hundred lines it is a feature, and it belongs in `src/`.
