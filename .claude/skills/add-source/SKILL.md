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

- Write `fetch_pages` first (step 3), add the slug to `ADAPTERS` in `scraper/sources/__init__.py`, then capture **one** response through the shared client:
  `uv run --project scraper python -m scraper.capture $source`
  It saves `scraper/tests/fixtures/$source/<YYYY-MM-DD>.<ext>` byte-for-byte and never overwrites an existing file.
- Fixtures are immutable. Never edit an existing one; a hook blocks it. If the site changed, capture a new dated file.
- If the payload is large, keep it as is. Don't hand-trim JSON; that hides real-world edge cases.
- **Profile the fixture before writing tests.** Look at the encoding (mojibake), HTML entities, salary units, and irrelevant (non-dev) items. Remote OK had all four.

## 3. Write the adapter: `scraper/sources/$source.py`

Follow `scraper/sources/remoteok.py`. Required module members (enforced by `tests/test_sources_registry.py`):
- Constants: `SLUG`, `SOURCE_NAME` (exactly as in SOURCES.md), `KIND` (`api` | `rss` | `html`), `BASE_URL`, `FIXTURE_EXT`.
- `fetch_pages(client) -> Iterator[Page]`: one request per page, at the source's allowed rate, through `scraper.http.HttpClient` only.
- `split(page) -> Iterator[RawItem]`: one item per posting, with `external_id`, `url` and `payload` (raw JSON/HTML of that one item). Skip non-job elements.
- `fetch(client)`: `fetch_pages` + `split`.
- `parse(raw) -> ParsedPosting` (`scraper/models.py`): fill only fields the payload actually states. **Never guess**: leave salary period, seniority, `ph_eligible`, etc. as `None`/`"unspecified"` and let `scraper/normalize/` derive them.
- `is_relevant(posting) -> bool`: developer roles only. Irrelevant items are still stored raw.
- Clean text with `scraper.normalize.text.clean_text` / `html_to_text` (entities, mojibake, block vs inline HTML).
- `source_url` must be the posting's own URL on that source (for attribution).
- Use BeautifulSoup + lxml for HTML fragments and feedparser for RSS. Don't use regex on raw HTML.
- No LLM or AI API calls, ever.

## 4. Test: `scraper/tests/test_source_$source.py`

- Load the fixture from disk (never the network). Assert on:
  - item count, and that `external_id` values are unique
  - the full parsed dict for 2–3 representative postings
  - edge cases found in the fixture (missing salary, HTML in description, odd location text)
  - source-specific quirks (e.g. Remote OK: the first element is a legal notice and is skipped)
  - the relevance filter (counts of dev vs non-dev items)
- Run: `uv run --project scraper python -m pytest scraper/tests/test_source_$source.py`
- Then a dry run over the fixture, with no network and no DB:
  `uv run --project scraper python -m scraper.pipeline --source $source --dry-run --fixture <fixture>`

## 5. Seed row: `dashboard/prisma/seed.ts`

- In `SOURCES`, set the source's `isActive: true` and `termsUrl`, and keep `slug`, `name`, `baseUrl`, `kind`, `crawlIntervalMinutes` (≥ 1440 unless the terms allow more often) and `attributionText` (e.g. "via Remote OK"). Then run `pnpm db:seed`. The pipeline refuses to run a source whose row has `is_active=false`.

## 6. Workflow step: `.github/workflows/scrape.yml`

- Add one step per source, before `aggregate.py`:
  `uv run --project scraper python -m scraper.pipeline --source $source`
- Give it `continue-on-error: true`, so one broken source doesn't block the others. The failure is still recorded in `crawl_runs`.

## 7. Verify and report

- `uv run --project scraper ruff check scraper` and `uv run --project scraper pytest`
- Suggest `/run-pipeline $source` for a dry run against the live source.
- Report: files created, fixture path, test results, and anything in the terms the user should know (rate limits, attribution wording).
