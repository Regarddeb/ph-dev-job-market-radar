"""Deterministic classification: dev-role filter, seniority, job type, work setup, ph_eligible.

Rules follow docs/SPEC.md §6. Everything here is regex over text the source states; when
the text doesn't support a value the result is "unspecified" / None (never guessed).
"""

from __future__ import annotations

import re

from scraper.models import JobType, WorkSetup

Seniority = str  # 'intern' | 'junior' | 'mid' | 'senior' | 'lead' | 'unspecified'

_I = re.IGNORECASE

# --------------------------------------------------------------------------- dev roles

# The title has to name a software role. Source tags are not enough: Remote OK's tags are
# keyword-stuffed (e.g. "Tax Manager" tagged dev/php, "Account Manager" tagged golang).
_DEV_TITLE = re.compile(
    r"\b(?:"
    r"engineer(?:s|ing)?|developer|programmer|coder|desarrollador(?:a)?|"
    r"dev\s?ops|devsecops|sre|site\s+reliability|"
    r"full[\s-]?stack|front[\s-]?end|back[\s-]?end|"
    r"qa|quality\s+assurance|test\s+automation|tester|sdet|"
    r"(?:software|solutions?|cloud|data|systems?|platform|security|technical|enterprise)"
    r"\s+architect|"
    r"tech(?:nical)?\s+lead|head\s+of\s+(?:technology|engineering)|cto|"
    r"data\s+scientist|machine\s+learning|ml\s+ops|mlops|"
    r"python|javascript|typescript|golang|rust|ruby|rails|php|java|kotlin|swift|"
    r"react|angular|vue|node(?:\.?js)?|django|laravel|\.net|flutter|ios|android"
    r")\b",
    _I,
)

# Titles that contain a dev word but aren't software roles.
_NON_DEV_TITLE = re.compile(
    r"\b(?:"
    r"sales|account\s+(?:executive|manager)|business\s+development|recruit(?:er|ing|ment)|"
    r"talent|marketing|customer\s+(?:success|support)|support\s+specialist|"
    r"accountant|accounting|tax|property|legal|paralegal|"
    r"(?:civil|mechanical|electrical|chemical|structural|process|manufacturing|hvac|"
    r"field\s+service|biomedical|sound|audio|mixing)\s+engineer"
    r")\b",
    _I,
)


def is_dev_title(title: str) -> bool:
    """True if the title names a software/developer role and isn't a known non-dev role."""
    return bool(_DEV_TITLE.search(title)) and not _NON_DEV_TITLE.search(title)


# --------------------------------------------------------------------------- seniority

# SPEC order; first match wins. Applied to the title only: descriptions routinely mention
# other levels ("you'll mentor junior engineers", "report to a senior lead").
_SENIORITY: list[tuple[re.Pattern[str], Seniority]] = [
    (re.compile(r"\b(?:lead|principal|staff)\b", _I), "lead"),
    (re.compile(r"\b(?:senior|sr)\b\.?", _I), "senior"),
    (re.compile(r"\bintern(?:ship)?\b", _I), "intern"),
    (re.compile(r"\b(?:junior|jr\b\.?|entry[\s-]level)", _I), "junior"),
]


def seniority(title: str) -> Seniority:
    for pattern, level in _SENIORITY:
        if pattern.search(title):
            return level
    return "unspecified"


# --------------------------------------------------------------------------- job type

# Title: short and explicit, so the plain SPEC patterns apply.
_JOB_TYPE_SHORT: list[tuple[re.Pattern[str], JobType]] = [
    (re.compile(r"\bpart[\s-]?time\b", _I), "part_time"),
    (re.compile(r"\b(?:freelance(?:r)?|project[\s-]based)\b", _I), "freelance"),
    # Not "Smart Contract Engineer": that's the technology, not the employment type.
    (re.compile(r"(?<!smart\s)(?<!smart-)\bcontract(?:ual|or)?\b", _I), "contract"),
    (re.compile(r"\bfull[\s-]?time\b", _I), "full_time"),
]

# Descriptions: a type counts only when stated about this job: a labelled field
# ("Type: Full-time", "Hours: Part-time"), an item in a "Remote · Full time · ..." line, or
# a phrase like "this is a full-time role". "Contract" alone also means smart contracts,
# API contracts or signing a contract, so it always needs employment context.
_LABEL = (
    r"(?:type|job\s+type|position\s+type|role\s+type|employment(?:\s+type)?|"
    r"classification|hours|contract|engagement|commitment)\s*:\s*(?:regular,?\s*)?"
)
_ITEM_START = r"(?:^|[|\u00b7\u2022,/]\s*)"  # start of line or after | · • , /
_ITEM_END = r"\s*(?:[|\u00b7\u2022,/]|$)"
_FULL = r"full[\s-]?time"
_PART = r"part[\s-]?time"
_NOUN = r"(?:role|position|job|basis|opportunity|engagement|employment|contract|hire)"

_JOB_TYPE_LONG: list[tuple[re.Pattern[str], JobType]] = [
    (re.compile(
        rf"\b{_LABEL}{_PART}\b|{_ITEM_START}{_PART}{_ITEM_END}|"
        rf"\b{_PART}\s+(?:freelance\s+)?{_NOUN}\b|\bthis\s+is\s+a\s+{_PART}\b",
        _I | re.M), "part_time"),
    (re.compile(
        rf"\b{_LABEL}(?:freelance|project[\s-]based)\b|"
        rf"{_ITEM_START}(?:freelance|project[\s-]based){_ITEM_END}|"
        rf"\b(?:freelance|project[\s-]based)\s+{_NOUN}\b",
        _I | re.M), "freelance"),
    (re.compile(
        rf"\b{_LABEL}(?:{_FULL}\s+)?contract(?:or|ual)?\b|"
        rf"{_ITEM_START}contract(?:or)?{_ITEM_END}|"
        r"\b(?:contract(?:ual)?|contractor)\s+(?:role|position|basis|engagement|job|"
        r"opportunity)\b|\bcontract[\s-]based\b|\bon\s+a\s+contract(?:ual)?\s+basis\b|"
        r"\bcontract[\s-]to[\s-]hire\b|\b\d{1,2}[\s-](?:month|week|year)s?\s+contract\b|"
        r"\b(?:one|two|three|six|twelve)[\s-](?:month|week|year)s?\s+contract\b|"
        rf"\bindependent\s+contractor\b|\b{_FULL}\s+contractor\b|"
        rf"\b(?:{_FULL}|permanent)\s+or\s+contract(?:or)?\b",
        _I | re.M), "contract"),
    (re.compile(
        rf"\b{_LABEL}{_FULL}\b(?!\s+contract)|{_ITEM_START}{_FULL}{_ITEM_END}|"
        rf"\b{_FULL}\s+(?:permanent\s+)?{_NOUN}\b|\bthis\s+is\s+a\s+(?:permanent,?\s+)?{_FULL}\b|"
        # "full-time or contract" states both types: matched here and by the contract rule,
        # so job_type() sees the conflict.
        rf"\b{_FULL}\s+or\s+contract(?:or)?\b",
        _I | re.M), "full_time"),
]  # fmt: skip


def _types(patterns: list[tuple[re.Pattern[str], JobType]], text: str) -> list[JobType]:
    return [jt for pattern, jt in patterns if pattern.search(text)]


def job_type(source_value: JobType, title: str, description: str | None) -> JobType:
    """Source field first, then the title, then the description.

    SPEC order (part-time, freelance, contract, full-time), first match wins. In the
    description, full-time alongside another type ("full-time or contract", "Full time ·
    Permanent or contract") is a real conflict and stays unspecified. Source tags aren't
    used: Remote OK's are keyword-stuffed (non-dev roles carry "full time", "part time").
    """
    if source_value != "unspecified":
        return source_value
    if found := _types(_JOB_TYPE_SHORT, title):
        return found[0]
    if not description:
        return "unspecified"
    found = _types(_JOB_TYPE_LONG, description)
    if not found or ("full_time" in found and len(found) > 1):
        return "unspecified"
    return found[0]


# --------------------------------------------------------------------------- work setup

# Hybrid is checked before remote so "hybrid (2 days remote)" isn't read as remote.
_WORK_SETUP: list[tuple[re.Pattern[str], WorkSetup]] = [
    (re.compile(r"\bhybrid\b", _I), "hybrid"),
    (re.compile(r"\bremote\b|\bwfh\b|\bwork\s+from\s+home\b", _I), "remote"),
    (re.compile(r"\bon[\s-]?site\b|\bin[\s-]office\b", _I), "onsite"),
]


def work_setup(source_value: WorkSetup, title: str, location: str | None) -> WorkSetup:
    """Source field first, then the title and location line. Descriptions aren't used:
    "remote" there is often about tooling or teams ("remote-first culture", "remote APIs")."""
    if source_value != "unspecified":
        return source_value
    text = f"{title} | {location or ''}"
    for pattern, setup in _WORK_SETUP:
        if pattern.search(text):
            return setup
    return "unspecified"


# --------------------------------------------------------------------------- ph_eligible

# Short codes are case-sensitive so prose ("join us", "us only") doesn't count.
_US = r"(?-i:US|USA|U\.S\.A?\.?)"
_NON_PH_PLACE = (
    r"(?:the\s+)?(?:" + _US + r"|United\s+States|America|North\s+America|Canada|"
    r"(?-i:UK|EU|EMEA|LATAM)|United\s+Kingdom|Europe|European\s+Union|Latin\s+America|"
    r"Germany|France|Spain|Brazil|Mexico|India|Australia|Israel|Ireland)(?!\w)"
)
# "able to work in US time zones / hours" is about overlap, not where the hire may live.
# Up to two words may sit between the place and the time word ("US Eastern time zone").
_NOT_HOURS = r"(?!\s+(?:[\w-]+\s+){0,2}?(?:time[\s-]?zones?|hours|business\s+hours|shifts?)\b)"

# Explicit positives about where the hire can be. Strong = names the Philippines.
_PH_STRONG = re.compile(r"\bphilippines\b|\bfilipinos?\b|\bph[\s-]based\b", _I)

# Negatives that name the Philippines themselves. Checked first: otherwise the mention
# would read as a strong positive ("We cannot hire in the Philippines").
_PH_NAME = r"(?:(?:the\s+)?philippines|filipinos?|ph[\s-]based)"
_PH_NEGATIVE = re.compile(
    r"\b(?:not|cannot|can't|unable\s+to|don't|do\s+not)\s+(?:currently\s+)?"
    r"(?:hire|hiring|accept|accepting|consider|considering|open\s+to)\b[^.\n]{0,40}?\b"
    + _PH_NAME
    + r"\b|"
    r"\b(?:except|excluding|other\s+than|outside(?:\s+of)?)\s+" + _PH_NAME + r"\b|"
    r"\b" + _PH_NAME + r"\b[^.\n]{0,40}?\b(?:(?:are|is)\s+not\s+eligible|ineligible|"
    r"(?:are|is)\s+excluded|cannot\s+apply|not\s+(?:accepted|supported))\b",
    _I,
)

# Generic positives in the LOCATION field (short, about the job itself).
_LOCATION_GENERIC = re.compile(
    r"\bworldwide\b|\banywhere\b|\bglobal(?:ly)?\b|\basia\b|\bapac\b|\basia[\s-]pacific\b|"
    r"\bsouth[\s-]?east\s+asia\b",
    _I,
)

# Generic positives in the DESCRIPTION need hiring context: bare "worldwide" / "Asia" there
# is usually marketing ("millions of users worldwide", "leading platform in Southeast Asia").
_DESC_GENERIC = re.compile(
    r"\banywhere\s+in\s+the\s+world\b|"
    r"\b(?:work(?:ing)?(?:\s+remotely)?\s+from|based|located|live|living|hire|hiring|"
    r"candidates?|applicants?)\s+(?:from\s+)?anywhere\b(?!\s+in\s+(?!the\s+world))|"
    r"\bremote\s*[-(:/,]?\s*(?:worldwide|global|anywhere)\b|"
    r"\b(?:hire|hiring|candidates?|applicants?|talent|open\s+to)\b[^.\n]{0,40}?"
    r"\b(?:worldwide|globally|from\s+any\s+country|asia|apac|asia[\s-]pacific)\b",
    _I,
)

# The title can scope a role to a region: "APAC Python" (positive), "Senior Software
# Engineer LATAM" (negative: the role is for that region).
_TITLE_POSITIVE = re.compile(
    r"\b(?:apac|asia(?:[\s-]pacific)?|south[\s-]?east\s+asia|worldwide|anywhere|philippines)\b",
    _I,
)
_TITLE_REGION_ONLY = re.compile(
    r"\b(?-i:US|USA|LATAM|EMEA|EU|UK)\b|\b(?:Latin\s+America|North\s+America|Europe|Canada)\b",
    _I,
)

# Explicit negatives (SPEC: US only, must reside/be located in <non-PH>, EU timezone
# required, US work authorization), plus their common phrasings.
_NEGATIVE = re.compile(
    r"\b" + _US + r"[\s-]only\b|\b(?:" + _US + r"|United\s+States)\s+(?:residents|citizens)"
    r"\s+only\b|"
    r"\bmust\s+(?:reside|be\s+located|live|be\s+based)\s+in\s+" + _NON_PH_PLACE + r"|"
    r"\b(?:authori[sz]ed|eligible|legally\s+able|able)\s+to\s+work\s+in\s+"
    + _NON_PH_PLACE
    + _NOT_HOURS
    + r"|"
    r"\b" + _US + r"\s+work\s+authori[sz]ation\b|"
    r"\bwork\s+authori[sz]ation\b[^.\n]{0,60}?\b(?:" + _US + r"|United\s+States)\b|"
    r"\b(?-i:EU)\s+time[\s-]?zones?\s+(?:required|only)\b|"
    r"\banywhere\s+in\s+" + _NON_PH_PLACE,
    _I,
)

# A location field that names only the US (e.g. "US", "Remote - US", "United States").
_LOCATION_US_ONLY = re.compile(
    r"^\s*(?:remote\s*[-(,:/]?\s*)?(?:" + _US + r"|United\s+States(?:\s+of\s+America)?)"
    r"\s*\)?\s*(?:only)?\s*$",
    _I,
)


def ph_eligible(title: str, location: str | None, description: str | None) -> bool | None:
    """True / False only when the text says so; None otherwise.

    1. A negative that names the Philippines ("cannot hire in the Philippines") -> False.
    2. An explicit negative beats a generic positive (worldwide, anywhere, Asia, APAC); with
       a strong positive (the Philippines named) it's a conflict -> None.
    3. A title scoped to another region ("... LATAM") is weaker: False only when nothing
       positive is stated; "Engineer (US or APAC)" -> None.
    """
    loc = location or ""
    desc = description or ""
    if _PH_NEGATIVE.search(f"{title} | {loc}") or _PH_NEGATIVE.search(desc):
        return False
    explicit_negative = bool(
        _NEGATIVE.search(loc) or _NEGATIVE.search(desc) or _LOCATION_US_ONLY.match(loc)
    )
    strong = bool(_PH_STRONG.search(f"{title} | {loc}") or _PH_STRONG.search(desc))
    generic = bool(
        _TITLE_POSITIVE.search(title) or _LOCATION_GENERIC.search(loc) or _DESC_GENERIC.search(desc)
    )

    if explicit_negative:
        return None if strong else False
    if _TITLE_REGION_ONLY.search(title):
        return None if (strong or generic) else False
    if strong or generic:
        return True
    return None
