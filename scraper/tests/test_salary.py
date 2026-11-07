"""normalize/salary.py: text parsing and monthly conversion (docs/SPEC.md §6)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scraper.normalize.salary import Salary, detect_period, parse_salary, to_monthly

D = Decimal


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The SPEC's example forms.
        ("₱40k–60k/month", Salary("PHP", "month", D(40000), D(60000))),
        ("PHP 50,000", Salary("PHP", None, D(50000), D(50000))),
        ("$15–20/hr", Salary("USD", "hour", D(15), D(20))),
        ("$30,000/yr", Salary("USD", "year", D(30000), D(30000))),
        ("USD 90k - 130k", Salary("USD", None, D(90000), D(130000))),
        # Other real-world shapes.
        ("USD 60,000 - 110,000/year", Salary("USD", "year", D(60000), D(110000))),
        ("$110 - $175 p/hr", Salary("USD", "hour", D(110), D(175))),
        ("EUR 53,000 – 59,000 per annum", Salary("EUR", "year", D(53000), D(59000))),
        ("£45k-55k a year", Salary("GBP", "year", D(45000), D(55000))),
        ("CA$120k to CA$140k annually", Salary("CAD", "year", D(120000), D(140000))),
        ("S$6,000 monthly", Salary("SGD", "month", D(6000), D(6000))),
        ("₱800/day", Salary("PHP", "day", D(800), D(800))),
        ("$1.2m/yr", Salary("USD", "year", D(1200000), D(1200000))),
    ],
)
def test_parse_salary(text: str, expected: Salary) -> None:
    assert parse_salary(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "Competitive",
        "DOE",
        "40k-60k",  # no currency stated: never assume one
        "$90k - $50k",  # min > max: contradictory
        "$0",
        "x" * 300,  # a paragraph, not a salary line
    ],
)
def test_parse_salary_rejects(text: str | None) -> None:
    assert parse_salary(text) is None


@pytest.mark.parametrize(
    ("text", "period"),
    [
        ("$20/hr", "hour"),
        ("$20 an hour", "hour"),
        ("$20 hourly", "hour"),
        ("₱800 per day", "day"),
        ("$900/wk", "week"),
        ("₱60k/mo", "month"),
        ("$90k p.a.", "year"),
        ("$90k annually", "year"),
        ("$90k", None),  # unstated: no period is guessed
        ("PH-based, $20", None),  # "PH" is the Philippines, not "per hour"
        ("$20/hr or $3,000/month", None),  # two periods: ambiguous
    ],
)
def test_detect_period(text: str, period: str | None) -> None:
    assert detect_period(text) == period


@pytest.mark.parametrize(
    ("amount", "period", "monthly"),
    [
        (20, "hour", D(3200)),  # x 160
        (1000, "day", D(22000)),  # x 22
        (1200, "week", D(5200)),  # x 52/12
        (50000, "month", D(50000)),
        (120000, "year", D(10000)),  # / 12
    ],
)
def test_to_monthly(amount: int, period: str, monthly: Decimal) -> None:
    assert to_monthly(amount, period) == pytest.approx(monthly)


def test_to_monthly_unknown_period_is_none() -> None:
    assert to_monthly(50000, None) is None
    assert to_monthly(50000, "fortnight") is None


# Review fixes: the amount must sit next to the currency, and ambiguous forms are refused.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5+ years, $100k/yr", Salary("USD", "year", D(100000), D(100000))),
        ("$1,200.50/mo", Salary("USD", "month", D("1200.50"), D("1200.50"))),
        ("50,000 PHP monthly", Salary("PHP", "month", D(50000), D(50000))),
        ("90k USD per year", Salary("USD", "year", D(90000), D(90000))),
    ],
)
def test_parse_salary_anchors_to_the_currency(text: str, expected: Salary) -> None:
    assert parse_salary(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "€60.000 - €80.000 per year",  # dot thousands: ambiguous with a decimal
        "USD 2025 bonus",  # a year, no period
        "$10M ARR, $5k/mo",  # two separate amounts
        "Benefits in USD; 3 weeks PTO",  # no amount next to the marker
    ],
)
def test_parse_salary_refuses_ambiguous(text: str) -> None:
    assert parse_salary(text) is None
