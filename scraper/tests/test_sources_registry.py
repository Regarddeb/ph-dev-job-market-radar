"""Every registered adapter must be Allowed in docs/SOURCES.md, with a terms-check date."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scraper.sources import ADAPTERS, get_adapter

SOURCES_MD = Path(__file__).resolve().parents[2] / "docs" / "SOURCES.md"
REQUIRED = ("SLUG", "SOURCE_NAME", "KIND", "BASE_URL", "FIXTURE_EXT")
FUNCTIONS = ("fetch_pages", "split", "fetch", "parse", "is_relevant")


def _section(md: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\b.*?(?=^## |\Z)", md, re.M | re.S)
    return m.group(0) if m else ""


def _rows(section: str) -> dict[str, list[str]]:
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0] not in ("Source", "---"):
            rows[cells[0]] = cells
    return rows


@pytest.mark.parametrize("slug", ADAPTERS)
def test_adapter_interface(slug: str) -> None:
    adapter = get_adapter(slug)
    for name in REQUIRED:
        assert hasattr(adapter, name), f"{slug}: missing {name}"
    for name in FUNCTIONS:
        assert callable(getattr(adapter, name, None)), f"{slug}: missing {name}()"
    assert slug == adapter.SLUG
    assert adapter.KIND in {"api", "rss", "html"}


@pytest.mark.parametrize("slug", ADAPTERS)
def test_adapter_is_allowed_in_sources_md(slug: str) -> None:
    md = SOURCES_MD.read_text(encoding="utf-8")
    name = get_adapter(slug).SOURCE_NAME
    allowed = _rows(_section(md, "Allowed"))
    assert name in allowed, f"{name} is not in the Allowed table of docs/SOURCES.md"
    row = allowed[name]
    assert row[4] == "Allowed", f"{name}: status is {row[4]!r}, not 'Allowed'"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[5]), f"{name}: no terms-checked date"
    for other in ("Unclear", "Forbidden", "Candidates"):
        assert name not in _rows(_section(md, other)), f"{name} also listed under {other}"


def test_unknown_source_rejected() -> None:
    with pytest.raises(KeyError):
        get_adapter("remotive")  # Unclear as of 2026-11-06
