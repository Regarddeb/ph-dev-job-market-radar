"""scraper/backfill_hn.py: thread discovery and history windows (no network, no database)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from scraper.backfill_hn import discover, past_threads
from scraper.http import HttpClient
from scraper.sources import hn_hiring as hn


def ts(y: int, m: int, d: int = 1) -> int:
    return int(datetime(y, m, d, 15, tzinfo=UTC).timestamp())


# whoishiring posts three threads a month; only "Who is hiring?" ones are backfilled.
STORIES = [
    {"id": 30, "type": "story", "time": ts(2026, 11), "kids": [301],
     "title": "Ask HN: Who is hiring? (November 2026)"},
    {"id": 29, "type": "story", "time": ts(2026, 11),
     "title": "Ask HN: Who wants to be hired? (November 2026)"},
    {"id": 20, "type": "story", "time": ts(2026, 10), "kids": [201, 202],
     "title": "Ask HN: Who is hiring? (October 2026)"},
    {"id": 19, "type": "story", "time": ts(2026, 10),
     "title": "Ask HN: Freelancer? Seeking freelancer? (October 2026)"},
    {"id": 10, "type": "story", "time": ts(2026, 9), "kids": [101],
     "title": "Ask HN: Who is hiring? (September 2026)"},
]  # fmt: skip


def test_past_threads_skip_the_current_one_and_end_at_the_next() -> None:
    threads = past_threads(STORIES)
    assert [t.id for t in threads] == [20, 10]  # newest first; November is the daily crawl's
    october, september = threads
    assert october.ends == datetime(2026, 11, 1, 15, tzinfo=UTC)
    assert september.ends == october.posted
    assert october.kids == ["201", "202"]


def test_past_threads_needs_two_hiring_threads() -> None:
    assert past_threads(STORIES[:2]) == []
    assert past_threads([]) == []


def test_discover_stops_at_the_cutoff() -> None:
    by_id = {s["id"]: s for s in STORIES}
    user = {"id": "whoishiring", "submitted": [30, 29, 20, 19, 10, 5]}
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url.endswith("/user/whoishiring.json"):
            return httpx.Response(200, text=json.dumps(user))
        sid = int(url.rsplit("/", 1)[1].removesuffix(".json"))
        return httpx.Response(200, text=json.dumps(by_id.get(sid)))

    client = HttpClient(user_agent="job-radar-test", transport=httpx.MockTransport(handler),
                        sleep=lambda _s: None)  # fmt: skip
    with client:
        stories = discover(client, cutoff=datetime(2026, 9, 15, tzinfo=UTC))
    assert [s["id"] for s in stories] == [30, 29, 20, 19]
    assert hn.item_url(5) not in requested  # stopped at September, before older items
