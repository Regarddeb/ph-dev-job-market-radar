"""fetch -> raw -> parse -> normalize -> (tag, dedupe: steps 5-6) -> load.

    uv run --project scraper python -m scraper.pipeline --source remoteok --dry-run
    uv run --project scraper python -m scraper.pipeline --source remoteok
    uv run --project scraper python -m scraper.pipeline --source remoteok --fixture <path>

--dry-run   fetch + parse + report; writes nothing.
--fixture   read a saved response instead of the network (works with or without --dry-run).

Writes only rows (never DDL) with DATABASE_URL (the jobradar_rw role). Idempotent: raw rows
and postings are upserts on (source_id, external_id); re-runs bump last_seen_at.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from scraper.http import FetchError, HttpClient
from scraper.models import Page, ParsedPosting, RawItem
from scraper.normalize.text import normalize_company, normalize_title
from scraper.sources import get_adapter

log = logging.getLogger("scraper.pipeline")
ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- pure steps


@dataclass
class Outcome:
    raw: RawItem
    posting: ParsedPosting | None = None
    error: str | None = None
    relevant: bool = False


@dataclass
class Stats:
    pages: int = 0
    items: int = 0
    parsed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    relevant: list[ParsedPosting] = field(default_factory=list)
    new_postings: int = 0


def content_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint(company_norm: str, title_norm: str, work_setup: str) -> str:
    return hashlib.sha1(  # noqa: S324 - a dedupe key, not security
        f"{company_norm}|{title_norm}|{work_setup}".encode()
    ).hexdigest()


def process(adapter: ModuleType, raw: RawItem) -> Outcome:
    try:
        posting = adapter.parse(raw)
    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        return Outcome(raw=raw, error=f"{type(exc).__name__}: {exc}"[:2000])
    return Outcome(raw=raw, posting=posting, relevant=adapter.is_relevant(posting))


def posting_row(p: ParsedPosting) -> dict[str, Any]:
    """Columns for `postings`. Derived fields (seniority, PHP salary, ph_eligible) arrive in
    step 5; until then they keep their 'unknown' defaults: never guessed."""
    company_norm = normalize_company(p.company_name) if p.company_name else ""
    title_norm = normalize_title(p.title)
    return {
        "external_id": p.external_id,
        "title": p.title,
        "title_normalized": title_norm,
        "job_type": p.job_type,
        "work_setup": p.work_setup,
        "location_text": p.location_text,
        "salary_raw": p.salary_raw,
        "salary_currency": p.salary_currency,
        "salary_period": p.salary_period,
        "description": p.description,
        "source_url": p.source_url,
        "posted_at": p.posted_at,
        "fingerprint": fingerprint(company_norm, title_norm, p.work_setup)
        if company_norm
        else None,
    }


def coverage(stats: Stats) -> list[tuple[str, str]]:
    rel = stats.relevant
    n = len(rel) or 1

    def pct(k: int) -> str:
        return f"{100 * k / n:.0f}% ({k}/{len(rel)})"

    return [
        ("Fetched (pages / items)", f"{stats.pages} / {stats.items}"),
        ("Parsed OK", str(stats.parsed)),
        ("Parse errors", str(len(stats.errors))),
        ("Relevant (dev roles)", str(len(rel))),
        ("% with salary stated", pct(sum(p.salary_raw is not None for p in rel))),
        ("% salary with known period", pct(sum(p.salary_period is not None for p in rel))),
        ("% with company", pct(sum(p.company_name is not None for p in rel))),
        ("% with location text", pct(sum(p.location_text is not None for p in rel))),
        ("% job_type stated by source", pct(sum(p.job_type != "unspecified" for p in rel))),
        ("Seniority / ph_eligible / skills", "not derived yet (build step 5)"),
    ]


# --------------------------------------------------------------------------- page sources


def pages_from_fixture(adapter: ModuleType, path: Path) -> Iterator[Page]:
    with path.open(encoding="utf-8", newline="") as fh:
        yield Page(url=f"fixture:{path.name}", text=fh.read())


# --------------------------------------------------------------------------- database

SQL_RAW_UPSERT = """
INSERT INTO raw_postings (source_id, crawl_run_id, external_id, url, payload, content_hash)
VALUES (%(source_id)s, %(crawl_run_id)s, %(external_id)s, %(url)s, %(payload)s, %(hash)s)
ON CONFLICT (source_id, external_id) DO UPDATE SET
    crawl_run_id = EXCLUDED.crawl_run_id,
    url          = EXCLUDED.url,
    payload      = EXCLUDED.payload,
    fetched_at   = now(),
    parsed_at    = CASE WHEN raw_postings.content_hash = EXCLUDED.content_hash
                        THEN raw_postings.parsed_at END,
    parse_error  = CASE WHEN raw_postings.content_hash = EXCLUDED.content_hash
                        THEN raw_postings.parse_error END,
    content_hash = EXCLUDED.content_hash
RETURNING id
"""

SQL_COMPANY_UPSERT = """
INSERT INTO companies (name, normalized_name) VALUES (%s, %s)
ON CONFLICT (normalized_name) DO UPDATE SET name = companies.name
RETURNING id
"""

SQL_POSTING_UPSERT = """
INSERT INTO postings (
    raw_posting_id, source_id, external_id, company_id, title, title_normalized,
    job_type, work_setup, location_text, salary_raw, salary_currency, salary_period,
    description, source_url, posted_at, fingerprint)
VALUES (
    %(raw_posting_id)s, %(source_id)s, %(external_id)s, %(company_id)s, %(title)s,
    %(title_normalized)s, %(job_type)s::job_type, %(work_setup)s::work_setup,
    %(location_text)s, %(salary_raw)s, %(salary_currency)s, %(salary_period)s,
    %(description)s, %(source_url)s, %(posted_at)s, %(fingerprint)s)
ON CONFLICT (source_id, external_id) DO UPDATE SET
    raw_posting_id   = EXCLUDED.raw_posting_id,
    company_id       = EXCLUDED.company_id,
    title            = EXCLUDED.title,
    title_normalized = EXCLUDED.title_normalized,
    job_type         = EXCLUDED.job_type,
    work_setup       = EXCLUDED.work_setup,
    location_text    = EXCLUDED.location_text,
    salary_raw       = EXCLUDED.salary_raw,
    salary_currency  = EXCLUDED.salary_currency,
    salary_period    = EXCLUDED.salary_period,
    description      = COALESCE(EXCLUDED.description, postings.description),
    source_url       = EXCLUDED.source_url,
    posted_at        = COALESCE(EXCLUDED.posted_at, postings.posted_at),
    fingerprint      = EXCLUDED.fingerprint,
    last_seen_at     = now(),
    is_active        = true
RETURNING (xmax = 0) AS inserted
"""


class Loader:
    """All writes for one crawl run. One transaction per item, so a bad row can't sink
    the run; the crawl_runs row is committed first so failures are always recorded."""

    def __init__(self, dsn: str, slug: str) -> None:
        import psycopg  # local import: --dry-run never needs a database driver connection

        self.conn = psycopg.connect(dsn, autocommit=False)
        row = self.conn.execute(
            "SELECT id, is_active FROM sources WHERE slug = %s", (slug,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"source {slug!r} not seeded; run `pnpm db:seed` in dashboard/")
        self.source_id, active = row
        if not active:
            raise SystemExit(f"source {slug!r} has is_active=false in the seed; refusing to run")
        self.run_id = self.conn.execute(
            "INSERT INTO crawl_runs (source_id) VALUES (%s) RETURNING id", (self.source_id,)
        ).fetchone()[0]
        self.conn.commit()

    def store(self, outcome: Outcome) -> bool:
        """Persist one item. Returns True if a new posting was inserted."""
        raw = outcome.raw
        with self.conn.transaction():
            raw_id = self.conn.execute(
                SQL_RAW_UPSERT,
                {
                    "source_id": self.source_id,
                    "crawl_run_id": self.run_id,
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
                return False
            self.conn.execute(
                "UPDATE raw_postings SET parsed_at = now(), parse_error = NULL WHERE id = %s",
                (raw_id,),
            )
            if not outcome.relevant or outcome.posting is None:
                return False
            p = outcome.posting
            company_id = None
            if p.company_name and (norm := normalize_company(p.company_name)):
                company_id = self.conn.execute(
                    SQL_COMPANY_UPSERT, (p.company_name, norm)
                ).fetchone()[0]
            row = posting_row(p) | {
                "raw_posting_id": raw_id,
                "source_id": self.source_id,
                "company_id": company_id,
            }
            return bool(self.conn.execute(SQL_POSTING_UPSERT, row).fetchone()[0])

    def finish(self, stats: Stats, error: str | None = None) -> None:
        self.conn.rollback()  # discard anything half-done before recording the outcome
        with self.conn.transaction():
            self.conn.execute(
                """UPDATE crawl_runs SET finished_at = now(), status = %s::crawl_status,
                       pages_fetched = %s, postings_found = %s, postings_new = %s,
                       error_message = %s
                   WHERE id = %s""",
                (
                    "failed" if error else "ok",
                    stats.pages,
                    len(stats.relevant),
                    stats.new_postings,
                    error,
                    self.run_id,
                ),
            )
            if error is None:
                self.conn.execute(
                    "UPDATE sources SET last_crawled_at = now() WHERE id = %s", (self.source_id,)
                )
        self.conn.close()


# --------------------------------------------------------------------------- run


def run(
    adapter: ModuleType,
    pages: Iterable[Page],
    loader: Loader | None,
) -> Stats:
    stats = Stats()
    for page in pages:
        stats.pages += 1
        for raw in adapter.split(page):
            stats.items += 1
            outcome = process(adapter, raw)
            if outcome.error:
                stats.errors.append((raw.external_id, outcome.error))
            else:
                stats.parsed += 1
                if outcome.relevant and outcome.posting is not None:
                    stats.relevant.append(outcome.posting)
            if loader is not None and loader.store(outcome):
                stats.new_postings += 1
    return stats


def print_report(stats: Stats, *, dry_run: bool) -> None:
    rows = coverage(stats)
    if not dry_run:
        rows.insert(4, ("New postings inserted", str(stats.new_postings)))
    width = max(len(k) for k, _ in rows)
    print(("DRY RUN: nothing written\n" if dry_run else "") + "-" * (width + 24))
    for k, v in rows:
        print(f"{k:<{width}}  {v}")
    for ext_id, err in stats.errors[:3]:
        print(f"  parse error {ext_id}: {err[:160]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the scraper pipeline for one source.")
    parser.add_argument("--source", required=True, help="adapter slug, e.g. remoteok")
    parser.add_argument("--dry-run", action="store_true", help="fetch + parse only; no writes")
    parser.add_argument("--fixture", type=Path, help="read this saved response, not the network")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv(ROOT / ".env")
    adapter = get_adapter(args.source)

    loader = None
    if not args.dry_run:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
            return 2
        loader = Loader(dsn, adapter.SLUG)

    stats = Stats()
    error: str | None = None
    client: HttpClient | None = None
    try:
        if args.fixture:
            pages: Iterable[Page] = pages_from_fixture(adapter, args.fixture)
        else:
            client = HttpClient()
            pages = adapter.fetch_pages(client)
        stats = run(adapter, pages, loader)
    except FetchError as exc:
        error = str(exc)
        log.error("fetch failed: %s", exc)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log.exception("pipeline crashed")
        raise
    finally:
        if client is not None:
            client.close()
        if loader is not None:
            loader.finish(stats, error)

    print_report(stats, dry_run=args.dry_run)
    if client is not None:
        print(f"HTTP requests made: {client.requests_made}")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
