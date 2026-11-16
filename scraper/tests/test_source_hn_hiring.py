"""HN "Who is Hiring?" adapter against the 2026-11-08 fixture (November 2026 thread).

The fixture is JSONL: every response of one crawl (user record, scanned stories, then each
top-level comment), bodies unchanged. Nothing here touches the network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from scraper import pipeline
from scraper.http import HttpClient
from scraper.models import ParsedPosting, RawItem
from scraper.sources import hn_hiring as hn

FIXTURE = Path(__file__).parent / "fixtures" / "hn_hiring" / "2026-11-08.jsonl"
THREAD_ID = 50338728


@pytest.fixture(scope="module")
def pages() -> list:
    return list(pipeline.pages_from_fixture(hn, FIXTURE))


@pytest.fixture(scope="module")
def raws(pages: list) -> dict[str, RawItem]:
    return {r.external_id: r for page in pages for r in hn.split(page)}


@pytest.fixture(scope="module")
def parsed(raws: dict[str, RawItem]) -> dict[str, ParsedPosting]:
    return {i: hn.parse(r) for i, r in raws.items()}


# --------------------------------------------------------------------------- shape


def test_fixture_shape(pages: list, raws: dict[str, RawItem]) -> None:
    assert len(pages) == 249
    thread = json.loads(next(p.text for p in pages if str(THREAD_ID) in p.url))
    assert thread["title"] == "Ask HN: Who is hiring? (November 2026)"
    assert len(thread["kids"]) == 247
    # 247 top-level comments: 40 deleted or dead are skipped, 207 live ones become items.
    assert len(raws) == 207
    assert all(r.url == f"https://news.ycombinator.com/item?id={i}" for i, r in raws.items())


def test_non_comments_and_removed_comments_are_skipped(pages: list) -> None:
    for page in pages:
        data = json.loads(page.text)
        if (
            not isinstance(data, dict)
            or data.get("type") != "comment"
            or data.get("deleted")
            or data.get("dead")
        ):
            assert list(hn.split(page)) == []


def test_every_item_parses(parsed: dict[str, ParsedPosting]) -> None:
    assert len(parsed) == 207
    assert all(p.title and p.description for p in parsed.values())


# --------------------------------------------------------------------------- parsing


def test_pipe_header_fully_parsed(parsed: dict[str, ParsedPosting]) -> None:
    p = parsed["50338732"]
    assert p.model_dump(exclude={"description"}) == {
        "external_id": "50338732",
        "title": "DevOps Engineer",
        "company_name": "Simple Analytics",
        "source_url": "https://news.ycombinator.com/item?id=50338732",
        "location_text": "REMOTE (worldwide, any timezone)",
        "posted_at": datetime(2026, 11, 2, 16, 1, 43, tzinfo=UTC),
        "work_setup": "unspecified",  # derived later by normalize/classify
        "job_type": "unspecified",
        "salary_raw": "€5,000/month (full-time)",
        "salary_currency": None,  # parsed later from salary_raw
        "salary_period": None,
        "salary_min": None,
        "salary_max": None,
        "tags": [],
    }
    # HTML entities (&#x2F;) are decoded and the header is the first line.
    assert (p.description or "").startswith("Simple Analytics | DevOps Engineer | REMOTE")


def test_salary_without_period_is_kept_raw(parsed: dict[str, ParsedPosting]) -> None:
    p = parsed["50340287"]  # JPMorganChase | Lead Software Engineer | ONSITE (...) | $156,750 - ...
    assert (p.company_name, p.title, p.location_text, p.salary_raw) == (
        "JPMorganChase",
        "Lead Software Engineer",
        "ONSITE (Jersey City, NJ)",
        "$156,750 - $215,000.",
    )
    row = pipeline.posting_row(p)
    assert row["salary_currency"] == "USD"
    assert row["salary_period"] is None and row["salary_min_monthly"] is None  # not guessed


def test_role_from_body_when_header_has_none(parsed: dict[str, ParsedPosting]) -> None:
    # "Middesk | Full-time | SF / NYC | Hybrid | <url>", then a list of roles with salaries.
    assert parsed["50342990"].title == "Forward Deployed Engineer"
    assert parsed["50342990"].location_text == "SF / NYC | Hybrid"
    # Prose lines are not titles: Fly.io's body starts "Hey folks, Fly.io is a developer-..."
    assert parsed["50342723"].title == "Networking Engineer"


def test_company_is_not_a_place_or_url(parsed: dict[str, ParsedPosting]) -> None:
    assert parsed["50339895"].company_name is None  # "Cologne, Germany | Product Engineer"
    assert parsed["50339853"].company_name == "Better Stack"


def test_prose_header_company(parsed: dict[str, ParsedPosting]) -> None:
    assert parsed["50349601"].company_name == "DigitalTolk"  # "DigitalTolk is hiring ..."
    assert parsed["50349615"].company_name == "UNICEF"  # "UNICEF - REMOTE backend dev - ..."


def test_location_segment_with_a_role_word_stays_a_location(
    parsed: dict[str, ParsedPosting],
) -> None:
    p = parsed["50344646"]  # "... | Varies between REMOTE (... account exec position) and ..."
    assert p.title == "Senior/Staff Java Engineers, Account Executive"
    assert (p.location_text or "").startswith("Varies between REMOTE")


# --------------------------------------------------------------------------- relevance


def test_relevance_count(parsed: dict[str, ParsedPosting]) -> None:
    assert sum(hn.is_relevant(p) for p in parsed.values()) == 156


@pytest.mark.parametrize(
    "ext_id",
    [
        "50338732",  # DevOps Engineer
        "50352150",  # IMC Trading: "IMC" is not "I'm" (job-seeker check)
        "50344646",  # mixed roles: Java Engineers + Account Executive
        "50342697",  # "Fullstack Engineer / Customer Success Engineer / ..."
        "50342990",  # role only in the body
    ],
)
def test_relevant(parsed: dict[str, ParsedPosting], ext_id: str) -> None:
    assert hn.is_relevant(parsed[ext_id])


@pytest.mark.parametrize(
    "ext_id",
    [
        "50377145",  # Independent Sales Representative
        "50339514",  # Founding Sales (Founding AE)
        "50341447",  # CISO
        "50403646",  # job seeker: "Location: Estonia Remote:Yes ... Willing to relocate: No"
        "50382899",  # job seeker: "I'm Rajneesh Verma, a Full-Stack & AI Engineer ..."
        "50382129",  # "."
    ],
)
def test_not_relevant(parsed: dict[str, ParsedPosting], ext_id: str) -> None:
    assert not hn.is_relevant(parsed[ext_id])


def _comment(text: str) -> RawItem:
    payload = json.dumps({"id": 1, "type": "comment", "time": 1794000000, "text": text})
    return RawItem(external_id="1", url=hn.comment_url(1), payload=payload)


@pytest.mark.parametrize(
    "text",
    [
        "SEEKING WORK | Remote | Full-stack engineer",
        "SEEKING FREELANCE - Egypt (UTC+2) - Remote<p>Senior Full-Stack Engineer (4+ yrs).",
        "Seeking freelance | Backend Developer | Remote",
    ],
)
def test_freelancer_thread_seekers_are_not_postings(text: str) -> None:
    assert not hn.is_relevant(hn.parse(_comment(text)))


def test_seeking_freelancer_is_a_client_not_a_company() -> None:
    p = hn.parse(
        _comment("SEEKING FREELANCER | Devops Engineer | Remote - UK or EU<p>We need help.")
    )
    assert hn.is_relevant(p)
    assert p.company_name is None  # the tag is not a company; the header states none
    assert p.title == "Devops Engineer"
    assert p.location_text == "Remote - UK or EU"
    assert p.job_type == "freelance"  # stated by the tag itself


def test_derived_fields_on_hn_text(parsed: dict[str, ParsedPosting]) -> None:
    row = pipeline.posting_row(parsed["50338732"])
    assert row["work_setup"] == "remote"
    assert row["ph_eligible"] is True  # "REMOTE (worldwide, any timezone)"
    assert row["job_type"] == "full_time"  # "| Full-time, 32h, 24h possible |"
    assert (row["salary_currency"], row["salary_period"]) == ("EUR", "month")
    assert pipeline.posting_row(parsed["50349601"])["ph_eligible"] is True  # names PH


# --------------------------------------------------------------------------- incremental fetch


def _client_from_fixture(pages: list, requested: list[str]) -> HttpClient:
    bodies = {p.url: p.text for p in pages}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url not in bodies:  # a kid we didn't capture (deleted later): HN returns null
            return httpx.Response(200, text="null")
        return httpx.Response(200, text=bodies[url])

    return HttpClient(user_agent="job-radar-test", transport=httpx.MockTransport(handler),
                      sleep=lambda _s: None)  # fmt: skip


def test_fetch_pages_full_crawl_offline(pages: list) -> None:
    requested: list[str] = []
    with _client_from_fixture(pages, requested) as client:
        fetched = list(hn.fetch_pages(client))
    assert [p.url for p in fetched] == [p.url for p in pages]
    assert requested[0].endswith("/user/whoishiring.json")


def test_fetch_pages_skips_ids_on_listing_returns(pages: list) -> None:
    requested: list[str] = []
    listed: list[list[str]] = []
    skip = {"50338732", "50342723"}

    def on_listing(ids: list[str]) -> set[str]:
        listed.append(ids)
        return skip

    with _client_from_fixture(pages, requested) as client:
        fetched = list(hn.fetch_pages(client, on_listing=on_listing))
    assert len(listed) == 1 and len(listed[0]) == 247  # the whole thread is reported
    assert len(fetched) == len(pages) - 2
    assert not any(hn.item_url(i) in requested for i in skip)


def test_is_final_after_edit_window() -> None:
    posted = datetime(2026, 11, 2, 16, 0, tzinfo=UTC)
    payload = json.dumps({"id": 1, "time": int(posted.timestamp())})
    assert not hn.is_final(payload, posted + timedelta(minutes=30))  # could still be edited
    assert hn.is_final(payload, posted + timedelta(hours=2))
    assert not hn.is_final("not json", posted)


def test_pipeline_dry_run_over_fixture() -> None:
    stats = pipeline.run(hn, pipeline.pages_from_fixture(hn, FIXTURE), loader=None)
    assert (stats.pages, stats.items, stats.parsed) == (249, 207, 207)
    assert stats.errors == []
    assert len(stats.relevant) == 156
