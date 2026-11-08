"""Backfill past HN "Who is Hiring?" threads (docs/SPEC.md §9; run by backfill-hn.yml).

    uv run --project scraper python -m scraper.backfill_hn --dry-run           # plan only
    uv run --project scraper python -m scraper.backfill_hn --months 60 --max-requests 15000

- Official HN API only, through the shared client (>= 1 s between requests).
- Threads: the `whoishiring` account's submissions, newest first, back to --months. The
  newest hiring thread is the current one and belongs to the daily crawl; it's skipped.
- Resumable: comments already in raw_postings are skipped (past threads are final), so a run
  stopped by --max-requests or the 6 h job limit continues where it left off.
- History, not "seen now": a backfilled posting gets first_seen_at = the comment's time and
  last_seen_at = the thread's end (the next hiring thread's time), starts inactive, and the
  backfill writes no crawl_runs row. Parsing, relevance and normalization are the daily
  adapter's (scraper/sources/hn_hiring.py) and pipeline's.
- Writes rows only (no DDL), with DATABASE_URL (jobradar_rw). One transaction per comment.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import psycopg
from dotenv import load_dotenv

from scraper.db import connect
from scraper.http import HttpClient
from scraper.models import Page, RawItem
from scraper.pipeline import ROOT, SQL_RAW_UPSERT, PostingWriter, content_hash, process
from scraper.sources import hn_hiring as hn

DAYS_PER_MONTH = 30.44
log = logging.getLogger("scraper.backfill_hn")


@dataclass(frozen=True)
class Thread:
    id: int
    title: str
    posted: datetime
    ends: datetime  # when the next hiring thread replaced it
    kids: list[str] = field(default_factory=list)


def _is_hiring(story: dict) -> bool:
    return story.get("type") == "story" and bool(hn.THREAD_TITLE.match(story.get("title", "")))


def past_threads(stories: Iterable[dict]) -> list[Thread]:
    """Hiring stories (any order) -> past threads, newest first, each ending when the next
    newer one was posted. The newest (current) thread has no end yet and is left out."""
    hiring = sorted((s for s in stories if _is_hiring(s)), key=lambda s: s["time"])
    return [
        Thread(
            id=int(older["id"]),
            title=older["title"],
            posted=datetime.fromtimestamp(older["time"], tz=UTC),
            ends=datetime.fromtimestamp(newer["time"], tz=UTC),
            kids=[str(k) for k in older.get("kids") or []],
        )
        for older, newer in reversed(list(itertools.pairwise(hiring)))
    ]


def discover(client: HttpClient, cutoff: datetime) -> list[dict]:
    """Stories submitted by whoishiring back to `cutoff` (submissions are newest first)."""
    user = client.get(f"{hn.API}/user/whoishiring.json").json() or {}
    stories: list[dict] = []
    for sid in user.get("submitted") or []:
        item = client.get(hn.item_url(sid)).json() or {}
        if item.get("type") != "story" or "time" not in item:
            continue
        if datetime.fromtimestamp(item["time"], tz=UTC) < cutoff:
            break
        stories.append(item)
    return stories


@dataclass
class Report:
    threads: int = 0
    comments_listed: int = 0
    already_stored: int = 0
    fetched: int = 0
    stored: int = 0
    relevant: int = 0
    parse_errors: int = 0
    stopped_early: bool = False


class Store:
    """The backfill's database side. Autocommit, so each comment's transaction commits on
    its own (a crash keeps everything before it). A dropped connection is reopened and the
    item retried once; a second failure stops the run, which can then be resumed."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._open()

    def _open(self) -> None:
        self.conn = connect(self.dsn, autocommit=True)
        row = self.conn.execute("SELECT id FROM sources WHERE slug = %s", (hn.SLUG,)).fetchone()
        if row is None:
            raise SystemExit("source hn_hiring is not seeded; run `pnpm db:seed` in dashboard/")
        self.source_id = row[0]
        self.writer = PostingWriter(self.conn, self.source_id)

    def close(self) -> None:
        self.conn.close()

    def known(self, ids: list[str]) -> set[str]:
        rows = self.conn.execute(
            "SELECT external_id FROM raw_postings WHERE source_id = %s AND external_id = ANY(%s)",
            (self.source_id, ids),
        ).fetchall()
        return {r[0] for r in rows}

    def save(self, raw: RawItem, thread: Thread) -> str:
        """Store one comment. Returns "error", "irrelevant" or "relevant"."""
        try:
            return self._save(raw, thread)
        except psycopg.OperationalError as exc:
            log.warning("database connection lost (%s); reconnecting and retrying once", exc)
            try:
                self.conn.close()
            finally:
                self._open()
            return self._save(raw, thread)

    def _save(self, raw: RawItem, thread: Thread) -> str:
        outcome = process(hn, raw)
        with self.conn.transaction():
            raw_id = self.conn.execute(
                SQL_RAW_UPSERT,
                {
                    "source_id": self.source_id,
                    "crawl_run_id": None,
                    "external_id": raw.external_id,
                    "url": raw.url,
                    "payload": raw.payload,
                    "hash": content_hash(raw.payload),
                },
            ).fetchone()[0]
            if outcome.error is not None:
                self.conn.execute(
                    "UPDATE raw_postings SET parse_error = %s, parsed_at = NULL WHERE id = %s",
                    (outcome.error, raw_id),
                )
                return "error"
            self.conn.execute(
                "UPDATE raw_postings SET parsed_at = now(), parse_error = NULL WHERE id = %s",
                (raw_id,),
            )
            if not outcome.relevant or outcome.posting is None:
                return "irrelevant"
            posted = outcome.posting.posted_at or thread.posted
            self.writer.write(
                outcome.posting,
                raw_id,
                seen=False,
                first_seen=posted,
                last_seen=max(posted, thread.ends),  # a late comment can postdate the next one
                active_if_new=False,
            )
            return "relevant"


def run(
    store: Store, client: HttpClient, threads: list[Thread], max_requests: int, *, dry_run: bool
) -> Report:
    report = Report(threads=len(threads))
    for thread in threads:
        known = store.known(thread.kids)
        report.comments_listed += len(thread.kids)
        report.already_stored += len(known)
        todo = [k for k in thread.kids if k not in known]
        print(f"{thread.title}: {len(thread.kids)} comments, {len(todo)} to fetch", flush=True)
        if dry_run:
            continue
        for kid in todo:
            if client.requests_made >= max_requests:
                report.stopped_early = True
                return report
            resp = client.get(hn.item_url(kid))
            report.fetched += 1
            for raw in hn.split(Page(url=str(resp.url), text=resp.text)):
                status = store.save(raw, thread)  # counted only after it committed
                report.stored += 1
                report.parse_errors += status == "error"
                report.relevant += status == "relevant"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill past HN 'Who is hiring?' threads.")
    parser.add_argument("--months", type=int, default=60, help="how far back (default 60)")
    parser.add_argument(
        "--max-requests", type=int, default=15_000, help="stop after N HTTP requests"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list threads and counts; fetch no comments"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
        return 2

    cutoff = datetime.now(UTC) - timedelta(days=args.months * DAYS_PER_MONTH)
    store = Store(dsn)
    try:
        with HttpClient() as client:
            threads = past_threads(discover(client, cutoff))
            report = run(store, client, threads, args.max_requests, dry_run=args.dry_run)
        print(
            ("DRY RUN: no comments fetched, nothing written\n" if args.dry_run else "") + "-" * 44
        )
        for key, value in vars(report).items():
            print(f"{key:<20} {value}")
        remaining = report.comments_listed - report.already_stored - report.fetched
        print(f"{'remaining (approx.)':<20} {remaining}  (deleted/dead comments are re-checked)")
        print(f"{'HTTP requests':<20} {client.requests_made}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
