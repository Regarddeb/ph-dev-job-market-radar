"""Remote OK adapter against the saved fixture (never the live API)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scraper.models import Page, ParsedPosting
from scraper.sources import remoteok

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "2026-11-06.json"


@pytest.fixture(scope="module")
def page() -> Page:
    return Page(url=remoteok.API_URL, text=FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parsed(page: Page) -> dict[str, ParsedPosting]:
    return {p.external_id: p for p in map(remoteok.parse, remoteok.split(page))}


def test_skips_legal_notice_and_keeps_all_jobs(page: Page) -> None:
    data = json.loads(page.text)
    assert "legal" in data[0]
    items = list(remoteok.split(page))
    assert len(items) == len(data) - 1 == 99
    assert len({i.external_id for i in items}) == 99


def test_raw_payload_round_trips(page: Page) -> None:
    item = next(remoteok.split(page))
    job = json.loads(item.payload)
    assert str(job["id"]) == item.external_id
    assert job["url"] == item.url


def test_every_item_parses_with_attribution_url(parsed: dict[str, ParsedPosting]) -> None:
    assert len(parsed) == 99
    for p in parsed.values():
        assert p.source_url.startswith("https://remoteOK.com/remote-jobs/")
        assert p.source_url.endswith(p.external_id)
        assert p.work_setup == "remote"
        assert p.job_type == "unspecified"  # not stated as a field; classify.py decides later


def test_representative_posting(parsed: dict[str, ParsedPosting]) -> None:
    p = parsed["1137688"]
    assert p.title == "Senior Vue Developer"
    assert p.company_name == "Lemon.io"
    assert p.location_text is None
    assert p.posted_at == datetime(2026, 11, 5, 12, 45, 45, tzinfo=UTC)
    assert p.salary_raw == "USD 50,000 - 180,000/year"
    assert (p.salary_currency, p.salary_period) == ("USD", "year")
    assert (p.salary_min, p.salary_max) == (50000.0, 180000.0)
    assert "javascript" in p.tags and "full stack" in p.tags
    assert p.description is not None
    assert p.description.startswith("Lemon.io helps companies in the US and Europe")


def test_small_salary_values_get_no_period(parsed: dict[str, ParsedPosting]) -> None:
    # 30-36 USD is clearly not annual; we keep it but refuse to guess the period.
    p = parsed["1137155"]
    assert p.salary_raw == "USD 30 - 36 (period not stated)"
    assert p.salary_currency == "USD"
    assert p.salary_period is None
    assert (p.salary_min, p.salary_max) == (30.0, 36.0)


def test_missing_salary_stays_null(parsed: dict[str, ParsedPosting]) -> None:
    no_salary = [p for p in parsed.values() if p.salary_raw is None]
    assert len(no_salary) == 99 - 28
    for p in no_salary:
        assert p.salary_currency is p.salary_period is p.salary_min is p.salary_max is None


def test_text_is_cleaned(parsed: dict[str, ParsedPosting]) -> None:
    assert parsed["1137677"].location_text == "München"  # mojibake in source data
    assert parsed["1137680"].title == "Entry Level Scheduling & Coordinating Reservations Online"
    assert parsed["1137155"].title.startswith("Oracle Fusion Cloud Lead — Logistics")
    assert "Penumbra’s commitment" in (parsed["1137550"].description or "")


def test_inline_html_stays_on_one_line(parsed: dict[str, ParsedPosting]) -> None:
    desc = parsed["1137479"].description or ""
    assert desc.startswith("Location: 100% remote (Ohio residency required)\nClassification:")


def test_relevance_keeps_developer_roles_only(parsed: dict[str, ParsedPosting]) -> None:
    relevant = {i for i, p in parsed.items() if remoteok.is_relevant(p)}
    assert len(relevant) == 73
    assert "1137688" in relevant  # Senior Vue Developer
    for non_dev in ("1137479", "1137677", "1137680"):  # dean, M&A intern, travel booking
        assert non_dev not in relevant


def test_contradictory_salary_is_dropped() -> None:
    payload = json.dumps(
        {"id": 1, "position": "Dev", "url": "https://remoteOK.com/remote-jobs/1",
         "salary_min": 90000, "salary_max": 50000, "tags": ["dev"]}
    )  # fmt: skip
    p = remoteok.parse(
        remoteok.RawItem(external_id="1", url="https://remoteOK.com/remote-jobs/1", payload=payload)
    )
    assert p.salary_raw is None and p.salary_min is None
