import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";
import { type TrendPoint, type WeekRow, toWeeklySeries } from "@/lib/queries/skills-series";

export type { TrendPoint } from "@/lib/queries/skills-series";

const TAG: CacheTag = "skill-stats";

/** Skills compared, and the pool the trend chart can pick from. */
export const TOP_SKILLS = 15;
export const TREND_SKILLS = 8;
export const TREND_WEEKS = 12;

export type SkillComparison = { name: string; current: number; previous: number };
export type SkillsData = {
  /** Manila date the windows end on (inclusive), YYYY-MM-DD. */
  asOf: string | null;
  comparison: SkillComparison[];
  trendSkills: string[];
  trend: TrendPoint[];
};

/**
 * From daily_skill_stats (written by scraper/aggregate.py): new postings per skill in the
 * last 30 days vs the 30 before, and weekly new postings for the top skills.
 */
export async function getSkillsData(): Promise<SkillsData> {
  "use cache";
  cacheTag(TAG);
  cacheLife("days");

  const [latest] = await db().$queryRaw<{ as_of: string | null }[]>`
    SELECT max(date)::text AS as_of FROM daily_skill_stats`;
  const asOf = latest?.as_of ?? null;
  if (!asOf) return { asOf, comparison: [], trendSkills: [], trend: [] };

  const comparison = await db().$queryRaw<SkillComparison[]>`
    SELECT s.name,
           coalesce(sum(d.new_postings) FILTER (WHERE d.date > ${asOf}::date - 30), 0)::int
             AS current,
           coalesce(sum(d.new_postings) FILTER (
             WHERE d.date <= ${asOf}::date - 30 AND d.date > ${asOf}::date - 60), 0)::int
             AS previous
    FROM daily_skill_stats d JOIN skills s ON s.id = d.skill_id
    WHERE d.date > ${asOf}::date - 60
    GROUP BY s.name
    HAVING sum(d.new_postings) > 0
    ORDER BY current DESC, previous DESC, s.name
    LIMIT ${TOP_SKILLS}`;

  const trendSkills = comparison.slice(0, TREND_SKILLS).map((c) => c.name);
  const rows = await db().$queryRaw<WeekRow[]>`
    SELECT date_trunc('week', d.date)::date::text AS week, s.name,
           sum(d.new_postings)::int AS n
    FROM daily_skill_stats d JOIN skills s ON s.id = d.skill_id
    WHERE d.date > ${asOf}::date - ${TREND_WEEKS * 7}::int
      AND s.name = ANY(${trendSkills})
    GROUP BY 1, 2`;

  return { asOf, comparison, trendSkills, trend: toWeeklySeries(rows, trendSkills) };
}
