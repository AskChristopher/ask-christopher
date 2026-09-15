# Deployment

**Method: manual upload through cPanel's File Manager. There is nothing else.**

No SSH, no FTP, no git on the server, no shell, no CI. GoDaddy Web Hosting
Deluxe with cPanel is the whole deployment surface, and the only way a file
reaches production is a person putting it there through the File Manager UI.

This is a constraint to design around rather than a temporary gap. Every
consequence below follows from it.

## The rules that follow

**GitHub is the source of truth; the server is a copy.** The server is never
edited in place, because an edit made there exists nowhere else and is lost the
moment the file is next uploaded. If something needs to change on the server, it
changes in the repository first and is uploaded second.

**Every batch must be reproducible from the committed files.** Anything that
lives only in the document root and not in the repository cannot be restored
after a mistake, and cannot be reviewed before one. `.htaccess` is the case that
forced this file to exist: it shipped in the 2026-08-29 cutover, was never
tracked, and had to be downloaded from the server to be read.

**Prepare, hand off, stop.** The working sequence is fixed:

1. Prepare the exact production file or files locally, byte-for-byte final.
2. State the precise destination path for each one.
3. **Stop.** The upload is Christopher's step and nobody else's.
4. On his confirmation, verify against the live public site.
5. Only then move to the next batch.

**If the batch contains any `.py` file, restarting the Python app is part of
step 3, not a follow-up.** An upload without a restart leaves the old code
answering, and every hash check still passes — see *Uploading a `.py` file does
nothing until Passenger restarts* below.

Verification is public and read-only — `GET` and `HEAD` against the live URLs.
It never assumes access to the server it is checking.

**Never verify by `POST /api/ask` unless a live call is the point.** That path
calls the model and consumes a gate slot: roughly $0.27 on a cold cache write.
`GET /api/health` reports the prefix fingerprint and the gate state for free,
which is what routine verification needs.

**A `POST` that cannot pass validation is free, and is sometimes the only
honest check.** `_ask` validates before it consults the gate, so a deliberately
invalid payload returns `400` without touching the budget or the model. That is
the one case where `POST /api/ask` is legitimate for routine verification — and
it is how a backend upload is confirmed, since nothing else distinguishes old
code from new from outside. Read the gate before and after to prove it.

**Uploading a `.py` file does nothing until Passenger restarts.** Static files
under `public_html` are served from disk on every request, so a frontend upload
takes effect immediately. Backend code is *imported once* per worker and cached
in memory — a changed `web.py` sitting on disk is not the code answering
requests. Restart from cPanel's **Setup Python App → Restart**, or create or
re-save `~/apps/ask-api/tmp/restart.txt` through the File Manager, which is the
Passenger convention and works without leaving the one tool available.

This did not come up between 2026-08-29 and 2026-09-02 because every batch in
that window was frontend-only. The first backend change since the cutover made
it matter, and the failure mode is the worst kind: the upload succeeds, the
file is correct on disk, every hash matches, and the bug is still live.

## Path map

`USER` is the cPanel account name; the File Manager shows these as `public_html`
and `apps/ask-api` under the home directory.

| Repo path | Server path | Notes |
|---|---|---|
| `deploy/htaccess` | `/home/USER/public_html/.htaccess` | **Renamed on upload.** Tracked without the leading dot so it cannot be mistaken for configuration governing the repository itself |
| `web/index.html` | `/home/USER/public_html/index.html` | |
| `web/app.js` | `/home/USER/public_html/app.js` | |
| `web/app.css` | `/home/USER/public_html/app.css` | |
| `web/styles.css` | `/home/USER/public_html/styles.css` | |
| `web/tokens/*.css` | `/home/USER/public_html/tokens/` | All eight. `styles.css` is 274 bytes of `@import`, so a missing token file is a silent style break rather than an error |
| `passenger_wsgi.py` | `/home/USER/apps/ask-api/passenger_wsgi.py` | **Restart the Python app after uploading** |
| `src/ask_christopher/*.py` | `/home/USER/apps/ask-api/src/ask_christopher/` | `passenger_wsgi.py` puts `src/` on `sys.path` itself — there is no build backend and no install step. **Restart the Python app after uploading**, or the old code keeps answering |

Not files, and not uploadable: `ANTHROPIC_API_KEY`, `ASK_DAILY_LIMIT`, and
optionally `ASK_USAGE_DB` are set in cPanel's Environment Variables panel. See
`.env.example`. `ASK_DAILY_LIMIT` absent leaves the gate closed and every
request returns 503, by design.

Never upload: `.env`, `usage.sqlite3`, `tests/`, `docs/`, `scripts/`, or
anything under `.git/`. The usage counter is server state and lives beside
`passenger_wsgi.py`, outside the document root.

## Verifying a batch

Frontend files are verified by fetching them and comparing sha256 against the
committed bytes — a `200` proves something is served, not that it is the right
thing. The backend has its own fingerprint: `GET /api/health` returns
`prefix_sha256`, which must equal the value pinned in `tests/test_prompt.py`.
When those two checks pass, the live service is the service the recorded
measurements describe.

## Batch log

Newest first. A batch is listed once verified, with the commit that recorded it.

| Date | Batch | Files | State |
|---|---|---|---|
| 2026-09-03 | **Turn-2 fix** — role-aware message length | `src/ask_christopher/web.py`, `web/app.js` | Live, verified `e314f35`. First batch to need a Passenger restart |
| 2026-09-02 | Frontend v3 — answer formatting, showcase, duplicate-submit fix | `web/index.html`, `web/app.css`, `web/app.js` | Live, verified `a7b7543` |
| 2026-09-01 | Frontend v2 — three-column shell, arrival, thread | `web/index.html`, `web/app.css`, `web/app.js` | Live, verified `45ac256` |
| 2026-08-30 | Canonical origin — force HTTPS, www to apex, HSTS header | `deploy/htaccess` | **Prepared, awaiting upload** |
| 2026-08-29 | Phase 2 cutover | `web/` (12), `passenger_wsgi.py`, `src/ask_christopher/`, `.htaccess` | Live, verified `fec4bef` and re-verified `4f15d58` |

### Batch 2026-09-02 (turn-2 fix) — `e314f35`

**Two files, and one of them is backend — the first backend change since the
2026-08-29 cutover.** That makes this the first batch that needs a Passenger
restart, and the restart is not optional: without it the corrected `web.py`
sits on disk while the old code keeps answering.

| Order | Upload this | To exactly this path | Bytes | sha256 |
|---|---|---|---|---|
| 1 | `src/ask_christopher/web.py` | `/home/USER/apps/ask-api/src/ask_christopher/web.py` | 13,483 | `a8e397c3cd537ac6273046e0f51d14890cc57c518a1fb5dfc3b0e043a3b30940` |
| 2 | — | **Restart the Python app** (Setup Python App → Restart, or re-save `~/apps/ask-api/tmp/restart.txt`) | — | — |
| 3 | `web/app.js` | `/home/USER/public_html/app.js` | 32,482 | `ba1316369e9b7b783308bd21c1d4bedd007423013088a19cd7c35af861a94c9d` |

**Nothing else.** Not `index.html`, not `app.css`, not `styles.css`, not
`tokens/*.css`, not `passenger_wsgi.py`, not any other file under
`src/ask_christopher/`. `tests/` is never uploaded.

**Backend first, and the order carries a reason.** `web.py` alone fixes the
bug; `app.js` alone fixes nothing, because it only improves the wording of an
error the old server never sends. Uploading the backend first therefore ends the
outage at step 2 rather than at step 3. Neither intermediate state is broken: an
old frontend meeting the new server maps `history_entry_too_long` to a generic
"something went wrong", which is wrong but harmless, and a new frontend meeting
the old server simply never reaches its new branch.

**Not a prompt or corpus change.** `prompts/`, `knowledge/`, the model settings
and the assembled prefix are untouched, so `prefix_sha256` must still read
`63f3b4c3...` afterwards. If it moves, something was uploaded that should not
have been.

#### Verifying it, without spending anything

The hashes prove the right bytes are on disk. They cannot prove Passenger
reloaded — and that is the failure this batch is most likely to hit. One `POST`
settles it for free, because it can never pass validation and so never reaches
the gate or the model:

```
POST /api/ask   {"messages": [
  {"role": "user",      "content": "First question."},
  {"role": "assistant", "content": "x" * 8193},
  {"role": "user",      "content": "Second question."}]}
```

| Response | Meaning |
|---|---|
| `400 {"error": "history_entry_too_long"}` | **New code is live.** The restart took effect |
| `400 {"error": "question_too_long"}` | Old code is still answering. Restart again |
| `200` | Neither — something is wrong; stop and report it |

Read `GET /api/health` before and after to confirm the gate counter does not
move, which is the proof the check was free.

Then the ordinary checks: `/app.js` fetched and sha256-compared against the
table above, `prefix_sha256` unchanged, and the twelve files *not* in this batch
re-fetched and confirmed unchanged.

**What this verification still does not establish.** A real two-turn
conversation costs a gate slot and roughly $0.27 for the first question. The
free check above proves the corrected validation is running; it does not prove a
second turn now returns an answer, because proving that requires paying for one.
That is a deliberate stopping point, not an oversight.

#### Verified live, 2026-09-03 at 01:03Z

Uploaded and the Python app restarted by Christopher. **The six-step server
check below was run by Claude and cost nothing.** The real two-turn
conversation, which is the only thing that can confirm the fix end to end, was
run by Christopher in a browser — see the section after this one.

| Step | Check | Result |
|---|---|---|
| 1 | `GET /api/health` — gate before | `200`, `used: 0, limit: 10` |
| 2 | `POST /api/ask`, assistant entry 8,193 chars | **`400 {"error": "history_entry_too_long"}`** |
| 3 | `GET /api/health` — gate after | `used: 0`, **unchanged**; step 2 was free |
| 4 | `GET /app.js` | `200`, 32,482 B, **sha256 matches** `ba131636...f861a94c9d`. `Last-Modified: 2026-09-03 01:03:39Z` |
| 5 | `prefix_sha256`, plus the twelve document-root files **not** in this batch | Pin `63f3b4c3...` unchanged; **all twelve unchanged** |
| 6 | `GET /api/bogus`, `GET /api/ask` | `404 not_found`, `405 method_not_allowed` |

**Step 2 is the load-bearing one, and it is not a hash comparison.**
`history_entry_too_long` does not exist as a code in the previous `web.py`, so
the running interpreter answering with it is the *restart* being confirmed
rather than the bytes on disk. A file-hash check cannot make that claim, which
is exactly why the restart rule above needed its own verification design.

Step 3 is the proof that step 2 was free rather than an assurance that it was:
an 8,342-byte body reached `/api/ask` and the counter did not move, because
`_ask` validates before consulting the gate.

Step 5 proves the upload touched **one** document-root file. `app.js` matching
shows the right file arrived; the other twelve being byte-unchanged is what
establishes nothing else did.

#### End-to-end confirmation, by Christopher, in a browser

**Run by Christopher, not by Claude.** Claude made no model request at any point
in this batch.

The original reproduction sequence, in a fresh session: asked *"What does
Christopher build?"*, waited for the full live response, then clicked the
suggested *"What could he build for my organization?"*. **The second turn
returned a normal model response. The false `question_too_long` failure did not
occur.**

Corroborated from the server afterwards by a single free `GET /api/health`: the
gate counter had moved **0 to 2** within the same UTC day, which is exactly two
model requests and matches a two-turn conversation. That is independent evidence
for the report without Claude having made either call.

This is the check the hash-and-status verification structurally cannot perform,
and the reason it was left to a person rather than automated: confirming the fix
requires spending money, so it required a decision rather than a script.

### Batch 2026-09-02 — frontend v3

Evidence from the first live production conversation. Same three files, same
paths, all replacements. Backend, prompts, corpus and environment untouched;
the prefix fingerprint must still read `63f3b4c3...` afterwards.

| Upload this | To exactly this path | Bytes | sha256 |
|---|---|---|---|
| `web/index.html` | `/home/USER/public_html/index.html` | 8,987 | `1d4ee1c767957f51c7c9999ef1bf92c4326c73099358a14619d05b3b533f6bdf` |
| `web/app.css` | `/home/USER/public_html/app.css` | 26,036 | `ae0a6f2cd209d03f8f6607dc332bf683be4af981343f7481fe11098a1aad83d2` |
| `web/app.js` | `/home/USER/public_html/app.js` | 31,251 | `57c7dd24f4ce686e1082ddbf7e0849ed04d781e2d8ae905e979fc2b50dc300e6` |

Again: **do not re-upload `styles.css` or `tokens/*.css`.** All nine were
confirmed unchanged on the server during the v2 verification.

Upload all three in one File Manager operation if possible — every partial
state is broken, so the goal is to keep the window short rather than to
sequence around it. One at a time, use `app.css` then `app.js` then
`index.html`, so the moment the markup lands everything is consistent. Then
hard-refresh: nothing here sets cache headers, so a normal reload can serve the
old `app.js` and look exactly like a failed upload.

Verification is the same three free `GET`s as the v2 batch, plus re-fetching
the nine untouched files to prove the upload hit exactly three.

#### Verified live, 2026-09-02 at 21:46Z

Uploaded by Christopher; read back from the public endpoints. Every check a
`GET`. **No `POST /api/ask` was made, so the deployment cost nothing** and
consumed no gate slot.

| Check | Result |
|---|---|
| `/index.html`, `/app.css`, `/app.js` | `200`, and **sha256 equal to the table above** — 8,987 / 26,036 / 31,251 bytes, byte-for-byte the committed bytes at `a7b7543` |
| `Last-Modified` | `2026-09-02 02:13:14Z` on **all three, identical** — one upload operation, so there was no mixed-version window |
| `GET /` | Same sha256 as `/index.html` |
| `GET /api/health` | `prefix_sha256` still `63f3b4c3...`, matching the pin in `tests/test_prompt.py`; gate `used: 0, limit: 10` |
| The nine files **not** uploaded | `styles.css` and all eight `tokens/*.css` re-fetched and sha256-compared against the repository: **all nine identical** |
| Routing | `/api/bogus` → our `not_found`, `/api/ask` → our `method_not_allowed`, `/wp-login.php` still `404` |

**The v3 logic is present in the served JavaScript, not merely the right byte
count.** The fetched `app.js` was searched for `renderRich`, `safeUrl`,
`clearFailed`, `requestId`, `FIX 1` through `FIX 6`, both work-record ids, both
repository URLs, `Featured work.`, `Mentioned in that answer` and
`View on GitHub` — all present. The markup-from-string sinks are **absent** from
the same served file: no `.innerHTML =`, no `.outerHTML =`, no
`insertAdjacentHTML(`. So the security invariant holds on the bytes the public
is served, not only on the bytes in the repository. A rendered screenshot of the
live URL confirms the showcase rail carries both cards, the count and
`Featured work.`

Two lines of the verification probe reported a miss and **both were faults in
the probe rather than in the deployment**: one searched for an id that does not
exist (`ask-systems`), and one searched for a blurb phrase that spans a string
concatenation in the source and therefore only exists once assembled at
runtime. Recorded because a reader comparing probe output to this table would
otherwise see two unexplained misses.

**Not established, and the limitation is the important part of this record.**
The deployment is verified; the *behaviour* it deploys is not verified in
production. **No question has been submitted through v3 to the model.** The gate
read `used: 0` before and after, which is simultaneously the proof that nothing
was spent and the proof that the following are tested only locally, in a
headless browser against a stubbed `fetch`:

- **Markdown rendering** — bold, italics, both list kinds, safe links, heading
  markers stripped, and hostile input (`<script>`, `<b>`, `javascript:`,
  `mailto:`) refused. Verified against a synthetic reply, not a real one.
- **Showcase promotion** — matching, reordering, the signal highlight and the
  `Mentioned in that answer.` sub-line. Verified against a synthetic reply whose
  text was written to contain both record names.
- **Submission behaviour** — the six duplicate-submit fixes, across six paths.
  Verified by dispatching synthetic events, not by a person typing.

A real answer differs from the synthetic one in the way that matters here: its
Markdown is whatever the model chose to emit, and only a live question shows
which constructs actually appear. The first production question through v3 is
therefore still an unrun test, and should be treated as one.

### Batch 2026-09-01 — frontend v2

Three files, all replacements of files already at the document root. Nothing
new, nothing renamed, nothing deleted.

| Upload this | To exactly this path | sha256 |
|---|---|---|
| `web/index.html` | `/home/USER/public_html/index.html` | `1886d1732ed65537572677d78354d6b321a1dc400524baf4a85b779c3fb77aa0` |
| `web/app.css` | `/home/USER/public_html/app.css` | `2aa18c6ad360fbe9592c4226fe371076d2234b90ce311b1e8ac909fa52e86a09` |
| `web/app.js` | `/home/USER/public_html/app.js` | `4af951ecf73e1bb79f5fa6829b31a69fea593ea2fadb1f1c7c8ae788cd68125a` |

**Do not re-upload `styles.css` or `tokens/*.css`.** All nine were compared
byte-for-byte against `design_handoff_ask_christopher/design-system-tokens/`
and are identical to what the 2026-08-30 re-verification already proved is on
the server. Re-uploading them cannot help and can only introduce a difference.

**Backend untouched.** No change to `passenger_wsgi.py`, `src/ask_christopher/`,
`prompts/`, `knowledge/`, or any environment variable. The prefix fingerprint
must still read `63f3b4c3...` after this batch — if it moves, something was
uploaded that should not have been.

**Independent of the pending `deploy/htaccess` batch.** Neither depends on the
other, so they can go in either order or together.

Verification after upload, all free:

1. `GET /api/health` — `prefix_sha256` unchanged at `63f3b4c3...`, gate still reporting.
2. Fetch each of the three files and compare sha256 against the table above.
3. `GET /` and confirm `data-api="/api"` and `data-mode="ask"` are present.

Do **not** verify with `POST /api/ask`. This batch changes no backend
behaviour, and a `POST` costs a gate slot and roughly $0.27 on a cold cache
write. The frontend's own request path is unchanged from v1: same endpoint,
same `{messages}` body, same `{reply, usage}` handling.

#### Verified live, 2026-09-01 at 14:46Z

Uploaded by Christopher; read back from the public endpoints, every check a
`GET`. **No `POST /api/ask` was made, so the deployment cost nothing** and
consumed no gate slot.

| Check | Result |
|---|---|
| `/index.html`, `/app.css`, `/app.js` | `200`, and **sha256 equal to the table above** — 8,502 / 24,076 / 19,916 bytes |
| `Last-Modified` | 14:28:49Z to 14:29:03Z, consistent with one upload operation |
| `GET /` | Same sha256 as `/index.html`; `data-api="/api"`, `data-mode="ask"`, `id="showcase-cards"`, `id="askbar-locked"` all present in the served bytes |
| `GET /api/health` | `prefix_sha256` still `63f3b4c3...`, gate `used: 0, limit: 10` |
| The nine files **not** uploaded | `styles.css` and all eight `tokens/*.css` re-fetched and sha256-compared against the repo: **all nine identical** |
| Routing | `/api/bogus` → our `not_found`, `/api/ask` → our `method_not_allowed`, `/wp-login.php` and `/wp-admin/` still `404` |
| Headers | `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` |

Re-fetching the nine untouched files is what makes this a verification of the
*batch* rather than of the three files. A `200` on the three proves they
arrived; proving the other nine are unchanged is what establishes the upload
hit exactly three files and nothing else.

**Not established:** no question has travelled through the new `app.js` to the
model and back in production. The gate read `used: 0` before and after, which
is the evidence that nothing was spent — and equally the evidence that the
end-to-end path is verified only against a stubbed `fetch`. The request shape
is unchanged from v1, so there is no new reason to expect a failure; that is an
argument from unchanged code, not a measurement.

**Unchanged and still open:** `/ask` returns `404`, and no
`Strict-Transport-Security` header is sent. The pending `deploy/htaccess` batch
is what addresses the second. Neither is a regression from this batch.
