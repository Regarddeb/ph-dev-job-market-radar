"""scraper/dedupe.py: exact + fuzzy duplicate detection (pure logic, no database)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scraper.dedupe import Candidate, find_duplicates
from scraper.models import Page
from scraper.normalize.text import normalize_company
from scraper.pipeline import posting_row
from scraper.sources import remoteok

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "2026-11-06.json"
T0 = datetime(2026, 11, 1, tzinfo=UTC)
DESC = "We build payments infrastructure. You will own our Go services and Postgres. " * 5


def cand(id_: int, title: str = "senior go engineer", *, company: str | None = "acme",
         fp: str | None = None, days: float = 0, desc: str | None = DESC) -> Candidate:  # fmt: skip
    return Candidate(id_, company, title, fp, T0 + timedelta(days=days), desc)


def test_exact_fingerprint_within_window() -> None:
    found = find_duplicates([cand(1, fp="f"), cand(2, fp="f", days=10, desc=None)])
    assert found[2].canonical_id == 1 and found[2].reason == "exact"  # no description needed


def test_exact_outside_window_is_not_a_duplicate() -> None:
    assert find_duplicates([cand(1, fp="f"), cand(2, fp="f", days=31)]) == {}


def test_canonical_is_the_earliest_regardless_of_input_order() -> None:
    found = find_duplicates([cand(9, fp="f", days=5), cand(3, fp="f", days=1)])
    assert found == {9: found[9]} and found[9].canonical_id == 3


def test_same_day_tie_breaks_on_lowest_id() -> None:
    found = find_duplicates([cand(8, fp="f"), cand(4, fp="f")])
    assert list(found) == [8] and found[8].canonical_id == 4


def test_fuzzy_title_and_description() -> None:
    found = find_duplicates(
        [cand(1, "senior go engineer"), cand(2, "senior go engineer remote", days=3)]
    )
    assert found[2].canonical_id == 1 and found[2].reason == "fuzzy"


def test_fuzzy_needs_both_descriptions() -> None:
    assert find_duplicates([cand(1), cand(2, days=1, desc=None)]) == {}


def test_fuzzy_needs_similar_descriptions() -> None:
    other = "Join our data team to build ML pipelines in Python and Spark. " * 5
    assert find_duplicates([cand(1), cand(2, days=1, desc=other)]) == {}


def test_fuzzy_needs_similar_titles() -> None:
    assert find_duplicates([cand(1, "senior go engineer"), cand(2, "product designer")]) == {}


def test_different_companies_never_match() -> None:
    assert find_duplicates([cand(1, fp="f"), cand(2, fp="f", company="globex")]) == {}


def test_no_company_never_matches() -> None:
    assert find_duplicates([cand(1, company=None, fp="f"), cand(2, company=None, fp="f")]) == {}


def test_duplicates_point_at_the_root_not_at_each_other() -> None:
    found = find_duplicates([cand(1, fp="f"), cand(2, fp="f", days=5), cand(3, fp="f", days=10)])
    assert {k: m.canonical_id for k, m in found.items()} == {2: 1, 3: 1}


# --------------------------------------------------------------------------- fixture


@pytest.fixture(scope="module")
def fixture_candidates() -> dict[str, Candidate]:
    page = Page(url="fixture", text=FIXTURE.read_text(encoding="utf-8"))
    out: dict[str, Candidate] = {}
    for i, raw in enumerate(remoteok.split(page)):
        p = remoteok.parse(raw)
        if not remoteok.is_relevant(p):
            continue
        row = posting_row(p)
        out[raw.external_id] = Candidate(
            id=i + 1,
            company=normalize_company(p.company_name) if p.company_name else None,
            title=row["title_normalized"],
            fingerprint=row["fingerprint"],
            first_seen=T0,
            description=p.description,
        )
    return out


def test_fixture_has_no_duplicates(fixture_candidates: dict[str, Candidate]) -> None:
    # Includes Lemon.io's three roles, which share most of their description (Vue vs
    # DevOps scores 91 on description) but are different jobs.
    assert find_duplicates(fixture_candidates.values()) == {}


def test_fixture_repost_is_caught(fixture_candidates: dict[str, Candidate]) -> None:
    vue = fixture_candidates["1137688"]  # Lemon.io, Senior Vue Developer
    repost = replace(vue, id=9999, first_seen=T0 + timedelta(days=7))
    found = find_duplicates([*fixture_candidates.values(), repost])
    assert {k: m.canonical_id for k, m in found.items()} == {9999: vue.id}
    assert found[9999].reason == "exact"


def test_fixture_retitled_repost_is_caught_fuzzily(
    fixture_candidates: dict[str, Candidate],
) -> None:
    vue = fixture_candidates["1137688"]
    retitled = replace(
        vue, id=9999, title="senior vue.js developer remote", fingerprint=None,
        first_seen=T0 + timedelta(days=2),
    )  # fmt: skip
    found = find_duplicates([*fixture_candidates.values(), retitled])
    assert found[9999].canonical_id == vue.id and found[9999].reason == "fuzzy"
