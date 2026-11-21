/* Ask Christopher - frontend logic, v3. No framework, no build step.
 *
 * v3 follows the first live production conversation. Three things came out of
 * it, and this file is the whole of the response to all three:
 *
 * 1. The model emits lightweight Markdown - bold at least - and v2 rendered the
 *    characters literally. renderRich() below is a small tokenizer for exactly
 *    the subset prompts/persona.md permits: paragraphs, bold, italics,
 *    unordered and ordered lists, and safe links.
 *
 * 2. An empty showcase rail made a working site look unfinished. WORKS now
 *    holds records substantiated by knowledge/projects.md or by a published
 *    case study under /portfolio/ (added 2026-11), and the
 *    rail promotes them by deterministic string matching against the question
 *    and the answer. No API change, no structured model output.
 *
 * 3. A submission could produce two identical turns. Six changes, each marked
 *    FIX n below, make one submission produce exactly one turn structurally
 *    rather than by timing luck.
 *
 * The backend contract is untouched: POST /api/ask takes {messages} and returns
 * {reply, usage}. prompts/, knowledge/ and the validated Phase 1 prefix are
 * unaffected.
 *
 * SECURITY INVARIANT: this file never assigns innerHTML, outerHTML or
 * insertAdjacentHTML, and never calls eval or document.write. Every node is
 * built with createElement/createTextNode. That is what makes "never render
 * arbitrary model HTML" structural rather than filtered - if the model emits
 * <script>, it renders as visible text, because textContent is the only path
 * text ever takes. tests/test_web_frontend.py enforces this.
 *
 * Pure ASCII source. Typographic characters use \u escapes.
 */
(function () {
  "use strict";

  /* Where the WSGI app is mounted. Read from the page rather than hardcoded,
   * because the page is a static file at the document root and the API is a
   * separate Passenger mount. Change it in index.html, not here. */
  var API = (document.body.getAttribute("data-api") || "/api").replace(/\/$/, "") + "/ask";

  /* Mirrors MAX_HISTORY_MESSAGES and MAX_QUESTION_CHARS in web.py. The server
   * is authoritative and refuses anything longer; tests/test_web_frontend.py
   * asserts these two numbers still equal the server's, so the "kept in sync by
   * hand" note v2 carried is now an enforced invariant rather than a hope. */
  var MAX_HISTORY = 8;
  var MAX_CHARS = 1000;

  /* Show the remaining-questions warning only when it is nearly out. The count
   * is site-wide per UTC day, so the copy says so - it is not a per-visitor
   * allowance and must not read like one. */
  var WARN_AT = 3;

  var DASH = "\u2014";   /* em dash */
  var ARROW = "\u2192";  /* rightwards arrow */
  var DOT = "\u25cf";    /* black circle, the pulsing wait dot */

  /* The handoff's suggested questions are real brand voice and ship as-is, but
   * its kind labels quote placeholder counts ("3 case studies"). These labels
   * name the kind of question instead, which needs no data to be true. Every
   * one is answerable from the committed corpus. */
  var SUGGESTED = [
    { q: "What does Christopher build?", kind: "The work" },
    { q: "What AI systems has he actually built?", kind: "Projects" },
    { q: "Should this problem even be a course?", kind: "The method" },
    { q: "How does he decide what to build?", kind: "The thinking" },
    { q: "What could he build for my organization?", kind: "Services" }
  ];

  /* ------------------------------------------------------------- works ---
   *
   * Two records, and only two. Both are Status: Active with Evidence: Public
   * repository in knowledge/projects.md, which also records that the other five
   * repositories contain nothing but a copy of the profile README - so these
   * are the only two pieces a visitor can independently verify today.
   *
   * No metrics, no screenshots, no case studies, no clients. `ref` is the
   * evidence label rather than a date, because projects.md gives "as of July
   * 2026, Milestone 1" for one and an undated "90-day challenge" for the other,
   * and a date on a card would be inference.
   *
   * `match` is deliberately narrow. Bare "sprint" is excluded because it would
   * fire on "a sprint of work"; "this site" is excluded because it would fire on
   * almost any answer and make the promotion meaningless.
   *
   * `n` is unused while the cards carry no media. It is kept because
   * CONTENT-MODEL.md defines it and the numeral returns with the imagery. */
  var WORKS = {
    "vacation-rescue": {
      n: "01",
      cat: "Learning",
      ref: "Case study",
      title: "Vacation Rescue",
      blurb: "A facilitated multiplayer game for a remote team event, built in " +
             "Articulate Storyline so the only way to play was to talk. About 25 " +
             "players, four teams, 30 minutes.",
      headline: "Deployed " + DASH + " played live",
      href: "https://christophermathews.com/portfolio/vacation-rescue/",
      open: "Read the case study",
      match: ["vacation rescue"]
    },
    "beauty-in-the-details": {
      n: "02",
      cat: "Media",
      ref: "Case study",
      title: "Beauty in the Details",
      blurb: "A 90-second public-awareness explainer about coloboma, built in " +
             "Remotion in the style of an original T-shirt design.",
      headline: "Published",
      href: "https://christophermathews.com/portfolio/beauty-in-the-details/",
      open: "Watch and read",
      match: ["beauty in the details", "coloboma"]
    },
    "ask-christopher": {
      n: "03",
      cat: "AI",
      ref: "Public repo",
      title: "Ask Christopher",
      blurb: "The AI-powered front door to this site " + DASH + " a conversational " +
             "portfolio grounded in Christopher's own work, experience, projects, " +
             "and thinking.",
      headline: "Live " + DASH + " you are using it",
      href: "https://christophermathews.com/portfolio/ask-christopher/",
      open: "Read the case study",
      match: ["ask christopher", "askchristopher"]
    },
    "ai-systems-builder-sprint": {
      n: "04",
      cat: "AI",
      ref: "Public repo",
      title: "AI Systems Builder Sprint",
      blurb: "A public learning laboratory for applied AI " + DASH + " working " +
             "implementations of RAG, agents, MCP, tool calling, embeddings, " +
             "evaluation, guardrails, and more.",
      headline: "In build",
      href: "https://github.com/AskChristopher/ai-systems-builder-sprint",
      match: ["ai systems builder", "builder sprint", "learning laboratory"]
    }
  };

  /* What the rail holds before anything is asked. Never added to and never
   * removed from - matching reorders and highlights, nothing more. */
  var FEATURED = ["vacation-rescue", "beauty-in-the-details", "ask-christopher",
                  "ai-systems-builder-sprint"];

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
    turns: [],            // [{q, node}] answered turns only - never failures
    history: [],          // [{role, content}] exactly what POST /ask expects
    pending: null,        // question in flight
    busy: false,
    locked: false,        // the site's daily cap is reached
    requestId: 0,         // FIX 5: monotonic; a stale reply is discarded
    stopWait: null,       // teardown for the active wait ticker
    failedNode: null,     // FIX 2/3: the one transient error node, if any
    showcase: FEATURED.slice(),
    highlighted: [],      // ids matched by the last answer
    matchedInAnswer: false
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

  /* ==================================================== markdown subset ===
   *
   * The subset is not a guess. prompts/persona.md -> Formatting permits
   * structure only for comparisons, checklists, step-by-step instructions,
   * summaries and genuinely long explanations, and -> Conversational defaults
   * requires plain prose with no headers or bullets on simple questions. So
   * bold, italics and lists are expected output; headings are discouraged but
   * possible on a long answer.
   *
   * Not in the subset, and rendered as literal text: code spans and fences,
   * blockquotes, tables, images, and backslash escapes. Those are limits by
   * decision, revisitable if the model actually produces them.
   *
   * Parsing is line-based rather than blank-line-based on purpose: the model
   * routinely writes a lead-in sentence immediately above a list with no blank
   * line between, and a blank-line-only split would fold the bullets into the
   * paragraph. */

  var RE_HEADING = /^\s*#{1,6}\s+(.*)$/;
  var RE_BULLET = /^\s*[-*+]\s+(.*)$/;
  /* One or two digits only. "2026. That year..." is prose, not a list item. */
  var RE_ORDERED = /^\s*\d{1,2}[.)]\s+(.*)$/;

  /* The URL part tolerates one level of balanced parentheses. Without it a
   * link whose target contains them - a Wikipedia article, most obviously -
   * ends at the first ")" and leaves the second one stranded as visible text. */
  var RE_LINK = /\[([^\]\n]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)/;
  var RE_STRONG = /\*\*([^*]+)\*\*|__([^_]+)__/;
  var RE_EM = /\*([^*\n]+)\*|_([^_\n]+)_/;

  function renderRich(text) {
    var frag = document.createDocumentFragment();
    var lines = String(text).replace(/\r\n/g, "\n").split("\n");
    var para = [];
    var items = [];
    var listTag = null;

    function flushPara() {
      if (!para.length) return;
      var p = document.createElement("p");
      inline(para.join(" ").replace(/\s+/g, " ").trim(), p);
      frag.appendChild(p);
      para = [];
    }

    function flushList() {
      if (!items.length) { listTag = null; return; }
      var list = document.createElement(listTag);
      items.forEach(function (t) {
        var li = document.createElement("li");
        inline(t, li);
        list.appendChild(li);
      });
      frag.appendChild(list);
      items = [];
      listTag = null;
    }

    function flush() { flushPara(); flushList(); }

    lines.forEach(function (raw) {
      var line = raw.replace(/\s+$/, "");
      if (!line.trim()) { flush(); return; }

      var m = RE_HEADING.exec(line);
      if (m) {
        /* A heading becomes a plain paragraph. Never show raw syntax to a
         * visitor, and never invent a hierarchy the design did not approve. */
        flush();
        para.push(m[1]);
        flushPara();
        return;
      }

      m = RE_BULLET.exec(line);
      if (m) {
        flushPara();
        if (listTag && listTag !== "ul") flushList();
        listTag = "ul";
        items.push(m[1]);
        return;
      }

      m = RE_ORDERED.exec(line);
      if (m) {
        flushPara();
        if (listTag && listTag !== "ol") flushList();
        listTag = "ol";
        items.push(m[1]);
        return;
      }

      flushList();
      para.push(line);
    });

    flush();
    return frag;
  }

  /* Inline pass. Finds the earliest of link / strong / em, emits the text
   * before it as a text node, emits the element, and continues on the
   * remainder. Link is tested first and strong before em, so on a tie at the
   * same index the longer marker wins and "**bold**" is not read as italics. */
  function inline(text, parent) {
    var order = [["link", RE_LINK], ["strong", RE_STRONG], ["em", RE_EM]];

    while (text.length) {
      var best = null;
      for (var i = 0; i < order.length; i++) {
        var m = order[i][1].exec(text);
        if (m && (best === null || m.index < best.m.index)) {
          best = { kind: order[i][0], m: m };
        }
      }

      if (best === null) {
        parent.appendChild(document.createTextNode(text));
        return;
      }

      if (best.m.index > 0) {
        parent.appendChild(document.createTextNode(text.slice(0, best.m.index)));
      }

      if (best.kind === "link") {
        parent.appendChild(anchor(best.m[1], best.m[2]));
      } else {
        var node = document.createElement(best.kind === "strong" ? "strong" : "em");
        /* Recurse so bold inside italics, and vice versa, both work. */
        inline(best.m[1] !== undefined ? best.m[1] : best.m[2], node);
        parent.appendChild(node);
      }

      text = text.slice(best.m.index + best.m[0].length);
    }
  }

  /* Only absolute http(s). Everything else - javascript:, data:, relative
   * paths, protocol-relative - is refused rather than guessed at. mailto: is
   * excluded deliberately: services.md keeps Christopher's address out of the
   * corpus, and auto-linking mail would reopen that decision by accident. */
  function safeUrl(raw) {
    var s = String(raw).trim();
    if (!/^https?:\/\//i.test(s)) return null;
    if (/[\s<>"'`\\]/.test(s)) return null;
    return s;
  }

  function anchor(label, href) {
    var url = safeUrl(href);
    if (!url) {
      /* Refused. Show what the visitor was meant to read; emit no link. */
      return document.createTextNode(label);
    }
    var a = document.createElement("a");
    a.setAttribute("href", url);
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
    a.appendChild(document.createTextNode(label));
    return a;
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

  /* Resolve through state.turns rather than through thread child index. A
   * transient failure node can sit in the thread without being a turn, so the
   * two are no longer the same list. */
  function goToTurn(i) {
    var entry = state.turns[i];
    if (entry && entry.node) entry.node.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  /* ---------------------------------------------------------- showcase ---
   *
   * Reorders and highlights. It never adds a record, never removes one, and
   * never claims the answer cited anything - the rail is a showcase, not a
   * citation panel, and the backend supplies no per-answer provenance. */

  function matchWorks(question, reply) {
    var q = String(question || "").toLowerCase();
    var a = String(reply || "").toLowerCase();
    var inAnswer = [];
    var inQuestion = [];

    Object.keys(WORKS).forEach(function (id) {
      var keys = WORKS[id].match;
      if (keys.some(function (k) { return a.indexOf(k) >= 0; })) {
        inAnswer.push(id);
        return;
      }
      if (keys.some(function (k) { return q.indexOf(k) >= 0; })) {
        inQuestion.push(id);
      }
    });

    return { inAnswer: inAnswer, inQuestion: inQuestion };
  }

  function promoteShowcase(question, reply) {
    var m = matchWorks(question, reply);
    state.highlighted = m.inAnswer.concat(m.inQuestion);
    /* Only the answer earns the stronger sub-line. If the match came from the
     * question alone, "Mentioned in that answer" would be false. */
    state.matchedInAnswer = m.inAnswer.length > 0;
    renderShowcase();
  }

  function renderShowcase() {
    clear(els.showcaseCards);

    var ids = state.showcase.filter(function (id) { return WORKS[id]; });
    var hot = ids.filter(function (id) { return state.highlighted.indexOf(id) >= 0; });
    var rest = ids.filter(function (id) { return state.highlighted.indexOf(id) < 0; });
    var ordered = hot.concat(rest);

    ordered.forEach(function (id) {
      els.showcaseCards.appendChild(showcard(WORKS[id], hot.indexOf(id) >= 0));
    });

    var n = ordered.length;
    els.showcaseCount.textContent = n ? n + (n === 1 ? " piece" : " pieces") : "";
    els.showcaseIdle.hidden = n > 0;
    els.showcaseSub.textContent = n
      ? (state.matchedInAnswer ? "Mentioned in that answer." : "Featured work.")
      : "Nothing in here yet.";
  }

  /* An anchor rather than a button: the destination is a real repository, so
   * the visitor gets middle-click, open-in-new-tab and a status-bar preview.
   * No media area - there is no imagery for either piece, and two grey drop
   * targets would trade one unfinished signal for another. The media frame and
   * the project numeral return as a data change when screenshots exist. */
  function showcard(w, isHot) {
    var card = el("a", "showcard" + (isHot ? " showcard--live" : ""));
    card.setAttribute("href", w.href);
    card.setAttribute("target", "_blank");
    card.setAttribute("rel", "noopener noreferrer");

    var body = el("span", "showcard__body");

    var meta = el("span", "showcard__meta");
    meta.appendChild(el("span", "showcard__cat", w.cat));
    meta.appendChild(el("span", "showcard__ref", w.ref));
    body.appendChild(meta);

    body.appendChild(el("span", "showcard__title", w.title));
    body.appendChild(el("span", "showcard__blurb", w.blurb));

    var foot = el("span", "showcard__foot");
    foot.appendChild(el("span", "showcard__result", w.headline));
    foot.appendChild(el("span", "showcard__open", (w.open || "View on GitHub") + " " + ARROW));
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
    ask.appendChild(el("h2", "turn__q", question));
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
   * seconds and do not stream, so a static label plus three dots would read as
   * a hang. The label advances through named stages and starts reporting
   * elapsed seconds once the wait is long enough that the visitor needs
   * evidence rather than reassurance. No progress bar: there is no progress to
   * report, and a bar that measures nothing is a lie. */

  var STAGES = [
    { at: 0, label: "Thinking" },
    { at: 3, label: "Working through it" },
    { at: 8, label: "Still writing", elapsed: true },
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

  /* Tear the ticker down through state, not through a closure a handler might
   * skip. Without this a superseded request leaves a 1s interval running for
   * the life of the page. */
  function stopActiveWait() {
    if (!state.stopWait) return;
    state.stopWait();
    state.stopWait = null;
  }

  /* --------------------------------------------------------- settling ----- */

  function settleAnswer(ctx, reply) {
    ctx.turn.className = "turn rise";
    clear(ctx.slot);
    var body = el("div", "turn__body");
    body.appendChild(renderRich(reply));
    ctx.slot.appendChild(body);
  }

  function settleError(ctx, title, message, retryQuestion, offerReset) {
    ctx.turn.className = "turn turn--failed rise";
    clear(ctx.slot);

    var callout = el("div", "callout");
    callout.appendChild(el("p", "callout__title", title));
    callout.appendChild(el("p", "callout__body", message));

    if (retryQuestion || offerReset) {
      var actions = el("div", "callout__actions");

      if (retryQuestion) {
        var again = el("button", "btn btn--outline", "Ask again");
        again.type = "button";
        /* No cleanup here. submit() clears the outstanding failed node itself,
         * so this path and a manual re-send behave identically - which is the
         * whole point of FIX 3. */
        again.addEventListener("click", function () { submit(retryQuestion); });
        actions.appendChild(again);
      }

      /* Offered where retrying cannot work, so the recovery the visitor needs
       * is one click away rather than a rail button they have to find. */
      if (offerReset) {
        var fresh = el("button", "btn btn--outline", "New question");
        fresh.type = "button";
        fresh.addEventListener("click", function () { reset(); });
        actions.appendChild(fresh);
      }

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

  /* FIX 2/3: a failed attempt is transient. It renders so the visitor sees what
   * happened, but it is not a turn, and the next question removes it. */
  function clearFailed() {
    if (!state.failedNode) return;
    if (state.failedNode.parentNode) {
      state.failedNode.parentNode.removeChild(state.failedNode);
    }
    state.failedNode = null;
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
        body: "Start a fresh one and nothing you have already read goes away.",
        retry: false,
        reset: true
      };
    }
    /* The conversation carries an entry too long to replay. Distinct from
     * question_too_long on purpose: the visitor's question is fine, the history
     * behind it is the problem, and trimming what they typed cannot help. Only
     * a new conversation clears it, so that is the action offered. */
    if (code === "history_entry_too_long") {
      return {
        title: "This conversation got too long to carry on.",
        body: "Nothing is wrong with your question " + DASH + " an earlier answer in this " +
              "conversation is too long to send back. Start a fresh one and ask it " +
              "again; everything on the page stays where it is.",
        retry: false,
        reset: true
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

    /* FIX 1: claim the lock before any DOM work. v2 called setBusy after
     * addTurn, which was safe only because nothing yielded in between - an
     * invariant held by accident rather than by design. */
    setBusy(true);

    /* FIX 3: a new question supersedes any outstanding failure, however it was
     * triggered - Ask again, Enter on the restored text, or a suggested
     * question. This is the path that produced two identical turns. */
    clearFailed();

    /* FIX 5: one token per submission. Every handler below no-ops unless it is
     * still the current one, so a superseded reply cannot settle into state. */
    var id = ++state.requestId;

    els.input.value = "";
    state.pending = question;

    var ctx = addTurn(question);
    state.stopWait = startWait(ctx.slot);
    renderSession();

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
      if (id !== state.requestId) return null;
      stopActiveWait();

      if (r.ok && r.payload && typeof r.payload.reply === "string") {
        settleAnswer(ctx, r.payload.reply);
        return { kind: "answer", reply: r.payload.reply, usage: r.payload.usage };
      }
      if (r.status === 429) {
        settleLimit(ctx);
        return { kind: "limit" };
      }
      var m = messageFor(r.status, r.payload);
      settleError(ctx, m.title, m.body, m.retry ? question : null, !!m.reset);
      return { kind: "error" };
    }).catch(function () {
      if (id !== state.requestId) return null;
      stopActiveWait();
      var m = messageFor(0, null);
      settleError(ctx, m.title, m.body, question, false);
      return { kind: "error" };
    }).then(function (outcome) {
      if (id !== state.requestId) return;

      /* FIX 4: exactly one commit point. v2 pushed to state.turns in three
       * branches and again in .catch, so a throw inside the success handler
       * committed the same question twice. One push, driven by outcome. */
      if (outcome && outcome.kind === "answer") {
        state.history = sending.concat([{ role: "assistant", content: outcome.reply }]);
        state.turns.push({ q: question, node: ctx.turn });
        promoteShowcase(question, outcome.reply);
        showUsage(outcome.usage);
      } else if (outcome && outcome.kind === "limit") {
        state.turns.push({ q: question, node: ctx.turn });
      } else if (outcome && outcome.kind === "error") {
        /* FIX 2: not a turn. It takes no turn number and no session row, which
         * mirrors Session.send refusing to record an unanswered question. */
        state.failedNode = ctx.turn;
        els.input.value = question;
      }

      state.pending = null;
      renderSession();
      updatePlaceholder();
      setBusy(false);
    });
  }

  /* --------------------------------------------------------------- reset --- */

  function reset(e) {
    if (e) e.preventDefault();

    /* FIX 6: works while a request is in flight. v2 early-returned on busy, so
     * the button was silently dead during the multi-second wait - exactly when
     * someone is most likely to press it. Bumping the token (FIX 5) is what
     * makes this safe: the orphaned reply is discarded when it lands. */
    state.requestId++;
    stopActiveWait();

    state.turns = [];
    state.history = [];
    state.pending = null;
    state.failedNode = null;
    state.highlighted = [];
    state.matchedInAnswer = false;
    state.showcase = FEATURED.slice();

    clear(els.thread);
    els.arrival.hidden = false;
    els.railsuggested.hidden = true;
    els.input.value = "";
    els.hint.className = "askbar__hint";
    els.hint.textContent = HINT_DEFAULT;

    setBusy(false);
    renderSession();
    renderShowcase();
    updatePlaceholder();
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
