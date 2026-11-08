"""HN "Who is Hiring?" adapter: official HN API only (terms checked 2026-11-06, SOURCES.md).

- API: https://hacker-news.firebaseio.com/v0/ ("There is currently no rate limit"). We still
  keep >= 1 s between requests (the shared client's default). news.ycombinator.com itself
  has Crawl-delay: 30 and is never fetched; it is only linked to.
- The monthly thread is a story by the `whoishiring` account titled
  "Ask HN: Who is hiring? (<Month> <Year>)". Each top-level comment is one employer's post.
- Every response is one item, so the crawl is incremental: fetch_pages reports the thread's
  comment ids through `on_listing`, and skips the ids it returns (already stored and past
  HN's 2-hour edit window, see is_final). The pipeline still counts skipped ids as seen.
- Attribution: link to the comment, https://news.ycombinator.com/item?id=<id>, "via Hacker
  News".
- Parsing (the BeautifulSoup part): the comment body is HTML. By convention its first
  paragraph is a header like "Company | Role | Location | Salary | URL"; see parse().
- Fixtures are JSONL: one captured response per line ({"url", "text"}), bodies unchanged.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime, timedelta

from scraper.http import HttpClient
from scraper.models import Page, ParsedPosting, RawItem
from scraper.normalize.classify import is_dev_title
from scraper.normalize.salary import detect_currency
from scraper.normalize.text import html_to_text

SLUG = "hn_hiring"
SOURCE_NAME = 'HN "Who is Hiring?"'
KIND = "api"
BASE_URL = "https://news.ycombinator.com"
API = "https://hacker-news.firebaseio.com/v0"
FIXTURE_EXT = "jsonl"

THREAD_TITLE = re.compile(r"^Ask HN: Who is hiring\?", re.IGNORECASE)
# How many of whoishiring's newest submissions to scan for the hiring thread (it posts
# three threads a month: hiring, wants-to-be-hired, freelancer).
SCAN_SUBMISSIONS = 6
EDIT_WINDOW = timedelta(hours=2)

# ids -> the subset to skip (already stored and final). None = fetch everything.
OnListing = Callable[[list[str]], set[str]]


def item_url(item_id: int | str) -> str:
    return f"{API}/item/{item_id}.json"


def comment_url(item_id: int | str) -> str:
    return f"{BASE_URL}/item?id={item_id}"


def latest_thread_id(client: HttpClient, pages: list[Page]) -> int:
    """Find the newest "Who is hiring?" story among whoishiring's submissions."""
    resp = client.get(f"{API}/user/whoishiring.json")
    pages.append(Page(url=str(resp.url), text=resp.text))
    for sid in (resp.json().get("submitted") or [])[:SCAN_SUBMISSIONS]:
        story = client.get(item_url(sid))
        pages.append(Page(url=str(story.url), text=story.text))
        data = story.json() or {}
        if data.get("type") == "story" and THREAD_TITLE.match(data.get("title", "")):
            return int(sid)
    raise RuntimeError("no 'Who is hiring?' thread among whoishiring's newest submissions")


def fetch_pages(client: HttpClient, on_listing: OnListing | None = None) -> Iterator[Page]:
    """The user record, the scanned stories (the last one is the thread), then each
    top-level comment not in the skip set."""
    head: list[Page] = []
    latest_thread_id(client, head)  # appends the pages it fetched; the thread is last
    yield from head
    thread = json.loads(head[-1].text)
    kids = [str(k) for k in thread.get("kids") or []]
    skip = on_listing(kids) if on_listing else set()
    for kid in kids:
        if kid in skip:
            continue
        resp = client.get(item_url(kid))
        yield Page(url=str(resp.url), text=resp.text)


def split(page: Page) -> Iterator[RawItem]:
    """One RawItem per live top-level comment. Stories, the user record, and deleted or
    dead comments are not postings."""
    data = json.loads(page.text)
    if not isinstance(data, dict) or data.get("type") != "comment":
        return
    if data.get("deleted") or data.get("dead") or not data.get("text"):
        return
    yield RawItem(external_id=str(data["id"]), url=comment_url(data["id"]), payload=page.text)


def fetch(client: HttpClient) -> Iterable[RawItem]:
    for page in fetch_pages(client):
        yield from split(page)


def is_final(payload: str, fetched_at: datetime) -> bool:
    """A stored comment needn't be fetched again once it was fetched after HN's edit window
    (2 hours after posting) closed."""
    try:
        posted = datetime.fromtimestamp(int(json.loads(payload)["time"]), tz=UTC)
    except (ValueError, KeyError, TypeError):
        return False
    return fetched_at >= posted + EDIT_WINDOW


# --------------------------------------------------------------------------- parsing

_URL = re.compile(r"^\s*(?:https?://|www\.)\S+\s*$", re.IGNORECASE)
_SETUP_WORDS = re.compile(
    r"\b(?:remote|onsite|on-site|hybrid|in[\s-]office|in[\s-]person|relocat\w*|worldwide|"
    r"anywhere|time\s?zones?|timezone)\b",
    re.IGNORECASE,
)
# Places that commonly appear alone in a header segment ("Berlin", "SF / NYC").
_PLACES = re.compile(
    r"\b(?:US|USA|UK|EU|EEA|EMEA|APAC|LATAM|Europe|Asia|Canada|Germany|France|Spain|"
    r"Netherlands|Sweden|Switzerland|Japan|India|Singapore|Australia|Philippines|Brazil|"
    r"Mexico|Israel|Ireland|London|Berlin|Paris|Amsterdam|Munich|Stockholm|Zurich|Tokyo|"
    r"Toronto|Vancouver|NYC|New York|SF|San Francisco|Bay Area|Seattle|Austin|Boston|"
    r"Chicago|Denver|Los Angeles|Remote)\b"
)
_CITY_REGION = re.compile(r"^[A-Z][\w .'-]{1,30},\s*[A-Z][\w .'-]{1,30}$")  # "Reno, NV"
# A tech-stack segment ("Python, TypeScript, React") is not a location.
_TECH = re.compile(
    r"\b(?:python|typescript|javascript|react|node|golang|rust|java|kotlin|swift|ruby|"
    r"rails|django|aws|gcp|azure|kubernetes|postgres\w*|sql|llms?|ai agents)\b",
    re.IGNORECASE,
)
_ROLE_WORDS = re.compile(
    r"\b(?:engineers?|developers?|programmers?|designers?|scientists?|analysts?|managers?|"
    r"directors?|architects?|interns?|internship|researchers?|recruiters?|specialists?|"
    r"representatives?|executives?|ae|sre|devops|cto|ceo|coo|cfo|ciso|vp|head\s+of|"
    r"founding|lead|staff|principal|positions?|roles?|consultants?|admin\w*|"
    r"desarrollador\w*)\b",
    re.IGNORECASE,
)
_GENERIC_ROLE = re.compile(
    r"\b(?:multiple|several|various|many|open)\s+(?:\w+\s+)?(?:positions|roles)\b", re.I
)
_JOB_TYPE_ONLY = re.compile(
    r"^\W*(?:full[\s-]?time|part[\s-]?time|contract\w*|freelance|internship|permanent)\b",
    re.IGNORECASE,
)
# Job seekers who post in the hiring thread by mistake. Checked on the header line only
# (employers write "I'm the founder..." further down), plus the seeker-template field.
_SEEKER_HEADER = re.compile(
    r"^\W*(?:(?:i'?m|i am|my name is|hi,? i'?m)\b|location\s*:)", re.I
)  # \b: "IMC Trading | ..." is an employer, not "I'm ..."
# Where a role line's detail starts: "Forward Deployed Engineer ($148K) — NYC or SF".
_DASHES = "-" + chr(0x2013) + chr(0x2014)  # hyphen, en dash, em dash
_ROLE_LINE_END = re.compile(r"\s+(?:\(|[" + _DASHES + r"]|\|)\s*|:\s")
_SEEKER_FIELD = re.compile(r"^\s*willing to relocate\s*:", re.I | re.M)
_MAX_BODY_ROLE_LINE = 100
_MAX_ROLE_SEGMENT = 80
# Sentence words: a line containing them is prose about the company, not a role name.
_PROSE = re.compile(
    r"\b(?:we|we're|our|us|i|i'm|you|your|is|are|am|was|looking|hiring|here|join|"
    r"helps?|build(?:s|ing)?|typical|but|have|has|them|they)\b",
    re.IGNORECASE,
)
_ENUMERATOR = re.compile(r"^\s*(?:\d{1,2}[.)]|[a-z][.)])\s+", re.IGNORECASE)  # "1) ", "3. "
_SALARY_LINE = re.compile(r"^\s*(?:salary|compensation|pay|comp)\s*:\s*(.{3,120})$", re.I | re.M)
_PROSE_COMPANY = re.compile(r"^(.{2,60}?)\s+(?:-|\u2013|\u2014|\(|is hiring|are hiring)")
_MAX_COMPANY = 60
_MAX_TITLE = 160


def _segments(header: str) -> list[str]:
    return [s.strip() for s in header.split("|") if s.strip()]


def _role_pieces(segment: str) -> list[str]:
    """ "Senior/Staff Java Engineers, Account Executive" -> each role separately. A spaced
    slash separates roles ("Fullstack Engineer / Customer Success Engineer"); an unspaced
    one doesn't ("Senior/Staff")."""
    pieces = re.split(r",|\band\b|;|\s+/\s+", segment)
    return [p.strip() for p in pieces if p.strip()]


def _classify_segments(segments: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"role": [], "location": [], "salary": []}
    for seg in segments:
        if _URL.match(seg) or _JOB_TYPE_ONLY.match(seg):
            continue
        if detect_currency(seg) and re.search(r"\d", seg):
            out["salary"].append(seg)
        # Remote/onsite wording makes it a location unless it names a dev role
        # ("REMOTE backend dev"): "Varies between REMOTE ... (account exec position)" is one.
        elif _SETUP_WORDS.search(seg) and not is_dev_title(seg):
            out["location"].append(seg)
        elif (_ROLE_WORDS.search(seg) or is_dev_title(seg)) and not (
            len(seg) > _MAX_ROLE_SEGMENT and _PROSE.search(seg)
        ):
            # Long role lists are fine; long sentences aren't roles ("Salary ranges for the
            # Java Engineers range from 140k-230k, but the Euro positions don't have them").
            out["role"].append(seg)
        elif (_PLACES.search(seg) or _CITY_REGION.match(seg)) and not _TECH.search(seg):
            out["location"].append(seg)
    return out


def _first_role_line(lines: list[str]) -> str | None:
    """The first body line that is a role name ("Senior Backend Engineer (Go)"), not a
    sentence that mentions one ("We're hiring engineers", "Fly.io is a developer-focused")."""
    for line in lines[:40]:
        role = _ROLE_LINE_END.split(line.strip(" -*•:"), maxsplit=1)[0]
        role = _ENUMERATOR.sub("", role).strip()
        if 3 <= len(role) <= _MAX_BODY_ROLE_LINE and not _PROSE.search(role) and is_dev_title(role):
            return role
    return None


def _body_salary(lines: list[str]) -> str | None:
    for line in lines:
        if m := _SALARY_LINE.match(line):
            return m.group(1).strip()
    return None


def parse(raw: RawItem) -> ParsedPosting:
    item = json.loads(raw.payload)
    description = html_to_text(item.get("text"))
    if not description:
        raise ValueError("comment has no text")
    lines = description.splitlines()
    header = lines[0]
    body = lines[1:]

    company = title = location = salary = None
    segments = _segments(header)
    if len(segments) >= 2:
        first, rest = segments[0], segments[1:]
        # The first segment is the company unless it's clearly something else (a URL, a
        # place such as "Cologne, Germany", or a role).
        company = (
            first
            if len(first) <= _MAX_COMPANY
            and not _URL.match(first)
            and not _CITY_REGION.match(first)
            and not is_dev_title(first)
            else None
        )
        parts = _classify_segments(rest)
        title = " / ".join(dict.fromkeys(parts["role"])) or None
        location = " | ".join(parts["location"]) or None
        salary = parts["salary"][0] if parts["salary"] else None
    else:
        m = _PROSE_COMPANY.match(header)
        company = m.group(1).strip() if m else None
    salary = salary or _body_salary(body)
    if not title or _GENERIC_ROLE.search(title):
        # No specific role in the header: the first short body line naming a dev role
        # ("Senior Backend Engineer (Go)"), else the header itself.
        title = _first_role_line(body) or title or header
    title = title[:_MAX_TITLE].strip()

    return ParsedPosting(
        external_id=raw.external_id,
        title=title,
        company_name=company,
        source_url=raw.url,
        location_text=location,
        description=description,
        posted_at=datetime.fromtimestamp(item["time"], tz=UTC) if item.get("time") else None,
        salary_raw=salary,
    )


def is_relevant(posting: ParsedPosting) -> bool:
    """A hiring post for at least one developer role.

    - Job seekers posting in the wrong thread are not.
    - Mixed role lists ("Java Engineers, Account Executive") count if any role is a dev role.
    """
    text = posting.description or ""
    lines = text.splitlines()
    if (lines and _SEEKER_HEADER.match(lines[0])) or _SEEKER_FIELD.search(text):
        return False
    return any(is_dev_title(piece) for piece in _role_pieces(posting.title))
