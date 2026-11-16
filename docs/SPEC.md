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
                             0. fx.py (ECB rates -> exchange_rates)
                             1. scraper pipeline (one step per source), then dedupe.py
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

**Additions in the implemented schema** (marked `(+)` in `schema.prisma`):
- `sources.slug` (unique): the `--source <slug>` key and the Python module name (`remoteok`, `hn_hiring`; `weworkremotely` is seeded inactive and is Unclear).
- `postings.external_id` + `UNIQUE(source_id, external_id)`: the posting upsert key.
- `skill_aliases.requirements_only`: the alias only matches inside an extracted requirements section.
- Enums are Postgres enum types: `source_kind`, `crawl_status`, `seniority`, `job_type`, `work_setup`, `skill_category`.
- FKs that point at trimmed tables are nullable `ON DELETE SET NULL`: `postings.raw_posting_id`, `raw_postings.crawl_run_id`, `postings.company_id`, `postings.canonical_posting_id`.
- Hand-added CHECK constraints in the init migration: salary min ≤ max and > 0; `salary_period` ∈ hour/day/week/month/year; non-empty `source_url`; no self-canonical; `first_seen_at ≤ last_seen_at`; positive exchange rates; non-negative crawl counts.
- Skill dictionary: `dashboard/prisma/data/skills.json` (55 skills, 79 aliases), shared by the seed and `scraper/tests/test_skills.py`.

## 5. Pipeline

`scraper/pipeline.py`: fetch → raw → parse → normalize → tag → dedupe → load.

- Each adapter in `scraper/sources/<name>.py` exposes `fetch(client)`, which yields raw items, and `parse(raw)`, which returns the common dict validated by pydantic.
- `--source <name>` runs one source. `--dry-run` fetches and parses but doesn't write.
- Every run writes a `crawl_runs` row (status, counts, error).
- Parse failures are stored in `raw_postings.parse_error` and don't abort the run.
- A row the database refuses (a CHECK or type violation) is skipped and counted, and the run carries on. The `crawl_runs` row stays `ok` with a note in `error_message`, nothing is deactivated that run, and the command exits 1 so the workflow step is flagged. Connection errors still end the run.

## 6. Processing rules

Implemented in `scraper/normalize/` (`salary.py`, `classify.py`, `skills.py`) with fixture tests. `python -m scraper.reparse --source <slug>` re-applies the rules to stored `raw_postings` without fetching.

- **Dev-role filter.** A posting is kept only if its **title** names a software role (`classify.is_dev_title`) and isn't a known non-dev role (sales, account manager, recruiter, accounting, civil/mechanical engineer, …). Source tags alone don't count: Remote OK's are keyword-stuffed.
- **Salary.** Keep `salary_raw`. Parse forms like `₱40k–60k/month`, `PHP 50,000`, `$15–20/hr`, `$30,000/yr` and `USD 90k - 130k`. Convert to monthly (hourly × 160, daily × 22, weekly × 52/12, annual ÷ 12), then to PHP using `exchange_rates` for the first-seen date. NULL when absent or unparseable.
  - The adapter's structured salary fields win over parsing `salary_raw`. No stated period means no monthly figure.
  - The amount must sit next to the currency marker (`$100k`, `USD 90k`, `50,000 PHP`). Two separate amounts (`$10M ARR, $5k/mo`), dot-thousands (`€60.000`) and a bare year (`USD 2025`) are refused.
  - Remote OK: a bound of exactly USD 10,000 (the salary picker's floor, used as a placeholder) is not read as annual.
  - A bare `$` is USD. Marked dollars (`CA$`, `A$`, `S$`, `NZ$`, `HK$`) and ISO codes map to their own currency.
  - **Exchange rates:** ECB euro reference rates (`scraper/fx.py`, daily 90-day feed; history since 2021 loaded once). `php_per_unit` for currency X = PHP/EUR ÷ X/EUR. The lookup takes the latest rate on or before the posting's first-seen UTC day, at most 7 days back (weekends, TARGET holidays). Otherwise PHP stays NULL. The conversion runs in SQL, so it always uses the stored `first_seen_at`.
- **Seniority** (title only; case-insensitive, first match wins):
  1. `\b(lead|principal|staff)\b` → lead
  2. `\b(senior|sr\.?)\b` → senior
  3. `\bintern(ship)?\b` → intern
  4. `\b(junior|jr\.?|entry[- ]level)\b` → junior
  5. otherwise → unspecified
- **Job type:** `part[- ]time`, `freelance|project[- ]based`, `contract(ual)?`, `full[- ]time` (in this order, first match wins).
  - Checked in the source field, then the title, then the description. Source tags are not used.
  - In the description, a type counts only when it is stated about this job: a labelled field (`Type: Full-time`), an item in a `Remote · Full time · …` line, or a phrase like `this is a full-time role` / `contract-based`. Bare "contract" (smart contracts, API contracts) never counts.
  - Full-time alongside another type in the description (`full-time or contract`) is a conflict → `unspecified`.
- **Work setup:** the source's own field first, then the title and location: `hybrid` (checked first, so "hybrid, 2 days remote" isn't remote), then `remote|wfh|work from home`, then `on-site|in office`. Descriptions are not used.
- **ph_eligible** (title, location and description):
  - Strong positive: `philippines|filipino|PH-based`, anywhere.
  - A negative that names the Philippines itself (`cannot hire in the Philippines`, `anywhere except the Philippines`, `… Philippines are not eligible`) → false, checked first.
  - Generic positive: `asia|APAC|worldwide|anywhere` (plus `global` in the location field), in the title or location. In the description it needs hiring context (`work from anywhere`, `hiring … APAC`, `anywhere in the world`): bare "worldwide" or "Asia" there is usually marketing copy.
  - Negative: `US only`, `must (reside|be located) in <non-PH country>`, `EU timezone required`, `US work authorization`.
    - Also: `(authorized|eligible) to work in <non-PH country>` (but not "work in US time zones/hours") and `anywhere in <non-PH country>`.
    - Also: a location of only the US (`US`, `Remote - US`).
    - A title scoped to another region (`… LATAM`, `… EMEA`, `… US`) → false only when nothing positive is stated. `Engineer (US or APAC)` → NULL.
  - An explicit negative beats a generic positive. A negative together with a strong positive is a conflict → NULL. Any other conflict → NULL.
- **Skill tagging:** word-boundary regex aliases from `skill_aliases`, run over title + description.
  - Ambiguous names (Go, R, C, Swift, Rust, Dart, Spring) need context, e.g. `golang|\bgo (developer|engineer)\b`, or a match inside a requirements section extracted with BeautifulSoup.
  - Every alias has positive AND negative tests.
- **Dedupe:**
  - Pass 1 (exact): `fingerprint = sha1(company.normalized_name + title_normalized + work_setup)` within 30 days.
  - Pass 2 (fuzzy): same company AND rapidfuzz `token_set_ratio(title) ≥ 90` AND a description similarity check.
  - Duplicates set `canonical_posting_id`. Dashboard queries filter `canonical_posting_id IS NULL`.
  - Implemented in `scraper/dedupe.py`, which runs after all sources (cross-source).
  - Pass 2's description check is `fuzz.ratio ≥ 95`, not 90. Lemon.io's different roles share boilerplate and score 91.
  - Postings without a company never match, and neither do pass-2 pairs missing a description.
  - The canonical is the earliest-seen posting, and duplicates point straight at it.
  - Decisions are sticky: a run only adds duplicates among postings first seen in the last 60 days, because trimmed descriptions can't be re-checked. `--recompute` clears and redoes the last 30 days after a rule change.

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
| PH-friendly roles | `/ph-friendly` | Active postings that accept PH-based applicants (`ph_eligible = true`), newest first. Visitors filter by job type (default: part-time, freelance, contract, not stated; full-time off) and by skills (any of), in the browser. Replaced "Matches for me" on 2026-11-08: the whole site is a public, informational dashboard, so no page is built around one person's skill set |
| Ops | `/ops` | `crawl_runs` status/errors per source; last successful run per source (flag > 48 h); DB size (warn > 800 MB) |

- As built (step 7):
  - **Active** means listed in the source's latest successful crawl. The pipeline clears `is_active` for postings that crawl didn't see.
  - The Overview "donuts" are ranked horizontal bars. Most postings are `unspecified`, and bars compare the parts more exactly.
  - Skills compares rolling windows, the last 30 days vs the 30 before, rather than calendar months. Its trend chart shows up to 4 of the top 8 skills, each skill keeping its colour while selected, with end labels and a table view.
  - Salaries covers postings first seen in the last 90 days. Each posting counts at its (min + max)/2 monthly PHP midpoint. Only skills with n ≥ 3 are charted, and the page cites the ECB for exchange rates.
  - Chart colours are the validated dataviz categorical slots (`--chart-1..5` in `globals.css`).
  - **PH-friendly roles** (`/ph-friendly`) replaces "Matches for me". The site is public and informational, so visitors pick skills and job types themselves. Filtering runs client-side (`lib/ph-filter.ts`), so the page stays cached (tag `postings`).
- As built (2026-11-16, public-dashboard pass):
  - **Postings** (`/postings`) is filtered and paged on the server. The URL is the state (`q`, `type`, `setup`, `skill`, `source`, `ph`, `salary`, `sort`, `page`; `lib/postings-params.ts`), so any view can be shared. 25 per page, numbered pagination. Filter sets without free text are cached per set (tag `postings`); a text search goes straight to the database. The page shell is prerendered and the results stream in (Partial Prerender).
  - **One posting card** (`components/posting-card.tsx`) is used by Overview, Postings and PH-friendly. It shows only stated fields: company, location, salary as written plus the ECB-converted `≈ ₱…/month` when there is one, work setup, job type, seniority, a PH-friendly mark and skills.
  - **PH-friendly** shows 20 roles at a time ("Show more"); its filters stay client-side.
  - **Shell:** sticky header with the current section marked, light/dark theme (system default, remembered in `localStorage`, set by an inline script before first paint), and a footer on every page naming the sources and citing the ECB. Ops is labelled "Status" in the UI; the route is still `/ops`.
- Every posting row shows a "via <Source>" link to `source_url`.
- Data loaders use `'use cache'` + `cacheTag` with the tags `postings`, `skill-stats` and `ops`.
- `POST /api/revalidate` (Bearer `REVALIDATE_SECRET`) calls `revalidateTag(tag, "max")` for each tag.

## 9. Workflows

- `scrape.yml` runs daily at `7 17 * * *`, plus manual dispatch. One step per source (`continue-on-error`), then `aggregate.py` → `retention.py` → `curl` POST to `/api/revalidate`.
- `backfill-hn.yml` is manual. It loads 5 years of HN "Who is Hiring?" threads. Design (decided in step 8, built in step 9):
  - **Discovery.** `user/whoishiring.json` → `submitted` lists every thread the account has posted, three a month. Scan titles for "Ask HN: Who is hiring? (Month YYYY)" back 60 months (~180 story requests).
  - **Fetch.** For each thread, fetch its top-level comments through the same adapter code (`split`/`parse`/`is_relevant`). Past threads are final (`is_final`), so ids already in `raw_postings` are skipped and a run resumes where the last one stopped.
  - **Volume.** ~60 threads × ~450 comments ≈ 27k requests. Measured on the first run (2026-11-08): ~2.5 s per comment from a GitHub runner, being 1 s of API spacing plus round-trips to Neon in Singapore. So `--max-requests 6000` (~4.2 h) fits under the 6 h job limit, and the backfill takes ~5 manual runs.
  - **History, not "seen now".** A backfilled posting takes `first_seen_at` = the comment's time and `last_seen_at` = the thread's end (the next thread's time). It is inserted with `is_active = false`, and the backfill writes no `crawl_runs` or "seen" bumps. PHP salaries convert at the first-seen date; ECB history goes back to 2021.
  - **Size.** Raw payloads and descriptions older than 90 days are trimmed by `retention.py`, so 5 years stays around the 0.3 GB estimate in §7. Run `aggregate.py --full` afterwards.
  - **Monthly reposts.** Employers repost each month. Those land more than 30 days apart, outside dedupe's window, so each month counts as a separate posting (a monthly demand signal).
- **HN in the daily run** (`scrape.yml`, step 8): only the current thread, incrementally. Stored final comments are skipped and marked as still listed. Deleted or dead comments are never stored, so they're re-checked each run (~40 requests).
- `migrate.yml` runs on push to `main` when `dashboard/prisma/**` changes (and on manual dispatch): `prisma migrate deploy` using `MIGRATE_DATABASE_URL`, then the idempotent `pnpm db:seed` so sources and the skill dictionary follow the committed data.

## 10. Build order

1. Repo skeleton, Claude Code setup and docs. ✅
2. Neon roles; `schema.prisma`; first migration (`prisma migrate dev`); seed sources and ~50 skills with aliases. ✅
3. `scraper/http.py`, then Remote OK end to end via `/add-source` ✅. Remote OK replaced Remotive, which was excluded on 2026-11-06 because its robots.txt and Terms of Use conflict with its API page (see SOURCES.md, Forbidden).
4. A bare postings table page (`/postings`), so real data is visible. ✅
5. Salary, classification and skill-tagging rules, each with fixture tests; ECB exchange rates; title-based dev filter; `reparse` backfill. ✅
6. Dedupe (`scraper/dedupe.py`, daily step after the sources). ✅
7. `aggregate.py`, chart widgets, `/api/revalidate` wired to cached loaders. ✅ (`scrape.yml` calls it once the `DASHBOARD_URL` secret exists.)
8. HN "Who is Hiring?" parser (the BeautifulSoup showcase) and We Work Remotely RSS. ✅ HN is live (daily, incremental), and the 5-year backfill is designed (§9). We Work Remotely moved to **Unclear** (2026-11-08): its terms reportedly forbid storing data, and the owner must confirm before any adapter.
9. Workflows: `scrape.yml`, `migrate.yml`, then one run of `backfill-hn.yml`. ✅ All three workflows exist. `migrate.yml` also re-runs the idempotent seed. The backfill command was verified locally on October 2026; the full 60-month backfill runs via `backfill-hn.yml` after push.
10. `retention.py` and the Ops page DB-size warning. ✅ Retention runs daily after aggregate. The Ops page (`/ops`, tag `ops`, hourly cache) shows DB size against 1 GB with the 800 MB line, per-source health (stale after 48 h), and the last 20 crawl runs.
11. Deploy the dashboard to Vercel; README with architecture, fixture-based tests, attribution, screenshots. Deploy ✅ 2026-11-08: https://ph-dev-job-market-radar.vercel.app (`sin1`, CLI deploys, read-only DB role). README pending.
