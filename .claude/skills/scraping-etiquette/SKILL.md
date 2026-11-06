---
name: scraping-etiquette
description: Fetch rules for job-radar scraper code. Use when writing or changing anything that makes HTTP requests or parses source data in scraper/.
user-invocable: false
paths:
  - "scraper/**"
---

# Scraping etiquette (mandatory for scraper/)

## Which sources
- Fetch only sources whose status is **Allowed** in `docs/SOURCES.md`. Re-verify the terms before writing a new adapter.
- **Never**: JobStreet, JobsDB/SEEK, LinkedIn, Indeed, Upwork, OnlineJobs.ph, Remotive. Don't reference them in code, tests, fixtures or commands.
- Never log in, use cookies or sessions to reach gated data, solve CAPTCHAs, spoof browsers, bypass anti-bot measures, or rotate IPs, proxies or User-Agents.

## How to fetch
- All requests go through the **one shared client** in `scraper/http.py`. Never create an ad-hoc `httpx.get`/`requests` call.
- Use the identifying User-Agent from `SCRAPER_USER_AGENT` (project name, version, contact). Fail fast if it's unset.
- Rate limit per host: ≥ 1 s between requests by default, and slower where the source's terms say so. Poll each source once daily.
- Retry only on 429, 5xx and network errors, with exponential backoff and jitter (max 3 attempts). **Honor `Retry-After`**. Never retry other 4xx errors.
- Set timeouts (connect ~10 s, read ~30 s). Stream nothing you don't need.
- Fetch politely: check robots.txt for HTML sources and respect `Disallow`. Prefer official APIs and feeds over HTML.
- Paginate only as far as needed (stop at known `external_id`s or the source's documented limit).

## What to store
- **Raw first**: write every response to `raw_postings` (`payload`, `content_hash`, `fetched_at`) before parsing. Parsers re-run from raw without re-fetching.
- Keep `source_url` for every posting. The dashboard shows "via <Source>" linking to it. Remote OK needs a followed (not `rel=nofollow`) link and its name; HN links to the comment.
- Don't republish source data to other job boards.

## Parsing
- Deterministic only: regex, keyword dictionaries, BeautifulSoup + lxml, feedparser, rapidfuzz. **No LLM or AI API calls.**
- Validate parsed payloads with pydantic. A parse error is stored in `raw_postings.parse_error`; it doesn't crash the run.
- **Never guess**: missing salary, seniority or eligibility stays NULL / `unspecified`.
- Test against saved fixtures in `scraper/tests/fixtures/`, never live sites. Fixtures are immutable; add a new dated one when a site changes.

## Idempotency
- Loads are upserts on `(source_id, external_id)`; bump `last_seen_at`, never duplicate.
- Record each run in `crawl_runs` (status, counts, error message), including failures.
- Python never runs DDL. The schema belongs to Prisma (`dashboard/prisma/schema.prisma`).
