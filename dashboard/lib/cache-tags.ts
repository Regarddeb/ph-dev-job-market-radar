// Cache tags shared by data loaders (cacheTag) and /api/revalidate (revalidateTag).
export const CACHE_TAGS = ["postings", "skill-stats", "ops"] as const;

export type CacheTag = (typeof CACHE_TAGS)[number];
