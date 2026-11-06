"""Pipeline logic against the Remote OK fixture, without a database."""

from __future__ import annotations

from pathlib import Path

from scraper import pipeline
from scraper.models import RawItem
from scraper.sources import remoteok

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "2026-11-06.json"


def test_dry_run_over_fixture() -> None:
    stats = pipeline.run(remoteok, pipeline.pages_from_fixture(remoteok, FIXTURE), loader=None)
    assert (stats.pages, stats.items, stats.parsed) == (1, 99, 99)
    assert stats.errors == []
    assert len(stats.relevant) == 73
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
        # Derived fields are not in the row at all until build step 5.
        assert not {"seniority", "ph_eligible", "salary_min_php_monthly"} & row.keys()
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
    assert rows["Relevant (dev roles)"] == "73"
    assert rows["% with company"].startswith("100%")
