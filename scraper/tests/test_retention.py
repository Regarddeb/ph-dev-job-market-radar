"""retention.py: the windows match docs/SPEC.md §7 (the SQL itself is checked by --dry-run)."""

from __future__ import annotations

import re

from scraper.retention import RULES


def _rule(fragment: str) -> str:
    matches = [r.sql for r in RULES if fragment in r.sql]
    assert len(matches) == 1, fragment
    return matches[0]


def test_windows_match_the_spec() -> None:
    assert "interval '90 days'" in _rule("SET description = NULL")
    assert "interval '90 days'" in _rule("DELETE FROM raw_postings")
    assert "interval '1 year'" in _rule("DELETE FROM crawl_runs")
    assert "interval '5 years'" in _rule("DELETE FROM postings")
    assert "interval '5 years'" in _rule("DELETE FROM daily_skill_stats")


def test_descriptions_trim_by_last_seen_so_listed_postings_keep_them() -> None:
    assert "last_seen_at <" in _rule("SET description = NULL")


def test_every_delete_and_update_is_bounded() -> None:
    for rule in RULES:
        assert re.search(r"\bWHERE\b", rule.sql), f"unbounded statement: {rule.name}"
