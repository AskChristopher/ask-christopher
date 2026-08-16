"""Read `.env` into the process environment.

`CLAUDE.md` and `.env.example` both tell you to copy `.env.example` to `.env`,
and until now nothing read the result. Every live script resolved credentials
through the SDK's own `os.environ` lookup, so the documented setup silently did
not work and the key had to be exported by hand - which is how run 3 of the
judge calibration was made. Filed as item 8 of
`docs/evals/judge-calibration-review.md`.

Written against the standard library rather than adding `python-dotenv`. The
dependency list is deliberately two entries long, and a forty-line parser is
not the place to make it three.

Three rules, all of them load-bearing:

**The process environment wins.** A name already present in `os.environ` is
never overwritten, whatever its value. A stale `.env` must not be able to
shadow the key you just exported, and the failure it would cause - requests
billed against the wrong account, or rejected for no visible reason - gives no
symptom pointing back here.

**Values are never printed.** :class:`EnvLoad` carries names, never contents.
The one thing this module handles is a secret.

**Nothing is silent.** A missing file, a name skipped because the environment
already defined it, and a line that could not be parsed are all reported.
Loading is convenience; concealing which key was used is not.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, MutableMapping

from ask_christopher.prompt import repository_root

__all__ = [
    "ENV_FILENAME",
    "EnvLoad",
    "parse_env",
    "load_env",
    "load_env_reporting",
]


#: Read from the repository root, located the same way the corpus is - from the
#: package's own position rather than the working directory, so a script run
#: from anywhere finds the same file.
ENV_FILENAME = ".env"


@dataclass(frozen=True)
class EnvLoad:
    """What one load did. Names only - no value ever appears in this object."""

    path: Path
    exists: bool
    #: Names this call set into the environment.
    loaded: tuple[str, ...] = ()
    #: Names present in the file that the environment already defined, and which
    #: were therefore left alone.
    already_set: tuple[str, ...] = ()
    #: 1-based line numbers that are neither blank, comment, nor ``NAME=value``.
    malformed: tuple[int, ...] = ()

    @property
    def notice(self) -> str | None:
        """One ASCII line for a console, or ``None`` when there is nothing to say.

        Absent file and empty file are both silence: not having a `.env` is a
        supported way to run, so announcing it every time would train the reader
        to skip the line that also carries the warnings.
        """
        parts: list[str] = []
        if self.loaded:
            parts.append(f"loaded {', '.join(self.loaded)}")
        if self.already_set:
            parts.append(
                f"kept the environment's own {', '.join(self.already_set)}"
                " (the file's value was not used)"
            )
        if self.malformed:
            lines = ", ".join(str(n) for n in self.malformed)
            parts.append(f"could not parse line(s) {lines}")
        if not parts:
            return None
        return f"{ENV_FILENAME}: " + "; ".join(parts)


def parse_env(text: str) -> tuple[dict[str, str], tuple[int, ...]]:
    """Parse `.env` text into names and values, plus unparseable line numbers.

    Pure, so the grammar can be tested without a filesystem. Accepts what the
    format is actually written as by hand:

    * blank lines and ``#`` comments, ignored
    * an optional ``export `` prefix, so a file can be `source`d by a shell too
    * surrounding single or double quotes, stripped as a matched pair
    * whitespace around the name and around the value

    A value's own ``#`` is **not** treated as a comment. An API key may contain
    one, and dropping the tail of a secret would produce an authentication
    failure that points nowhere near this file. Comments get their own line.

    Later assignments to the same name win, matching how a shell would read it.
    """
    values: dict[str, str] = {}
    malformed: list[int] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()

        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not name:
            malformed.append(number)
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        values[name] = value

    return values, tuple(malformed)


def load_env(
    path: Path | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> EnvLoad:
    """Read `.env` and set any name the environment does not already define.

    Args:
        path: The file to read. Defaults to `.env` beside the repository root.
        environ: The mapping to populate. Defaults to ``os.environ``; injected
            so tests never mutate the real one.

    Returns:
        A record of what happened. A missing file is not an error - running
        with the key exported and no `.env` at all is a supported setup.
    """
    target = (repository_root() / ENV_FILENAME) if path is None else path
    target_environ = os.environ if environ is None else environ

    if not target.is_file():
        return EnvLoad(path=target, exists=False)

    # Same encoding contract as the corpus: decoded explicitly, never left to
    # the platform default.
    values, malformed = parse_env(target.read_text(encoding="utf-8"))

    loaded: list[str] = []
    already_set: list[str] = []
    for name, value in values.items():
        if name in target_environ:
            already_set.append(name)
            continue
        target_environ[name] = value
        loaded.append(name)

    return EnvLoad(
        path=target,
        exists=True,
        loaded=tuple(loaded),
        already_set=tuple(already_set),
        malformed=malformed,
    )


def load_env_reporting(
    path: Path | None = None,
    *,
    stream: IO[str] | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> EnvLoad:
    """:func:`load_env`, announcing on stderr what it did.

    Called at entry points, before a client is constructed. Output goes to
    stderr rather than stdout so it can never land inside a recorded run's
    output, and it says nothing at all when there is nothing to report.
    """
    result = load_env(path, environ=environ)
    notice = result.notice
    if notice is not None:
        print(notice, file=sys.stderr if stream is None else stream)
    return result
