from __future__ import annotations

import pytest

from scraper.normalize.text import (
    clean_text,
    fix_mojibake,
    html_to_text,
    normalize_company,
    normalize_title,
)


@pytest.mark.parametrize(
    ("broken", "fixed"),
    [
        ("MÃ¼nchen", "München"),
        ("Weâ\x80\x99ve been doing this", "We’ve been doing this"),
        ("Lead â\x80\x94 Logistics", "Lead — Logistics"),
        ("SÃ£o Paulo", "São Paulo"),
        # cp1252 flavour, mixed with correct punctuation on the same line
        ("support â€” not replace — fair", "support — not replace — fair"),
        ("Penumbraâ€™s commitment ’", "Penumbra’s commitment ’"),
        ("Expect â\x80\x9cVacation?â\x80\x9d", "Expect “Vacation?”"),
    ],
)
def test_fix_mojibake_repairs(broken: str, fixed: str) -> None:
    assert fix_mojibake(broken) == fixed


@pytest.mark.parametrize("ok", ["München", "plain ascii", "Café — déjà vu", "₱40k–60k", "Ã"])
def test_fix_mojibake_leaves_good_text_alone(ok: str) -> None:
    assert fix_mojibake(ok) == ok


def test_html_to_text_keeps_inline_on_one_line() -> None:
    html = (
        "<p><strong>Location</strong>: 100% remote</p><ul><li>Python</li><li>Go</li></ul>"
        "line one<br>line two &amp; more"
    )
    assert html_to_text(html) == ("Location: 100% remote\nPython\nGo\nline one\nline two & more")
    assert html_to_text("") is None
    assert html_to_text("<p> </p>") is None


def test_clean_text() -> None:
    assert clean_text("  Scheduling &amp; Coordinating\n\tReservations ") == (
        "Scheduling & Coordinating Reservations"
    )
    assert clean_text("   ") is None
    assert clean_text(None) is None


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior  Vue Developer!", "senior vue developer"),
        ("C++ / C# Engineer (Remote)", "c++ / c# engineer remote"),
        ("Node.js &amp; CI/CD", "node.js ci/cd"),
    ],
)
def test_normalize_title(title: str, expected: str) -> None:
    assert normalize_title(title) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Lemon.io", "lemon io"),
        ("Acme, Inc.", "acme"),
        ("Acme Inc", "acme"),
        ("ACME LLC", "acme"),
        ("Foo Pty Ltd", "foo"),
        ("Société Générale SA", "société générale"),
        ("Inc. Magazine", "inc magazine"),
    ],
)
def test_normalize_company(name: str, expected: str) -> None:
    assert normalize_company(name) == expected
