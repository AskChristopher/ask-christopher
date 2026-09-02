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

Verification is public and read-only — `GET` and `HEAD` against the live URLs.
It never assumes access to the server it is checking.

**Never verify by `POST /api/ask` unless a live call is the point.** That path
calls the model and consumes a gate slot: roughly $0.27 on a cold cache write.
`GET /api/health` reports the prefix fingerprint and the gate state for free,
which is what routine verification needs.

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
| `passenger_wsgi.py` | `/home/USER/apps/ask-api/passenger_wsgi.py` | |
| `src/ask_christopher/*.py` | `/home/USER/apps/ask-api/src/ask_christopher/` | `passenger_wsgi.py` puts `src/` on `sys.path` itself — there is no build backend and no install step |

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
| 2026-09-01 | Frontend v3 — answer formatting, showcase, duplicate-submit fix | `web/index.html`, `web/app.css`, `web/app.js` | **Prepared, awaiting upload** |
| 2026-09-01 | Frontend v2 — three-column shell, arrival, thread | `web/index.html`, `web/app.css`, `web/app.js` | Live, verified `45ac256` |
| 2026-08-30 | Canonical origin — force HTTPS, www to apex | `deploy/htaccess` | **Prepared, awaiting upload** |
| 2026-08-29 | Phase 2 cutover | `web/` (12), `passenger_wsgi.py`, `src/ask_christopher/`, `.htaccess` | Live, verified `fec4bef` and re-verified `4f15d58` |

### Batch 2026-09-01 (b) — frontend v3

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

### Batch 2026-09-01 (a) — frontend v2

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
