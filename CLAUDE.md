# PH Dev Job Market Radar

A portfolio project. A daily GitHub Actions job scrapes allowed remote-dev job sources (Python), classifies the listings with deterministic rules, and stores them in Neon Postgres. A Next.js dashboard on Vercel shows skill demand, pay and PH-eligible part-time/freelance roles. It showcases scraping (BeautifulSoup), data processing and dashboards.

Full design: @docs/SPEC.md · Source registry: @docs/SOURCES.md

## Hard rules
- **No LLM/AI API calls** anywhere in `scraper/` or `dashboard/`. Extraction uses only regex, keyword dictionaries and rapidfuzz.
- **Only sources marked Allowed in docs/SOURCES.md.** Never JobStreet, JobsDB/SEEK, LinkedIn, Indeed, Upwork or OnlineJobs.ph. No logins, anti-bot bypassing or IP/proxy rotation.
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
- **Skills live in `dashboard/prisma/data/skills.json`.** Each skill carries its own `match` / `no_match` examples. Use `/add-skill-tag`.

- **Adapters must be in the `ADAPTERS` allowlist** (`scraper/sources/__init__.py`) and Allowed in SOURCES.md. `tests/test_sources_registry.py` enforces both.
- **Remote OK's data has mojibake and HTML entities in the source itself**, and its feed mixes non-dev jobs. `clean_text` / `html_to_text` and `is_relevant` handle both. Salary values below USD 10k aren't treated as annual (no period is guessed).

## Status
Steps 1–3 are done. **Remote OK is live end to end**: 73 dev postings in Neon, and the daily `scrape.yml` is in place. **Remotive is "Unclear"** (robots.txt + Terms of Use vs its API page) and waits for written permission. Next is step 4: a bare postings table page on the dashboard. See SPEC §10.
