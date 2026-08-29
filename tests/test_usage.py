"""Tests for the fail-closed daily spend gate.

The gate's job is not to count accurately in the happy case - that part is
easy. Its job is to deny when it cannot count, because a gate that degrades
into a no-op while the endpoint keeps answering is how an unbounded bill
happens. Most of what follows tests the denial paths.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ask_christopher.usage import (
    DEFAULT_DB_NAME,
    GateDecision,
    UsageGate,
    gate_from_environ,
)


def _clock(*instants: datetime):
    """A clock that walks a fixed script, holding the last value."""
    seq = list(instants)

    def now() -> datetime:
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return now


DAY_ONE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
DAY_TWO = DAY_ONE + timedelta(days=1)


# --------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------


def test_first_request_is_allowed_and_counted(tmp_path: Path) -> None:
    gate = UsageGate(tmp_path / "u.sqlite3", 3, now=_clock(DAY_ONE))

    decision = gate.check_and_consume()

    assert decision.allowed
    assert decision.reason == "ok"
    assert decision.used == 1
    assert decision.remaining == 2


def test_consumption_accumulates_up_to_the_limit(tmp_path: Path) -> None:
    gate = UsageGate(tmp_path / "u.sqlite3", 3, now=_clock(DAY_ONE))

    used = [gate.check_and_consume().used for _ in range(3)]

    assert used == [1, 2, 3]


def test_the_request_after_the_limit_is_denied(tmp_path: Path) -> None:
    gate = UsageGate(tmp_path / "u.sqlite3", 2, now=_clock(DAY_ONE))
    gate.check_and_consume()
    gate.check_and_consume()

    decision = gate.check_and_consume()

    assert not decision.allowed
    assert decision.reason == "limit_reached"
    assert decision.used == 2, "a denied request must not increment the counter"
    assert decision.remaining == 0


def test_a_limit_of_one_allows_exactly_one(tmp_path: Path) -> None:
    """The boundary, asserted directly - off-by-one here is a doubled bill."""
    gate = UsageGate(tmp_path / "u.sqlite3", 1, now=_clock(DAY_ONE))

    assert gate.check_and_consume().allowed
    assert not gate.check_and_consume().allowed


def test_the_counter_survives_a_new_gate_instance(tmp_path: Path) -> None:
    """Passenger recycles workers. The count must outlive the process."""
    db = tmp_path / "u.sqlite3"
    UsageGate(db, 5, now=_clock(DAY_ONE)).check_and_consume()
    UsageGate(db, 5, now=_clock(DAY_ONE)).check_and_consume()

    assert UsageGate(db, 5, now=_clock(DAY_ONE)).peek().used == 2


# --------------------------------------------------------------------------
# Day rollover - no cron required
# --------------------------------------------------------------------------


def test_a_new_utc_day_starts_a_fresh_budget(tmp_path: Path) -> None:
    db = tmp_path / "u.sqlite3"
    day_one = UsageGate(db, 1, now=_clock(DAY_ONE))
    day_one.check_and_consume()
    assert not day_one.check_and_consume().allowed

    day_two = UsageGate(db, 1, now=_clock(DAY_TWO))

    assert day_two.check_and_consume().allowed, "the ceiling must reset at UTC midnight"


def test_yesterdays_count_does_not_affect_today(tmp_path: Path) -> None:
    db = tmp_path / "u.sqlite3"
    yesterday = UsageGate(db, 10, now=_clock(DAY_ONE))
    for _ in range(10):
        yesterday.check_and_consume()

    today = UsageGate(db, 10, now=_clock(DAY_TWO))

    assert today.check_and_consume().used == 1


# --------------------------------------------------------------------------
# Fail closed - the reason this module exists
# --------------------------------------------------------------------------


@pytest.mark.parametrize("limit", [None, 0, -1, -100])
def test_an_unusable_limit_leaves_the_gate_closed(tmp_path: Path, limit) -> None:
    """A missing ceiling denies rather than defaulting to something generous."""
    gate = UsageGate(tmp_path / "u.sqlite3", limit, now=_clock(DAY_ONE))

    decision = gate.check_and_consume()

    assert not decision.allowed
    assert decision.reason == "unconfigured"
    assert gate.limit is None


def test_an_unconfigured_gate_also_denies_on_peek(tmp_path: Path) -> None:
    gate = UsageGate(tmp_path / "u.sqlite3", None, now=_clock(DAY_ONE))

    assert gate.peek().reason == "unconfigured"


def test_an_unwritable_location_denies(tmp_path: Path) -> None:
    """A directory where the database should be. Cannot open, must not allow."""
    blocked = tmp_path / "u.sqlite3"
    blocked.mkdir()
    gate = UsageGate(blocked, 5, now=_clock(DAY_ONE))

    decision = gate.check_and_consume()

    assert not decision.allowed
    assert decision.reason == "storage_error"


def test_a_corrupt_database_denies(tmp_path: Path) -> None:
    db = tmp_path / "u.sqlite3"
    db.write_bytes(b"this is not a sqlite file" * 40)
    gate = UsageGate(db, 5, now=_clock(DAY_ONE))

    decision = gate.check_and_consume()

    assert not decision.allowed
    assert decision.reason == "storage_error"


def test_a_corrupt_database_denies_on_peek_too(tmp_path: Path) -> None:
    db = tmp_path / "u.sqlite3"
    db.write_bytes(b"not sqlite" * 40)

    assert UsageGate(db, 5, now=_clock(DAY_ONE)).peek().reason == "storage_error"


def test_peek_never_consumes(tmp_path: Path) -> None:
    """A health check must not spend the budget it reports on."""
    gate = UsageGate(tmp_path / "u.sqlite3", 2, now=_clock(DAY_ONE))

    for _ in range(10):
        gate.peek()

    assert gate.check_and_consume().used == 1


# --------------------------------------------------------------------------
# Concurrency - the reason this is SQLite and not a JSON file
# --------------------------------------------------------------------------


def test_overlapping_consumption_does_not_lose_updates(tmp_path: Path) -> None:
    """Interleave two gates on one database, as two Passenger workers would.

    A read-modify-write counter loses one of these. The transaction must not.
    """
    db = tmp_path / "u.sqlite3"
    worker_a = UsageGate(db, 10, now=_clock(DAY_ONE))
    worker_b = UsageGate(db, 10, now=_clock(DAY_ONE))

    for _ in range(5):
        worker_a.check_and_consume()
        worker_b.check_and_consume()

    assert worker_a.peek().used == 10


def test_a_second_writer_holding_the_lock_denies_rather_than_overcounts(
    tmp_path: Path,
) -> None:
    """A held write lock must produce a denial, not a silent double-spend."""
    db = tmp_path / "u.sqlite3"
    UsageGate(db, 5, now=_clock(DAY_ONE)).check_and_consume()

    blocker = sqlite3.connect(db, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        gate = UsageGate(db, 5, now=_clock(DAY_ONE))
        # timeout is 5s in the gate; shorten the wait by asserting the outcome
        # rather than the duration.
        decision = gate.check_and_consume()
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

    assert not decision.allowed
    assert decision.reason == "storage_error"


# --------------------------------------------------------------------------
# Retention
# --------------------------------------------------------------------------


def test_old_rows_are_pruned(tmp_path: Path) -> None:
    db = tmp_path / "u.sqlite3"
    UsageGate(db, 5, now=_clock(DAY_ONE)).check_and_consume()

    much_later = UsageGate(db, 5, now=_clock(DAY_ONE + timedelta(days=90)))
    much_later.check_and_consume()

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT day FROM daily_usage ORDER BY day").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1, "the 90-day-old row should have been pruned"


# --------------------------------------------------------------------------
# Environment wiring
# --------------------------------------------------------------------------


def test_environ_supplies_the_limit(tmp_path: Path) -> None:
    gate = gate_from_environ(
        {"ASK_DAILY_LIMIT": "42", "ASK_USAGE_DB": str(tmp_path / "u.sqlite3")}
    )

    assert gate.limit == 42


def test_a_missing_limit_leaves_the_gate_closed(tmp_path: Path) -> None:
    gate = gate_from_environ({}, app_root=tmp_path)

    assert gate.limit is None
    assert not gate.check_and_consume().allowed


@pytest.mark.parametrize("raw", ["", "   ", "lots", "10.5", "1e3", "ten"])
def test_an_unparseable_limit_leaves_the_gate_closed(tmp_path: Path, raw: str) -> None:
    gate = gate_from_environ({"ASK_DAILY_LIMIT": raw}, app_root=tmp_path)

    assert gate.limit is None


def test_the_database_defaults_beside_the_app_root(tmp_path: Path) -> None:
    gate = gate_from_environ({"ASK_DAILY_LIMIT": "5"}, app_root=tmp_path)

    assert gate.db_path == tmp_path / DEFAULT_DB_NAME


def test_decision_serialises_for_a_json_response() -> None:
    decision = GateDecision(True, "ok", 3, 10)

    assert decision.as_dict() == {
        "allowed": True,
        "reason": "ok",
        "used": 3,
        "limit": 10,
        "remaining": 7,
    }
