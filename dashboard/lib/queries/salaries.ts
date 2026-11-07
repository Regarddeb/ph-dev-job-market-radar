import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";

const TAG: CacheTag = "postings";

export const SALARY_WINDOW_DAYS = 90;
/** Below this many postings a median says little; those skills are listed, not charted. */
export const MIN_SAMPLE = 3;

export type SkillSalary = {
  name: string;
  /** Postings with a PHP monthly salary. */
  n: number;
  /** Median of each posting's monthly midpoint, (min + max) / 2, in PHP. */
  median: number;
  /** Lowest stated minimum and highest stated maximum, PHP per month. */
  low: number;
  high: number;
};

/** Per skill, over canonical postings first seen in the last 90 days with a PHP salary. */
export async function getSkillSalaries(): Promise<SkillSalary[]> {
  "use cache";
  cacheTag(TAG);
  cacheLife("days");

  return db().$queryRaw<SkillSalary[]>`
    SELECT s.name,
           count(*)::int AS n,
           round(percentile_cont(0.5) WITHIN GROUP (
             ORDER BY (p.salary_min_php_monthly + p.salary_max_php_monthly) / 2.0))::int
             AS median,
           min(p.salary_min_php_monthly)::int AS low,
           max(p.salary_max_php_monthly)::int AS high
    FROM postings p
    JOIN posting_skills ps ON ps.posting_id = p.id
    JOIN skills s ON s.id = ps.skill_id
    WHERE p.canonical_posting_id IS NULL
      AND p.salary_min_php_monthly IS NOT NULL
      AND p.first_seen_at >= now() - make_interval(days => ${SALARY_WINDOW_DAYS})
    GROUP BY s.name
    ORDER BY median DESC, s.name`;
}
