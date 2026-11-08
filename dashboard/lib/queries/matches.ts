import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";

const TAG: CacheTag = "postings";

export type MatchRow = {
  id: number;
  title: string;
  company: string | null;
  locationText: string | null;
  salaryRaw: string | null;
  jobType: string;
  postedAt: Date | null;
  firstSeenAt: Date;
  sourceUrl: string;
  sourceName: string;
  /** The owner's skills this posting is tagged with. */
  matched: string[];
};

export type Matches = {
  /** Wanted job type, PH-eligible, at least one skill: the real matches. */
  matches: MatchRow[];
  /** PH-eligible with a skill match, but the posting doesn't state its job type. */
  unstated: MatchRow[];
};

/**
 * Active, canonical, PH-eligible postings tagged with any of `skills`, newest first.
 * Arguments are part of the cache key; the config passes the same ones every time.
 */
export async function getMatches(skills: string[], jobTypes: string[]): Promise<Matches> {
  "use cache";
  cacheTag(TAG);
  cacheLife("days");

  const rows = await db().$queryRaw<MatchRow[]>`
    SELECT p.id, p.title, c.name AS company, p.location_text AS "locationText",
           p.salary_raw AS "salaryRaw", p.job_type::text AS "jobType",
           p.posted_at AS "postedAt", p.first_seen_at AS "firstSeenAt",
           p.source_url AS "sourceUrl", src.name AS "sourceName",
           array_agg(s.name ORDER BY s.name) AS matched
    FROM postings p
    JOIN sources src ON src.id = p.source_id
    LEFT JOIN companies c ON c.id = p.company_id
    JOIN posting_skills ps ON ps.posting_id = p.id
    JOIN skills s ON s.id = ps.skill_id AND s.name = ANY(${skills})
    WHERE p.is_active AND p.canonical_posting_id IS NULL
      AND p.ph_eligible
      AND (p.job_type::text = ANY(${jobTypes}) OR p.job_type = 'unspecified')
    GROUP BY p.id, c.name, src.name
    ORDER BY coalesce(p.posted_at, p.first_seen_at) DESC, p.id DESC
    LIMIT 200`;

  return {
    matches: rows.filter((r) => r.jobType !== "unspecified"),
    unstated: rows.filter((r) => r.jobType === "unspecified"),
  };
}
