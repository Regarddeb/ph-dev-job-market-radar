---
name: add-source
description: Add a new job source adapter end to end (fixture, parser, test, seed row, workflow step). Only for sources marked Allowed in docs/SOURCES.md.
disable-model-invocation: true
arguments: [source]
argument-hint: "[source-name]"
---

# Add source: $source

Follow these steps in order. Stop and report at the first failure.

## 1. Gate: is it allowed?

- Read `docs/SOURCES.md`. Find the row for `$source`.
- **Refuse and stop** if the source is in the Forbidden table, is missing, or its status is anything other than `Allowed` (`Candidate`, `Unclear`, `Rejected`). For a candidate, suggest running the `source-researcher` subagent first.
- If its "Terms checked" date is older than 90 days, re-check the terms, robots.txt and rate limits before continuing, and update the date and notes in `docs/SOURCES.md`.
- Re-read the `scraping-etiquette` rules (`.claude/skills/scraping-etiquette/SKILL.md`).

## 2. Save one fixture

- Fetch **one** response from the documented endpoint using `scraper/http.py`'s shared client (identifying User-Agent, rate limit), or with `curl -A "$SCRAPER_USER_AGENT"` if `http.py` doesn't exist yet.
- Save it unmodified as `scraper/tests/fixtures/$source/<YYYY-MM-DD>.<json|xml|html>`.
- Fixtures are immutable. Never edit an existing one; a hook blocks it. If the site changed, save a new dated file.
- If the payload is large, keep it as is. Don't hand-trim JSON; that hides real-world edge cases.

## 3. Write the adapter: `scraper/sources/$source.py`

- Expose module-level constants `SOURCE_NAME`, `KIND` (`api` | `rss` | `html`) and `BASE_URL`.
- `fetch(client) -> Iterable[RawItem]`: one request per page, at the source's allowed rate. Yield `external_id`, `url`, `payload` (raw text). Don't parse here.
- `parse(raw: RawItem) -> dict`: return the common posting dict validated by the shared pydantic model. Fill only fields the payload actually states. **Never guess**: leave salary, seniority, `ph_eligible`, etc. as `None`/`"unspecified"` and let `scraper/normalize/` derive them.
- `source_url` must be the posting's own URL on that source (for attribution).
- Use BeautifulSoup + lxml for HTML fragments and feedparser for RSS. Don't use regex on raw HTML.
- No LLM or AI API calls, ever.

## 4. Test: `scraper/tests/test_source_$source.py`

- Load the fixture from disk (never the network). Assert on:
  - item count, and that `external_id` values are unique
  - the full parsed dict for 2–3 representative postings
  - edge cases found in the fixture (missing salary, HTML in description, odd location text)
  - source-specific quirks (e.g. Remote OK: the first element is a legal notice and is skipped)
- Run: `uv run --project scraper pytest scraper/tests/test_source_$source.py`

## 5. Seed row: `dashboard/prisma/seed.ts`

- Add an idempotent upsert for the `sources` row: `name`, `base_url`, `kind`, `is_active: true`, `crawl_interval_minutes` (≥ 1440 unless the terms allow more often), `attribution_text` (e.g. "via Remotive"), `terms_url`.

## 6. Workflow step: `.github/workflows/scrape.yml`

- Add one step per source, before `aggregate.py`:
  `uv run --project scraper python -m scraper.pipeline --source $source`
- Give it `continue-on-error: true`, so one broken source doesn't block the others. The failure is still recorded in `crawl_runs`.

## 7. Verify and report

- `uv run --project scraper ruff check scraper` and `uv run --project scraper pytest`
- Suggest `/run-pipeline $source` for a dry run against the live source.
- Report: files created, fixture path, test results, and anything in the terms the user should know (rate limits, attribution wording).
