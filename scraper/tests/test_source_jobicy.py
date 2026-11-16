"""Jobicy adapter against the 2026-11-16 fixture (one API page, 100 jobs, all industries).

Nothing here touches the network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from scraper import pipeline
from scraper.http import HttpClient
from scraper.models import Page, ParsedPosting, RawItem
from scraper.sources import jobicy

FIXTURE = Path(__file__).parent / "fixtures" / "jobicy" / "2026-11-16.json"


@pytest.fixture(scope="module")
def page() -> Page:
    return next(iter(pipeline.pages_from_fixture(jobicy, FIXTURE)))


@pytest.fixture(scope="module")
def raws(page: Page) -> dict[str, RawItem]:
    return {r.external_id: r for r in jobicy.split(page)}


@pytest.fixture(scope="module")
def parsed(raws: dict[str, RawItem]) -> dict[str, ParsedPosting]:
    return {i: jobicy.parse(r) for i, r in raws.items()}


def test_fixture_shape(page: Page, raws: dict[str, RawItem]) -> None:
    assert len(list(jobicy.split(page))) == 100
    assert len(raws) == 100  # external ids are unique
    assert all(r.url.startswith("https://jobicy.com/jobs/") for r in raws.values())


def test_split_rejects_an_unexpected_body() -> None:
    with pytest.raises(ValueError, match="jobs"):
        list(jobicy.split(Page(url="x", text='{"success": false}')))


def test_split_skips_elements_without_id_or_url() -> None:
    body = json.dumps({"jobs": [{"id": 1}, {"url": "https://jobicy.com/jobs/2"}, "x"]})
    assert list(jobicy.split(Page(url="x", text=body))) == []


def test_posting_with_structured_salary(parsed: dict[str, ParsedPosting]) -> None:
    p = parsed["152419"]
    assert p.model_dump(exclude={"description"}) == {
        "external_id": "152419",
        "title": "Software Engineer, AI/ML Infrastructure",
        "company_name": "Thumbtack",
        "source_url": "https://jobicy.com/jobs/152419-software-engineer-ai-ml-infrastructure",
        "location_text": "Canada",
        "posted_at": datetime(2026, 11, 16, 3, 20, 7, tzinfo=UTC),
        "work_setup": "remote",
        "job_type": "full_time",
        "salary_raw": "CAD 123,300 - 159,500/year",
        "salary_currency": "CAD",
        "salary_period": "year",
        "salary_min": 123300.0,
        "salary_max": 159500.0,
        "tags": ["DevOps & Infrastructure"],
    }
    assert p.description and "<" not in p.description[:200]  # HTML converted to text


def test_posting_without_salary_states_none(parsed: dict[str, ParsedPosting]) -> None:
    p = parsed["155494"]
    assert (p.title, p.company_name, p.location_text) == (
        "Senior DevOps Engineer",
        "Documo Inc.",
        "Anywhere",
    )
    assert p.salary_raw is None and p.salary_currency is None and p.salary_period is None


def test_stated_periods_and_job_types(parsed: dict[str, ParsedPosting]) -> None:
    assert parsed["155412"].salary_raw == "USD 20 - 25/hour"
    assert parsed["155412"].salary_period == "hour"
    assert parsed["155412"].job_type == "part_time"
    assert parsed["162469"].salary_raw == "USD 25/hour"  # min == max shown once
    assert parsed["162469"].job_type == "contract"
    assert parsed["155448"].salary_period == "month"
    assert parsed["155448"].job_type == "unspecified"  # "Internship" is not one of our types


def test_html_entities_are_cleaned(parsed: dict[str, ParsedPosting]) -> None:
    assert parsed["159771"].title == "Product & Technical Communications"
    assert not any("&amp;" in p.title or "&#" in p.title for p in parsed.values())


def test_relevance_is_decided_by_title(parsed: dict[str, ParsedPosting]) -> None:
    relevant = {i for i, p in parsed.items() if jobicy.is_relevant(p)}
    assert len(relevant) == 19  # the feed mixes sales, legal, support, finance, ...
    assert {"152419", "155494", "155430"} <= relevant
    assert "159771" not in relevant  # Product & Technical Communications


def test_derived_fields(parsed: dict[str, ParsedPosting]) -> None:
    anywhere = pipeline.posting_row(parsed["155494"])
    assert anywhere["ph_eligible"] is True  # jobGeo "Anywhere"
    assert anywhere["seniority"] == "senior"
    assert anywhere["salary_min_monthly"] is None  # no salary stated, none derived
    canada = pipeline.posting_row(parsed["152419"])
    assert canada["salary_currency"] == "CAD"
    assert float(canada["salary_min_monthly"]) == pytest.approx(123300 / 12)


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        ({"salaryMin": 0, "salaryMax": 0}, {}),
        ({"salaryMin": 90000, "salaryMax": 50000, "salaryCurrency": "USD"}, {}),
        (
            {"salaryMin": 5000, "salaryCurrency": "USD"},
            {
                "salary_raw": "USD 5,000 (period not stated)",
                "salary_currency": "USD",
                "salary_period": None,
                "salary_min": 5000.0,
                "salary_max": None,
            },
        ),
        # No currency: keep what was stated as text, but nothing comparable.
        (
            {"salaryMin": 40, "salaryMax": 60, "salaryPeriod": "hourly"},
            {"salary_raw": "40 - 60/hour"},
        ),
    ],
)
def test_salary_never_guesses(job: dict, expected: dict) -> None:
    assert jobicy._salary(job) == expected


def test_conflicting_job_types_stay_unspecified() -> None:
    assert jobicy._job_type(["Full-Time", "Contract"]) == "unspecified"
    assert jobicy._job_type("Freelance") == "freelance"
    assert jobicy._job_type(None) == "unspecified"


def test_fetch_pages_follows_the_cursor_and_stops() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        nxt = {None: "c1", "c1": "c2", "c2": None}[params.get("cursor")]
        return httpx.Response(200, json={"jobs": [], "nextCursor": nxt})

    client = HttpClient("test-agent", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    pages = list(jobicy.fetch_pages(client))
    assert len(pages) == 3
    assert seen == [
        {"count": "100"},
        {"count": "100", "cursor": "c1"},
        {"count": "100", "cursor": "c2"},
    ]


def test_fetch_pages_is_capped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": [], "nextCursor": "again"})

    client = HttpClient("test-agent", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    assert len(list(jobicy.fetch_pages(client))) == jobicy.MAX_PAGES


def test_pipeline_dry_run_over_fixture() -> None:
    stats = pipeline.run(jobicy, pipeline.pages_from_fixture(jobicy, FIXTURE), loader=None)
    assert (stats.items, stats.parsed, len(stats.errors), len(stats.relevant)) == (100, 100, 0, 19)
