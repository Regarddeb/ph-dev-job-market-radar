# PH Dev Job Market Radar: Specification

A personal portfolio project that tracks the remote developer job market for a Philippines-based developer. Once a day it fetches allowed job sources, cleans and classifies the listings with deterministic rules, stores them in Postgres, and shows trends in a web dashboard: which skills are in demand, what roles pay, and which part-time/freelance roles accept PH-based applicants.

It showcases three things: **web scraping (BeautifulSoup)**, **data processing**, and **dashboards**.

## 1. Hard rules

1. **No LLM integration in the app.** No AI/LLM API calls anywhere in `scraper/` or `dashboard/`. All extraction is rule-based (regex, keyword dictionaries, rapidfuzz).
2. **Only sources marked Allowed** in [SOURCES.md](SOURCES.md). Never log in, bypass anti-bot measures, or rotate IPs/proxies.
3. **Follow each source's terms**: rate limits, an identifying User-Agent, attribution. Every posting keeps its `source_url`, and the dashboard shows a "via <Source>" link on every posting.
4. **Prisma owns the schema** (`dashboard/prisma/schema.prisma`). Python never runs DDL. Never edit a committed migration; add a new one. Every table and column is snake_case via `@map` / `@@map`.
5. **Raw first.** Every fetched response goes into `raw_postings` before parsing, so parsers can re-run without re-fetching.
6. **Fixture tests.** Parsers are tested against saved fixtures in `scraper/tests/fixtures/`, never live sites. Fixtures are immutable; add a new one when a site changes.
7. **Never guess.** Salary, seniority, `ph_eligible`, etc. stay NULL / `unspecified` when the text doesn't support a value.
8. **Idempotent runs.** Loads are upserts keyed on `(source_id, external_id)`, so a run can be late, skipped or repeated.

## 2. Architecture

```
Allowed sources ──fetch──> GitHub Actions daily workflow (Python)
                             1. scraper pipeline (one step per source)
                             2. aggregate.py  (daily_skill_stats, fill missed days)
                             3. retention.py  (trim old text)
                             4. POST dashboard /api/revalidate
                                   │ writes
                                   v
                             Neon Postgres (free tier, 1 GB per project)
                                   ^ reads (read-only role)
                                   │
                           Vercel (Hobby): Next.js dashboard
                             /api/revalidate -> revalidateTag -> cached pages
```

- GitHub Actions does all writing. Vercel only serves the dashboard, using a **read-only** DB role. No Vercel Cron jobs.
- Schedule: `7 17 * * *` (UTC) = 01:07 Manila, an off-peak minute. GitHub schedules can start late. In public repos, scheduled workflows auto-disable after 60 days without repo activity, so the Ops page flags any source with no successful run in 48 h.

### Database roles (Neon)

| Role | Host | Used by | Env var |
| --- | --- | --- | --- |
| owner (`neondb_owner`) | direct | Prisma Migrate, seed | `MIGRATE_DATABASE_URL` |
| `jobradar_rw` | pooled | scraper, aggregate, retention (GitHub Actions) | `DATABASE_URL` |
| `jobradar_ro` | pooled | dashboard (Vercel `DATABASE_URL`), `postgres` MCP | `JOBRADAR_READONLY_DATABASE_URL` locally |

`jobradar_rw` gets SELECT, INSERT, UPDATE and DELETE on tables plus USAGE on sequences, with no DDL. `jobradar_ro` gets SELECT only, with `default_transaction_read_only = on`. Default privileges are set so future tables inherit both grants. Both roles are created with SQL by `scripts/setup_db_roles.py`, not through the Neon API, so they are not members of `neon_superuser`.

Neon project: `job-radar` (`rough-pine-12150056`) in `aws-ap-southeast-1` (Singapore), database `neondb`. Deploy the dashboard to Vercel region `sin1` to match.

## 3. Stack

- **Scraper** (`scraper/`, Python 3.12, managed by uv): httpx (one shared client: User-Agent, rate limit, retries with backoff on 429/5xx, honours Retry-After), BeautifulSoup + lxml, feedparser, pydantic, rapidfuzz, psycopg 3, pytest, ruff.
- **Dashboard** (`dashboard/`, TypeScript, pnpm): Next.js 16 App Router (Cache Components), Prisma 7 ORM + Migrate with `@prisma/adapter-neon`, Tailwind 4 + shadcn/ui, Recharts, Vitest, ESLint, Prettier. No auth: the whole dashboard is public (decided 2026-11-02).
- **Infra:** GitHub Actions, Vercel Hobby (root directory `dashboard/`), Neon Postgres.

## 4. Schema

Defined in `dashboard/prisma/schema.prisma`. Names below are the snake_case database names.

```
sources(id, name, base_url, kind['api'|'rss'|'html'], is_active, crawl_interval_minutes, last_crawled_at, attribution_text, terms_url)
crawl_runs(id, source_id, started_at, finished_at, status['running'|'ok'|'failed'], pages_fetched, postings_found, postings_new, error_message)
raw_postings(id, source_id, crawl_run_id, external_id, url, payload TEXT, content_hash, fetched_at, parsed_at, parse_error, UNIQUE(source_id, external_id))
companies(id, name, normalized_name UNIQUE)
postings(id, raw_posting_id, source_id, company_id, title, title_normalized,
  seniority['intern'|'junior'|'mid'|'senior'|'lead'|'unspecified'],
  job_type['full_time'|'part_time'|'contract'|'freelance'|'unspecified'],
  work_setup['remote'|'hybrid'|'onsite'|'unspecified'],
  ph_eligible BOOLEAN NULL, location_text,
  salary_raw, salary_currency, salary_period, salary_min_php_monthly, salary_max_php_monthly,
  description TEXT NULL, source_url NOT NULL,
  posted_at, first_seen_at, last_seen_at, is_active, fingerprint,
  canonical_posting_id NULL REFERENCES postings(id))
skills(id, name, category['language'|'framework'|'database'|'tool'|'cloud'])
skill_aliases(id, skill_id, pattern)          -- regex
posting_skills(posting_id, skill_id, PK(posting_id, skill_id))
exchange_rates(date, currency, php_per_unit, PK(date, currency))
daily_skill_stats(date, skill_id, active_postings, new_postings, median_salary_php, PK(date, skill_id))
```

## 5. Pipeline

`scraper/pipeline.py`: fetch → raw → parse → normalize → tag → dedupe → load.

- Each adapter in `scraper/sources/<name>.py` exposes `fetch(client)`, which yields raw items, and `parse(raw)`, which returns the common dict validated by pydantic.
- `--source <name>` runs one source. `--dry-run` fetches and parses but doesn't write.
- Every run writes a `crawl_runs` row (status, counts, error).
- Parse failures are stored in `raw_postings.parse_error` and don't abort the run.

## 6. Processing rules

- **Salary.** Keep `salary_raw`. Parse forms like `₱40k–60k/month`, `PHP 50,000`, `$15–20/hr`, `$30,000/yr` and `USD 90k - 130k`. Convert to monthly (hourly × 160, daily × 22, annual ÷ 12), then to PHP using `exchange_rates` for the first-seen date. NULL when absent or unparseable.
- **Seniority** (case-insensitive, first match wins):
  1. `\b(lead|principal|staff)\b` → lead
  2. `\b(senior|sr\.?)\b` → senior
  3. `\bintern(ship)?\b` → intern
  4. `\b(junior|jr\.?|entry[- ]level)\b` → junior
  5. otherwise → unspecified
- **Job type:** `part[- ]time`, `freelance|project[- ]based`, `contract(ual)?`, `full[- ]time`.
- **Work setup:** the source's own field first, then `remote|wfh|work from home`, then `hybrid`.
- **ph_eligible:**
  - Positive: `philippines|PH-based|filipino|asia|APAC|worldwide|anywhere`.
  - Negative: `US only`, `must (reside|be located) in <non-PH country>`, `EU timezone required`, `US work authorization`.
  - An explicit negative beats a generic positive. Any other conflict → NULL.
- **Skill tagging:** word-boundary regex aliases from `skill_aliases`, run over title + description.
  - Ambiguous names (Go, R, C, Swift, Rust, Dart, Spring) need context, e.g. `golang|\bgo (developer|engineer)\b`, or a match inside a requirements section extracted with BeautifulSoup.
  - Every alias has positive AND negative tests.
- **Dedupe:**
  - Pass 1 (exact): `fingerprint = sha1(company.normalized_name + title_normalized + work_setup)` within 30 days.
  - Pass 2 (fuzzy): same company AND rapidfuzz `token_set_ratio(title) ≥ 90` AND a description similarity check.
  - Duplicates set `canonical_posting_id`. Dashboard queries filter `canonical_posting_id IS NULL`.

## 7. History and retention

Neon free tier = 1 GB per project. Keep 5 years of history and trim bulky text so it fits.

| Data | Kept for |
| --- | --- |
| postings (minus description), posting_skills, daily_skill_stats | 5 years |
| postings.description | 90 days, then set NULL |
| raw_postings.payload | 90 days, then delete |
| crawl_runs | 1 year |

- Estimate: ~150 new postings/day ≈ 275k in 5 years ≈ 0.3 GB trimmed (0.8–1 GB untrimmed).
- The Ops page shows DB size and warns above 800 MB. The fallback is 3 years of history.
- At the cap, Neon blocks writes but deletes nothing.
- `aggregate.py` recomputes missing days from `first_seen_at` / `last_seen_at`.

## 8. Dashboard

| Page | Route | Content |
| --- | --- | --- |
| Overview | `/` | Stat cards (active postings, new this week, % with salary, % remote and PH-eligible); job type and work setup donuts |
| Skills | `/skills` | Top skills this month vs last (bar, % change); weekly trend line for selected skills |
| Salaries | `/salaries` | Median and range per skill, always with sample size (n) |
| Matches for me | `/matches` | Public page. Postings matching the owner's skill set, part-time/freelance and PH-eligible, newest first. The skill set is a committed config file (`dashboard/config/my-skills.ts`), not stored in the DB, so the dashboard stays read-only |
| Ops | `/ops` | `crawl_runs` status/errors per source; last successful run per source (flag > 48 h); DB size (warn > 800 MB) |

- Every posting row shows a "via <Source>" link to `source_url`.
- Data loaders use `'use cache'` + `cacheTag` with the tags `postings`, `skill-stats` and `ops`.
- `POST /api/revalidate` (Bearer `REVALIDATE_SECRET`) calls `revalidateTag(tag, "max")` for each tag.

## 9. Workflows

- `scrape.yml` runs daily at `7 17 * * *`, plus manual dispatch. One step per source (`continue-on-error`), then `aggregate.py` → `retention.py` → `curl` POST to `/api/revalidate`.
- `backfill-hn.yml` is manual. It loads 5 years of HN "Who is Hiring?" threads.
- `migrate.yml` runs on push to `main` when `dashboard/prisma/**` changes: `prisma migrate deploy` using `MIGRATE_DATABASE_URL`.

## 10. Build order

1. Repo skeleton, Claude Code setup and docs. ✅
2. Neon roles; `schema.prisma`; first migration (`prisma migrate dev`); seed sources and ~50 skills with aliases.
3. `scraper/http.py`, then Remotive end to end via `/add-source`.
4. A bare postings table page, so real data is visible.
5. Salary, classification and skill-tagging rules, each with fixture tests.
6. Remote OK, then dedupe.
7. `aggregate.py`, chart widgets, `/api/revalidate` wired to cached loaders.
8. HN "Who is Hiring?" parser (the BeautifulSoup showcase) and We Work Remotely RSS.
9. Workflows: `scrape.yml`, `migrate.yml`, then one run of `backfill-hn.yml`.
10. `retention.py` and the Ops page DB-size warning.
11. Deploy the dashboard to Vercel; README with architecture, fixture-based tests, attribution, screenshots.
