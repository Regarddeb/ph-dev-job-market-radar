import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type { CacheTag } from "@/lib/cache-tags";
import { db } from "@/lib/db";

const POSTINGS_TAG: CacheTag = "postings";

/** Bare table for now; pagination comes when the row count needs it. */
export const POSTINGS_LIMIT = 200;

export type PostingRow = {
  id: number;
  title: string;
  company: string | null;
  locationText: string | null;
  salaryRaw: string | null;
  postedAt: Date | null;
  firstSeenAt: Date;
  sourceUrl: string;
  sourceId: number;
  sourceName: string;
};

export type SourceAttribution = { id: number; name: string; attributionText: string };

export type ActivePostings = {
  rows: PostingRow[];
  /** Total active canonical postings, which can exceed rows.length. */
  total: number;
  /** One entry per source that appears in rows. */
  sources: SourceAttribution[];
};

/**
 * Active, canonical postings (duplicates excluded), newest first.
 * Invalidated by POST /api/revalidate after each daily scrape; `days` is only a fallback.
 */
export async function getActivePostings(): Promise<ActivePostings> {
  "use cache";
  cacheTag(POSTINGS_TAG);
  cacheLife("days");

  const where = { isActive: true, canonicalPostingId: null };

  const [postings, total] = await Promise.all([
    db().posting.findMany({
      where,
      orderBy: [
        { postedAt: { sort: "desc", nulls: "last" } },
        { firstSeenAt: "desc" },
        { id: "desc" },
      ],
      take: POSTINGS_LIMIT,
      select: {
        id: true,
        title: true,
        locationText: true,
        salaryRaw: true,
        postedAt: true,
        firstSeenAt: true,
        sourceUrl: true,
        company: { select: { name: true } },
        source: { select: { id: true, name: true, attributionText: true } },
      },
    }),
    db().posting.count({ where }),
  ]);

  const sources = new Map<number, SourceAttribution>();
  const rows = postings.map((p): PostingRow => {
    sources.set(p.source.id, p.source);
    return {
      id: p.id,
      title: p.title,
      company: p.company?.name ?? null,
      locationText: p.locationText,
      salaryRaw: p.salaryRaw,
      postedAt: p.postedAt,
      firstSeenAt: p.firstSeenAt,
      sourceUrl: p.sourceUrl,
      sourceId: p.source.id,
      sourceName: p.source.name,
    };
  });

  return { rows, total, sources: [...sources.values()] };
}
