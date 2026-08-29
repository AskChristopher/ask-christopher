"""A fail-closed daily spend gate for the public prototype.

One question to the public endpoint costs real money, and the dominant term is
the cold cache write on a ~41,800-token prefix. An unbounded endpoint is an
unbounded bill, so the gate is a launch requirement rather than hardening to be
added later.

**Why SQLite and not a JSON counter.** Passenger runs several worker processes
and recycles them without warning. A JSON file read-modify-written by each
worker loses updates whenever two requests overlap, and a gate that silently
undercounts is worse than no gate: it reports a limit that is not being
enforced. In-memory counters have the same problem plus amnesia on recycle.
``sqlite3`` is in the standard library, needs no daemon, and gives a real
transaction across processes - which is the whole requirement. No dependency is
added.

**Fail closed, everywhere.** A missing limit, an unparseable limit, an
unwritable database, a locked database, a corrupt file: every one of these
denies the request. The failure mode being engineered against is not a wrong
count but a gate that stops working while the endpoint keeps answering.

**The day rolls over without a cron.** Rows are keyed by UTC date, so the first
request after midnight writes a new row and the previous one simply stops being
consulted. Nothing has to run on a schedule, which matters on hosting where
nothing reliably does.

**A consumed slot is not refunded.** ``check_and_consume`` charges before the
model is called, and a failed API call still counts. Refunding would need a
second write and a guarantee that the process survives long enough to make it;
neither is available here. Over-counting costs a few unspent requests at the
margin, under-counting costs money, and only one of those is recoverable.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

__all__ = [
    "DEFAULT_DB_NAME",
    "GateDecision",
    "UsageGate",
    "gate_from_environ",
]

#: Kept beside the application, never under a web-served directory.
DEFAULT_DB_NAME = "usage.sqlite3"

#: Rows older than this are pruned opportunistically. One row per day means
#: growth is trivial either way; this exists so the file cannot grow forever.
_RETAIN_DAYS = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_usage (
    day   TEXT PRIMARY KEY,
    count INTEGER NOT NULL
)
"""


@dataclass(frozen=True)
class GateDecision:
    """The outcome of one gate consultation.

    ``reason`` is a stable machine-readable token rather than prose, so the WSGI
    layer can map it to a status code and a message without string matching:

    ``ok``
        Allowed. ``used`` includes the slot just consumed.
    ``limit_reached``
        The configured daily limit is already spent.
    ``unconfigured``
        No usable limit was supplied. Denied - an unconfigured gate is an
        ungated endpoint, which is the thing this module exists to prevent.
    ``storage_error``
        The counter could not be read or written. Denied.
    """

    allowed: bool
    reason: str
    used: int
    limit: int | None

    @property
    def remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "used": self.used,
            "limit": self.limit,
            "remaining": self.remaining,
        }


class UsageGate:
    """A per-UTC-day request ceiling backed by a SQLite counter.

    ``limit`` of ``None`` or anything below 1 renders the gate permanently
    closed. That is deliberate: the constructor accepts a bad configuration
    rather than raising, so a misconfigured deployment returns a clean 503 on
    every request instead of failing to boot in a way that might be papered
    over.
    """

    def __init__(
        self,
        db_path: Path | str,
        limit: int | None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._limit = limit if (limit is not None and limit >= 1) else None
        self._now = now or (lambda: datetime.now(timezone.utc))

    @property
    def limit(self) -> int | None:
        return self._limit

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _day(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None hands transaction control to us, so the
        # read-and-increment below is one BEGIN IMMEDIATE rather than two
        # statements racing between workers.
        conn = sqlite3.connect(self._db_path, timeout=5.0, isolation_level=None)
        conn.execute(_SCHEMA)
        return conn

    def peek(self) -> GateDecision:
        """Report usage without consuming a slot. Safe for a health endpoint."""
        if self._limit is None:
            return GateDecision(False, "unconfigured", 0, None)

        day = self._day()
        try:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT count FROM daily_usage WHERE day = ?", (day,)
                ).fetchone()
            finally:
                conn.close()
        except Exception:
            return GateDecision(False, "storage_error", 0, self._limit)

        used = int(row[0]) if row else 0
        allowed = used < self._limit
        return GateDecision(allowed, "ok" if allowed else "limit_reached", used, self._limit)

    def check_and_consume(self) -> GateDecision:
        """Consume one slot if the day's ceiling has not been reached.

        The read and the increment share one ``BEGIN IMMEDIATE`` transaction,
        which takes a write lock before reading. Two Passenger workers arriving
        together therefore serialise instead of both seeing the same count and
        both writing it back.
        """
        if self._limit is None:
            return GateDecision(False, "unconfigured", 0, None)

        day = self._day()
        try:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT count FROM daily_usage WHERE day = ?", (day,)
                ).fetchone()
                used = int(row[0]) if row else 0

                if used >= self._limit:
                    conn.execute("ROLLBACK")
                    return GateDecision(False, "limit_reached", used, self._limit)

                conn.execute(
                    "INSERT INTO daily_usage (day, count) VALUES (?, 1) "
                    "ON CONFLICT(day) DO UPDATE SET count = count + 1",
                    (day,),
                )
                conn.execute(
                    "DELETE FROM daily_usage WHERE day < date(?, ?)",
                    (day, f"-{_RETAIN_DAYS} days"),
                )
                conn.execute("COMMIT")
            finally:
                conn.close()
        except Exception:
            # Includes sqlite3.OperationalError on lock timeout, and any OS
            # error creating the file. Denying is the point.
            return GateDecision(False, "storage_error", 0, self._limit)

        return GateDecision(True, "ok", used + 1, self._limit)


def gate_from_environ(
    environ: dict[str, str] | None = None,
    *,
    app_root: Path | str | None = None,
) -> UsageGate:
    """Build a gate from environment variables.

    ``ASK_DAILY_LIMIT``
        Required. Integer. Absent or unparseable leaves the gate closed, which
        means a deployment that forgets it serves 503 rather than spending
        without a ceiling.
    ``ASK_USAGE_DB``
        Optional absolute path to the counter. Defaults to ``usage.sqlite3``
        beside ``app_root``. Keep it outside any web-served directory.
    """
    env = os.environ if environ is None else environ

    raw = env.get("ASK_DAILY_LIMIT", "").strip()
    try:
        limit: int | None = int(raw)
    except ValueError:
        limit = None

    configured = env.get("ASK_USAGE_DB", "").strip()
    if configured:
        db_path = Path(configured)
    else:
        base = Path(app_root) if app_root is not None else Path.cwd()
        db_path = base / DEFAULT_DB_NAME

    return UsageGate(db_path, limit)
