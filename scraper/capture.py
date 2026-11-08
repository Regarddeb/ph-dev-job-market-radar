"""Save a source's raw responses as new, immutable test fixtures.

    uv run --project scraper python -m scraper.capture remoteok

Writes scraper/tests/fixtures/<slug>/<YYYY-MM-DD>[-N].<ext>, byte-for-byte as received.
Never overwrites: an existing date gets a -2, -3, ... suffix. Uses the shared HttpClient,
so the User-Agent and rate limits apply.

Sources with FIXTURE_EXT "jsonl" (many requests per crawl, e.g. HN) get one file with one
captured response per line, {"url": ..., "text": <body unchanged>}, and capture the whole
crawl unless --max-pages is given.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from scraper.http import HttpClient
from scraper.sources import get_adapter

FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures"


def next_free_path(directory: Path, stem: str, ext: str) -> Path:
    candidate = directory / f"{stem}.{ext}"
    n = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{n}.{ext}"
        n += 1
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="adapter slug, e.g. remoteok")
    parser.add_argument(
        "--max-pages", type=int, default=None, help="stop after N pages (default 1; jsonl: all)"
    )
    args = parser.parse_args(argv)

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    adapter = get_adapter(args.source)
    out_dir = FIXTURES / adapter.SLUG
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(UTC).strftime("%Y-%m-%d")

    with HttpClient() as client:
        if adapter.FIXTURE_EXT == "jsonl":
            path = next_free_path(out_dir, stem, "jsonl")
            items = pages = 0
            # One JSON record per line; json.dumps escapes newlines inside bodies.
            with path.open("w", encoding="utf-8", newline="") as fh:
                for page in adapter.fetch_pages(client):
                    record = {"url": page.url, "text": page.text}
                    fh.write(json.dumps(record, ensure_ascii=False))
                    fh.write(chr(10))
                    pages += 1
                    items += sum(1 for _ in adapter.split(page))
                    if args.max_pages and pages >= args.max_pages:
                        break
            print(
                f"saved {path.relative_to(FIXTURES.parent.parent.parent)} "
                f"({pages} responses, {items} items)"
            )
        else:
            max_pages = args.max_pages or 1
            for i, page in enumerate(adapter.fetch_pages(client), start=1):
                path = next_free_path(out_dir, stem, adapter.FIXTURE_EXT)
                # newline="" + exact text: keep the body as received (no newline translation).
                with path.open("w", encoding="utf-8", newline="") as fh:
                    fh.write(page.text)
                items = sum(1 for _ in adapter.split(page))
                print(f"saved {path.relative_to(FIXTURES.parent.parent.parent)} ({items} items)")
                if i >= max_pages:
                    break
        print(f"requests made: {client.requests_made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
