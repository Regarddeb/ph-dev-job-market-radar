"""Mark duplicate postings by setting canonical_posting_id (docs/SPEC.md §6, Dedupe).

    uv run --project scraper python -m scraper.dedupe --dry-run
    uv run --project scraper python -m scraper.dedupe
    uv run --project scraper python -m scraper.dedupe --recompute   # after a rule change

Rules, across all sources, within WINDOW (30 days) of first_seen_at:
- Pass 1 (exact): same fingerprint = sha1(company.normalized_name | title_normalized |
  work_setup).
- Pass 2 (fuzzy): same company AND rapidfuzz token_set_ratio(title) >= 90 AND
  ratio(description) >= 95. token_set_ratio alone treats "senior software engineer" and
  "senior software engineer ii" as identical (one is a subset of the other), so the
  description check is what tells different roles at one company apart. 95, not 90:
  Lemon.io's "Senior Vue Developer" and "Senior DevOps Engineer" share boilerplate and
  score 91 on description (the 2026-11-06 fixture); only their titles (67) differ.
- Postings without a company, or without a description (pass 2), are never matched.
- The canonical is the earliest-seen posting (lowest id on ties); duplicates point straight
  at it, never at another duplicate.

Decisions are sticky: a run only adds duplicates among postings first seen in the last
LOOKBACK (60) days and never clears one, because old descriptions are trimmed after 90 days
and couldn't be re-checked. --recompute first clears canonical_posting_id for postings first
seen in the last WINDOW days, then re-runs. Writes rows only (no DDL), with DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from dotenv import load_dotenv
from rapidfuzz import fuzz
from rapidfuzz.utils import default_process

from scraper.db import connect
from scraper.pipeline import ROOT

WINDOW = timedelta(days=30)
LOOKBACK = timedelta(days=60)
TITLE_THRESHOLD = 90
DESCRIPTION_THRESHOLD = 95


@dataclass(frozen=True)
class Candidate:
    id: int
    company: str | None  # companies.normalized_name
    title: str  # postings.title_normalized
    fingerprint: str | None
    first_seen: datetime
    description: str | None


@dataclass(frozen=True)
class Match:
    canonical_id: int
    reason: str  # "exact" | "fuzzy"
    title_score: float = 100.0
    description_score: float = 100.0


def _fuzzy(a: Candidate, b: Candidate) -> Match | None:
    if not a.description or not b.description:
        return None  # can't confirm without both descriptions: not a duplicate
    title_score = fuzz.token_set_ratio(a.title, b.title, processor=default_process)
    if title_score < TITLE_THRESHOLD:
        return None
    desc_score = fuzz.ratio(a.description, b.description, processor=default_process)
    if desc_score < DESCRIPTION_THRESHOLD:
        return None
    return Match(b.id, "fuzzy", title_score, desc_score)


def find_duplicates(candidates: Iterable[Candidate]) -> dict[int, Match]:
    """{duplicate id: Match(canonical id, ...)} for the given (currently canonical) postings.

    Postings are visited oldest first; each is compared with the canonicals of the same
    company first seen at most WINDOW earlier. Exact matches are checked before fuzzy ones.
    """
    canonicals: dict[str, list[Candidate]] = defaultdict(list)  # oldest first
    result: dict[int, Match] = {}
    for c in sorted(candidates, key=lambda c: (c.first_seen, c.id)):
        if not c.company:
            continue
        earlier = [k for k in canonicals[c.company] if c.first_seen - k.first_seen <= WINDOW]
        match = next(
            (
                Match(k.id, "exact")
                for k in earlier
                if c.fingerprint and c.fingerprint == k.fingerprint
            ),
            None,
        )
        if match is None:
            match = next((m for k in earlier if (m := _fuzzy(c, k))), None)
        if match is None:
            canonicals[c.company].append(c)
        else:
            result[c.id] = match
    return result


# --------------------------------------------------------------------------- database

SQL_CANDIDATES = """
SELECT p.id, c.normalized_name, p.title_normalized, p.fingerprint, p.first_seen_at,
       p.description
FROM postings p LEFT JOIN companies c ON c.id = p.company_id
WHERE p.canonical_posting_id IS NULL AND p.first_seen_at >= now() - %s
"""

SQL_CLEAR_RECENT = """
UPDATE postings SET canonical_posting_id = NULL
WHERE canonical_posting_id IS NOT NULL AND first_seen_at >= now() - %s
"""

SQL_MARK = "UPDATE postings SET canonical_posting_id = %s WHERE id = %s AND id <> %s"

# Safety net: point any duplicate-of-a-duplicate at the root canonical.
SQL_FLATTEN = """
UPDATE postings d SET canonical_posting_id = c.canonical_posting_id
FROM postings c
WHERE d.canonical_posting_id = c.id AND c.canonical_posting_id IS NOT NULL
  AND c.canonical_posting_id <> d.id
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mark duplicate postings.")
    parser.add_argument("--dry-run", action="store_true", help="report; roll back")
    parser.add_argument(
        "--recompute", action="store_true", help=f"clear the last {WINDOW.days} days first"
    )
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
        return 2

    with connect(dsn) as conn:
        cleared = 0
        if args.recompute:
            cleared = conn.execute(SQL_CLEAR_RECENT, (WINDOW,)).rowcount
        rows = conn.execute(SQL_CANDIDATES, (LOOKBACK,)).fetchall()
        found = find_duplicates(Candidate(*row) for row in rows)
        for dup_id, m in found.items():
            conn.execute(SQL_MARK, (m.canonical_id, dup_id, m.canonical_id))
        flattened = conn.execute(SQL_FLATTEN).rowcount

        print(("DRY RUN: rolled back\n" if args.dry_run else "") + "-" * 40)
        print(f"{'candidates (canonical, last 60 days)':<38} {len(rows)}")
        if args.recompute:
            print(f"{'cleared (recompute)':<38} {cleared}")
        for reason in ("exact", "fuzzy"):
            n = sum(m.reason == reason for m in found.values())
            print(f"{'marked duplicate (' + reason + ')':<38} {n}")
        print(f"{'flattened chains':<38} {flattened}")
        titles = {r[0]: r[2] for r in rows}
        for dup_id, m in sorted(found.items()):
            print(
                f"  {dup_id} -> {m.canonical_id} [{m.reason} title={m.title_score:.0f} "
                f"desc={m.description_score:.0f}] {titles.get(dup_id, '')[:60]}"
            )
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
