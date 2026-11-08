"""Re-run parse + normalize + tag over stored raw_postings (no network).

    uv run --project scraper python -m scraper.reparse --source remoteok --dry-run
    uv run --project scraper python -m scraper.reparse --source remoteok

Use after changing a parser or a normalization rule (Raw first, docs/SPEC.md §1.5).
- Relevant items are upserted with fresh derived fields, PHP salary and skills. Crawl
  history (first/last seen, is_active) is left alone; rows inserted here take the raw
  fetch time as first/last seen, and are active only if that raw item came from the
  source's latest successful crawl.
- Postings whose raw item no longer passes the adapter's is_relevant() are deleted (their
  posting_skills cascade). They're derived rows and can always be rebuilt from raw.
- raw_postings.parsed_at / parse_error are refreshed.
Writes rows only (no DDL), with DATABASE_URL (jobradar_rw). One transaction per source:
either the whole reparse lands or none of it does.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from dotenv import load_dotenv

from scraper.db import connect
from scraper.models import RawItem
from scraper.pipeline import ROOT, PostingWriter, posting_row, process
from scraper.sources import get_adapter

SQL_RAW = """
SELECT id, external_id, url, payload, fetched_at FROM raw_postings
WHERE source_id = %s ORDER BY id
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reparse stored raw_postings for one source.")
    parser.add_argument("--source", required=True, help="adapter slug, e.g. remoteok")
    parser.add_argument("--dry-run", action="store_true", help="report changes; roll back")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    adapter = get_adapter(args.source)

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
        return 2

    with connect(dsn) as conn:
        row = conn.execute("SELECT id FROM sources WHERE slug = %s", (adapter.SLUG,)).fetchone()
        if row is None:
            raise SystemExit(f"source {adapter.SLUG!r} not seeded")
        source_id = row[0]
        writer = PostingWriter(conn, source_id)
        # Raw items fetched by the latest successful crawl are still in the feed; older ones
        # may not be, so postings first created here from them start inactive.
        latest_ok = conn.execute(
            "SELECT max(started_at) FROM crawl_runs WHERE source_id = %s AND status = 'ok'",
            (source_id,),
        ).fetchone()[0]
        existing = dict(
            conn.execute(
                "SELECT external_id, title FROM postings WHERE source_id = %s", (source_id,)
            ).fetchall()
        )

        counts: Counter[str] = Counter()
        irrelevant: list[str] = []
        for raw_id, ext_id, url, payload, fetched_at in conn.execute(
            SQL_RAW, (source_id,)
        ).fetchall():
            outcome = process(adapter, RawItem(external_id=ext_id, url=url, payload=payload))
            if outcome.error is not None:
                counts["parse errors"] += 1
                conn.execute(
                    "UPDATE raw_postings SET parse_error = %s, parsed_at = NULL WHERE id = %s",
                    (outcome.error, raw_id),
                )
                continue
            conn.execute(
                "UPDATE raw_postings SET parsed_at = now(), parse_error = NULL WHERE id = %s",
                (raw_id,),
            )
            posting = outcome.posting
            assert posting is not None
            if not outcome.relevant:
                if ext_id in existing:
                    irrelevant.append(ext_id)
                counts["not relevant"] += 1
                continue
            in_latest = latest_ok is not None and fetched_at >= latest_ok
            _, inserted = writer.write(
                posting, raw_id, seen=False, seen_at=fetched_at, active_if_new=in_latest
            )
            counts["inserted" if inserted else "updated"] += 1
            derived = posting_row(posting)
            counts[f"seniority={derived['seniority']}"] += 1
            counts[f"ph_eligible={derived['ph_eligible']}"] += 1

        if irrelevant:
            conn.execute(
                "DELETE FROM postings WHERE source_id = %s AND external_id = ANY(%s)",
                (source_id, irrelevant),
            )
        counts["deleted (no longer relevant)"] = len(irrelevant)

        php = conn.execute(
            """SELECT count(*) FILTER (WHERE salary_currency IS NOT NULL),
                      count(*) FILTER (WHERE salary_min_php_monthly IS NOT NULL),
                      (SELECT count(*) FROM posting_skills ps JOIN postings p2
                         ON p2.id = ps.posting_id WHERE p2.source_id = %s)
               FROM postings WHERE source_id = %s""",
            (source_id, source_id),
        ).fetchone()

        print(("DRY RUN: rolled back\n" if args.dry_run else "") + "-" * 48)
        for key in sorted(counts):
            print(f"{key:<34} {counts[key]}")
        print(f"{'with salary currency / PHP monthly':<34} {php[0]} / {php[1]}")
        print(f"{'posting_skills rows':<34} {php[2]}")
        for ext_id in irrelevant:
            print(f"  delete {ext_id}: {existing[ext_id]}")

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
