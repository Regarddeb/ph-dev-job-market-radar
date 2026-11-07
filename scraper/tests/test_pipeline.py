"""Pipeline logic against the Remote OK fixture, without a database."""

from __future__ import annotations

from pathlib import Path

import pytest

from scraper import pipeline
from scraper.models import ParsedPosting, RawItem
from scraper.sources import remoteok

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "2026-11-06.json"


def test_dry_run_over_fixture() -> None:
    stats = pipeline.run(remoteok, pipeline.pages_from_fixture(remoteok, FIXTURE), loader=None)
    assert (stats.pages, stats.items, stats.parsed) == (1, 99, 99)
    assert stats.errors == []
    assert len(stats.relevant) == 36  # title-based dev filter
    assert stats.new_postings == 0


def test_parse_error_is_captured_not_raised() -> None:
    bad = RawItem(external_id="x", url="https://remoteOK.com/remote-jobs/x", payload='{"id": 1}')
    outcome = pipeline.process(remoteok, bad)  # no position -> empty title -> invalid
    assert outcome.posting is None
    assert outcome.error is not None and "ValidationError" in outcome.error


def test_posting_row_has_no_guessed_fields() -> None:
    stats = pipeline.run(remoteok, pipeline.pages_from_fixture(remoteok, FIXTURE), loader=None)
    for p in stats.relevant:
        row = pipeline.posting_row(p)
        assert row["source_url"] == p.source_url
        # PHP amounts are computed in SQL from the monthly figures, never in Python.
        assert "salary_min_php_monthly" not in row
        assert row["seniority"] in {"intern", "junior", "senior", "lead", "unspecified"}
        assert row["ph_eligible"] in {True, False, None}
        if p.company_name:
            assert row["fingerprint"] is not None and len(row["fingerprint"]) == 40


def test_fingerprint_is_stable_and_order_sensitive() -> None:
    a = pipeline.fingerprint("acme", "senior python developer", "remote")
    assert a == pipeline.fingerprint("acme", "senior python developer", "remote")
    assert a != pipeline.fingerprint("acme", "senior python developer", "hybrid")


def test_content_hash_detects_change() -> None:
    assert pipeline.content_hash("a") != pipeline.content_hash("b")
    assert len(pipeline.content_hash("a")) == 64


def test_coverage_report_rows() -> None:
    stats = pipeline.run(remoteok, pipeline.pages_from_fixture(remoteok, FIXTURE), loader=None)
    rows = dict(pipeline.coverage(stats))
    assert rows["Relevant (dev roles)"] == "36"
    assert rows["% with company"].startswith("100%")


def test_salary_fields_structured_annual() -> None:
    stats = pipeline.run(remoteok, pipeline.pages_from_fixture(remoteok, FIXTURE), loader=None)
    vue = next(p for p in stats.relevant if p.external_id == "1137688")
    fields = pipeline.salary_fields(vue)
    assert (fields["salary_currency"], fields["salary_period"]) == ("USD", "year")
    assert vue.salary_min is not None
    assert float(fields["salary_min_monthly"]) == pytest.approx(vue.salary_min / 12)


def test_salary_fields_from_raw_text() -> None:
    p = ParsedPosting(external_id="1", title="Dev", source_url="https://example.com/1",
                      salary_raw="$15-20/hr")  # fmt: skip
    fields = pipeline.salary_fields(p)
    assert (fields["salary_currency"], fields["salary_period"]) == ("USD", "hour")
    assert (fields["salary_min_monthly"], fields["salary_max_monthly"]) == (2400, 3200)


def test_salary_fields_without_period_give_no_monthly() -> None:
    p = ParsedPosting(external_id="1", title="Dev", source_url="https://example.com/1",
                      salary_raw="USD 30 - 36 (period not stated)", salary_currency="USD",
                      salary_min=30, salary_max=36)  # fmt: skip
    fields = pipeline.salary_fields(p)
    assert fields["salary_period"] is None
    assert fields["salary_min_monthly"] is None and fields["salary_max_monthly"] is None
