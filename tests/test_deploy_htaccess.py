"""Static guards on ``deploy/htaccess``.

This file exists because of a defect a prior review caught: ``deploy/README.md``
claimed the prepared ``deploy/htaccess`` batch addressed the missing
``Strict-Transport-Security`` header finding, while the file itself carried no
such directive. Reading the diff would not have caught it -- both files looked
finished on their own. These checks pin the header directive to the file that
is meant to ship it, so a future edit to either side fails here rather than
reintroducing the same doc/implementation gap.

Entirely static: this never contacts the server or requires ``mod_headers`` to
be installed anywhere. It only reads the committed file.
"""

from __future__ import annotations

import re
from pathlib import Path

HTACCESS = Path(__file__).resolve().parents[1] / "deploy" / "htaccess"


def _read() -> str:
    return HTACCESS.read_text(encoding="utf-8")


def test_htaccess_sets_an_hsts_header() -> None:
    """The claim in deploy/README.md must be true of the file, not aspirational."""
    text = _read()
    assert re.search(
        r'Header\s+always\s+set\s+Strict-Transport-Security\s+"max-age=\d+"',
        text,
    ), "deploy/htaccess must set a Strict-Transport-Security header via mod_headers"


def test_hsts_header_is_scoped_to_https_responses() -> None:
    """A header sent on a plaintext response is not a spec violation but is
    pointless: HSTS is meaningful only once Apache confirms the connection was
    actually TLS. ``env=HTTPS`` is the standard Apache way to make that
    conditional; its absence would mean the directive fires unconditionally.
    """
    text = _read()
    match = re.search(
        r'Header\s+always\s+set\s+Strict-Transport-Security\s+"[^"]*"([^\n]*)', text
    )
    assert match is not None
    assert "env=HTTPS" in match.group(1)


def test_hsts_directive_is_wrapped_in_mod_headers_guard() -> None:
    """Shared hosting is not guaranteed to load every Apache module.

    The rest of this file guards every directive that depends on a module
    (``mod_rewrite``) with an ``<IfModule>`` block so a missing module degrades
    to no rule rather than a server error. The HSTS directive needs the same
    treatment for ``mod_headers``.
    """
    text = _read()
    guarded = re.search(
        r"<IfModule mod_headers\.c>.*?Strict-Transport-Security.*?</IfModule>",
        text,
        re.DOTALL,
    )
    assert guarded is not None, (
        "the Strict-Transport-Security directive must sit inside an "
        "<IfModule mod_headers.c> block, matching the mod_rewrite guards "
        "used elsewhere in this file"
    )


def test_hsts_header_omits_includesubdomains_and_preload() -> None:
    """Neither directive is appropriate yet for this deployment.

    ``includeSubDomains`` would force HTTPS on every subdomain of
    christophermathews.com, including ones never confirmed to serve HTTPS at
    all. ``preload`` joins a browser-maintained list that is effectively
    permanent. Both are a later decision, made once the plain header has run
    in production without incident -- not part of its first rollout.
    """
    text = _read()
    match = re.search(r'Strict-Transport-Security\s+"([^"]*)"', text)
    assert match is not None
    value = match.group(1)
    assert "includeSubDomains" not in value
    assert "preload" not in value
