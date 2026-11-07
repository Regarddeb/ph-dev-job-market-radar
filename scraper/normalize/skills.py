"""Skill tagging from the alias dictionary (skill_aliases / dashboard/prisma/data/skills.json).

- Each alias is a Python `re` pattern applied with re.IGNORECASE over title + description.
- requirements_only aliases (for ambiguous names) only match inside the requirements section
  of the description (see requirements_section).
- Full runs load aliases from the DB (seeded from skills.json); dry runs and tests read the
  JSON directly, so both use the same dictionary.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SKILLS_JSON = Path(__file__).resolve().parents[2] / "dashboard" / "prisma" / "data" / "skills.json"

# Heading lines that open a requirements/skills section (description text from html_to_text
# keeps one block element per line, so headings arrive as their own short lines).
_REQ_HEADING = re.compile(
    r"^\W*(?:requirements?|qualifications?|(?:required|preferred|technical|key)\s+skills|"
    r"skills(?:\s+(?:&|and)\s+experience)?|must[\s-]haves?|nice[\s-]to[\s-]haves?|"
    r"what\s+you\W?ll\s+(?:need|bring)|what\s+we\W?re\s+looking\s+for|"
    r"you\s+(?:have|bring|are)|about\s+you|who\s+you\s+are|tech(?:nical)?\s+stack|"
    r"(?:our\s+)?stack|tools\s+(?:&|and)\s+technologies|experience)\W*$",
    re.IGNORECASE,
)
# Lines that end a section: another short heading-like line ending in ":" or a known
# non-requirements heading.
_OTHER_HEADING = re.compile(
    r"^\W*(?:benefits|perks|what\s+we\s+offer|compensation|salary|about\s+(?:us|the\s+"
    r"company|the\s+role)|responsibilities|what\s+you\W?ll\s+do|how\s+to\s+apply|"
    r"the\s+role|our\s+values|why\s+join)\W*$",
    re.IGNORECASE,
)
_MAX_HEADING_LEN = 60


@dataclass(frozen=True)
class Alias:
    skill: str
    pattern: re.Pattern[str]
    requirements_only: bool = False


def requirements_section(description: str | None) -> str:
    """Text under requirements-like headings, up to the next unrelated heading."""
    if not description:
        return ""
    out: list[str] = []
    inside = False
    for line in description.splitlines():
        stripped = line.strip()
        if len(stripped) <= _MAX_HEADING_LEN and _REQ_HEADING.match(stripped):
            inside = True
            continue
        if inside and len(stripped) <= _MAX_HEADING_LEN and _OTHER_HEADING.match(stripped):
            inside = False
            continue
        if inside:
            out.append(stripped)
    return "\n".join(out)


class Tagger:
    def __init__(self, aliases: Iterable[Alias]) -> None:
        self.aliases = list(aliases)

    @classmethod
    def from_rows(cls, rows: Iterable[tuple[str, str, bool]]) -> Tagger:
        """(skill name, pattern, requirements_only) rows, e.g. from skill_aliases."""
        return cls(
            Alias(name, re.compile(pattern, re.IGNORECASE), bool(req_only))
            for name, pattern, req_only in rows
        )

    @classmethod
    def from_json(cls, path: Path = SKILLS_JSON) -> Tagger:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_rows(
            (s["name"], a["pattern"], a.get("requirements_only", False))
            for s in data["skills"]
            for a in s["aliases"]
        )

    def tag(self, title: str, description: str | None) -> set[str]:
        text = f"{title}\n{description or ''}"
        reqs: str | None = None  # extracted lazily: most aliases don't need it
        found: set[str] = set()
        for alias in self.aliases:
            if alias.skill in found:
                continue
            if alias.requirements_only:
                if reqs is None:
                    reqs = requirements_section(description)
                haystack = reqs
            else:
                haystack = text
            if haystack and alias.pattern.search(haystack):
                found.add(alias.skill)
        return found
