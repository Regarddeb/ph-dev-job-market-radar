"""scraper/fx.py: ECB reference rates -> PHP per unit (cross rates), from a saved fixture."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scraper import fx

FIXTURE = Path(__file__).parent / "fixtures" / "ecb" / "2026-11-07-hist-90d.xml"


@pytest.fixture(scope="module")
def rates() -> list[fx.Rate]:
    return fx.parse_xml(FIXTURE.read_bytes())


def test_xml_fixture_shape(rates: list[fx.Rate]) -> None:
    days = {r.day for r in rates}
    assert len(days) == 65
    assert min(days) == date(2026, 8, 10) and max(days) == date(2026, 11, 6)
    assert len({(r.day, r.currency) for r in rates}) == len(rates)  # one row per key
    assert all(r.php_per_unit > 0 for r in rates)
    assert not any(r.currency == "PHP" for r in rates)  # PHP->PHP is 1, never stored


def test_xml_cross_rate(rates: list[fx.Rate]) -> None:
    by_key = {(r.day, r.currency): r.php_per_unit for r in rates}
    day = date(2026, 11, 6)
    # On 2026-11-06 the ECB quoted USD 1.1165 per EUR; EUR->PHP is stored as quoted.
    eur = by_key[(day, "EUR")]
    assert by_key[(day, "USD")] == (eur / Decimal("1.1165")).quantize(fx.SCALE)
    assert by_key[(day, "USD")] == Decimal("63.016570")


def test_cross_rates_need_a_php_quote() -> None:
    assert list(fx.cross_rates(date(2026, 1, 2), {"USD": Decimal("1.1")})) == []


def test_cross_rates_values() -> None:
    out = {r.currency: r.php_per_unit for r in fx.cross_rates(
        date(2026, 1, 2), {"USD": Decimal("1.25"), "PHP": Decimal("70"), "JPY": Decimal("175")}
    )}  # fmt: skip
    assert out == {"EUR": Decimal("70.000000"), "USD": Decimal("56.000000"),
                   "JPY": Decimal("0.400000")}  # fmt: skip


# Same layout as eurofxref-hist.csv (header row, trailing comma, N/A for missing quotes).
HISTORY_CSV = (
    "Date,USD,JPY,PHP,HRK,\n"
    "2026-11-06,1.1165,176.77,70.358,N/A,\n"
    "2022-12-30,1.0666,140.66,59.32,7.5365,\n"
    "2020-12-31,1.2271,126.49,58.947,7.5519,\n"
)


def test_history_csv_skips_na_and_old_days() -> None:
    rates = fx.parse_history_csv(HISTORY_CSV, since=date(2021, 1, 1))
    days = {r.day for r in rates}
    assert days == {date(2026, 11, 6), date(2022, 12, 30)}
    hrk = [r for r in rates if r.currency == "HRK"]
    assert [r.day for r in hrk] == [date(2022, 12, 30)]  # N/A in 2026 -> no row


def test_unzip_history() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("eurofxref-hist.csv", HISTORY_CSV)
    assert fx.unzip_history(buf.getvalue()) == HISTORY_CSV


def test_xml_with_a_dtd_is_refused() -> None:
    evil = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "1.5">]>'
        b'<Envelope><Cube><Cube time="2026-01-02"><Cube currency="PHP" rate="&e;"/>'
        b"</Cube></Cube></Envelope>"
    )
    with pytest.raises(ValueError, match="DTD"):
        fx.parse_xml(evil)
