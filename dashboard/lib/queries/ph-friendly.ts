import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";

const TAG: CacheTag = "postings";

export type PhRole = {
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
  /** Every skill the posting is tagged with (may be empty). */
  skills: string[];
};

/**
 * Active, canonical postings that say they accept Philippines-based applicants
 * (ph_eligible = true; unknown is not counted), newest first, with their skills.
 * Visitors filter them by skill and job type in the browser.
 */
export async function getPhFriendlyRoles(): Promise<PhRole[]> {
  "use cache";
  cacheTag(TAG);
  cacheLife("days");

  return db().$queryRaw<PhRole[]>`
    SELECT p.id, p.title, c.name AS company, p.location_text AS "locationText",
           p.salary_raw AS "salaryRaw", p.job_type::text AS "jobType",
           p.posted_at AS "postedAt", p.first_seen_at AS "firstSeenAt",
           p.source_url AS "sourceUrl", src.name AS "sourceName",
           coalesce(array_agg(s.name ORDER BY s.name) FILTER (WHERE s.name IS NOT NULL), '{}')
             AS skills
    FROM postings p
    JOIN sources src ON src.id = p.source_id
    LEFT JOIN companies c ON c.id = p.company_id
    LEFT JOIN posting_skills ps ON ps.posting_id = p.id
    LEFT JOIN skills s ON s.id = ps.skill_id
    WHERE p.is_active AND p.canonical_posting_id IS NULL AND p.ph_eligible
    GROUP BY p.id, c.name, src.name
    ORDER BY coalesce(p.posted_at, p.first_seen_at) DESC, p.id DESC
    LIMIT 300`;
}
