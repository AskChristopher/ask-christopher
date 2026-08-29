/* Ask Christopher - frontend logic. No framework, no build step.
 *
 * Replaces AskShell.jsx's canned ANSWERS lookup with a call to the WSGI
 * wrapper. Everything else the prototype did - thread state, a draft field,
 * suggested questions - is the same shape in ~140 lines of DOM code.
 *
 * The conversation lives here, in the browser. The server is stateless because
 * Passenger recycles workers without warning, so a server-side session would
 * vanish mid-conversation. History is sent with each request and trimmed to the
 * server's ceiling before sending, so the server never has to reject a request
 * this file could have shaped correctly.
 */
(function () {
  "use strict";

  /* Where the WSGI app is mounted. Read from the page rather than hardcoded,
   * because the page and the API are served from different places: the page is
   * a static file (at /ask), the API is the Passenger app (at /api). A
   * relative "ask" would resolve to /ask/ask from a page at /ask/, which is
   * the wrong URL and fails as a 404 rather than loudly.
   *
   * Change the mount point in index.html, not here. */
  var API = (document.body.getAttribute("data-api") || "/api").replace(/\/$/, "") + "/ask";

  // Mirrors MAX_HISTORY_MESSAGES in web.py. Kept in sync by hand; the server
  // is authoritative and will refuse anything longer.
  var MAX_HISTORY = 8;
  var MAX_CHARS = 1000;

  var SUGGESTED = [
    "What does Christopher build?",
    "Show me his AI projects.",
    "Should this problem even be a course?",
    "What could he build for my organization?"
  ];

  var els = {
    form: document.getElementById("form"),
    input: document.getElementById("q"),
    send: document.getElementById("send"),
    thread: document.getElementById("thread"),
    intro: document.getElementById("intro"),
    prompts: document.getElementById("prompts"),
    suggested: document.getElementById("suggested"),
    scroll: document.getElementById("scroll"),
    status: document.getElementById("status"),
    note: document.getElementById("note")
  };

  // [{role, content}, ...] - exactly the shape POST /ask expects.
  var history = [];
  var busy = false;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderPrompts() {
    SUGGESTED.forEach(function (q) {
      var b = el("button", "prompt", q);
      b.type = "button";
      b.addEventListener("click", function () { submit(q); });
      els.prompts.appendChild(b);
    });

    SUGGESTED.forEach(function (q) {
      var a = el("a", null, q);
      a.href = "#";
      a.addEventListener("click", function (e) { e.preventDefault(); submit(q); });
      els.suggested.appendChild(a);
    });
  }

  function addTurn(question) {
    els.intro.hidden = true;
    els.suggested.hidden = false;

    var turn = el("div", "turn");
    turn.appendChild(el("h2", "turn__q", question));
    var answer = el("p", "turn__a turn__a--pending");
    turn.appendChild(answer);
    els.thread.appendChild(turn);
    els.scroll.scrollTop = els.scroll.scrollHeight;
    return answer;
  }

  function settle(node, text, isError) {
    node.className = "turn__a" + (isError ? " turn__a--error" : "");
    node.textContent = text;
    els.scroll.scrollTop = els.scroll.scrollHeight;
  }

  function setBusy(state) {
    busy = state;
    els.input.disabled = state;
    els.send.disabled = state;
    els.status.textContent = state ? "Thinking" : "Ready";
    if (!state) els.input.focus();
  }

  /* Map a server error to something a visitor can act on. Deliberately no
   * exception detail - the server does not send any, and inventing a cause
   * would be guessing. */
  function messageFor(status, payload) {
    var code = payload && payload.error;
    if (code === "daily_limit_reached") {
      return "This prototype has a daily question limit and today's is used up. " +
             "Try again tomorrow, or reach Christopher through ChristopherMathews.com.";
    }
    if (code === "gate_unavailable") {
      return "The assistant is not accepting questions right now. This is a " +
             "configuration problem on our side, not something you did.";
    }
    if (code === "question_too_long") {
      return "That question is longer than the limit. Try trimming it.";
    }
    if (code === "history_too_long") {
      return "This conversation has reached its length limit. Reload to start a new one.";
    }
    if (status === 502) {
      return "The model did not answer that time. Worth trying again.";
    }
    if (status === 0) {
      return "Could not reach the assistant. Check your connection and try again.";
    }
    return "Something went wrong handling that question.";
  }

  function submit(question) {
    if (busy) return;
    question = (question || "").trim();
    if (!question) return;
    if (question.length > MAX_CHARS) {
      question = question.slice(0, MAX_CHARS);
    }

    els.input.value = "";
    var answer = addTurn(question);
    setBusy(true);

    // Trim oldest turns first, keeping whole exchanges, and leave room for the
    // question being asked.
    var sending = history.slice(-(MAX_HISTORY - 1)).concat([
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
      if (r.ok && r.payload && typeof r.payload.reply === "string") {
        settle(answer, r.payload.reply, false);
        // Commit to history only on success, mirroring Session.send: a failed
        // turn must not leave a question in the record that was never answered.
        history = sending.concat([{ role: "assistant", content: r.payload.reply }]);
        showUsage(r.payload.usage);
      } else {
        settle(answer, messageFor(r.status, r.payload), true);
      }
    }).catch(function () {
      settle(answer, messageFor(0, null), true);
    }).then(function () {
      setBusy(false);
    });
  }

  function showUsage(usage) {
    if (!usage || typeof usage.used !== "number" || !usage.limit) return;
    var left = usage.limit - usage.used;
    if (left > 5) return;
    els.note.className = "composer__note composer__note--warn";
    els.note.textContent = left > 0
      ? left + " question" + (left === 1 ? "" : "s") + " left today on this prototype"
      : "Daily limit reached";
  }

  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    submit(els.input.value);
  });

  renderPrompts();
  els.input.focus();
})();
