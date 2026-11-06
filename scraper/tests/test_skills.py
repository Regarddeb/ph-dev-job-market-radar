"""Skill dictionary tests (dashboard/prisma/data/skills.json).

Each skill carries its own `match` / `no_match` examples next to its aliases, so adding a
skill without positive and negative cases fails here. Matching mirrors the tagger:
re.search(pattern, text, re.IGNORECASE).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

SKILLS_JSON = Path(__file__).resolve().parents[2] / "dashboard" / "prisma" / "data" / "skills.json"
CATEGORIES = {"language", "framework", "database", "tool", "cloud"}

SKILLS: list[dict[str, Any]] = json.loads(SKILLS_JSON.read_text(encoding="utf-8"))["skills"]


def matches(skill: dict[str, Any], text: str) -> list[str]:
    """Return the alias patterns of `skill` that match `text`."""
    return [a["pattern"] for a in skill["aliases"] if re.search(a["pattern"], text, re.IGNORECASE)]


def _cases(key: str) -> list[Any]:
    return [pytest.param(s, text, id=f"{s['name']}: {text}") for s in SKILLS for text in s[key]]


def test_dictionary_shape() -> None:
    names = [s["name"] for s in SKILLS]
    assert len(names) == len(set(names)), "duplicate skill names"
    assert len(SKILLS) >= 50
    for s in SKILLS:
        assert s["category"] in CATEGORIES, s["name"]
        assert s["aliases"], f"{s['name']} has no aliases"
        assert s["match"], f"{s['name']} needs at least one positive example"
        assert s["no_match"], f"{s['name']} needs at least one negative example"
        patterns = [a["pattern"] for a in s["aliases"]]
        assert len(patterns) == len(set(patterns)), f"{s['name']} has duplicate aliases"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s["name"])
def test_aliases_compile(skill: dict[str, Any]) -> None:
    for alias in skill["aliases"]:
        re.compile(alias["pattern"], re.IGNORECASE)


@pytest.mark.parametrize(("skill", "text"), _cases("match"))
def test_positive_examples(skill: dict[str, Any], text: str) -> None:
    assert matches(skill, text), f"expected {skill['name']!r} to match {text!r}"


@pytest.mark.parametrize(("skill", "text"), _cases("no_match"))
def test_negative_examples(skill: dict[str, Any], text: str) -> None:
    hits = matches(skill, text)
    assert not hits, f"{skill['name']!r} wrongly matched {text!r} via {hits}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s["name"])
def test_no_catastrophic_backtracking(skill: dict[str, Any]) -> None:
    # Adversarial-ish inputs: long runs of word chars, separators and near-misses.
    probes = [
        "a" * 5000,
        ("go " * 2000),
        (", " * 2000) + "x",
        "node" + "/" * 3000,
        "c" * 5000 + "#",
    ]
    for alias in skill["aliases"]:
        rx = re.compile(alias["pattern"], re.IGNORECASE)
        for probe in probes:
            start = time.perf_counter()
            rx.search(probe)
            assert time.perf_counter() - start < 0.2, f"slow pattern {alias['pattern']!r}"
