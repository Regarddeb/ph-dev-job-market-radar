"""normalize/classify.py: dev-role filter, seniority, job type, work setup, ph_eligible.

Unit cases use phrasing taken from real postings; the fixture tests at the bottom pin the
results on the 2026-11-06 Remote OK fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scraper.models import Page, ParsedPosting
from scraper.normalize import classify
from scraper.pipeline import posting_row
from scraper.sources import remoteok

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok" / "2026-11-06.json"

# --------------------------------------------------------------------------- dev roles


@pytest.mark.parametrize(
    "title",
    [
        "Senior Vue Developer",
        "Software Engineer Infrastructure",
        "AWS Cloud Solutions Architect",
        "Tech lead",
        "Head of Technology",
        "APAC Python",
        "DESARROLLADOR FULL STACK",
        "QA Tester Entry Level",
        "Senior DevOps Engineer",
        "Frontend Engineer",
        "Site Reliability Engineer",
    ],
)
def test_dev_titles(title: str) -> None:
    assert classify.is_dev_title(title)


@pytest.mark.parametrize(
    "title",
    [
        "Sales Operations Analyst",  # slipped through on tags before the title check
        "Tax Manager Private Client",
        "Senior Property Manager ENG",
        "Client Accounting Division Manager",
        "Partner Operations Manager",
        "Scientific Account Executive",
        "Contract Recruiter",
        "Technical Account Manager",
        "Sales Engineer",
        "Mechanical Engineer",
        "Data Analyst",
        "Architectural Designer",
        "Technical Product Manager AI Stockbroking App",
    ],
)
def test_non_dev_titles(title: str) -> None:
    assert not classify.is_dev_title(title)


# --------------------------------------------------------------------------- seniority


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("Senior Staff Infrastructure & Security Engineer", "lead"),  # staff wins (rule 1)
        ("Principal Engineer", "lead"),
        ("Tech lead", "lead"),
        ("Senior Backend Engineer", "senior"),
        ("Sr Solutions Architect", "senior"),
        ("Sr. Python Developer", "senior"),
        ("Software Engineering Intern", "intern"),
        ("Internship: Frontend", "intern"),
        ("Junior React Developer", "junior"),
        ("Jr. Developer", "junior"),
        ("QA Tester Entry Level", "junior"),
        ("Entry-level Engineer", "junior"),
        ("Software Engineer II", "unspecified"),
        ("Internal Tools Engineer", "unspecified"),  # "intern" needs a word boundary
        ("Leading Edge Developer", "unspecified"),
        ("Head of Technology", "unspecified"),  # not in the rules: not guessed
    ],
)
def test_seniority(title: str, level: str) -> None:
    assert classify.seniority(title) == level


# --------------------------------------------------------------------------- job type


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Part-time React Developer", None, "part_time"),
        ("Freelance Designer", None, "freelance"),
        ("Contract Python Developer", None, "contract"),
        ("Full-time Go Engineer", None, "full_time"),
        ("Dev", "This is a full-time role requiring a 40-hour work week.", "full_time"),
        ("Dev", "Reports to: Director\nClassification: Regular, Full-time", "full_time"),
        ("Dev", "Remote, Brazil, Full Time, Individual Contributor", "full_time"),
        ("Dev", "Full-time / Remote / Office Opportunity", "full_time"),
        ("Dev", "Type: Full-time contractor. Start in December.", "contract"),
        ("Dev", "Contract: most roles are contract-based.", "contract"),
        ("Dev", "This role is a one year contract position.", "contract"),
        ("Dev", "Please note: This is a part-time freelance position.", "part_time"),
        ("Dev", "Project-based | Remote | United States | Contract", "freelance"),
    ],
)
def test_job_type_stated(title: str, description: str | None, expected: str) -> None:
    assert classify.job_type("unspecified", title, description) == expected


@pytest.mark.parametrize(
    "description",
    [
        "Experience writing smart contracts in Solidity.",
        "Own CDS Hook API contracts and evolution.",
        "From first contact to signed contract.",
        "Perks/Benefits we offer for full-time team members.",  # about others, not this job
        "Senior consulting engagement — full-time or contract.",  # conflict
        "Remote or Berlin · Full time · Permanent or contract",  # conflict
        "You work full-time remotely and deliver without supervision",
    ],
)
def test_job_type_not_guessed(description: str) -> None:
    assert classify.job_type("unspecified", "Developer", description) == "unspecified"


def test_job_type_source_field_wins() -> None:
    assert classify.job_type("contract", "Full-time Developer", None) == "contract"


# --------------------------------------------------------------------------- work setup


@pytest.mark.parametrize(
    ("source", "title", "location", "expected"),
    [
        ("remote", "Developer", "Boston", "remote"),  # the source's own field first
        ("unspecified", "Developer (Remote)", None, "remote"),
        ("unspecified", "Developer", "WFH", "remote"),
        ("unspecified", "Developer", "Hybrid - Makati", "hybrid"),
        ("unspecified", "Developer", "Hybrid, 2 days remote", "hybrid"),
        ("unspecified", "Developer", "Onsite, Cebu", "onsite"),
        ("unspecified", "Developer", "Makati", "unspecified"),
    ],
)
def test_work_setup(source: str, title: str, location: str | None, expected: str) -> None:
    assert classify.work_setup(source, title, location) == expected  # type: ignore[arg-type]


# --------------------------------------------------------------------------- ph_eligible


@pytest.mark.parametrize(
    ("title", "location", "description"),
    [
        ("Developer", "Philippines", None),
        ("Developer", "Anywhere in the World", None),
        ("Developer", "Worldwide", None),
        ("Developer", "APAC", None),
        ("APAC Python", None, None),
        ("Dev", None, "selected countries in Asia (Japan, Singapore, the Philippines, Vietnam)"),
        ("Dev", None, "You can be based anywhere. A lot of our people are in New York."),
        ("Dev", None, "Remote work from anywhere"),
        ("Dev", None, "We are hiring Filipino developers."),
        ("Dev", None, "Open to candidates in APAC time zones."),
    ],
)
def test_ph_eligible_positive(title: str, location: str | None, description: str | None) -> None:
    assert classify.ph_eligible(title, location, description) is True


@pytest.mark.parametrize(
    ("title", "location", "description"),
    [
        ("Developer", "US", None),
        ("Developer", "Remote - US", None),
        ("Developer", "United States", None),
        ("Senior Software Engineer LATAM", None, None),
        ("Dev", None, "Must be legally authorized to work in the US. Bachelor's preferred."),
        ("Dev", None, "Candidates must be authorized to work in the United States"),
        ("Dev", None, "Work from anywhere in Canada and USA"),
        ("Dev", None, "This is a remote position that can be located anywhere in the US or Canada"),
        ("Dev", None, "US only."),
        ("Dev", None, "You must reside in Germany."),
        ("Dev", None, "Requires US work authorization."),
        ("Dev", None, "EU timezone required."),
        # an explicit negative beats a generic positive
        ("Dev", "Worldwide", "Must be authorized to work in the US."),
    ],
)
def test_ph_eligible_negative(title: str, location: str | None, description: str | None) -> None:
    assert classify.ph_eligible(title, location, description) is False


@pytest.mark.parametrize(
    ("title", "location", "description"),
    [
        ("Developer", None, None),
        ("Developer", "Boston", None),  # a city isn't an eligibility statement
        # marketing copy, not hiring scope
        ("Dev", None, "Trusted by hundreds of millions worldwide."),
        ("Dev", None, "The leading insurance platform in Southeast Asia."),
        ("Dev", None, "Send payouts to anyone, anywhere, instantly."),
        ("Dev", None, "Don't publish the work anywhere: no public pull request."),
        ("Dev", None, "Customers across Europe, North America, Asia-Pacific and beyond."),
        # overlap with US hours is not a residency rule
        ("Dev", None, "Available to work in US time zones (graveyard shift)."),
        ("Dev", None, "Be able to work in US hours."),
        ("Dev", None, "Let us only hire the best; join us."),  # "us" isn't the US
        # conflict: the Philippines named, and an explicit negative
        ("Dev", "Philippines", "Must be authorized to work in the US."),
    ],
)
def test_ph_eligible_unknown(title: str, location: str | None, description: str | None) -> None:
    assert classify.ph_eligible(title, location, description) is None


# --------------------------------------------------------------------------- fixture


@pytest.fixture(scope="module")
def rows() -> dict[str, dict]:
    page = Page(url="fixture", text=FIXTURE.read_text(encoding="utf-8"))
    parsed: dict[str, ParsedPosting] = {
        raw.external_id: remoteok.parse(raw) for raw in remoteok.split(page)
    }
    return {i: posting_row(p) for i, p in parsed.items() if remoteok.is_relevant(p)}


def test_fixture_relevance_count(rows: dict[str, dict]) -> None:
    assert len(rows) == 36


@pytest.mark.parametrize(
    ("ext_id", "field", "value"),
    [
        ("1137688", "seniority", "senior"),  # Senior Vue Developer
        ("1137687", "seniority", "lead"),  # Senior Staff ... Engineer
        ("1136701", "seniority", "junior"),  # QA Tester Entry Level
        ("1137685", "job_type", "contract"),  # "Type: Full-time contractor"
        ("1137597", "job_type", "full_time"),  # "Classification: Regular, Full-time"
        ("1137534", "job_type", "part_time"),  # "a part-time freelance position"
        ("1137571", "job_type", "unspecified"),  # "Full time · Permanent or contract"
        ("1137688", "ph_eligible", True),  # "selected countries in Asia (... Philippines"
        ("1137534", "ph_eligible", True),  # APAC Python
        ("1137597", "ph_eligible", False),  # authorized to work in the US
        ("1137527", "ph_eligible", False),  # anywhere in Canada and USA
        ("1137572", "ph_eligible", False),  # ... LATAM
        ("1137538", "ph_eligible", None),  # "publish the work anywhere" is not a positive
        ("1137688", "work_setup", "remote"),  # Remote OK is remote-only
    ],
)
def test_fixture_values(rows: dict[str, dict], ext_id: str, field: str, value: object) -> None:
    assert rows[ext_id][field] == value


def test_fixture_never_guesses_mid(rows: dict[str, dict]) -> None:
    # No rule yields "mid"; unknown levels must stay unspecified.
    assert all(r["seniority"] != "mid" for r in rows.values())


@pytest.mark.parametrize(
    "probe",
    [
        "a" * 20000,
        "work " * 4000,
        "full time " * 2000,
        "hiring " + "x " * 5000 + "asia",
        "$" + "1," * 5000,
        "\n".join(["Requirements"] * 3000),
    ],
)
def test_rules_run_in_linear_time(probe: str) -> None:
    import time

    from scraper.normalize.salary import parse_salary
    from scraper.normalize.skills import requirements_section

    start = time.perf_counter()
    classify.is_dev_title(probe)
    classify.seniority(probe)
    classify.job_type("unspecified", probe, probe)
    classify.work_setup("unspecified", probe, probe)
    classify.ph_eligible(probe, probe, probe)
    parse_salary(probe[:200])
    requirements_section(probe)
    assert time.perf_counter() - start < 0.5


# --------------------------------------------------------------------------- review fixes


@pytest.mark.parametrize(
    ("title", "location", "description"),
    [
        ("Dev", None, "We cannot hire in the Philippines at this time."),
        ("Dev", "Anywhere except the Philippines", None),
        ("Dev", "Worldwide", "Candidates from the Philippines are not eligible."),
        ("Dev", None, "We are not currently accepting applicants from the Philippines."),
    ],
)
def test_ph_named_negatives_are_false(
    title: str, location: str | None, description: str | None
) -> None:
    assert classify.ph_eligible(title, location, description) is False


def test_time_zone_overlap_with_qualifier_is_not_residency() -> None:
    text = "You must be able to work in the US Eastern time zone."
    assert classify.ph_eligible("Dev", None, text) is None


def test_title_region_with_a_positive_is_a_conflict() -> None:
    assert classify.ph_eligible("Software Engineer (US or APAC)", None, None) is None
    assert classify.ph_eligible("Senior Software Engineer LATAM", None, None) is False


@pytest.mark.parametrize("title", ["Smart Contract Engineer", "Solidity Smart-Contract Developer"])
def test_smart_contract_title_is_not_a_job_type(title: str) -> None:
    assert classify.job_type("unspecified", title, None) == "unspecified"
