/* Ask Christopher - frontend logic, v2. No framework, no build step.
 *
 * v1 was a single-column thread. v2 drives the handoff's three-column shell:
 * arrival, conversation thread, a working session rail, and a showcase rail
 * that renders from a work-record registry. The registry is empty, because
 * every portfolio item in the design prototype is placeholder content and
 * knowledge/projects.md carries no imagery and no figures with a method.
 * Adding real work later is a change to WORKS, not to layout or to this file's
 * rendering path - which is the content-model requirement the handoff sets.
 *
 * The backend contract is untouched: POST /api/ask takes {messages} and
 * returns {reply, usage}. Nothing here asks the model for structured fields,
 * so prompts/, knowledge/ and the validated Phase 1 prefix are unaffected and
 * the 40 recorded eval outcomes still describe the live service.
 *
 * The conversation lives here, in the browser. The server is stateless because
 * Passenger recycles workers without warning, so a server-side session would
 * vanish mid-conversation. History is sent with each request and trimmed to
 * the server's ceiling before sending.
 *
 * Pure ASCII source. Typographic characters use \u escapes.
 */
(function () {
  "use strict";

  /* Where the WSGI app is mounted. Read from the page rather than hardcoded,
   * because the page is a static file at the document root and the API is a
   * separate Passenger mount. Change it in index.html, not here. */
  var API = (document.body.getAttribute("data-api") || "/api").replace(/\/$/, "") + "/ask";

  /* Mirrors MAX_HISTORY_MESSAGES and MAX_QUESTION_CHARS in web.py. Kept in
   * sync by hand; the server is authoritative and refuses anything longer. */
  var MAX_HISTORY = 8;
  var MAX_CHARS = 1000;

  /* Show the remaining-questions warning only when it is nearly out. The
   * count is site-wide per UTC day, so the copy says so - it is not a
   * per-visitor allowance and must not read like one. */
  var WARN_AT = 3;

  var DASH = "\u2014";   /* em dash */
  var ARROW = "\u2192";  /* rightwards arrow */
  var DOT = "\u25cf";    /* black circle, the pulsing wait dot */

  /* The handoff's suggested questions are real brand voice and ship as-is,
   * but its kind labels quote placeholder counts ("3 case studies"). These
   * labels name the kind of question instead, which needs no data to be true.
   * Every one of these is answerable from the committed corpus. */
  var SUGGESTED = [
    { q: "What does Christopher build?", kind: "The work" },
    { q: "What AI systems has he actually built?", kind: "Projects" },
    { q: "Should this problem even be a course?", kind: "The method" },
    { q: "How does he decide what to build?", kind: "The thinking" },
    { q: "What could he build for my organization?", kind: "Services" }
  ];

  /* Work records. Empty, deliberately.
   *
   * The shape is CONTENT-MODEL.md's Work type, reduced to the fields the
   * showcase rail reads. Fill this in only from material that actually
   * exists: a headline of "In build" is a valid value and is the right answer
   * for unfinished work - borrowing a number is not. A figure without its
   * method does not ship.
   *
   * FEATURED lists the ids the rail holds before any question is asked. */
  var WORKS = {};
  var FEATURED = [];

  var els = {
    reset: document.getElementById("reset"),
    newq: document.getElementById("newq"),
    arrival: document.getElementById("arrival"),
    suggested: document.getElementById("suggested"),
    railsuggested: document.getElementById("railsuggested"),
    raillist: document.getElementById("raillist"),
    sessionlist: document.getElementById("sessionlist"),
    sessionEmpty: document.getElementById("session-empty"),
    thread: document.getElementById("thread"),
    scroll: document.getElementById("scroll"),
    form: document.getElementById("form"),
    input: document.getElementById("q"),
    send: document.getElementById("send"),
    hint: document.getElementById("hint"),
    askLive: document.getElementById("askbar-live"),
    askLocked: document.getElementById("askbar-locked"),
    showcaseCards: document.getElementById("showcase-cards"),
    showcaseCount: document.getElementById("showcase-count"),
    showcaseSub: document.getElementById("showcase-sub"),
    showcaseIdle: document.getElementById("showcase-idle")
  };

  var HINT_DEFAULT = els.hint.textContent;

  /* ------------------------------------------------------------- state --- */

  var state = {
    turns: [],        // [{ q, node }] one per asked question, answered or not
    history: [],      // [{role, content}] exactly what POST /ask expects
    pending: null,    // question in flight
    busy: false,
    locked: false,    // the site's daily cap is reached
    showcase: FEATURED.slice()
  };

  /* --------------------------------------------------------------- dom --- */

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function pad(n) {
    return (n < 10 ? "0" : "") + n;
  }

  /* ------------------------------------------------------------ arrival --- */

  function renderSuggested() {
    SUGGESTED.forEach(function (item) {
      var b = el("button", "suggested__item");
      b.type = "button";
      b.appendChild(el("span", null, item.q));
      b.appendChild(el("span", "suggested__kind", item.kind.toUpperCase() + " " + ARROW));
      b.addEventListener("click", function () { submit(item.q); });
      els.suggested.appendChild(b);

      var li = el("li");
      var r = el("button", "raillist__row", item.q);
      r.type = "button";
      r.addEventListener("click", function () { submit(item.q); });
      li.appendChild(r);
      els.raillist.appendChild(li);
    });
  }

  /* ------------------------------------------------------- session rail --- */

  function renderSession() {
    clear(els.sessionlist);

    var rows = state.turns.map(function (t, i) {
      return { label: t.q, i: i, pending: false };
    });
    if (state.pending) {
      rows.push({ label: state.pending, i: rows.length, pending: true });
    }

    els.sessionEmpty.hidden = rows.length > 0;

    rows.forEach(function (row, idx) {
      var li = el("li");
      var b = el("button", "sessionlist__row", row.label);
      b.type = "button";
      if (row.pending) {
        b.className += " sessionlist__row--pending";
      } else if (idx === rows.length - 1) {
        b.className += " sessionlist__row--current";
      }
      b.addEventListener("click", function () { goToTurn(row.i); });
      li.appendChild(b);
      els.sessionlist.appendChild(li);
    });
  }

  function goToTurn(i) {
    var node = els.thread.children[i];
    if (node) node.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  /* ---------------------------------------------------------- showcase ---
   *
   * Renders from WORKS. With no records it renders zero cards and shows the
   * idle state - the same code path that will render cards, running with an
   * empty registry rather than being switched off. Never reports a count of
   * zero: the handoff bans statistics in this rail, and "0 pieces" is the
   * worst kind. */

  function renderShowcase() {
    clear(els.showcaseCards);

    var ids = state.showcase.filter(function (id) { return WORKS[id]; });

    ids.forEach(function (id) {
      els.showcaseCards.appendChild(showcard(WORKS[id]));
    });

    var n = ids.length;
    els.showcaseCount.textContent = n ? n + (n === 1 ? " piece" : " pieces") : "";
    els.showcaseIdle.hidden = n > 0;
    els.showcaseSub.textContent = n
      ? "A few pieces to start with."
      : "Nothing in here yet.";
  }

  function showcard(w) {
    var card = el("button", "showcard");
    card.type = "button";
    card.disabled = true;   // nothing to open until the artifact view exists
    card.title = "Opening a piece arrives with the next batch";

    var media = el("span", "showcard__media");
    var slot = el("span", "showcard__slot");
    slot.style.aspectRatio = w.ratio || "16 / 10";
    slot.appendChild(el("span", "showcard__n", w.n || ""));
    media.appendChild(slot);
    card.appendChild(media);

    var body = el("span", "showcard__body");
    var meta = el("span", "showcard__meta");
    meta.appendChild(el("span", "showcard__cat", w.cat || ""));
    meta.appendChild(el("span", "showcard__ref", w.ref || ""));
    body.appendChild(meta);
    body.appendChild(el("span", "showcard__title", w.title || ""));
    body.appendChild(el("span", "showcard__blurb", w.blurb || ""));

    var foot = el("span", "showcard__foot");
    foot.appendChild(el("span", "showcard__result", w.headline || ""));
    foot.appendChild(el("span", "showcard__open", "Open " + ARROW));
    body.appendChild(foot);

    card.appendChild(body);
    return card;
  }

  /* ------------------------------------------------------------- thread --- */

  function addTurn(question) {
    els.arrival.hidden = true;
    els.railsuggested.hidden = false;

    var turn = el("div", "turn turn--pending rise");

    var ask = el("div", "turn__ask");
    ask.appendChild(el("span", "turn__num", pad(state.turns.length + 1) + " " + DASH + " ASKED"));
    var h = el("h2", "turn__q", question);
    ask.appendChild(h);
    turn.appendChild(ask);

    var slot = el("div", "turn__slot");
    turn.appendChild(slot);

    els.thread.appendChild(turn);
    turn.scrollIntoView({ block: "start", behavior: "smooth" });
    return { turn: turn, slot: slot };
  }

  /* --------------------------------------------------------- wait state ---
   *
   * The handoff tuned its loading state for a 950ms fake. Real answers take
   * seconds and do not stream, so a static label plus three dots would read
   * as a hang. The label advances through named stages and starts reporting
   * elapsed seconds once the wait is long enough that the visitor needs
   * evidence rather than reassurance. No progress bar: there is no progress
   * to report, and a bar that is not measuring anything is a lie. */

  var STAGES = [
    { at: 0,  label: "Thinking" },
    { at: 3,  label: "Working through it" },
    { at: 8,  label: "Still writing", elapsed: true },
    { at: 16, label: "This one is taking a while", elapsed: true }
  ];

  function startWait(slot) {
    var wait = el("div", "wait");
    wait.setAttribute("role", "status");
    var label = el("span", "wait__label");
    wait.appendChild(label);
    for (var i = 0; i < 3; i++) wait.appendChild(el("span", "wait__dot", DOT));
    slot.appendChild(wait);

    var skeleton = el("div", "skeleton");
    for (var j = 0; j < 3; j++) skeleton.appendChild(el("span"));
    slot.appendChild(skeleton);

    var started = Date.now();

    function tick() {
      var secs = Math.floor((Date.now() - started) / 1000);
      var stage = STAGES[0];
      for (var k = 0; k < STAGES.length; k++) {
        if (secs >= STAGES[k].at) stage = STAGES[k];
      }
      label.textContent = stage.elapsed
        ? stage.label + " " + DASH + " " + secs + "s"
        : stage.label;
    }

    tick();
    var timer = setInterval(tick, 1000);
    return function stop() { clearInterval(timer); };
  }

  /* --------------------------------------------------------- settling ----- */

  function settleAnswer(ctx, reply) {
    ctx.turn.className = "turn rise";
    clear(ctx.slot);

    var body = el("div", "turn__body");
    paragraphs(reply).forEach(function (p) {
      body.appendChild(el("p", null, p));
    });
    ctx.slot.appendChild(body);
  }

  /* Blank-line separated blocks become paragraphs; a single newline inside a
   * block is a soft wrap and is collapsed. The model writes prose, so this is
   * the whole of the formatting contract - no Markdown parsing, because
   * nothing instructs the model to emit Markdown and half-rendering it would
   * be worse than not rendering it. */
  function paragraphs(text) {
    return String(text)
      .replace(/\r\n/g, "\n")
      .split(/\n\s*\n/)
      .map(function (p) { return p.replace(/\s*\n\s*/g, " ").trim(); })
      .filter(function (p) { return p.length > 0; });
  }

  function settleError(ctx, title, message, retryQuestion) {
    ctx.turn.className = "turn rise";
    clear(ctx.slot);

    var callout = el("div", "callout");
    callout.appendChild(el("p", "callout__title", title));
    callout.appendChild(el("p", "callout__body", message));

    if (retryQuestion) {
      var actions = el("div", "callout__actions");
      var again = el("button", "btn btn--outline", "Ask again");
      again.type = "button";
      again.addEventListener("click", function () {
        ctx.turn.parentNode.removeChild(ctx.turn);
        state.turns = state.turns.filter(function (t) { return t.node !== ctx.turn; });
        renderSession();
        submit(retryQuestion);
      });
      actions.appendChild(again);
      callout.appendChild(actions);
    }

    ctx.slot.appendChild(callout);
  }

  /* The daily-cap panel. No count and no "your questions": the gate is a
   * ceiling for the whole site per UTC day. */
  function settleLimit(ctx) {
    ctx.turn.className = "turn rise";
    clear(ctx.slot);

    var panel = el("div", "limit");

    var label = el("p", "metalabel metalabel--signal");
    label.appendChild(el("span", "metalabel__t", "Asking is paused"));
    panel.appendChild(label);

    panel.appendChild(el("h3", "limit__title", "Today's questions are used up."));
    panel.appendChild(el("p", "limit__body",
      "Answering costs real compute, so the site caps how many questions it " +
      "takes in a day rather than quietly degrading the answers. The cap is " +
      "for the whole site rather than for you, and it resets at midnight UTC."));

    ctx.slot.appendChild(panel);
    lock();
  }

  /* ------------------------------------------------------------ plumbing --- */

  function setBusy(on) {
    state.busy = on;
    els.input.disabled = on;
    els.send.disabled = on;
    if (!on && !state.locked) els.input.focus();
  }

  function lock() {
    state.locked = true;
    els.askLive.hidden = true;
    els.askLocked.hidden = false;
  }

  function updatePlaceholder() {
    els.input.placeholder = state.turns.length
      ? "Ask a follow-up\u2026"
      : "What are you trying to solve?";
  }

  /* Map a server error to something a visitor can act on. Deliberately no
   * exception detail - the server sends none, and inventing a cause would be
   * guessing. */
  function messageFor(status, payload) {
    var code = payload && payload.error;

    if (code === "gate_unavailable") {
      return {
        title: "Asking is not available right now.",
        body: "This is a configuration problem on our side, not something you did.",
        retry: true
      };
    }
    if (code === "question_too_long") {
      return { title: "That question is over the length limit.", body: "Try trimming it.", retry: false };
    }
    if (code === "history_too_long") {
      return {
        title: "This conversation has reached its length limit.",
        body: "Use New question to start a fresh one. Nothing you have read goes away.",
        retry: false
      };
    }
    if (status === 502) {
      return { title: "The answer didn't come back.", body: "Nothing was wrong with your question. Worth trying again.", retry: true };
    }
    if (status === 0) {
      return { title: "Could not reach the assistant.", body: "Check your connection and try again.", retry: true };
    }
    return { title: "Something went wrong handling that question.", body: "Worth trying again.", retry: true };
  }

  function showUsage(usage) {
    if (!usage || typeof usage.used !== "number" || !usage.limit) return;
    var left = usage.limit - usage.used;

    if (left <= 0) { lock(); return; }
    if (left > WARN_AT) {
      els.hint.className = "askbar__hint";
      els.hint.textContent = HINT_DEFAULT;
      return;
    }

    els.hint.className = "askbar__hint askbar__hint--warn";
    els.hint.textContent = left + " question" + (left === 1 ? "" : "s") +
      " left on the site today";
  }

  /* -------------------------------------------------------------- submit --- */

  function submit(question) {
    if (state.busy || state.locked) return;

    question = (question || "").trim();
    if (!question) return;
    if (question.length > MAX_CHARS) question = question.slice(0, MAX_CHARS);

    els.input.value = "";
    state.pending = question;

    var ctx = addTurn(question);
    var stopWait = startWait(ctx.slot);
    renderSession();
    setBusy(true);

    /* Trim oldest exchanges first, leaving room for the question being asked.
     * The server would refuse an over-long history; shaping it correctly here
     * means it never has to. */
    var sending = state.history.slice(-(MAX_HISTORY - 1)).concat([
      { role: "user", content: question }
    ]);

    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: sending })
    }).then(function (res) {
      return res.json().then(function (payload) {
        return { status: res.status, ok: res.ok, payload: payload };
      }).catch(function () {
        return { status: res.status, ok: false, payload: null };
      });
    }).then(function (r) {
      stopWait();

      if (r.ok && r.payload && typeof r.payload.reply === "string") {
        settleAnswer(ctx, r.payload.reply);
        /* Commit to history only on success, mirroring Session.send: a failed
         * turn must not leave a question in the record that was never
         * answered. */
        state.history = sending.concat([{ role: "assistant", content: r.payload.reply }]);
        state.turns.push({ q: question, node: ctx.turn });
        showUsage(r.payload.usage);
      } else if (r.status === 429) {
        settleLimit(ctx);
        state.turns.push({ q: question, node: ctx.turn });
      } else {
        var m = messageFor(r.status, r.payload);
        settleError(ctx, m.title, m.body, m.retry ? question : null);
        state.turns.push({ q: question, node: ctx.turn });
        /* Preserve the question either way. On a retryable failure it backs
         * the Ask again button; on a length failure it is what needs editing. */
        els.input.value = question;
      }
    }).catch(function () {
      stopWait();
      var m = messageFor(0, null);
      settleError(ctx, m.title, m.body, question);
      state.turns.push({ q: question, node: ctx.turn });
    }).then(function () {
      state.pending = null;
      renderSession();
      updatePlaceholder();
      setBusy(false);
    });
  }

  /* --------------------------------------------------------------- reset --- */

  function reset(e) {
    if (e) e.preventDefault();
    if (state.busy) return;

    state.turns = [];
    state.history = [];
    state.pending = null;
    state.showcase = FEATURED.slice();

    clear(els.thread);
    els.arrival.hidden = false;
    els.railsuggested.hidden = true;
    els.input.value = "";
    els.hint.className = "askbar__hint";
    els.hint.textContent = HINT_DEFAULT;

    renderSession();
    renderShowcase();
    updatePlaceholder();
    if (!state.locked) els.input.focus();
    els.arrival.scrollIntoView({ block: "start" });
  }

  /* ----------------------------------------------------------- wiring ----- */

  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    submit(els.input.value);
  });
  els.reset.addEventListener("click", reset);
  els.newq.addEventListener("click", reset);

  renderSuggested();
  renderSession();
  renderShowcase();
  updatePlaceholder();
  els.input.focus();
})();
