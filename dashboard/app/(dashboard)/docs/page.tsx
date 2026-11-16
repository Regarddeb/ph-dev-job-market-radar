import type { Metadata } from "next";
import Link from "next/link";

import { ArchitectureDiagram } from "@/components/architecture-diagram";
import { Flow } from "@/components/flow";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "What PH Dev Job Market Radar is for, how the daily pipeline runs, its tech stack, its data model and the rules it follows.",
};

const SECTIONS = [
  { id: "purpose", label: "Purpose" },
  { id: "architecture", label: "How it runs" },
  { id: "pipeline", label: "Posting pipeline" },
  { id: "rules", label: "Processing rules" },
  { id: "stack", label: "Tech stack" },
  { id: "data", label: "Data model" },
  { id: "highlights", label: "Highlights" },
  { id: "limits", label: "Limits" },
] as const;

const LINK = "text-foreground underline underline-offset-4";

function Section({
  id,
  title,
  children,
}: {
  id: (typeof SECTIONS)[number]["id"];
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-28 space-y-4">
      <h2 id={`${id}-h`} className="text-xl font-semibold tracking-tight">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Prose({ children }: { children: React.ReactNode }) {
  return <div className="text-muted-foreground max-w-prose space-y-3 text-sm">{children}</div>;
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="bg-muted text-foreground rounded px-1 py-0.5 font-mono text-[0.8em]">
      {children}
    </code>
  );
}

const STACK = [
  {
    area: "Scraper",
    where: "scraper/",
    items: [
      ["Python 3.12 + uv", "one locked environment, locally and in CI"],
      ["httpx", "one shared client: identifying User-Agent, per-host rate limit, retries"],
      ["BeautifulSoup + lxml", "turns Hacker News comment HTML into text and fields"],
      ["pydantic", "validates every parsed posting before it is stored"],
      ["rapidfuzz", "fuzzy title and description matching for duplicates"],
      ["psycopg 3", "writes rows to Postgres; never runs DDL"],
      ["pytest + ruff", "tests against saved fixtures, never live sites"],
    ],
  },
  {
    area: "Dashboard",
    where: "dashboard/",
    items: [
      ["Next.js 16 (App Router)", "Cache Components: prerendered pages, tagged caches"],
      ["Prisma 7", "owns the schema and migrations; typed queries"],
      ["Tailwind CSS 4 + shadcn/ui", "styling and base components"],
      ["Recharts", "the skill and salary charts"],
      ["Vitest", "unit tests for formatting, filters and pagination"],
    ],
  },
  {
    area: "Infrastructure",
    where: ".github/workflows/",
    items: [
      ["GitHub Actions", "the daily scrape, migrations, and the one-off history backfill"],
      ["Neon Postgres", "free tier, 1 GB; three roles with different rights"],
      ["Vercel", "hosts the dashboard in Singapore, next to the database"],
    ],
  },
] as const;

const TABLES = [
  {
    name: "sources",
    role: "Each job site the scraper may use, with its terms URL and attribution text.",
    columns: ["slug", "name", "kind", "is_active", "attribution_text", "terms_url"],
  },
  {
    name: "crawl_runs",
    role: "One row per run of one source: status, counts and any error. Feeds the Status page.",
    columns: ["source_id", "started_at", "status", "postings_found", "postings_new"],
  },
  {
    name: "raw_postings",
    role: "The response for each posting exactly as fetched, stored before any parsing.",
    columns: ["source_id", "external_id", "payload", "content_hash", "parse_error"],
  },
  {
    name: "postings",
    role: "The cleaned posting: stated facts plus the fields derived by rules.",
    columns: [
      "title",
      "company_id",
      "seniority",
      "job_type",
      "work_setup",
      "ph_eligible",
      "salary_raw",
      "salary_min_php_monthly",
      "source_url",
      "first_seen_at",
      "is_active",
      "canonical_posting_id",
    ],
  },
  {
    name: "companies",
    role: "Company names, matched on a normalised form so spelling variants share one row.",
    columns: ["name", "normalized_name"],
  },
  {
    name: "skills / skill_aliases",
    role: "The skill dictionary: each skill and the regex patterns that detect it.",
    columns: ["name", "category", "pattern", "requirements_only"],
  },
  {
    name: "posting_skills",
    role: "Which skills each posting mentions (many to many).",
    columns: ["posting_id", "skill_id"],
  },
  {
    name: "exchange_rates",
    role: "PHP per unit of each currency per day, derived from ECB euro reference rates.",
    columns: ["date", "currency", "php_per_unit"],
  },
  {
    name: "daily_skill_stats",
    role: "Precomputed per day and skill, so the charts don't scan every posting.",
    columns: ["date", "skill_id", "active_postings", "new_postings", "median_salary_php"],
  },
] as const;

const RULES = [
  {
    field: "Developer role?",
    rule: "The title must name a software role and not a known non-dev one. Source tags are ignored: they are often keyword-stuffed.",
  },
  {
    field: "Salary",
    rule: "Kept as written. Converted to PHP per month only when a currency, an amount next to it and a period are all stated (hourly × 160, daily × 22, annual ÷ 12).",
  },
  {
    field: "Seniority",
    rule: "From the title only: lead / principal / staff, senior, intern, junior. Otherwise unspecified.",
  },
  {
    field: "Job type",
    rule: "The source's own field first, then the title, then phrases in the description that are about this job. Full-time alongside another type is a conflict and stays unspecified.",
  },
  {
    field: "Work setup",
    rule: "The source's field, then the title and location: hybrid is checked before remote, so “hybrid, 2 days remote” is not remote.",
  },
  {
    field: "PH-eligible",
    rule: "True when the Philippines is named, or worldwide / anywhere / Asia / APAC hiring is stated. False for “US only”, required work authorisation elsewhere and similar. A conflict, or silence, stays unknown.",
  },
  {
    field: "Skills",
    rule: "Word-boundary regex aliases over the title and description. Ambiguous names (Go, R, C, Swift, Rust) need context, such as “Go developer” or a requirements section.",
  },
  {
    field: "Duplicates",
    rule: "Same company with the same normalised title and setup within 30 days, or a near-identical title and description. Duplicates point at the earliest posting and are hidden.",
  },
] as const;

export default function DocsPage() {
  return (
    <article className="space-y-12">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">How it works</h1>
        <p className="text-muted-foreground max-w-prose text-sm">
          What this site is for, how the data gets here each day, what it is built with and the
          rules it follows. The full specification and source registry live in the{" "}
          <a
            href="https://github.com/Regarddeb/ph-dev-job-market-radar"
            target="_blank"
            rel="noopener"
            className={LINK}
          >
            GitHub repository
          </a>
          .
        </p>
        <nav aria-label="On this page">
          <ul className="flex flex-wrap gap-1.5 text-xs">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="text-muted-foreground hover:text-foreground hover:bg-muted inline-block rounded-md border px-2.5 py-1"
                >
                  {s.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <Section id="purpose" title="Purpose">
        <Prose>
          <p>
            PH Dev Job Market Radar tracks the remote developer job market from the point of view of
            a developer based in the Philippines. It answers three questions:{" "}
            <Link href="/skills" className={LINK}>
              which skills are in demand
            </Link>
            ,{" "}
            <Link href="/salaries" className={LINK}>
              what roles pay
            </Link>{" "}
            in pesos, and{" "}
            <Link href="/ph-friendly" className={LINK}>
              which roles accept PH-based applicants
            </Link>
            .
          </p>
          <p>
            It is a personal portfolio project that shows three things working together: web
            scraping, rule-based data processing, and a dashboard. It is informational only. It is
            not a job board: every posting links back to where it was published, and you apply
            there.
          </p>
        </Prose>
      </Section>

      <Section id="architecture" title="How it runs">
        <Prose>
          <p>
            Once a day a scheduled job fetches the sources, processes the postings and writes them
            to the database. The website never fetches a job site itself; it only reads what the job
            stored.
          </p>
        </Prose>
        <ArchitectureDiagram />
        <h3 className="pt-2 text-sm font-medium">The daily run, step by step</h3>
        <Flow
          label="Steps of the daily run, in order"
          steps={[
            { tag: "fx", title: "Exchange rates", note: "ECB rates for the last 90 days" },
            {
              tag: "pipeline",
              title: "Each source",
              note: "its own step; one failing doesn't stop the rest",
            },
            { tag: "dedupe", title: "Duplicates", note: "across all sources" },
            { tag: "aggregate", title: "Daily stats", note: "per skill, last 35 days" },
            { tag: "retention", title: "Trim", note: "old descriptions and raw payloads" },
            { tag: "revalidate", title: "Refresh site", note: "cached pages rebuild" },
          ]}
        />
        <Prose>
          <p>
            Every step is idempotent: rows are upserts keyed on the source and the posting&apos;s id
            there, so a run can be late, skipped or repeated without creating duplicates. Each
            source&apos;s run is recorded, and the{" "}
            <Link href="/ops" className={LINK}>
              Status page
            </Link>{" "}
            flags any source that has not succeeded in 48 hours.
          </p>
        </Prose>
      </Section>

      <Section id="pipeline" title="What happens to one posting">
        <Flow
          label="Stages one posting passes through"
          steps={[
            { title: "Fetch", note: "rate-limited, identified client" },
            { title: "Store raw", note: "before any parsing" },
            { title: "Parse", note: "only what the source states" },
            { title: "Filter", note: "developer roles only" },
            { title: "Derive", note: "salary, seniority, type, PH-eligible" },
            { title: "Tag skills", note: "regex dictionary" },
            { title: "Load", note: "upsert; convert salary to PHP" },
          ]}
        />
        <Prose>
          <p>
            The raw response is saved first, so a rule can be improved later and re-applied to
            everything already collected without fetching again. A posting that fails to parse is
            recorded with its error and does not stop the run.
          </p>
          <p>
            A posting is <strong className="text-foreground">active</strong> while its source still
            lists it. When a later successful crawl no longer sees it, it stays in the history for
            trends but leaves the lists.
          </p>
        </Prose>
      </Section>

      <Section id="rules" title="Processing rules">
        <Prose>
          <p>
            Every derived field comes from fixed rules: regular expressions, keyword dictionaries
            and fuzzy string matching. No AI model is involved anywhere, so the same posting always
            produces the same result and each rule has tests.
          </p>
        </Prose>
        <dl className="ring-foreground/10 divide-y rounded-xl ring-1">
          {RULES.map((r) => (
            <div key={r.field} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_1fr] sm:gap-4">
              <dt className="text-sm font-medium">{r.field}</dt>
              <dd className="text-muted-foreground text-sm">{r.rule}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section id="stack" title="Tech stack">
        <div className="grid gap-4 lg:grid-cols-3">
          {STACK.map((group) => (
            <Card key={group.area}>
              <CardHeader>
                <CardTitle>{group.area}</CardTitle>
                <CardDescription className="font-mono text-xs">{group.where}</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2.5">
                  {group.items.map(([name, why]) => (
                    <li key={name} className="text-sm">
                      <span className="font-medium">{name}</span>
                      <span className="text-muted-foreground block text-xs">{why}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>

      <Section id="data" title="Data model">
        <Prose>
          <p>
            The schema is defined once, in Prisma, and changed only through migrations. The scraper
            writes rows but can never alter tables.
          </p>
        </Prose>
        <Flow
          label="How the main tables relate"
          steps={[
            { tag: "sources", title: "Source", note: "has many runs and postings" },
            { tag: "raw_postings", title: "Raw response", note: "one per posting, as fetched" },
            { tag: "postings", title: "Posting", note: "parsed and classified" },
            { tag: "posting_skills", title: "Skills", note: "many per posting" },
            { tag: "daily_skill_stats", title: "Daily stats", note: "what the charts read" },
          ]}
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TABLES.map((t) => (
            <div
              key={t.name}
              className="bg-card ring-foreground/10 space-y-2 rounded-xl p-4 ring-1"
            >
              <h3 className="font-mono text-sm font-medium">{t.name}</h3>
              <p className="text-muted-foreground text-xs">{t.role}</p>
              <ul className="flex flex-wrap gap-1" aria-label={`Main columns of ${t.name}`}>
                {t.columns.map((c) => (
                  <li key={c} className="bg-muted rounded px-1.5 py-0.5 font-mono text-[0.7rem]">
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <Prose>
          <p>
            A duplicate keeps its row and points at the original through{" "}
            <Code>canonical_posting_id</Code>; lists and charts count only rows where that is empty.
            Unknown values are stored as <Code>NULL</Code> or <Code>unspecified</Code>, never filled
            in.
          </p>
        </Prose>
      </Section>

      <Section id="highlights" title="Highlights">
        <ul className="grid gap-3 sm:grid-cols-2">
          {[
            [
              "Only permitted sources",
              "Each source's terms, robots.txt and API rules are checked and recorded before any code is written. Sites that forbid scraping are never touched, and nothing sits behind a login.",
            ],
            [
              "Never guess",
              "If a posting doesn't state a salary period, seniority or where it hires, the field stays empty. A smaller honest sample beats a larger invented one.",
            ],
            [
              "Attribution on every posting",
              "Each row carries a followed “via Source” link to the original, as the sources' terms ask.",
            ],
            [
              "Raw first, reparse later",
              "Because responses are stored before parsing, improving a rule updates past data without another request to the source.",
            ],
            [
              "Tests use saved fixtures",
              "Parsers are tested against real captured responses kept in the repository. Tests never call a live site.",
            ],
            [
              "Least privilege",
              "Three database roles: migrations, a writer that cannot change tables, and a read-only role for this website.",
            ],
            [
              "Fast, cheap pages",
              "Pages are prerendered and cached by tag, then refreshed once after each daily run instead of querying on every visit.",
            ],
            [
              "Five years in 1 GB",
              "Descriptions and raw payloads are trimmed after 90 days; the compact facts and daily stats are kept for trends.",
            ],
          ].map(([title, body]) => (
            <li key={title} className="ring-foreground/10 rounded-xl p-4 ring-1">
              <h3 className="text-sm font-medium">{title}</h3>
              <p className="text-muted-foreground mt-1 text-sm">{body}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="limits" title="What the numbers can and can't tell you">
        <Prose>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              The sample is three remote-focused sources, not the whole market. It leans towards
              companies that post on them, many of them US and European startups.
            </li>
            <li>
              Most postings state no salary, and many that do give no period, so salary charts rest
              on a minority of postings. Each chart shows its sample size.
            </li>
            <li>
              “PH-friendly” means the posting says so. Many roles that would accept a PH-based
              applicant never state it and are not counted.
            </li>
            <li>
              PHP amounts use ECB euro reference rates (other currencies derived as cross rates) for
              the day a posting was first seen. They are for comparison, not a quote.
            </li>
            <li>Data is refreshed once a day, so a posting may close before it leaves the list.</li>
          </ul>
        </Prose>
      </Section>
    </article>
  );
}
