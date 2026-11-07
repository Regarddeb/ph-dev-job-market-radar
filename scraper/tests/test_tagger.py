"""normalize/skills.py: the tagger and requirements-section extraction.

Per-alias positive/negative examples live in skills.json and run in test_skills.py; these
tests cover how the tagger applies them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scraper.models import Page
from scraper.normalize.skills import Alias, Tagger, requirements_section
from scraper.sources import remoteok

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "2026-11-06.json"

DESCRIPTION = """About us
We build payment rails in Go and serve customers worldwide.
Requirements:
5+ years with Python
Experience with R for analysis
Benefits
Free coffee, C level access
"""


@pytest.fixture(scope="module")
def tagger() -> Tagger:
    return Tagger.from_json()


def test_requirements_section_stops_at_next_heading() -> None:
    assert (
        requirements_section(DESCRIPTION) == "5+ years with Python\nExperience with R for analysis"
    )


@pytest.mark.parametrize(
    "heading", ["Requirements", "What you'll need:", "What you’ll bring", "Tech stack", "About you"]
)
def test_requirements_headings(heading: str) -> None:
    assert requirements_section(f"Intro\n{heading}\nRust\nBenefits\nPTO") == "Rust"


def test_requirements_section_empty() -> None:
    assert requirements_section(None) == ""
    assert requirements_section("No headings here, Python everywhere.") == ""


def test_requirements_only_alias_ignores_text_outside_the_section() -> None:
    t = Tagger([Alias("R", re.compile(r"\b(?-i:R)\b", re.I), requirements_only=True)])
    assert t.tag("Data Engineer", DESCRIPTION) == {"R"}
    assert t.tag("Data Engineer", "R is mentioned in passing.\nNo requirements heading.") == set()


def test_tag_title_and_description(tagger: Tagger) -> None:
    found = tagger.tag("Senior Python Developer", "Stack: Django, PostgreSQL and React.")
    assert {"Python", "Django", "PostgreSQL", "React"} <= found


def test_tag_negatives(tagger: Tagger) -> None:
    found = tagger.tag("Developer", "Node.js backend. Salary PHP 50,000. Let's go to market.")
    assert "Node.js" in found
    assert "PHP" not in found  # the currency, not the language
    assert "Go" not in found  # the verb, not the language
    assert "JavaScript" not in found  # "Node.js" alone isn't JavaScript


def test_tag_empty(tagger: Tagger) -> None:
    assert tagger.tag("Account Executive", None) == set()


def test_fixture_tags(tagger: Tagger) -> None:
    page = Page(url="fixture", text=FIXTURE.read_text(encoding="utf-8"))
    parsed = {raw.external_id: remoteok.parse(raw) for raw in remoteok.split(page)}

    def tags(ext_id: str) -> set[str]:
        p = parsed[ext_id]
        return tagger.tag(p.title, p.description)

    assert {"Django", "Python", "React", "TypeScript"} <= tags("1137572")  # Sr SWE LATAM
    assert {"Go", "Node.js"} <= tags("1137551")  # Senior Backend Engineer
    assert tags("1137534") == {"Python"}  # APAC Python
