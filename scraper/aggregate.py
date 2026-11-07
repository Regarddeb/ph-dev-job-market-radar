"""Compute daily_skill_stats from postings + posting_skills (docs/SPEC.md §7).

    uv run --project scraper python -m scraper.aggregate              # last 35 days
    uv run --project scraper python -m scraper.aggregate --full       # all history
    uv run --project scraper python -m scraper.aggregate --dry-run

Per Manila calendar day D and skill (canonical postings only):
- active_postings: first seen on or before D and last seen on or after D (listed that day).
- new_postings: first seen on D.
- median_salary_php: median of the monthly PHP midpoint (min + max) / 2 over that day's
  active postings that have a PHP salary; NULL if none (never a guess).

Recomputing a range deletes and re-inserts its rows in one transaction, so a run fills any
missed days, picks up dedupe/reparse changes, and is idempotent. The default 35-day range
covers dedupe's 30-day window. Days are Asia/Manila dates: the dashboard's audience is in the
Philippines, and the 17:07 UTC run lands at 01:07 Manila. Writes rows only (no DDL).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

from scraper.pipeline import ROOT

TZ = "Asia/Manila"  # inlined in the SQL below
DEFAULT_DAYS = 35

SQL_RANGE = """
SELECT
    CASE WHEN %(full)s
         THEN min((first_seen_at AT TIME ZONE 'Asia/Manila')::date)
         ELSE (now() AT TIME ZONE 'Asia/Manila')::date - %(days)s END,
    (now() AT TIME ZONE 'Asia/Manila')::date
FROM postings
"""

SQL_DELETE = "DELETE FROM daily_skill_stats WHERE date BETWEEN %(start)s AND %(end)s"

SQL_INSERT = """
WITH days AS (
    SELECT generate_series(%(start)s::date, %(end)s::date, interval '1 day')::date AS d
),
p AS (
    SELECT id,
           (first_seen_at AT TIME ZONE 'Asia/Manila')::date AS fs,
           (last_seen_at  AT TIME ZONE 'Asia/Manila')::date AS ls,
           (salary_min_php_monthly + salary_max_php_monthly) / 2.0 AS mid
    FROM postings
    WHERE canonical_posting_id IS NULL
      AND (last_seen_at  AT TIME ZONE 'Asia/Manila')::date >= %(start)s
      AND (first_seen_at AT TIME ZONE 'Asia/Manila')::date <= %(end)s
)
INSERT INTO daily_skill_stats (date, skill_id, active_postings, new_postings, median_salary_php)
SELECT days.d,
       ps.skill_id,
       count(*),
       count(*) FILTER (WHERE p.fs = days.d),
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY p.mid))::int
FROM days
JOIN p ON p.fs <= days.d AND p.ls >= days.d
JOIN posting_skills ps ON ps.posting_id = p.id
GROUP BY days.d, ps.skill_id
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute daily_skill_stats.")
    parser.add_argument("--full", action="store_true", help="recompute all history")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="days back to recompute")
    parser.add_argument("--dry-run", action="store_true", help="report; roll back")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
        return 2

    import psycopg

    with psycopg.connect(dsn, autocommit=False) as conn:
        start, end = conn.execute(SQL_RANGE, {"full": args.full, "days": args.days}).fetchone()
        if start is None:  # --full on an empty table
            print("no postings; nothing to aggregate")
            return 0
        start = min(start, end)
        params: dict[str, date] = {"start": start, "end": end}
        deleted = conn.execute(SQL_DELETE, params).rowcount
        inserted = conn.execute(SQL_INSERT, params).rowcount
        days = (end - start + timedelta(days=1)).days
        print(("DRY RUN: rolled back\n" if args.dry_run else "") + "-" * 40)
        print(f"{'range (Manila days)':<24} {start} .. {end} ({days} days)")
        print(f"{'rows deleted':<24} {deleted}")
        print(f"{'rows inserted':<24} {inserted}")
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
