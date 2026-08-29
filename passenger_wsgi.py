"""Passenger entry point for the cPanel Python application.

cPanel points Passenger at this file and expects a module-level callable named
``application``. Everything here runs once per worker, at import - which is
where the prompt gets assembled, so a request never pays for it.

Kept to plumbing on purpose: path setup, credentials, gate, application. There
is no logic to test here, and anything that needs testing belongs in
``ask_christopher.web`` where the offline suite can reach it.

Environment variables, all set in cPanel's panel rather than in a file:

``ANTHROPIC_API_KEY``
    Required. ``load_env`` only fills names the environment does not already
    define, so a value set here wins over any ``.env`` that reaches the server.
``ASK_DAILY_LIMIT``
    Required. Integer daily request ceiling. Absent leaves the gate closed and
    every request returns 503 - an unconfigured gate must not become an
    ungated endpoint.
``ASK_USAGE_DB``
    Optional. Path to the counter. Defaults beside this file, which cPanel keeps
    outside the document root.
"""

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent

# The package lives under src/ and there is no build backend, so the path is set
# explicitly rather than relying on an install.
sys.path.insert(0, str(APP_ROOT / "src"))

from ask_christopher.env import load_env  # noqa: E402
from ask_christopher.usage import gate_from_environ  # noqa: E402
from ask_christopher.web import build_application  # noqa: E402

# Harmless when the file is absent, which is the expected state on the server.
load_env(APP_ROOT / ".env")


def _client():
    """Construct a client per request.

    Imported lazily so that a missing or broken ``anthropic`` install surfaces
    as a request-time error with a log line, rather than preventing the worker
    from booting at all and taking the health endpoint down with it.
    """
    import anthropic

    return anthropic.Anthropic()


application = build_application(
    _client,
    gate_from_environ(os.environ, app_root=APP_ROOT),
)
