"""Remote OK adapter: https://remoteok.com/api (terms checked 2026-11-06, docs/SOURCES.md).

- One request per run: the API returns only the latest ~100 jobs, across ALL categories.
- Element 0 of the JSON array is the legal notice / API ToS, not a job: skipped.
- Attribution: link to the job's Remote OK URL (followed link) and name "Remote OK".
  Never use the Remote OK logo.
- Remote OK is a remote-only board, so work_setup comes from the source: "remote".
- Text fields arrive with HTML entities and UTF-8-as-Latin-1 mojibake (in the source data
  itself); clean_text() repairs both.
- Salary: salary_min / salary_max are Remote OK's structured fields, in USD. The period is
  not stated per job. Values above ANNUAL_FLOOR_USD are treated as annual (Remote OK's
  convention); smaller values (e.g. 30-36, clearly hourly or monthly) keep amount and
  currency but salary_period stays NULL, so no PHP/month figure is derived. 0 = not stated.
  Exactly 10,000 is the bottom of Remote OK's salary picker and shows up as a placeholder
  ("10,000 - 120,000", "10,000 - 10,000"), so a bound at the floor also leaves the period
  NULL rather than reading it as USD 833/month.
- Relevance: only developer roles become postings (is_relevant, decided by the title);
  every item is still stored raw.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from scraper.http import HttpClient
from scraper.models import Page, ParsedPosting, RawItem
from scraper.normalize.classify import is_dev_title
from scraper.normalize.text import clean_text, html_to_text

SLUG = "remoteok"
SOURCE_NAME = "Remote OK"
KIND = "api"
BASE_URL = "https://remoteok.com"
API_URL = "https://remoteok.com/api"
FIXTURE_EXT = "json"

ANNUAL_FLOOR_USD = 10_000


def fetch_pages(client: HttpClient) -> Iterator[Page]:
    response = client.get(API_URL)
    yield Page(url=str(response.url), text=response.text)


def split(page: Page) -> Iterator[RawItem]:
    data = json.loads(page.text)
    if not isinstance(data, list):
        raise ValueError("Remote OK API: expected a JSON array")
    for element in data:
        if not isinstance(element, dict) or "legal" in element or "id" not in element:
            continue  # the legal notice (element 0) or anything that isn't a job
        yield RawItem(
            external_id=str(element["id"]),
            url=str(element.get("url") or f"{BASE_URL}/remote-jobs/{element['id']}"),
            payload=json.dumps(element, ensure_ascii=False, sort_keys=True),
        )


def fetch(client: HttpClient) -> Iterable[RawItem]:
    for page in fetch_pages(client):
        yield from split(page)


def _html_to_text(html: str | None) -> str | None:
    return html_to_text(html)


def _posted_at(job: dict[str, Any]) -> datetime | None:
    if job.get("date"):
        try:
            return datetime.fromisoformat(str(job["date"]))
        except ValueError:
            pass
    epoch = job.get("epoch")
    if isinstance(epoch, int | float) and epoch > 0:
        return datetime.fromtimestamp(epoch, tz=UTC)
    return None


def _amount(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and value > 0 else None


def _salary(job: dict[str, Any]) -> dict[str, Any]:
    lo, hi = _amount(job.get("salary_min")), _amount(job.get("salary_max"))
    if lo is None and hi is None:
        return {}
    if lo is not None and hi is not None and lo > hi:
        return {}  # contradictory: store nothing rather than guess which is right
    bounds = [v for v in dict.fromkeys((lo, hi)) if v is not None]  # 75k-75k -> 75k
    shown = " - ".join(f"{v:,.0f}" for v in bounds)
    annual = all(v > ANNUAL_FLOOR_USD for v in (lo, hi) if v is not None)
    return {
        "salary_raw": f"USD {shown}/year" if annual else f"USD {shown} (period not stated)",
        "salary_currency": "USD",
        "salary_period": "year" if annual else None,
        "salary_min": lo,
        "salary_max": hi,
    }


def parse(raw: RawItem) -> ParsedPosting:
    job = json.loads(raw.payload)
    tags = [clean_text(str(t)) for t in (job.get("tags") or [])]
    return ParsedPosting(
        external_id=raw.external_id,
        title=clean_text(job.get("position")) or "",
        company_name=clean_text(job.get("company")),
        source_url=raw.url,
        location_text=clean_text(job.get("location")),
        description=_html_to_text(job.get("description")),
        posted_at=_posted_at(job),
        work_setup="remote",
        tags=[t for t in tags if t],
        **_salary(job),
    )


def is_relevant(posting: ParsedPosting) -> bool:
    """Developer roles only; Remote OK's feed mixes in support, sales, travel, etc.

    Decided by the title (normalize.classify.is_dev_title). Tags alone aren't trusted: they
    are keyword-stuffed ("Tax Manager" tagged dev/php, "Account Manager" tagged golang).
    """
    return is_dev_title(posting.title)
