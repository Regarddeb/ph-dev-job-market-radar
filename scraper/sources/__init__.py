"""One adapter per allowed source (see docs/SOURCES.md).

Each module `scraper/sources/<slug>.py` exposes:
    SLUG, SOURCE_NAME, KIND, BASE_URL, FIXTURE_EXT
    fetch_pages(client) -> Iterator[Page]   # raw HTTP bodies (what fixtures store)
    split(page) -> Iterator[RawItem]        # one item per posting (stored in raw_postings)
    fetch(client) -> Iterable[RawItem]      # fetch_pages + split
    parse(raw) -> ParsedPosting             # only facts the source states
"""

from __future__ import annotations

import importlib
from types import ModuleType

# Explicit allowlist: adding a source means adding it here (via /add-source) AND marking it
# Allowed in docs/SOURCES.md. tests/test_sources_registry.py checks both.
ADAPTERS: tuple[str, ...] = ("remoteok",)


def get_adapter(slug: str) -> ModuleType:
    if slug not in ADAPTERS:
        raise KeyError(f"unknown or not-allowed source {slug!r}; known: {', '.join(ADAPTERS)}")
    return importlib.import_module(f"scraper.sources.{slug}")
