"""fetch -> raw -> parse -> normalize -> tag -> (dedupe: step 6) -> load.

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
import inspect
import json
import logging
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from scraper.db import connect
from scraper.http import FetchError, HttpClient
from scraper.models import Page, ParsedPosting, RawItem
from scraper.normalize import classify
from scraper.normalize.salary import parse_salary, to_monthly
from scraper.normalize.skills import Tagger
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
    # Incremental sources (HN): listed items not re-fetched because they're stored and final.
    skipped_known: int = 0


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


def salary_fields(p: ParsedPosting) -> dict[str, Any]:
    """Currency, period and monthly amounts in the posting's own currency.

    The adapter's structured fields win; otherwise salary_raw is parsed. The monthly amounts
    are converted to PHP in SQL (SQL_SALARY_PHP) at the posting's first-seen date.
    """
    currency, period = p.salary_currency, p.salary_period
    lo, hi = p.salary_min, p.salary_max
    if lo is None and hi is None and (parsed := parse_salary(p.salary_raw)):
        currency, period, lo, hi = parsed.currency, parsed.period, parsed.minimum, parsed.maximum
    lo, hi = (lo if lo is not None else hi), (hi if hi is not None else lo)
    monthly_min = to_monthly(lo, period) if lo is not None else None
    monthly_max = to_monthly(hi, period) if hi is not None else None
    return {
        "salary_currency": currency,
        "salary_period": period,
        "salary_min_monthly": monthly_min,
        "salary_max_monthly": monthly_max,
    }


def posting_row(p: ParsedPosting) -> dict[str, Any]:
    """Columns for `postings`, including the rule-derived fields (docs/SPEC.md §6).

    Unknowns stay 'unspecified' / None: never guessed.
    """
    company_norm = normalize_company(p.company_name) if p.company_name else ""
    title_norm = normalize_title(p.title)
    setup = classify.work_setup(p.work_setup, p.title, p.location_text)
    return {
        "external_id": p.external_id,
        "title": p.title,
        "title_normalized": title_norm,
        "seniority": classify.seniority(p.title),
        "job_type": classify.job_type(p.job_type, p.title, p.description),
        "work_setup": setup,
        "ph_eligible": classify.ph_eligible(p.title, p.location_text, p.description),
        "location_text": p.location_text,
        "salary_raw": p.salary_raw,
        **salary_fields(p),
        "description": p.description,
        "source_url": p.source_url,
        "posted_at": p.posted_at,
        "fingerprint": fingerprint(company_norm, title_norm, setup) if company_norm else None,
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
        *derived_coverage(rel, pct),
    ]


def derived_coverage(rel: list[ParsedPosting], pct: Any) -> list[tuple[str, str]]:
    rows = [posting_row(p) for p in rel]
    tagger = Tagger.from_json()
    tagged = sum(bool(tagger.tag(p.title, p.description)) for p in rel)
    return [
        ("% seniority known", pct(sum(r["seniority"] != "unspecified" for r in rows))),
        ("% job_type known", pct(sum(r["job_type"] != "unspecified" for r in rows))),
        ("% ph_eligible known", pct(sum(r["ph_eligible"] is not None for r in rows))),
        ("  of which PH-eligible", pct(sum(r["ph_eligible"] is True for r in rows))),
        ("% salary convertible", pct(sum(r["salary_min_monthly"] is not None for r in rows))),
        ("% with >= 1 skill", pct(tagged)),
    ]


# --------------------------------------------------------------------------- page sources


def pages_from_fixture(adapter: ModuleType, path: Path) -> Iterator[Page]:
    """A fixture is one response body, or for .jsonl one captured response per line
    ({"url", "text"}): sources like HN need many requests per crawl."""
    with path.open(encoding="utf-8", newline="") as fh:
        if path.suffix == ".jsonl":
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    yield Page(url=rec["url"], text=rec["text"])
        else:
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

# %(seen)s: true for a crawl (the posting was just seen: bump last_seen_at, mark active);
# false for a reparse or backfill (leave the crawl history alone). Rows inserted that way
# take %(first_seen)s / %(last_seen)s (reparse: the raw fetch time; backfill: the posting's
# own dates) and %(active)s.
SQL_POSTING_UPSERT = """
INSERT INTO postings (
    raw_posting_id, source_id, external_id, company_id, title, title_normalized,
    seniority, job_type, work_setup, ph_eligible, location_text,
    salary_raw, salary_currency, salary_period,
    description, source_url, posted_at, fingerprint, first_seen_at, last_seen_at, is_active)
VALUES (
    %(raw_posting_id)s, %(source_id)s, %(external_id)s, %(company_id)s, %(title)s,
    %(title_normalized)s, %(seniority)s::seniority, %(job_type)s::job_type,
    %(work_setup)s::work_setup, %(ph_eligible)s, %(location_text)s,
    %(salary_raw)s, %(salary_currency)s, %(salary_period)s,
    %(description)s, %(source_url)s, %(posted_at)s, %(fingerprint)s,
    COALESCE(%(first_seen)s, now()), COALESCE(%(last_seen)s, now()), %(active)s)
ON CONFLICT (source_id, external_id) DO UPDATE SET
    raw_posting_id   = EXCLUDED.raw_posting_id,
    company_id       = EXCLUDED.company_id,
    title            = EXCLUDED.title,
    title_normalized = EXCLUDED.title_normalized,
    seniority        = EXCLUDED.seniority,
    job_type         = EXCLUDED.job_type,
    work_setup       = EXCLUDED.work_setup,
    ph_eligible      = EXCLUDED.ph_eligible,
    location_text    = EXCLUDED.location_text,
    salary_raw       = EXCLUDED.salary_raw,
    salary_currency  = EXCLUDED.salary_currency,
    salary_period    = EXCLUDED.salary_period,
    description      = COALESCE(EXCLUDED.description, postings.description),
    source_url       = EXCLUDED.source_url,
    posted_at        = COALESCE(EXCLUDED.posted_at, postings.posted_at),
    fingerprint      = EXCLUDED.fingerprint,
    last_seen_at     = CASE WHEN %(seen)s THEN now() ELSE postings.last_seen_at END,
    is_active        = CASE WHEN %(seen)s THEN true ELSE postings.is_active END
RETURNING id, (xmax = 0) AS inserted
"""

# Monthly amounts (in the posting's currency) -> PHP, at the rate for the posting's
# first-seen date (UTC day). The latest ECB rate on or before that day is used, looking
# back at most 7 days (weekends, TARGET holidays); no rate -> NULL, never a guess.
# Both amounts are set only if both fit the INT column and the > 0 CHECK; an absurd value
# ("$900m/month") or one that rounds to 0 leaves both NULL instead of failing the row.
SQL_SALARY_PHP = """
UPDATE postings p SET
    salary_min_php_monthly = CASE WHEN fx.ok THEN fx.lo::int END,
    salary_max_php_monthly = CASE WHEN fx.ok THEN fx.hi::int END
FROM (
    SELECT v.id, v.lo, v.hi,
           COALESCE(v.lo BETWEEN 1 AND 2147483647 AND v.hi BETWEEN 1 AND 2147483647
                    AND v.lo <= v.hi, false) AS ok
    FROM (
        SELECT p2.id,
               round(%(min)s::numeric * r.rate) AS lo,
               round(%(max)s::numeric * r.rate) AS hi
        FROM postings p2
        CROSS JOIN LATERAL (
            SELECT CASE WHEN %(currency)s::text = 'PHP' THEN 1::numeric ELSE (
                SELECT er.php_per_unit FROM exchange_rates er
                WHERE er.currency = %(currency)s::text
                  AND er.date <= (p2.first_seen_at AT TIME ZONE 'UTC')::date
                  AND er.date >  (p2.first_seen_at AT TIME ZONE 'UTC')::date - 7
                ORDER BY er.date DESC LIMIT 1) END AS rate
        ) r
        WHERE p2.id = %(id)s
    ) v
) fx
WHERE p.id = fx.id
"""

SQL_KNOWN_RAW = """
SELECT external_id, payload, fetched_at FROM raw_postings
WHERE source_id = %s AND external_id = ANY(%s)
"""

# Listed but not re-fetched: still listed, so still seen and active.
SQL_MARK_LISTED = """
UPDATE postings SET last_seen_at = now(), is_active = true
WHERE source_id = %s AND external_id = ANY(%s)
"""

SQL_DEACTIVATE_UNSEEN = """
UPDATE postings SET is_active = false
WHERE source_id = %s AND is_active
  AND last_seen_at < (SELECT started_at FROM crawl_runs WHERE id = %s)
"""

SQL_SKILLS_CLEAR = "DELETE FROM posting_skills WHERE posting_id = %s"
SQL_SKILLS_INSERT = """
INSERT INTO posting_skills (posting_id, skill_id)
SELECT %s, id FROM skills WHERE name = ANY(%s)
ON CONFLICT DO NOTHING
"""
SQL_ALIASES = """
SELECT s.name, a.pattern, a.requirements_only
FROM skill_aliases a JOIN skills s ON s.id = a.skill_id
ORDER BY s.name, a.id
"""


class PostingWriter:
    """Writes one parsed posting with its derived fields, PHP salary and skills.

    Shared by the crawl (Loader) and by reparse (scraper/reparse.py). The caller owns the
    transaction.
    """

    def __init__(self, conn: Any, source_id: int) -> None:
        self.conn = conn
        self.source_id = source_id
        self.tagger = Tagger.from_rows(conn.execute(SQL_ALIASES).fetchall())

    def write(
        self,
        p: ParsedPosting,
        raw_id: int,
        *,
        seen: bool,
        seen_at: Any = None,
        active_if_new: bool = True,
        first_seen: Any = None,
        last_seen: Any = None,
    ) -> tuple[int, bool]:
        """Upsert the posting. Returns (posting id, inserted?).

        For rows inserted without a crawl (seen=False): seen_at sets both first and last
        seen (reparse); first_seen / last_seen set them separately (backfill), and
        active_if_new says whether the row starts active. A crawl always inserts active rows
        seen now.
        """
        company_id = None
        if p.company_name and (norm := normalize_company(p.company_name)):
            company_id = self.conn.execute(SQL_COMPANY_UPSERT, (p.company_name, norm)).fetchone()[0]
        row = posting_row(p)
        params = row | {
            "raw_posting_id": raw_id,
            "source_id": self.source_id,
            "company_id": company_id,
            "seen": seen,
            "first_seen": first_seen or seen_at,
            "last_seen": last_seen or seen_at,
            "active": True if seen else active_if_new,
        }
        posting_id, inserted = self.conn.execute(SQL_POSTING_UPSERT, params).fetchone()
        self.conn.execute(
            SQL_SALARY_PHP,
            {
                "id": posting_id,
                "currency": row["salary_currency"],
                "min": row["salary_min_monthly"],
                "max": row["salary_max_monthly"],
            },
        )
        skills = sorted(self.tagger.tag(p.title, p.description))
        self.conn.execute(SQL_SKILLS_CLEAR, (posting_id,))
        if skills:
            self.conn.execute(SQL_SKILLS_INSERT, (posting_id, skills))
        return posting_id, bool(inserted)


class Loader:
    """All writes for one crawl run. One transaction per item, so a bad row can't sink
    the run; the crawl_runs row is committed first so failures are always recorded."""

    def __init__(self, dsn: str, slug: str) -> None:

        self.conn = connect(dsn)
        row = self.conn.execute(
            "SELECT id, is_active FROM sources WHERE slug = %s", (slug,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"source {slug!r} not seeded; run `pnpm db:seed` in dashboard/")
        self.source_id, active = row
        if not active:
            raise SystemExit(f"source {slug!r} has is_active=false in the seed; refusing to run")
        self.writer = PostingWriter(self.conn, self.source_id)
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
            _, inserted = self.writer.write(outcome.posting, raw_id, seen=True)
            return inserted

    def listing_callback(
        self, adapter: ModuleType, stats: Stats
    ) -> Callable[[list[str]], set[str]]:
        """For incremental adapters: given every id the source currently lists, return the
        ids to skip (stored, and final per adapter.is_final), and mark those as seen."""

        def on_listing(ids: list[str]) -> set[str]:
            is_final = getattr(adapter, "is_final", None)
            with self.conn.transaction():
                rows = self.conn.execute(SQL_KNOWN_RAW, (self.source_id, ids)).fetchall()
                skip = {
                    ext_id
                    for ext_id, payload, fetched_at in rows
                    if is_final is None or is_final(payload, fetched_at)
                }
                if skip:
                    self.conn.execute(SQL_MARK_LISTED, (self.source_id, sorted(skip)))
            stats.skipped_known = len(skip)
            return skip

        return on_listing

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
                # Active = listed in the source's latest successful crawl. Only after a
                # complete, error-free run, and only if it found or re-listed postings (an
                # empty feed is more likely an outage than every job closing at once).
                if stats.relevant or stats.skipped_known:
                    self.conn.execute(SQL_DEACTIVATE_UNSEEN, (self.source_id, self.run_id))
        self.conn.close()


# --------------------------------------------------------------------------- run


def run(
    adapter: ModuleType,
    pages: Iterable[Page],
    loader: Loader | None,
    stats: Stats | None = None,
) -> Stats:
    stats = stats if stats is not None else Stats()
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
        if stats.skipped_known:
            rows.insert(1, ("Listed, already stored (skipped)", str(stats.skipped_known)))
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
            if (
                loader is not None
                and "on_listing" in inspect.signature(adapter.fetch_pages).parameters
            ):
                pages = adapter.fetch_pages(
                    client, on_listing=loader.listing_callback(adapter, stats)
                )
            else:
                pages = adapter.fetch_pages(client)
        run(adapter, pages, loader, stats)
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
