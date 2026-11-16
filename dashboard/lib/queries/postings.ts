import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";
import type { Prisma } from "@/lib/generated/prisma/client";
import { PAGE_SIZE, type PostingFilters, pageCount } from "@/lib/postings-params";

const POSTINGS_TAG: CacheTag = "postings";

/** One posting as the list shows it. Unknown fields stay null / "unspecified". */
export type PostingRow = {
  id: number;
  title: string;
  company: string | null;
  locationText: string | null;
  jobType: string;
  workSetup: string;
  seniority: string;
  phEligible: boolean | null;
  salaryRaw: string | null;
  salaryMinPhpMonthly: number | null;
  salaryMaxPhpMonthly: number | null;
  postedAt: Date | null;
  firstSeenAt: Date;
  sourceUrl: string;
  sourceName: string;
  skills: string[];
};

export type PostingsPage = {
  rows: PostingRow[];
  /** Postings matching the filters, across all pages. */
  total: number;
  /** The page actually returned (a page past the end is clamped to the last one). */
  page: number;
  pages: number;
};

export type SourceFacet = { slug: string; name: string; attributionText: string; n: number };
export type SkillFacet = { name: string; n: number };
export type PostingFacets = {
  /** Active canonical postings, unfiltered. */
  total: number;
  sources: SourceFacet[];
  skills: SkillFacet[];
};

const SELECT = {
  id: true,
  title: true,
  locationText: true,
  jobType: true,
  workSetup: true,
  seniority: true,
  phEligible: true,
  salaryRaw: true,
  salaryMinPhpMonthly: true,
  salaryMaxPhpMonthly: true,
  postedAt: true,
  firstSeenAt: true,
  sourceUrl: true,
  company: { select: { name: true } },
  source: { select: { name: true } },
  skills: { select: { skill: { select: { name: true } } }, orderBy: { skill: { name: "asc" } } },
} satisfies Prisma.PostingSelect;

/** Active, canonical postings (duplicates hidden) narrowed by the visitor's filters. */
function where(f: PostingFilters): Prisma.PostingWhereInput {
  return {
    isActive: true,
    canonicalPostingId: null,
    ...(f.types.length > 0 && { jobType: { in: f.types } }),
    ...(f.setups.length > 0 && { workSetup: { in: f.setups } }),
    ...(f.ph && { phEligible: true }),
    ...(f.salary && { salaryRaw: { not: null } }),
    ...(f.source && { source: { slug: f.source } }),
    ...(f.skills.length > 0 && { skills: { some: { skill: { name: { in: f.skills } } } } }),
    ...(f.q && {
      OR: [
        { title: { contains: f.q, mode: "insensitive" } },
        { company: { name: { contains: f.q, mode: "insensitive" } } },
      ],
    }),
  };
}

const NEWEST: Prisma.PostingOrderByWithRelationInput[] = [
  { postedAt: { sort: "desc", nulls: "last" } },
  { firstSeenAt: "desc" },
  { id: "desc" },
];

async function queryPostingsPage(f: PostingFilters): Promise<PostingsPage> {
  const filter = where(f);
  const total = await db().posting.count({ where: filter });
  const pages = pageCount(total);
  const page = Math.min(f.page, pages);
  const postings = await db().posting.findMany({
    where: filter,
    // "Highest pay" ranks by the converted monthly PHP maximum; postings without one go last.
    orderBy:
      f.sort === "salary"
        ? [{ salaryMaxPhpMonthly: { sort: "desc", nulls: "last" } }, ...NEWEST]
        : NEWEST,
    skip: (page - 1) * PAGE_SIZE,
    take: PAGE_SIZE,
    select: SELECT,
  });
  const rows = postings.map(({ company, source, skills, ...p }): PostingRow => ({
    ...p,
    company: company?.name ?? null,
    sourceName: source.name,
    skills: skills.map((s) => s.skill.name),
  }));
  return { rows, total, page, pages };
}

async function cachedPostingsPage(f: PostingFilters): Promise<PostingsPage> {
  "use cache";
  cacheTag(POSTINGS_TAG);
  cacheLife("days");
  return queryPostingsPage(f);
}

/**
 * One page of postings. Chip/toggle combinations are cached per filter set (invalidated by
 * POST /api/revalidate after each daily scrape); free-text searches go straight to the
 * database, so arbitrary search strings can't fill the cache.
 */
export function getPostingsPage(f: PostingFilters): Promise<PostingsPage> {
  return f.q ? queryPostingsPage(f) : cachedPostingsPage(f);
}

/** How many skill chips the filter offers. */
const SKILL_FACETS = 18;

/** Filter options with counts over all active canonical postings. */
export async function getPostingFacets(): Promise<PostingFacets> {
  "use cache";
  cacheTag(POSTINGS_TAG);
  cacheLife("days");

  const sources = await db().$queryRaw<SourceFacet[]>`
    SELECT src.slug, src.name, src.attribution_text AS "attributionText", count(*)::int AS n
    FROM postings p JOIN sources src ON src.id = p.source_id
    WHERE p.is_active AND p.canonical_posting_id IS NULL
    GROUP BY src.id
    ORDER BY n DESC, src.name`;
  const skills = await db().$queryRaw<SkillFacet[]>`
    SELECT s.name, count(*)::int AS n
    FROM postings p
    JOIN posting_skills ps ON ps.posting_id = p.id
    JOIN skills s ON s.id = ps.skill_id
    WHERE p.is_active AND p.canonical_posting_id IS NULL
    GROUP BY s.name
    ORDER BY n DESC, s.name
    LIMIT ${SKILL_FACETS}`;
  return { total: sources.reduce((sum, s) => sum + s.n, 0), sources, skills };
}
