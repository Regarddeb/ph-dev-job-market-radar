"""Salary text -> (currency, period, min, max), and conversion to a monthly amount.

Rules (docs/SPEC.md §6):
- Keep salary_raw as stated. Parse forms like "₱40k-60k/month", "PHP 50,000", "$15-20/hr",
  "$30,000/yr", "USD 90k - 130k".
- Monthly = hourly x 160, daily x 22, weekly x 52/12, annual / 12.
- PHP conversion uses exchange_rates for the posting's first-seen date; that lookup lives in
  SQL (pipeline.SQL_SALARY_PHP) so it always uses the stored first_seen_at.
- Never guess: no stated period -> period None -> no monthly figure. Unknown currency ->
  None. A bare "$" is read as USD (the convention on the remote boards we use); explicitly
  marked dollars (CA$, A$, S$, NZ$, HK$, and the ISO codes) map to their own currency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from scraper.models import SalaryPeriod

HOURS_PER_MONTH = Decimal(160)
DAYS_PER_MONTH = Decimal(22)
WEEKS_PER_MONTH = Decimal(52) / Decimal(12)
MONTHS_PER_YEAR = Decimal(12)

_TO_MONTHLY: dict[str, Decimal] = {
    "hour": HOURS_PER_MONTH,
    "day": DAYS_PER_MONTH,
    "week": WEEKS_PER_MONTH,
    "month": Decimal(1),
    "year": Decimal(1) / MONTHS_PER_YEAR,
}

# Currency markers, most specific first. Codes are matched as whole words.
_CURRENCY_MARKERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:\bCA\$|\bC\$|\bCAD\b)", re.I), "CAD"),
    (re.compile(r"(?:\bAU\$|\bA\$|\bAUD\b)", re.I), "AUD"),
    (re.compile(r"(?:\bNZ\$|\bNZD\b)", re.I), "NZD"),
    (re.compile(r"(?:\bS\$|\bSGD\b)", re.I), "SGD"),
    (re.compile(r"(?:\bHK\$|\bHKD\b)", re.I), "HKD"),
    (re.compile(r"(?:\bUS\$|\bUSD\b)", re.I), "USD"),
    (re.compile(r"(?:₱|\bPHP\b|\bPhP\b)"), "PHP"),
    (re.compile(r"(?:€|\bEUR\b)", re.I), "EUR"),
    (re.compile(r"(?:£|\bGBP\b)", re.I), "GBP"),
    (re.compile(r"(?:₹|\bINR\b)", re.I), "INR"),
    (re.compile(r"(?:¥|\bJPY\b)", re.I), "JPY"),
    (re.compile(r"\bCHF\b", re.I), "CHF"),
    (re.compile(r"\$"), "USD"),
]

_PERIODS: list[tuple[re.Pattern[str], SalaryPeriod]] = [
    (
        re.compile(r"(?:/\s*|\bper\s+|\ban\s+|\ba\s+)(?:hr|hour)\b|\bhourly\b", re.I),
        "hour",
    ),
    (re.compile(r"(?:/\s*|\bper\s+|\ba\s+)day\b|\bdaily\b|\bper\s+diem\b", re.I), "day"),
    (re.compile(r"(?:/\s*|\bper\s+|\ba\s+)(?:wk|week)\b|\bweekly\b", re.I), "week"),
    (re.compile(r"(?:/\s*|\bper\s+|\ba\s+)(?:mo|mos|mth|month)\b|\bmonthly\b", re.I), "month"),
    (
        re.compile(
            r"(?:/\s*|\bper\s+|\ba\s+)(?:yr|year|annum)\b|\bannual(?:ly)?\b|\bp\.?a\.?(?!\w)"
            r"|\byearly\b",
            re.I,
        ),
        "year",
    ),
]

# A number like 40, 40.5, 40,000, 1,200.50, 1.2m, 90k. Bounded quantifiers keep it linear.
_NUM = r"(\d{1,3}(?:,\d{3}){1,3}(?:\.\d{1,2})?|\d{1,9}(?:\.\d{1,2})?)\s?([km])?\b"
# Range separators: hyphen, en dash, em dash, "to". The second end may repeat the currency.
_SEP = "(?:-|\u2013|\u2014|to)"
_RANGE = _NUM + r"(?:\s?" + _SEP + r"\s?(?:[^\d\s]{1,4}\s?)?" + _NUM + r")?"
# The amount must sit right next to the currency marker: "$100k", "USD 90k", "50,000 PHP".
# Otherwise stray numbers win ("5+ years, $100k" -> 5; "$10M ARR, $5k/mo" -> 10M).
_AFTER_MARKER = re.compile(r"\s?" + _RANGE, re.I)
_BEFORE_MARKER = re.compile(_RANGE + r"\s?$", re.I)
# "60.000" (European thousands separator) is ambiguous with a decimal: refuse it.
_DOT_THOUSANDS = re.compile(r"\d{1,3}(?:\.\d{3})+(?!\d)")


@dataclass(frozen=True)
class Salary:
    currency: str
    period: SalaryPeriod | None
    minimum: Decimal
    maximum: Decimal


def _amount(digits: str, suffix: str | None) -> Decimal:
    value = Decimal(digits.replace(",", ""))
    if suffix:
        value *= 1000 if suffix.lower() == "k" else 1_000_000
    return value


def _find_currency(text: str) -> tuple[str, re.Pattern[str]] | None:
    for pattern, code in _CURRENCY_MARKERS:
        if pattern.search(text):
            return code, pattern
    return None


def _amount_matches(text: str, marker: re.Pattern[str]) -> list[re.Match[str]]:
    """Amounts written next to each occurrence of the currency marker.

    A marker inside an earlier match ("$40k - $60k") belongs to that range.
    """
    found: list[re.Match[str]] = []
    for m in marker.finditer(text):
        if found and m.start() < found[-1].end():
            continue
        hit = _AFTER_MARKER.match(text, m.end()) or _BEFORE_MARKER.search(text, 0, m.start())
        if hit and not any(hit.span() == f.span() for f in found):
            found.append(hit)
    return found


def detect_currency(text: str) -> str | None:
    found = _find_currency(text)
    return found[0] if found else None


def detect_period(text: str) -> SalaryPeriod | None:
    found = {period for pattern, period in _PERIODS if pattern.search(text)}
    return found.pop() if len(found) == 1 else None  # two different periods: ambiguous


def _looks_like_year(digits: str, suffix: str | None) -> bool:
    return suffix is None and len(digits) == 4 and digits[:2] in ("19", "20")


def parse_salary(text: str | None) -> Salary | None:
    """Parse one salary statement. None unless a currency and an amount next to it are
    stated, and the amount is unambiguous."""
    if not text or len(text) > 200:  # a salary line, not a whole description
        return None
    found = _find_currency(text)
    if found is None:
        return None
    currency, marker = found
    matches = _amount_matches(text, marker)
    if len(matches) != 1:
        return None  # no amount, or two separate amounts ("$10M ARR, $5k/mo"): ambiguous
    match = matches[0]
    number_start = match.start(1)
    if _DOT_THOUSANDS.match(text, number_start):
        return None
    lo_digits, lo_suffix, hi_digits, hi_suffix = match.groups()
    if hi_digits is None:
        lo = hi = _amount(lo_digits, lo_suffix)
    else:
        # "40-60k": the suffix written once applies to both ends.
        lo = _amount(lo_digits, lo_suffix or hi_suffix)
        hi = _amount(hi_digits, hi_suffix)
    period = detect_period(text)
    if period is None and _looks_like_year(lo_digits, lo_suffix):
        return None  # "USD 2025 bonus": a year, not an amount
    if lo <= 0 or hi <= 0 or lo > hi:
        return None
    return Salary(currency=currency, period=period, minimum=lo, maximum=hi)


def to_monthly(amount: Decimal | float, period: str | None) -> Decimal | None:
    """Amount per `period` -> amount per month. None when the period is unknown."""
    if period is None or period not in _TO_MONTHLY:
        return None
    return Decimal(str(amount)) * _TO_MONTHLY[period]
