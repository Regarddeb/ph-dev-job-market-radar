# PH Dev Job Market Radar

A portfolio project. A daily GitHub Actions job scrapes allowed remote-dev job sources (Python), classifies the listings with deterministic rules, and stores them in Neon Postgres. A Next.js dashboard on Vercel shows skill demand, pay and PH-eligible part-time/freelance roles. It showcases scraping (BeautifulSoup), data processing and dashboards.

Full design: @docs/SPEC.md · Source registry: @docs/SOURCES.md

## Hard rules
- **No LLM/AI API calls** anywhere in `scraper/` or `dashboard/`. Extraction uses only regex, keyword dictionaries and rapidfuzz.
- **Only sources marked Allowed in docs/SOURCES.md.** Never JobStreet, JobsDB/SEEK, LinkedIn, Indeed, Upwork, OnlineJobs.ph or Remotive. No logins, anti-bot bypassing or IP/proxy rotation.
- Respect each source's terms: rate limits, an identifying User-Agent (`SCRAPER_USER_AGENT`), attribution. Every posting keeps `source_url`, and the UI shows "via <Source>".
- **Prisma owns the schema.** Python never runs DDL. Never edit a committed migration; add a new one. Use snake_case DB names via `@map` / `@@map`.
- **Raw first:** store responses in `raw_postings` before parsing.
- **Tests use fixtures** in `scraper/tests/fixtures/`, never live sites. Fixtures are immutable; add a new dated file.
- **Never guess:** unknown salary, seniority, `ph_eligible`, etc. stay NULL / `unspecified`.
- **Idempotent:** upserts on `(source_id, external_id)`.

## Layout
- `scraper/`: Python 3.12 (uv project; `__init__.py` makes it the `scraper` package)
  - `http.py`: the shared httpx client
  - `sources/<name>.py`: one adapter per source
  - `normalize/`: salary, classify, skills
  - `dedupe.py`, `pipeline.py`, `aggregate.py`, `retention.py`
  - `tests/fixtures/`
- `dashboard/`: Next.js 16 App Router (Cache Components), Prisma 7 (`prisma.config.ts`, client generated to `lib/generated/prisma`), Tailwind 4 + shadcn/ui (base-nova), Recharts, Vitest
  - Routes are in `app/(dashboard)/`; the revalidation endpoint is `app/api/revalidate/`.
  - Next 16 differs from older versions: read `dashboard/AGENTS.md` and `node_modules/next/dist/docs/` before writing Next code.
- `.github/workflows/`: `scrape.yml`, `backfill-hn.yml`, `migrate.yml` (not yet created)
- `.claude/`: skills (`add-source`, `add-skill-tag`, `run-pipeline`, `scraping-etiquette`), agents (`source-researcher`, `parser-reviewer`, `data-quality-auditor`), hooks

## Environment
- Windows + Git Bash. Use forward slashes. Bare `python` is the MS Store stub, so run Python through **uv**.
- Run scraper commands **from the repo root** with `--project scraper`. Never put `scraper/` itself on `sys.path`: `scraper/http.py` would shadow the stdlib `http` module.
- Secrets live in one root `.env` (copy `.env.example`; never commit it, and Claude never edits it). `dashboard/next.config.ts` and `prisma.config.ts` load `../.env`.
- Database URLs:
  - `DATABASE_URL`: read-write, pooled; used by the scraper.
  - `MIGRATE_DATABASE_URL`: owner, direct; used by Prisma Migrate.
  - `JOBRADAR_READONLY_DATABASE_URL`: read-only; used by the local dashboard and the `postgres` MCP server. It must be exported in the shell that launches Claude Code.
- Neon: org `Humphrey` (`org-empty-pond-46580301`), project `job-radar` (`rough-pine-12150056`), region `aws-ap-southeast-1`, database `neondb`, branch `main`. `neon.ts` and the root `package.json` are Neon config only. `.neon` is the local link file (gitignored).
- Roles: the owner `neondb_owner` (migrations only), `jobradar_rw` (no DDL) and `jobradar_ro` (SELECT only, read-only transactions). `scripts/setup_db_roles.py` creates them or rotates their passwords and rewrites `.env`. Re-run it after any `neon env pull`, because that overwrites `DATABASE_URL` with the owner role.
- GitHub secrets: `DATABASE_URL`, `MIGRATE_DATABASE_URL`, `SCRAPER_USER_AGENT`, `REVALIDATE_SECRET`, `DASHBOARD_URL`.
- Vercel env: `DATABASE_URL` (the read-only role) and `REVALIDATE_SECRET`.

## Commands (keep current)
```bash
# scraper (from repo root)
uv sync --project scraper                                   # install deps (Python 3.12 auto-installed)
uv run --project scraper python -m pytest                   # tests (fixtures only)
uv run --project scraper ruff check scraper                 # lint
uv run --project scraper ruff format scraper                # format
uv run --project scraper python -m scraper.pipeline --source <slug> --dry-run   # fetch+parse, no writes
uv run --project scraper python -m scraper.pipeline --source <slug>             # full run into Neon
uv run --project scraper python -m scraper.pipeline --source <slug> --fixture <file> [--dry-run]  # no network
uv run --project scraper python -m scraper.capture <slug>                       # save a new dated fixture
uv run --project scraper python -m scraper.reparse --source <slug> [--dry-run]  # re-apply rules to stored raw (no fetch)
uv run --project scraper python -m scraper.fx [--history|--fixture <f>|--capture] [--dry-run]  # ECB rates -> exchange_rates
uv run --project scraper python -m scraper.dedupe [--dry-run] [--recompute]     # mark duplicates (all sources)
uv run --project scraper python -m scraper.aggregate [--full|--days N] [--dry-run]  # daily_skill_stats (Manila days)
uv run --project scraper python -m scraper.backfill_hn [--months 60] [--max-requests N] [--dry-run]  # past HN threads (resumable)
uv run --project scraper python -m scraper.retention [--dry-run]                  # trim per SPEC §7

# dashboard (cd dashboard)
pnpm install                 # also runs prisma generate
pnpm dev                     # http://localhost:3000
pnpm lint | pnpm typecheck | pnpm test | pnpm format
pnpm build                   # prisma generate + next build
pnpm db:migrate --name <x>   # prisma migrate dev (MIGRATE_DATABASE_URL)
pnpm db:deploy               # prisma migrate deploy
pnpm db:seed                 # idempotent seed: sources, skills, aliases (prisma/data/skills.json)

# Neon roles (repo root): add --grants-only to re-apply grants without rotating passwords
uv run --project scraper python scripts/setup_db_roles.py

# Claude Code hooks self-test
uv run --no-project python .claude/hooks/test_hooks.py
```

## Hooks (in `.claude/settings.json`)
- `guard_files.py` blocks edits to `.env*` (except `.env.example`), to existing fixtures, and to git-tracked migrations.
- `guard_bash.py` blocks shell commands that name forbidden job-site domains.
- `format_file.py` runs ruff on `.py` files and Prettier + ESLint on dashboard TS/JS after each edit, and reports leftover lint problems.

## Gotchas
- **Smart App Control is on** in this Windows install, and it sometimes blocks uv's venv launchers (`.venv/Scripts/python.exe`, `pytest.exe`) with "An Application Control policy has blocked this file". Fix it with `cd scraper && uv venv --clear && uv sync`. Prefer `python -m pytest` over the `pytest.exe` shim.
- **Neon connections can fail on the first try** (P1001 / timeouts) while the compute wakes from scale-to-zero. Retry once before debugging.
- **Open Postgres connections only with `scraper.db.connect`.** It sets a connect timeout, TCP keepalives and `tcp_user_timeout`. Without them, a connection Neon silently drops makes a statement hang about 10 minutes; this happened twice. Long runs use autocommit with one transaction per item, so a crash keeps earlier work.
- **Skills live in `dashboard/prisma/data/skills.json`.** Each skill carries its own `match` / `no_match` examples. Use `/add-skill-tag`.

- **Adapters must be in the `ADAPTERS` allowlist** (`scraper/sources/__init__.py`) and Allowed in SOURCES.md. `tests/test_sources_registry.py` enforces both.
- **Remote OK's data has mojibake and HTML entities in the source itself**, and its feed mixes non-dev jobs. `clean_text` / `html_to_text` and `is_relevant` handle both. Salary values below USD 10k aren't treated as annual (no period is guessed).
- **Remote OK tags are keyword-stuffed** ("Tax Manager" tagged `dev`, `php`). Relevance, job type and ph_eligible never rely on them; the title decides relevance (`classify.is_dev_title`).
- **After changing any rule in `scraper/normalize/` or a parser**, run `python -m scraper.reparse --source <slug> --dry-run`, then without `--dry-run`. Reparse deletes postings that no longer pass `is_relevant` (they rebuild from raw).
- **HN fixtures are JSONL** (one captured response per line); `capture` and `--fixture` handle `.jsonl`. HN's header line is `Company | Role | Location | Salary | URL` in any order, or free prose; `hn_hiring.parse` classifies segments, and `is_relevant` drops job seekers posting in the hiring thread.
- **HN freelancer-thread tags turn up in the hiring thread.** `SEEKING WORK` / `SEEKING FREELANCE` headers are job seekers (dropped by `is_relevant`); `SEEKING FREELANCER` is a client hiring: the tag is not a company, and it sets `job_type = freelance`.
- **`/postings` state lives in the URL** (`dashboard/lib/postings-params.ts`). Add a filter there first (parse, query string, test), then in `lib/queries/postings.ts` and `components/postings-filters.tsx`. The page reads `searchParams` inside `<Suspense>`, which Cache Components requires.
- **Incremental sources:** an adapter whose `fetch_pages` takes `on_listing` reports every listed id. The pipeline skips stored ones that pass `adapter.is_final` and still counts them as seen.
- **`is_active` = listed in the source's latest successful crawl.** `Loader.finish` clears it for unseen postings, but only after an error-free run that found postings.
- **Restart `pnpm dev` after editing `globals.css` theme tokens.** A long-running dev server kept serving the old CSS.
- **PHP salaries come from ECB cross rates.** Any page that shows a PHP-converted salary must cite the ECB and say the rates are derived (SOURCES.md, Reference data).

## Status
Steps 1–10 are done. The daily run is fx → remoteok → hn_hiring → dedupe → aggregate → retention → revalidate; revalidate is skipped until `DASHBOARD_URL` exists. Overview, Skills and Salaries show real charts, Ops shows crawl health and DB size, and PH-friendly (`/ph-friendly`) lists roles open to PH-based applicants, which visitors filter by job type and skills. The whole site is public and informational, with no per-person pages.
- **Two live sources:** Remote OK (39 dev postings) and **HN "Who is Hiring?"** (156 from the November 2026 thread, official API, incremental). Both get seniority, job type, ph_eligible, PHP salary (ECB rates since 2021) and skills derived.
- **We Work Remotely is Unclear** (2026-11-08): don't build it until the owner confirms its terms.
- **Sources vetted 2026-11-16** (SOURCES.md): Jobicy came back Allowed from `source-researcher` and waits for the owner's confirmation; the HN freelancer thread is a candidate under HN's existing terms; Himalayas, Working Nomads, Greenhouse, Lever, Ashby, Arbeitnow, Adzuna and The Muse are Unclear.
- **Public-dashboard pass (2026-11-16):** `/postings` has server-side filters and numbered pagination, all posting lists share `components/posting-card.tsx`, and the shell has a sticky header, theme toggle and attribution footer (SPEC §8). Not yet deployed.
- **The HN 5-year backfill is built** (`scraper/backfill_hn.py`, `backfill-hn.yml`, resumable, ~5 manual runs of 6,000 requests, ~4.2 h each). It was tested with 60 requests into October 2026: 44 inactive postings with their historical dates.
- **`migrate.yml`** runs `prisma migrate deploy` and then the idempotent seed whenever `dashboard/prisma/**` changes on main. The daily `scrape.yml` loads rates first. **Remotive is excluded** (Forbidden in SOURCES.md since 2026-11-06). `/postings` lists active canonical postings via the cached loader `lib/queries/postings.ts` (tag `postings`; prerendered at build, so `pnpm build` reads Neon). **Deployed (2026-11-08): https://ph-dev-job-market-radar.vercel.app**. The Vercel project is `ph-dev-job-market-radar` (CLI-linked from `dashboard/`, no Git integration: deploy with `cd dashboard && vercel deploy --prod`). Functions run in `sin1` (`dashboard/vercel.json`), and env holds the read-only `DATABASE_URL` and `REVALIDATE_SECRET`. The GitHub secrets `DASHBOARD_URL` and `REVALIDATE_SECRET` (rotated 2026-11-08) let the daily scrape revalidate the live site. Next: README and screenshots (the rest of step 11). The HN backfill is in progress (started 2026-11-08; re-dispatch `backfill-hn.yml` until `remaining` is ~0). See SPEC §10.
