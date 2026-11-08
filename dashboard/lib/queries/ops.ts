import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";

const TAG: CacheTag = "ops";

/** A source with no successful crawl in this long is flagged (scheduled workflows can stop). */
export const STALE_HOURS = 48;
/** Neon free tier: 1 GB per project. Warn well before writes are blocked (SPEC §7). */
export const DB_LIMIT_BYTES = 1024 ** 3;
export const DB_WARN_BYTES = 800 * 1024 ** 2;

export type SourceHealth = {
  id: number;
  name: string;
  slug: string;
  isActive: boolean;
  lastStatus: "running" | "ok" | "failed" | null;
  lastStartedAt: Date | null;
  lastError: string | null;
  lastOkAt: Date | null;
  hoursSinceOk: number | null;
  stale: boolean;
  activePostings: number;
};

export type CrawlRunRow = {
  id: number;
  source: string;
  status: "running" | "ok" | "failed";
  startedAt: Date;
  durationSeconds: number | null;
  pagesFetched: number;
  postingsFound: number;
  postingsNew: number;
  error: string | null;
};

export type OpsData = {
  checkedAt: Date;
  sources: SourceHealth[];
  runs: CrawlRunRow[];
  dbBytes: number;
  tables: { name: string; bytes: number }[];
};

/** Crawl health, recent runs and database size. Refreshed by /api/revalidate ("ops"). */
export async function getOpsData(): Promise<OpsData> {
  "use cache";
  cacheTag(TAG);
  cacheLife("hours");

  const [sources, runs, size, tables] = await Promise.all([
    db().$queryRaw<SourceHealth[]>`
      SELECT s.id, s.name, s.slug, s.is_active AS "isActive",
             lr.status::text AS "lastStatus", lr.started_at AS "lastStartedAt",
             lr.error_message AS "lastError",
             ok.started_at AS "lastOkAt",
             round(extract(epoch FROM now() - ok.started_at) / 3600)::int AS "hoursSinceOk",
             (s.is_active AND (ok.started_at IS NULL
                OR ok.started_at < now() - make_interval(hours => ${STALE_HOURS}))) AS stale,
             (SELECT count(*) FROM postings p
               WHERE p.source_id = s.id AND p.is_active
                 AND p.canonical_posting_id IS NULL)::int AS "activePostings"
      FROM sources s
      LEFT JOIN LATERAL (
        SELECT status, started_at, error_message FROM crawl_runs c
        WHERE c.source_id = s.id ORDER BY c.started_at DESC LIMIT 1) lr ON true
      LEFT JOIN LATERAL (
        SELECT started_at FROM crawl_runs c
        WHERE c.source_id = s.id AND c.status = 'ok' ORDER BY c.started_at DESC LIMIT 1) ok ON true
      ORDER BY s.is_active DESC, s.name`,
    db().$queryRaw<CrawlRunRow[]>`
      SELECT c.id, s.name AS source, c.status::text AS status, c.started_at AS "startedAt",
             round(extract(epoch FROM c.finished_at - c.started_at))::int AS "durationSeconds",
             c.pages_fetched AS "pagesFetched", c.postings_found AS "postingsFound",
             c.postings_new AS "postingsNew", left(c.error_message, 300) AS error
      FROM crawl_runs c JOIN sources s ON s.id = c.source_id
      ORDER BY c.started_at DESC
      LIMIT 20`,
    db().$queryRaw<{ bytes: number; now: Date }[]>`
      SELECT pg_database_size(current_database())::float8 AS bytes, now() AS now`,
    db().$queryRaw<{ name: string; bytes: number }[]>`
      SELECT relname::text AS name, pg_total_relation_size(relid)::float8 AS bytes
      FROM pg_stat_user_tables
      ORDER BY bytes DESC
      LIMIT 6`,
  ]);

  return {
    checkedAt: size[0]?.now ?? new Date(0),
    sources,
    runs,
    dbBytes: size[0]?.bytes ?? 0,
    tables,
  };
}
