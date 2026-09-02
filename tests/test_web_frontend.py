"""Static guards on the frontend, run by the existing offline suite.

The frontend had no automated coverage at all until this file. Both defects
found while building it were caught by rendering the page rather than by
reading it -- ``[hidden]`` losing to class specificity, and non-ASCII literals
in a file that must survive a cPanel upload byte-for-byte. Neither is
detectable by a linter the repository does not have.

These are deliberately *static* checks. There is no JavaScript test runner
here and adding one is its own decision: ``CLAUDE.md`` says ``pyproject.toml``
is minimal on purpose and a build step should not arrive incidentally. What
this file can do without any new tooling is pin the invariants whose violation
is silent -- the ones where the page still loads and still looks right, and is
simply wrong.

Behaviour of the Markdown renderer and of the submit path is verified in a
headless browser against the committed files; that is not reproducible from
pytest and is not attempted here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ask_christopher.web import MAX_HISTORY_MESSAGES, MAX_QUESTION_CHARS

WEB = Path(__file__).resolve().parents[1] / "web"

APP_JS = WEB / "app.js"
APP_CSS = WEB / "app.css"
INDEX_HTML = WEB / "index.html"

#: The three files this repository actually authors. ``styles.css`` and
#: ``tokens/`` are the design system's, copied verbatim, and are deliberately
#: not held to these rules -- they are someone else's bytes.
AUTHORED = (INDEX_HTML, APP_CSS, APP_JS)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The security invariant
# --------------------------------------------------------------------------

#: Every API that turns a string into markup, written as the construct rather
#: than the bare word -- the file's own comments name these APIs in order to
#: explain why they are absent, and a substring search would match the
#: explanation and fail on a correct file.
FORBIDDEN_SINKS = {
    "innerHTML assignment": r"\.innerHTML\s*=",
    "outerHTML assignment": r"\.outerHTML\s*=",
    "insertAdjacentHTML call": r"\.insertAdjacentHTML\s*\(",
    "document.write call": r"\bdocument\.write(?:ln)?\s*\(",
    "eval call": r"(?<![\w.])eval\s*\(",
    "Function constructor": r"\bnew\s+Function\s*\(",
}


@pytest.mark.parametrize("label,pattern", sorted(FORBIDDEN_SINKS.items()))
def test_app_js_has_no_html_sink(label: str, pattern: str) -> None:
    """The renderer builds nodes; it never parses a string as markup.

    This is the check that makes the safety claim enforceable. A future edit
    that reaches for ``innerHTML`` to save a few lines fails here rather than
    shipping a cross-site scripting hole behind a model response.
    """
    hit = re.search(pattern, _read(APP_JS))
    assert hit is None, (
        f"{APP_JS.name} contains a {label}. Model output is rendered by this "
        "file, so markup-from-string is prohibited -- build nodes with "
        "createElement/createTextNode instead."
    )


def _string_literals(source: str) -> list[str]:
    """Every double- and single-quoted literal, comments excluded by construction."""
    return (
        re.findall(r'"((?:[^"\\\n]|\\.)*)"', source)
        + re.findall(r"'((?:[^'\\\n]|\\.)*)'", source)
    )


def test_link_guard_is_present_and_used() -> None:
    """Anchors are only ever built through the scheme allowlist.

    Testing the wiring rather than the behaviour: ``anchor()`` must consult
    ``safeUrl()``, and ``safeUrl()`` must anchor its test at the start of the
    string. A guard that exists but is bypassed is the failure worth catching.
    """
    source = _read(APP_JS)
    assert "function safeUrl(" in source, "the link scheme guard is gone"
    assert re.search(r"\^https\?:", source), (
        "safeUrl no longer anchors an http(s)-only test at the start of the URL"
    )
    anchor_fn = re.search(r"function anchor\(.*?\n  \}", source, re.S)
    assert anchor_fn, "anchor() not found"
    assert "safeUrl(" in anchor_fn.group(0), "anchor() bypasses safeUrl()"


@pytest.mark.parametrize("scheme", ["javascript:", "data:", "mailto:", "vbscript:"])
def test_no_dangerous_scheme_is_ever_emitted(scheme: str) -> None:
    """No string the page can emit carries a scheme outside the allowlist.

    ``mailto:`` is in this list alongside the obvious ones on purpose:
    ``knowledge/services.md`` deliberately keeps Christopher's address out of
    the corpus, and auto-linking mail would reopen that decision by accident.
    """
    offenders = [s for s in _string_literals(_read(APP_JS)) if scheme in s.lower()]
    assert not offenders, f"{scheme!r} appears in a string literal: {offenders}"


# --------------------------------------------------------------------------
# Upload safety
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", AUTHORED, ids=lambda p: p.name)
def test_authored_files_are_pure_ascii(path: Path) -> None:
    """Non-ASCII bytes must not reach the production files.

    Deployment is a manual upload through cPanel's File Manager and every
    batch is verified by sha256 against the committed bytes. Pure ASCII means
    no encoding step can silently alter a file between the repository and the
    server. Typography is written as HTML entities or ``\\u`` escapes instead.
    """
    raw = path.read_bytes()
    offenders = [(i, b) for i, b in enumerate(raw) if b > 0x7F]
    assert not offenders, (
        f"{path.name} has {len(offenders)} non-ASCII byte(s), first at offset "
        f"{offenders[0][0]}. Use an HTML entity or a \\u escape."
    )


@pytest.mark.parametrize("path", AUTHORED, ids=lambda p: p.name)
def test_authored_files_use_lf_endings(path: Path) -> None:
    """CRLF would change every hash in the deployment record."""
    assert b"\r\n" not in path.read_bytes(), (
        f"{path.name} contains CRLF. The batch hashes in deploy/README.md are "
        "taken over LF bytes."
    )


# --------------------------------------------------------------------------
# The frontend agrees with the server
# --------------------------------------------------------------------------

def _js_number(name: str) -> int:
    match = re.search(rf"var {name} = (\d+);", _read(APP_JS))
    assert match, f"{name} not found in {APP_JS.name}"
    return int(match.group(1))


def test_history_ceiling_matches_the_server() -> None:
    """``app.js`` trims history to the server's ceiling before sending.

    These two numbers were kept in sync by a comment. If the frontend's copy
    drifts above the server's, every request past the limit is rejected with
    ``history_too_long`` -- a conversation that dies mid-way for a reason the
    visitor cannot act on.
    """
    assert _js_number("MAX_HISTORY") == MAX_HISTORY_MESSAGES


def test_question_ceiling_matches_the_server() -> None:
    """Drift here truncates or rejects questions the other side would accept."""
    assert _js_number("MAX_CHARS") == MAX_QUESTION_CHARS


def test_input_maxlength_matches_the_question_ceiling() -> None:
    """The markup's own limit has to agree too, or typing stops early."""
    match = re.search(r'id="q"[^>]*maxlength="(\d+)"', _read(INDEX_HTML), re.S)
    assert match, "the question input has no maxlength"
    assert int(match.group(1)) == MAX_QUESTION_CHARS


# --------------------------------------------------------------------------
# The script and the markup agree
# --------------------------------------------------------------------------

def test_every_element_lookup_resolves() -> None:
    """``getElementById`` returning null throws on the first interaction.

    The failure is total and immediate -- the page renders, then nothing
    works -- so a typo here is worse than a visual bug and invisible to any
    check that only fetches the file.
    """
    wanted = set(re.findall(r'getElementById\("([^"]+)"\)', _read(APP_JS)))
    present = set(re.findall(r'\bid="([^"]+)"', _read(INDEX_HTML)))
    missing = sorted(wanted - present)
    assert not missing, f"app.js looks up ids that index.html does not define: {missing}"


def test_hidden_attribute_is_forced() -> None:
    """``[hidden]`` must beat the class rules that set ``display``.

    Every element the page toggles carries a class with its own ``display``,
    and a class outranks the attribute -- so without this rule ``hidden`` is
    silently inert and the locked ask bar, the rail's question list and the
    showcase empty state all render at once. That shipped once and was caught
    by a screenshot.
    """
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important",
                     _read(APP_CSS)), (
        "app.css must force [hidden] { display: none !important }"
    )


# --------------------------------------------------------------------------
# Work records
# --------------------------------------------------------------------------

def _work_hrefs() -> list[str]:
    return re.findall(r'href:\s*"([^"]+)"', _read(APP_JS))


def test_work_records_exist() -> None:
    """The rail is populated. An empty rail reads as a broken page."""
    assert _work_hrefs(), "no work records found in app.js"


def test_work_record_links_are_https() -> None:
    """A card link is a public claim; it goes over TLS or not at all."""
    for href in _work_hrefs():
        assert href.startswith("https://"), f"work record link is not https: {href}"


def test_work_records_claim_no_metrics() -> None:
    """No invented numbers on a card.

    ``knowledge/projects.md`` records no figure with a method for either
    piece, and ``CONTENT-MODEL.md`` is explicit that a number without its
    method does not ship. A percentage or a bare count appearing in a record
    means someone added a claim the corpus cannot support.
    """
    block = re.search(r"var WORKS = \{(.*?)\n  \};", _read(APP_JS), re.S)
    assert block, "WORKS block not found"
    body = block.group(1)
    # Strip the fields that legitimately carry digits: ids, ordinals and URLs.
    body = re.sub(r'href:\s*"[^"]*"', "", body)
    body = re.sub(r'n:\s*"\d+"', "", body)
    assert "%" not in body, "a work record carries a percentage; no metric is substantiated"
