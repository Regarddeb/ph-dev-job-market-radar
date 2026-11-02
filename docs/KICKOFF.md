You are taking over a new portfolio project, "PH Dev Job Market Radar". The repo is empty or nearly empty. Everything you need is below. Read all of it before doing anything.

# What the project is

A personal portfolio project that tracks the remote developer job market for a Philippines-based developer. It scrapes allowed job sources once a day, cleans and classifies the listings with deterministic rules, stores them in Postgres, and shows trends in a web dashboard: which skills are in demand, what roles pay, and which part-time/freelance roles accept PH-based applicants.

It must clearly demonstrate three things: **web scraping (BeautifulSoup)**, **data processing**, and **dashboards**.

# Hard rules

- **No LLM integration in the app.** No AI/LLM API calls anywhere in `scraper/` or `dashboard/`. All extraction is rule-based (regex, keyword dictionaries, rapidfuzz). Claude Code is a dev tool here, not a runtime dependency.
- **Only scrape sources marked Allowed** (list below). Never add JobStreet, JobsDB/SEEK, LinkedIn, Indeed, Upwork or OnlineJobs.ph. Never log in, bypass anti-bot measures, or rotate IPs/proxies.
- **Follow each source's terms**: rate limits, an identifying User-Agent, attribution. Every posting keeps its source URL, and the dashboard shows a "via <Source>" link on every posting.
- **Prisma (in `dashboard/`) owns the schema.** Python never runs DDL; it only reads and writes rows. Never edit a committed migration; add a new one. Use `@map`/`@@map` so every table and column name is snake_case for the Python side.
- **Raw first.** Store every fetched response in `raw_postings` before parsing, so parsers can re-run without re-fetching.
- **Test parsers against saved fixtures** in `scraper/tests/fixtures/`, never against live sites. Existing fixtures are immutable; add a new one when a site changes.
- **Never guess.** Salary, seniority, `ph_eligible`, etc. stay NULL / `unspecified` when the text doesn't support a value.
- **Idempotent runs.** Loads are upserts keyed on `(source_id, external_id)`; a run can be late, skipped or re-run.

# Architecture

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

- GitHub Actions does all writing; Vercel only serves the dashboard with a **read-only** DB role. No Vercel Cron jobs.
- GitHub schedules run in UTC and can start late; use an off-peak minute, e.g. `7 17 * * *` (01:07 Manila). In public repos, scheduled workflows auto-disable after 60 days without repo activity, so the Ops page must flag any source with no successful run in 48 h.

# Stack

**Scraper (`scraper/`, Python 3.12):** httpx (one shared client: User-Agent, rate limit, retries with backoff on 429/5xx, respect Retry-After), BeautifulSoup + lxml, feedparser, pydantic (validate payloads), rapidfuzz, psycopg, pytest, ruff.

**Dashboard (`dashboard/`, TypeScript):** Next.js App Router, Prisma ORM + Prisma Migrate (connected to Neon through Prisma's Neon driver adapter; check current Prisma docs for setup), Tailwind + shadcn/ui, Recharts, Vitest, ESLint, Prettier. Auth.js only if "Matches for me" stays private (ask me later).

**Infra:** GitHub Actions, Vercel Hobby (root directory `dashboard/`), Neon Postgres.

# Repo layout

```
job-radar/
  .github/workflows/
    scrape.yml          daily: scrape -> aggregate -> retention -> revalidate
    backfill-hn.yml     manual: load 5 years of HN "Who is Hiring?" threads
    migrate.yml         on push to main: prisma migrate deploy
  scraper/
    http.py             shared httpx client
    sources/            one adapter per site: fetch() + parse() -> common dict
    normalize/          salary.py, classify.py, skills.py
    dedupe.py
    pipeline.py         fetch -> raw -> parse -> normalize -> tag -> dedupe -> load
    aggregate.py
    retention.py
    tests/fixtures/     saved raw responses (immutable)
    pyproject.toml
  dashboard/
    app/(dashboard)/    overview, skills, salaries, matches, ops
    app/api/revalidate/ checks REVALIDATE_SECRET, calls revalidateTag
    components/
    prisma/schema.prisma  Prisma schema (schema owner)
    prisma/migrations/    generated SQL migrations (committed, never edited)
    prisma/seed.ts        sources, skills, skill_aliases
  docs/                 SPEC.md, SOURCES.md
  CLAUDE.md
```

# Schema (define in `dashboard/prisma/schema.prisma`; snake_case names via `@map`/`@@map`)

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

# Processing rules

- **Salary:** keep `salary_raw`; parse forms like `₱40k–60k/month`, `PHP 50,000`, `$15–20/hr`, `$30,000/yr`, `USD 90k - 130k`; convert to monthly (hourly × 160, daily × 22, annual ÷ 12) and to PHP using `exchange_rates` for the first-seen date; NULL when absent or unparseable.
- **Seniority** (case-insensitive, first match wins): `\b(lead|principal|staff)\b` → lead; `\b(senior|sr\.?)\b` → senior; `\bintern(ship)?\b` → intern; `\b(junior|jr\.?|entry[- ]level)\b` → junior; else unspecified.
- **Job type:** `part[- ]time`, `freelance|project[- ]based`, `contract(ual)?`, `full[- ]time`. **Work setup:** source field first, then `remote|wfh|work from home`, `hybrid`.
- **ph_eligible:** positive `philippines|PH-based|filipino|asia|APAC|worldwide|anywhere`; negative `US only`, `must (reside|be located) in <non-PH country>`, `EU timezone required`, `US work authorization`. Explicit negative beats generic positive; other conflicts → NULL.
- **Skill tagging:** word-boundary regex aliases from `skill_aliases` over title + description. Ambiguous names (Go, R, C, Swift, Rust, Dart, Spring) need context (e.g. `golang|\bgo (developer|engineer)\b`) or a match inside a requirements section extracted with BeautifulSoup. Every alias gets positive AND negative tests.
- **Dedupe:** pass 1 exact `fingerprint = sha1(company.normalized_name + title_normalized + work_setup)` within 30 days; pass 2 fuzzy: same company AND rapidfuzz `token_set_ratio(title) ≥ 90` AND a description similarity check. Duplicates set `canonical_posting_id`; dashboard queries filter `canonical_posting_id IS NULL`.

# History and retention (Neon free tier = 1 GB per project)

Keep 5 years of history; trim bulky text so it fits.

| Data | Kept for |
| --- | --- |
| postings (minus description), posting_skills, daily_skill_stats | 5 years |
| postings.description | 90 days, then set NULL |
| raw_postings.payload | 90 days, then delete |
| crawl_runs | 1 year |

Estimate: ~150 new postings/day ≈ 275k in 5 years ≈ 0.3 GB trimmed (0.8–1 GB untrimmed). Ops page shows DB size and warns above 800 MB; fallback is 3 years of history. At the cap Neon blocks writes but deletes nothing. `aggregate.py` recomputes missing days from `first_seen_at`/`last_seen_at`.

# Sources

**Allowed** (verify terms again before implementing each; record the check date in `docs/SOURCES.md`):

| Source | Kind | Access | Rules |
| --- | --- | --- | --- |
| Remotive | api | `https://remotive.com/api/remote-jobs?category=software-dev` | ≤ ~4 requests/day (poll once daily); jobs delayed 24 h; don't resubmit to other job boards; link back to the Remotive URL and name Remotive as source |
| Remote OK | api | `https://remoteok.com/api` (`?tags=`) | Returns latest ~100 only; first array element is a legal notice, skip it; followed (not nofollow) link back + name Remote OK |
| We Work Remotely | rss | programming category RSS feeds | Verify terms first; link back |
| HN "Who is Hiring?" | api + html | official HN API; comment bodies parsed with BeautifulSoup | Polite rate; link to the comment. Also the 5-year backfill source |
| Himalayas, Arbeitnow, Greenhouse/Lever boards | api | official feeds | Candidates only: vet with `source-researcher` first |

**Forbidden:** JobStreet / JobsDB / SEEK (terms prohibit scraping and robots without written consent), LinkedIn, Indeed, Upwork (terms prohibit scraping), OnlineJobs.ph (no API; employer data behind login).

# Dashboard pages

- **Overview:** stat cards (active postings, new this week, % with salary, % remote and PH-eligible); job type and work setup donuts.
- **Skills:** top skills this month vs last (bar, % change); weekly trend line for selected skills.
- **Salaries:** median and range per skill, always with sample size (n).
- **Matches for me:** postings matching a saved skill set, part-time/freelance and PH-eligible, newest first.
- **Ops:** `crawl_runs` status/errors per source, last successful run per source (flag > 48 h), DB size (warn > 800 MB).

Every posting row shows a "via <Source>" link.

# Claude Code setup to create in this repo

- **`CLAUDE.md`:** concise project memory: purpose, hard rules, stack, layout, environment, commands (keep the commands list current), pointers to `docs/SPEC.md` and `docs/SOURCES.md`.
- **`docs/SPEC.md`:** this design (architecture, schema, processing rules, retention, dashboard, build order). **`docs/SOURCES.md`:** the allowed/forbidden registry above.
- **Skills (`.claude/skills/<name>/SKILL.md`):**
  - `add-source` (`disable-model-invocation: true`, arg `[source-name]`): refuse unless Allowed in SOURCES.md; save one fixture; write `scraper/sources/<name>.py`; pytest test; seed row in `dashboard/prisma/seed.ts`; add a step to `scrape.yml`.
  - `add-skill-tag` (args `[skill] [category]`): add aliases to the seed; positive + negative tests in `scraper/tests/test_skills.py`.
  - `run-pipeline` (`disable-model-invocation: true`): `python -m scraper.pipeline --source <name> --dry-run`; report fetched/parsed/errors and coverage (% salary, % seniority set, % ph_eligible set, avg skills).
  - `scraping-etiquette` (`user-invocable: false`, `paths: scraper/**`): the fetch rules above.
- **Subagents (`.claude/agents/`):**
  - `source-researcher` (tools: WebSearch, WebFetch, Read, Grep): vets a candidate source's terms, robots.txt, API, limits, attribution; returns a verdict and a SOURCES.md row; ambiguous terms → "Unclear".
  - `parser-reviewer` (tools: Read, Grep, Glob, Bash): read-only audit of parsers and rules against fixtures; finds guessing, salary errors, ordering bugs, alias false positives, regex risks.
  - `data-quality-auditor` (tools: Read, Grep + the `postgres` MCP server): read-only SQL checks: freshness, duplicates, salary sanity, coverage, missing `source_url`, missing daily stats.
- **Hooks (`.claude/settings.json` → Python scripts in `.claude/hooks/`, invoked as `python "$CLAUDE_PROJECT_DIR/.claude/hooks/<file>.py"`):**
  - PreToolUse `Edit|Write`: block edits to `.env*` (except `.env.example`), existing files in `scraper/tests/fixtures/`, and git-tracked files in `dashboard/prisma/migrations/` (exit 2 with a message).
  - PreToolUse `Bash`: block commands referencing jobstreet., jobsdb., seek.com, linkedin.com, indeed., upwork.com, onlinejobs.ph.
  - PostToolUse `Edit|Write`: `ruff format` + `ruff check --fix` for `.py`; Prettier + `eslint --fix` for `.ts/.tsx` (non-blocking).
- **MCP (`.mcp.json`):** `postgres` (read-only role via `${JOBRADAR_READONLY_DATABASE_URL}`), `playwright` (`@playwright/mcp`) to check the dashboard renders.
- **`.env.example`** and **`.gitignore`** (ignore `.env*` except the example, `.venv`, caches, `node_modules`, `.claude/settings.local.json`).

Check current Claude Code docs for exact skill, subagent, hook and MCP file formats before writing them.

# Environment

Windows + Git Bash. Use `python`, not `python3`. Use forward slashes in paths. Secrets: GitHub Actions secrets `DATABASE_URL`, `SCRAPER_USER_AGENT`, `REVALIDATE_SECRET`; Vercel env read-only `DATABASE_URL`, `REVALIDATE_SECRET`; local `.env` (never committed).

# Build order

1. Repo skeleton: `scraper/` (pyproject, pytest, ruff) and `dashboard/` (Next.js, TS, Tailwind, shadcn/ui, Prisma, Vitest, ESLint, Prettier); all the Claude Code setup files and docs above.
2. Neon: read-write + read-only roles; `schema.prisma`; first migration with `prisma migrate dev`; seed `sources` and ~50 skills with aliases.
3. `scraper/http.py`, then Remotive end to end (fetch, raw storage, parse, load) via the add-source procedure.
4. Bare postings table page so real data is visible.
5. Salary, classification and skill-tagging rules, each with fixture tests.
6. Remote OK, then dedupe.
7. `aggregate.py`, chart widgets, `/api/revalidate`.
8. HN "Who is Hiring?" parser (the BeautifulSoup showcase) and We Work Remotely RSS.
9. Workflows: `scrape.yml`, `migrate.yml`, then run `backfill-hn.yml` once.
10. `retention.py` and the Ops page DB-size warning.
11. Deploy dashboard to Vercel; README with architecture, fixture-based tests, attribution, screenshots.

# What to do now

1. Look at the current folder and tell me what's already there.
2. Do build-order step 1 only: create `CLAUDE.md`, `docs/SPEC.md`, `docs/SOURCES.md`, the `.claude/` setup (skills, subagents, hooks, settings), `.mcp.json`, `.env.example`, `.gitignore`, and the empty `scraper/` and `dashboard/` scaffolds.
3. **Before writing files, show me a short plan** (files to create, any decisions you need from me) and wait for my OK.
4. After step 1, verify the hooks fire (try a blocked edit and a blocked command), run `/mcp` and `/hooks` checks I should do, and stop. Tell me what I need to set up manually (Neon roles, env vars, GitHub secrets) before step 2.
