# 0004. Serve Phase 2 from a bare WSGI wrapper on cPanel, and replace WordPress

**Status:** Accepted
**Date:** 2026-08-29

---

## Context

Phase 1 closed with all 40 eval cases scored and a validated assistant that has no web layer at all. `src/ask_christopher/` holds prompt assembly, an API client, and a terminal REPL. There is no HTTP server, no framework, no endpoint.

Two assets arrived for Phase 2. The first is a design system — a Claude Skill now at [christopher-mathews-design-system](https://github.com/AskChristopher/christopher-mathews-design-system), holding CSS tokens, 25 React components, brand guidelines, and three click-through site prototypes. **It is not a website.** No `package.json`, no build, no router. The prototypes load React 18 development builds and `@babel/standalone` from unpkg and transpile JSX in the browser on every page load — correct for a generated prototype, unshippable as production.

The second is hosting: GoDaddy Web Hosting Deluxe, with cPanel, Git Version Control, Python applications, and a WordPress installation on `christophermathews.com`. cPanel's newest Python is 3.11.15, which [ADR-0003](0003-lower-the-supported-python-floor-to-3-11.md) unblocked by lowering the floor after verifying the prefix reproduces byte-identically at 134,403 bytes and `63f3b4c3…`.

Three facts shaped what follows.

**`Session` was already the right object.** `repl.py` documents it as *"Conversation state and transport. No terminal I/O"* — client injected, prompt assembled once at construction, history mutated only on success, and `main()` guarded by `if __name__ == "__main__"` so importing it has no side effects. Nothing about the HTTP layer required reimplementing behaviour Phase 1 measured.

**The prefix, not the hosting, is the cost problem.** At ~41,795 tokens on `claude-opus-5`, a cold cache write is $0.261 and a read is $0.021. Public traffic is bursty and uncorrelated, so most visitors pay the write: roughly **$0.27 for a new visitor's first question**, ~$0.03 for a follow-up inside the 5-minute TTL. Twenty visitors a day at three questions each is about $200/month. Pre-warming does not help — every 4.5 minutes costs ~$83/day.

**WordPress is not worth preserving.** It serves the current domain, but the design system implies a bespoke site with no CMS requirement, and wrapping React components in a WP theme means PHP theming work plus a build inside WordPress for no benefit. Treating it as legacy content to archive removes a whole class of `.htaccess` rewrite conflicts.

## Decision

> We will serve Phase 2 from a bare WSGI application on cPanel's Python 3.11 app, mount Ask Christopher at `/ask`, build the frontend as static files derived from the design system's tokens, and replace WordPress at the document root during a later cutover.

Four parts:

**A bare WSGI wrapper, no framework.** `src/ask_christopher/web.py` exposes `GET /health` and `POST /ask` in about 250 lines including documentation. Passenger wants a WSGI callable; `passenger_wsgi.py` provides one. **No dependency is added** — `anthropic` and `pyyaml` remain the entire runtime.

**A fail-closed daily gate backed by SQLite.** `src/ask_christopher/usage.py`. Rows keyed by UTC date, incremented inside one `BEGIN IMMEDIATE` transaction, configured by `ASK_DAILY_LIMIT`.

**A static frontend, no build step.** `web/` — one HTML file, one stylesheet, one script, plus the design system's `styles.css` and `tokens/` copied verbatim. No React, no Babel, no CDN except Google Fonts, which `tokens/fonts.css` already required.

**WordPress becomes legacy.** Back up, then archive at cutover. The new site takes the document root; `/ask` is a mount point under it.

Phase 1 behaviour is untouched: `claude-opus-5`, `max_tokens=2048`, `effort=low`, the two `cache_control` system blocks, and the byte-identical prefix all arrive by inheritance rather than restatement.

## Alternatives considered

**Flask or FastAPI.** Flask is the strongest competitor and the boring right answer for most projects: routing, request parsing, error handling, and a test client, all for one import. It lost on the same ground `pyproject.toml` already states — *"deliberately minimal… Don't add one incidentally"* — because for two routes it pulls six packages (flask, werkzeug, jinja2, click, itsdangerous, blinker) to replace roughly eighty lines of `json` and dict access. FastAPI lost harder: it is ASGI, and Passenger is WSGI, so it needs `a2wsgi` or a separate uvicorn process. **Revisit the moment a third route or real request parsing appears** — this is a decision about two endpoints, not a position on frameworks.

**Port the backend to Node so cPanel's Node selector could run it.** Genuinely attractive: one language for frontend and backend, one deploy target, which is the argument TypeScript nearly won ADR-0001 on. Rejected because `tests/test_prompt.py` guards the byte-identical prefix in Python and would guard nothing in a JavaScript reimplementation. Phase 1 spent $9.52 establishing behaviour on top of that invariant.

**Host the Python service off GoDaddy** (Render, Fly, Railway). Better process control, real streaming, no Passenger quirks. Rejected for the prototype because it adds a second host, a second pipeline, CORS, and a second place the API key lives — to solve problems this prototype has not yet hit. **Revisit when Passenger's buffering or process recycling actually blocks something.**

**Keep WordPress and mount the app at a subpath.** The original plan, and it worked: exclude the path above WP's `RewriteRule . /index.php [L]`. Rejected once WordPress stopped being worth keeping — the exclusion is a workaround for a constraint we are choosing not to have.

**A JSON file for the usage counter.** The obvious first idea and actively unsafe here. Passenger runs several workers and recycles them; a read-modify-write JSON counter loses updates whenever two requests overlap, and a gate that silently undercounts is worse than no gate because it reports a limit it is not enforcing. SQLite gives a real cross-process transaction from the standard library.

**Streaming responses.** Rejected for v1. Passenger behind Apache commonly buffers `text/event-stream` on shared hosting, so the likely outcome is a worse experience than a clean wait plus an indicator.

**Porting the React components properly, with Vite.** The right long-term answer for the Ask interface, and the components are already ESM-clean with `.d.ts` files. Rejected for v1 because a prototype does not need a build pipeline, and the tokens deliver the visual identity without one.

## Consequences

**Easier.** One host, one bill, no CORS, no DNS change to get started. The wrapper is thin enough to read in one sitting, and every Phase 1 test still covers the code paths that matter because the wrapper delegates rather than reimplements. Deleting WordPress removes the rewrite-ordering class of failure entirely.

**Harder — and accepted knowingly.**

- **The prefix cost is unsolved and will bite before anything else does.** [ADR-0002](0002-full-corpus-injection-is-a-baseline-not-the-architecture.md) already classifies full-corpus injection as a baseline and names retrieval an active requirement. The daily gate is a spend ceiling, not a fix; it makes the bill bounded, not small.
- **The frontend is a second implementation of the design system.** Tokens are copied, not imported. When the design system changes, `web/` does not. Acceptable for three CSS files and a prototype; it is technical debt with a name.
- **No source panel means the design's central promise is unmet.** `Sources.jsx` renders citations on the premise that every answer is traceable. The corpus is injected whole, so there is nothing to cite per answer, and a panel showing plausible-but-unused sources would be exactly the fabrication `knowledge/boundaries.md` forbids. Shipping without it is honest; shipping it would not be.
- **A failed API call still consumes a gate slot.** Refunding needs a second write and a guarantee the process survives to make it. Over-counting costs a few unspent requests; under-counting costs money.
- **Removing WordPress is the one genuinely irreversible step.** A full backup before cutover is not optional.

**Expensive to undo.** Little of it. The wrapper is one file; the gate is one file; the frontend is four. The WordPress removal is the exception, and a backup makes it recoverable rather than permanent.

## Revisit when

- **A third endpoint appears, or request parsing gets real.** That is when Flask stops being overhead and starts being leverage.
- **Retrieval lands (ADR-0002).** It shrinks the prefix — the actual fix for the per-visitor cost — and makes the source panel honest, so it reopens both of the largest consequences above.
- **Passenger's behaviour blocks something concrete** — SSE buffering, worker recycling, or a wheel that will not install. That is the trigger to move the service off shared hosting, not a general preference for better infrastructure.
- **Before the WordPress cutover**, as its own decision with its own backup. This ADR commits to the direction, not to a date.
