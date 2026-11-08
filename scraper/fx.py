"""Exchange rates into PHP from the ECB euro foreign exchange reference rates.

    uv run --project scraper python -m scraper.fx                 # last 90 days (daily job)
    uv run --project scraper python -m scraper.fx --history       # full history since --since
    uv run --project scraper python -m scraper.fx --fixture <f>   # no network
    uv run --project scraper python -m scraper.fx --capture       # save a new dated fixture
    ... add --dry-run to any of them to parse and report without writing.

Source: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/
(terms checked 2026-11-07; see docs/SOURCES.md, "Reference data").
- Rates are quoted as units of currency X per 1 EUR, published ~16:00 CET on TARGET working
  days. The ECB publishes them "for information purposes only", which is how we use them.
- Reuse is free if the ECB is cited as the source and changes are disclosed. Our change:
  PHP per unit of X is a cross rate, PHP_per_EUR / X_per_EUR (stored for every currency
  the ECB lists, plus EUR itself). The dashboard must say so wherever PHP salaries appear.
- robots.txt allows /stats/eurofxref/ with Crawl-delay 5; we make one request per run.

Writes rows only (no DDL) into exchange_rates, upserting on (date, currency), so re-runs and
overlapping windows are idempotent.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from lxml import etree

from scraper.db import connect
from scraper.http import HttpClient

BASE = "https://www.ecb.europa.eu/stats/eurofxref"
URL_90D = f"{BASE}/eurofxref-hist-90d.xml"
URL_HISTORY = f"{BASE}/eurofxref-hist.zip"
ECB_HOST = "www.ecb.europa.eu"
ECB_CRAWL_DELAY_S = 5.0

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures" / "ecb"
SCALE = Decimal("0.000001")  # exchange_rates.php_per_unit is DECIMAL(14, 6)


@dataclass(frozen=True)
class Rate:
    day: date
    currency: str
    php_per_unit: Decimal


def _decimal(value: str) -> Decimal | None:
    try:
        d = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        return None  # "N/A" and blanks in the history CSV
    return d if d.is_finite() and d > 0 else None


def cross_rates(day: date, per_eur: dict[str, Decimal]) -> Iterator[Rate]:
    """{currency: units per EUR} for one day -> PHP per unit of each currency.

    Yields nothing if the day has no PHP quote: no PHP rate means nothing can be derived.
    """
    php = per_eur.get("PHP")
    if php is None:
        return
    yield Rate(day, "EUR", php.quantize(SCALE))
    for currency, units in sorted(per_eur.items()):
        if currency in ("PHP", "EUR"):
            continue
        yield Rate(day, currency, (php / units).quantize(SCALE))


def parse_xml(text: str | bytes) -> list[Rate]:
    """The daily / 90-day XML: <Cube time="YYYY-MM-DD"><Cube currency=".." rate=".."/>..."""
    data = text.encode("utf-8") if isinstance(text, str) else text
    # The ECB feed never declares a DTD. Refuse one outright: libxml2 still expands internal
    # entities in attribute values even with resolve_entities=False.
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ValueError("ECB XML must not contain a DTD")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    root = etree.fromstring(data, parser=parser)
    rates: list[Rate] = []
    for day_cube in root.iter("{*}Cube"):
        stamp = day_cube.get("time")
        if not stamp:
            continue
        per_eur = {
            c.get("currency"): v
            for c in day_cube
            if c.get("currency") and (v := _decimal(c.get("rate", ""))) is not None
        }
        rates.extend(cross_rates(date.fromisoformat(stamp), per_eur))
    return rates


def parse_history_csv(text: str, *, since: date | None = None) -> list[Rate]:
    """eurofxref-hist.csv: `Date,USD,JPY,...,` then one row per day; "N/A" = no quote."""
    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(reader)]
    rates: list[Rate] = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        day = date.fromisoformat(row[0].strip())
        if since is not None and day < since:
            continue
        per_eur = {
            cur: v
            for cur, cell in zip(header[1:], row[1:], strict=False)
            if cur and (v := _decimal(cell)) is not None
        }
        rates.extend(cross_rates(day, per_eur))
    return rates


def unzip_history(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one CSV in the ECB history zip, found {names}")
        return zf.read(names[0]).decode("utf-8")


def make_client() -> HttpClient:
    return HttpClient(host_intervals={ECB_HOST: ECB_CRAWL_DELAY_S})  # robots.txt Crawl-delay


SQL_UPSERT = """
INSERT INTO exchange_rates (date, currency, php_per_unit) VALUES (%s, %s, %s)
ON CONFLICT (date, currency) DO UPDATE SET php_per_unit = EXCLUDED.php_per_unit
"""


def store(dsn: str, rates: list[Rate]) -> None:

    with connect(dsn) as conn, conn.cursor() as cur:
        cur.executemany(SQL_UPSERT, [(r.day, r.currency, r.php_per_unit) for r in rates])


def summarize(rates: list[Rate]) -> str:
    if not rates:
        return "no rates parsed"
    days = sorted({r.day for r in rates})
    usd = max((r for r in rates if r.currency == "USD"), key=lambda r: r.day, default=None)
    latest = f"; latest USD = {usd.php_per_unit} PHP ({usd.day})" if usd else ""
    return (
        f"{len(rates)} rates, {len(days)} days ({days[0]} .. {days[-1]}), "
        f"{len({r.currency for r in rates})} currencies{latest}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load ECB reference rates into exchange_rates.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--history", action="store_true", help="full history zip, not 90 days")
    mode.add_argument("--fixture", type=Path, help="parse this saved XML instead of fetching")
    mode.add_argument("--capture", action="store_true", help="save the 90-day XML as a fixture")
    parser.add_argument("--since", type=date.fromisoformat, default=date(2021, 1, 1))
    parser.add_argument("--dry-run", action="store_true", help="parse and report; no writes")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")

    if args.fixture:
        rates = parse_xml(args.fixture.read_bytes())
    else:
        with make_client() as client:
            if args.history:
                blob = client.get(URL_HISTORY).content
                rates = parse_history_csv(unzip_history(blob), since=args.since)
            else:
                body = client.get(URL_90D).content
                rates = parse_xml(body)
                if args.capture:
                    FIXTURES.mkdir(parents=True, exist_ok=True)
                    stem = datetime.now(UTC).strftime("%Y-%m-%d")
                    path, n = FIXTURES / f"{stem}-hist-90d.xml", 2
                    while path.exists():
                        path, n = FIXTURES / f"{stem}-hist-90d-{n}.xml", n + 1
                    path.write_bytes(body)  # byte-for-byte; fixtures are immutable
                    print(f"saved {path.relative_to(ROOT)}")
            print(f"HTTP requests made: {client.requests_made}")

    print(("DRY RUN: " if args.dry_run or args.capture else "") + summarize(rates))
    if args.dry_run or args.capture:
        return 0
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set (jobradar_rw role; see .env.example)", file=sys.stderr)
        return 2
    store(dsn, rates)
    print(f"stored {len(rates)} rows in exchange_rates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
