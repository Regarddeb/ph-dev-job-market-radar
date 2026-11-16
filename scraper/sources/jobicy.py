"""Jobicy adapter: https://jobicy.com/api/jobs (terms checked 2026-11-16, docs/SOURCES.md).

- Official keyless API. The docs allow storing and retaining the data; they require a
  credit and a clickable link to the Jobicy listing ("via Jobicy" -> the API's `url`), and
  that closed or expired jobs leave active listings.
- The feed serves only listings published in the last 7 days, newest first, 100 per
  request, with cursor pagination (`nextCursor` -> `cursor`, filters unchanged). One crawl
  walks the whole window, so "active" for Jobicy means "published in the last 7 days":
  a posting that leaves the window is hidden, which errs on the side the docs ask for.
- Polling: at most hourly and not at minute 00; we run once a day. MAX_PAGES caps a crawl.
- Jobicy is a remote-only board, so work_setup comes from the source: "remote".
- Stated fields are used as given: jobType, salaryMin/Max/Currency/Period, jobGeo (region
  eligibility, kept as location_text). jobLevel is not used: seniority comes from the title
  for every source.
- Relevance: developer roles only, decided by the title; every item is still stored raw.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from scraper.http import HttpClient
from scraper.models import JobType, Page, ParsedPosting, RawItem, SalaryPeriod
from scraper.normalize.classify import is_dev_title
from scraper.normalize.text import clean_text, html_to_text

SLUG = "jobicy"
SOURCE_NAME = "Jobicy"
KIND = "api"
BASE_URL = "https://jobicy.com"
API_URL = "https://jobicy.com/api/jobs"
FIXTURE_EXT = "json"

PAGE_SIZE = 100  # the API's maximum
MAX_PAGES = 20

_JOB_TYPES: dict[str, JobType] = {
    "full-time": "full_time",
    "full time": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "freelance": "freelance",
}
_PERIODS: dict[str, SalaryPeriod] = {
    "hourly": "hour",
    "hour": "hour",
    "daily": "day",
    "day": "day",
    "weekly": "week",
    "week": "week",
    "monthly": "month",
    "month": "month",
    "yearly": "year",
    "annual": "year",
    "annually": "year",
    "year": "year",
}


def fetch_pages(client: HttpClient) -> Iterator[Page]:
    params = {"count": str(PAGE_SIZE)}
    for _ in range(MAX_PAGES):
        response = client.get(API_URL, params=params)
        yield Page(url=str(response.url), text=response.text)
        cursor = (response.json() or {}).get("nextCursor")
        if not cursor:
            return
        params = {"count": str(PAGE_SIZE), "cursor": str(cursor)}


def split(page: Page) -> Iterator[RawItem]:
    data = json.loads(page.text)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise ValueError("Jobicy API: expected an object with a `jobs` array")
    for job in data["jobs"]:
        if not isinstance(job, dict) or "id" not in job or not job.get("url"):
            continue
        yield RawItem(
            external_id=str(job["id"]),
            url=str(job["url"]),
            payload=json.dumps(job, ensure_ascii=False, sort_keys=True),
        )


def fetch(client: HttpClient) -> Iterable[RawItem]:
    for page in fetch_pages(client):
        yield from split(page)


def _texts(value: Any) -> list[str]:
    """A field that is a string or a list of strings -> cleaned, non-empty strings."""
    items = value if isinstance(value, list) else [value]
    return [t for t in (clean_text(str(v)) for v in items if v is not None) if t]


def _job_type(value: Any) -> JobType:
    """The stated type; "unspecified" if none or if several different ones are listed."""
    found = {_JOB_TYPES[t.lower()] for t in _texts(value) if t.lower() in _JOB_TYPES}
    return found.pop() if len(found) == 1 else "unspecified"


def _posted_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace(" ", "T", 1))
    except ValueError:
        return None
    # Jobicy's docs give pubDate in UTC; a value without an offset is read as UTC.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _amount(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _salary(job: dict[str, Any]) -> dict[str, Any]:
    lo, hi = _amount(job.get("salaryMin")), _amount(job.get("salaryMax"))
    if lo is None and hi is None:
        return {}
    if lo is not None and hi is not None and lo > hi:
        return {}  # contradictory: store nothing rather than guess which is right
    currency = str(job.get("salaryCurrency") or "").strip().upper()
    stated_period = str(job.get("salaryPeriod") or "").strip().lower()
    period = _PERIODS.get(stated_period)
    bounds = [v for v in dict.fromkeys((lo, hi)) if v is not None]
    shown = " - ".join(f"{v:,.0f}" for v in bounds)
    known_currency = len(currency) == 3 and currency.isalpha()
    raw = f"{currency} {shown}" if known_currency else shown
    raw += f"/{period}" if period else " (period not stated)"
    if not known_currency:
        return {"salary_raw": raw}  # amounts without a currency can't be compared
    return {
        "salary_raw": raw,
        "salary_currency": currency,
        "salary_period": period,
        "salary_min": lo,
        "salary_max": hi,
    }


def parse(raw: RawItem) -> ParsedPosting:
    job = json.loads(raw.payload)
    return ParsedPosting(
        external_id=raw.external_id,
        title=clean_text(job.get("jobTitle")) or "",
        company_name=clean_text(job.get("companyName")),
        source_url=raw.url,
        location_text=", ".join(_texts(job.get("jobGeo"))) or None,
        description=html_to_text(job.get("jobDescription")),
        posted_at=_posted_at(job.get("pubDate")),
        work_setup="remote",
        job_type=_job_type(job.get("jobType")),
        tags=_texts(job.get("jobIndustry")),
        **_salary(job),
    )


def is_relevant(posting: ParsedPosting) -> bool:
    """Developer roles only, decided by the title (Jobicy lists every industry)."""
    return is_dev_title(posting.title)
