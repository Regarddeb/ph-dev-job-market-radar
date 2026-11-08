"""Trim old data so 5 years of history fit Neon's 1 GB free tier (docs/SPEC.md §7).

    uv run --project scraper python -m scraper.retention --dry-run
    uv run --project scraper python -m scraper.retention

- postings.description: NULL once the posting has been unseen for 90 days.
- raw_postings: rows fetched more than 90 days ago are deleted.
- crawl_runs: deleted after 1 year.
- postings (posting_skills cascade): deleted when last seen more than 5 years ago.
- daily_skill_stats: deleted after 5 years.

- A description is trimmed by last_seen_at, so a posting that is still listed keeps it.
  Dedupe's fuzzy pass only looks back 60 days, so it never needs a trimmed description.
- Deleting raw rows sets postings.raw_posting_id to NULL (FK ON DELETE SET NULL); reparse can
  then no longer rebuild those postings, which is the accepted trade-off.
- Runs daily after aggregate. Idempotent; writes rows only (no DDL; autovacuum reclaims the
  space). One transaction for the whole run.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

from scraper.db import connect
from scraper.pipeline import ROOT


@dataclass(frozen=True)
class Rule:
    name: str
    sql: str


RULES: tuple[Rule, ...] = (
    Rule(
        "descriptions trimmed (unseen 90 days)",
        "UPDATE postings SET description = NULL"
        " WHERE description IS NOT NULL AND last_seen_at < now() - interval '90 days'",
    ),
    Rule(
        "raw_postings deleted (fetched > 90 days ago)",
        "DELETE FROM raw_postings WHERE fetched_at < now() - interval '90 days'",
    ),
    Rule(
        "crawl_runs deleted (> 1 year)",
        "DELETE FROM crawl_runs WHERE started_at < now() - interval '1 year'",
    ),
    Rule(
        "postings deleted (last seen > 5 years ago)",
        "DELETE FROM postings WHERE last_seen_at < now() - interval '5 years'",
    ),
    Rule(
        "daily_skill_stats deleted (> 5 years)",
        "DELETE FROM daily_skill_stats WHERE date < (now() - interval '5 years')::date",
    ),
)

SQL_DB_SIZE = "SELECT pg_size_pretty(pg_database_size(current_database()))"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply the data retention policy.")
    parser.add_argument("--dry-run", action="store_true", help="report counts; roll back")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
        return 2

    with connect(dsn) as conn:
        counts = [(rule.name, conn.execute(rule.sql).rowcount) for rule in RULES]
        size = conn.execute(SQL_DB_SIZE).fetchone()[0]
        print(("DRY RUN: rolled back\n" if args.dry_run else "") + "-" * 52)
        for name, n in counts:
            print(f"{name:<46} {n}")
        print(f"{'database size':<46} {size}")
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
