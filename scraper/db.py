"""One way to open a Postgres connection, with timeouts.

Neon connections have twice gone silently dead mid-run (2026-11-07 reparse, 2026-11-08
backfill): with libpq's defaults a statement then waits ~10 minutes before the OS gives up.
These client-side settings make a dead connection fail within about a minute instead, so a
run errors out (and is recorded / can resume) rather than hanging.
"""

from __future__ import annotations

from typing import Any

CONNECT_KWARGS: dict[str, Any] = {
    "connect_timeout": 15,  # seconds; also covers Neon's scale-to-zero wake-up
    "keepalives": 1,
    "keepalives_idle": 30,  # probe an idle connection after 30 s
    "keepalives_interval": 10,
    "keepalives_count": 3,
    "tcp_user_timeout": 60_000,  # ms: unacknowledged sends fail after 60 s (Linux)
}


def connect(dsn: str, *, autocommit: bool = False) -> Any:
    import psycopg  # local import: dry runs never need a database driver connection

    return psycopg.connect(dsn, autocommit=autocommit, **CONNECT_KWARGS)
