import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";

const TAG: CacheTag = "postings";

export type Overview = {
  active: number;
  newThisWeek: number;
  withSalary: number;
  remotePhEligible: number;
  jobTypes: { key: string; n: number }[];
  workSetups: { key: string; n: number }[];
};

type Counts = {
  active: number;
  new_this_week: number;
  with_salary: number;
  remote_ph: number;
};
type Split = { key: string; n: number };

/** Stat tiles and splits over active, canonical postings. */
export async function getOverview(): Promise<Overview> {
  "use cache";
  cacheTag(TAG);
  cacheLife("days");

  const [counts] = await db().$queryRaw<Counts[]>`
    SELECT count(*) FILTER (WHERE is_active)::int AS active,
           count(*) FILTER (WHERE first_seen_at >= now() - interval '7 days')::int
             AS new_this_week,
           count(*) FILTER (WHERE is_active AND salary_raw IS NOT NULL)::int AS with_salary,
           count(*) FILTER (WHERE is_active AND work_setup = 'remote' AND ph_eligible)::int
             AS remote_ph
    FROM postings
    WHERE canonical_posting_id IS NULL`;

  const jobTypes = await db().$queryRaw<Split[]>`
    SELECT job_type::text AS key, count(*)::int AS n
    FROM postings
    WHERE canonical_posting_id IS NULL AND is_active
    GROUP BY 1 ORDER BY 2 DESC, 1`;

  const workSetups = await db().$queryRaw<Split[]>`
    SELECT work_setup::text AS key, count(*)::int AS n
    FROM postings
    WHERE canonical_posting_id IS NULL AND is_active
    GROUP BY 1 ORDER BY 2 DESC, 1`;

  return {
    active: counts?.active ?? 0,
    newThisWeek: counts?.new_this_week ?? 0,
    withSalary: counts?.with_salary ?? 0,
    remotePhEligible: counts?.remote_ph ?? 0,
    jobTypes,
    workSetups,
  };
}
