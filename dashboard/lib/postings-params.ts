// Pure URL <-> filter helpers for /postings (no DB, React or Next imports, so they unit-test).

export const PAGE_SIZE = 25;
const MAX_QUERY_LENGTH = 80;
const MAX_SKILLS = 10;

export const JOB_TYPES = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "freelance", label: "Freelance" },
] as const;

export const WORK_SETUPS = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
] as const;

export const SORTS = [
  { value: "newest", label: "Newest first" },
  { value: "salary", label: "Highest pay first" },
] as const;

export type JobTypeValue = (typeof JOB_TYPES)[number]["value"];
export type WorkSetupValue = (typeof WORK_SETUPS)[number]["value"];
export type SortValue = (typeof SORTS)[number]["value"];

export type PostingFilters = {
  /** Free-text search over title and company; "" when unset. */
  q: string;
  types: JobTypeValue[];
  setups: WorkSetupValue[];
  /** Skill names, any of. */
  skills: string[];
  /** Source slug; "" = every source. */
  source: string;
  /** Only postings that say they accept PH-based applicants. */
  ph: boolean;
  /** Only postings that state a salary. */
  salary: boolean;
  sort: SortValue;
  /** 1-based. */
  page: number;
};

export const DEFAULT_FILTERS: PostingFilters = {
  q: "",
  types: [],
  setups: [],
  skills: [],
  source: "",
  ph: false,
  salary: false,
  sort: "newest",
  page: 1,
};

export type RawSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** "a,b" or repeated params -> unique, sorted values (sorted so equal filters share a cache key). */
function list(value: string | string[] | undefined): string[] {
  const parts = (Array.isArray(value) ? value : [value ?? ""]).flatMap((v) => v.split(","));
  return [...new Set(parts.map((p) => p.trim()).filter(Boolean))].sort();
}

function allowed<T extends string>(values: string[], options: readonly { value: T }[]): T[] {
  const known = new Set<string>(options.map((o) => o.value));
  return values.filter((v): v is T => known.has(v));
}

/** Anything unknown or malformed falls back to the default, so any URL renders. */
export function parseFilters(params: RawSearchParams): PostingFilters {
  const page = Number.parseInt(first(params.page), 10);
  const sort = first(params.sort);
  return {
    q: first(params.q).slice(0, MAX_QUERY_LENGTH),
    types: allowed(list(params.type), JOB_TYPES),
    setups: allowed(list(params.setup), WORK_SETUPS),
    skills: list(params.skill).slice(0, MAX_SKILLS),
    source: /^[a-z0-9_]{1,40}$/.test(first(params.source)) ? first(params.source) : "",
    ph: first(params.ph) === "1",
    salary: first(params.salary) === "1",
    sort: SORTS.some((s) => s.value === sort) ? (sort as SortValue) : "newest",
    page: Number.isFinite(page) && page > 0 ? Math.min(page, 10_000) : 1,
  };
}

/** The query string for these filters; defaults are left out so URLs stay short. */
export function toQueryString(f: PostingFilters): string {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.types.length) p.set("type", f.types.join(","));
  if (f.setups.length) p.set("setup", f.setups.join(","));
  if (f.skills.length) p.set("skill", f.skills.join(","));
  if (f.source) p.set("source", f.source);
  if (f.ph) p.set("ph", "1");
  if (f.salary) p.set("salary", "1");
  if (f.sort !== "newest") p.set("sort", f.sort);
  if (f.page > 1) p.set("page", String(f.page));
  return p.toString();
}

export function postingsHref(f: PostingFilters): string {
  const qs = toQueryString(f);
  return qs ? `/postings?${qs}` : "/postings";
}

/** How many filters narrow the list (sort and page don't). */
export function activeFilterCount(f: PostingFilters): number {
  return (
    (f.q ? 1 : 0) +
    f.types.length +
    f.setups.length +
    f.skills.length +
    (f.source ? 1 : 0) +
    (f.ph ? 1 : 0) +
    (f.salary ? 1 : 0)
  );
}

export function pageCount(total: number, pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

/**
 * Page numbers to show, with "gap" where pages are skipped: first, last, and the current
 * page with one neighbour each side. pageItems(6, 12) -> [1, "gap", 5, 6, 7, "gap", 12].
 */
export function pageItems(current: number, pages: number): (number | "gap")[] {
  const wanted = new Set([1, pages, current - 1, current, current + 1]);
  const shown = [...wanted].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  for (const n of shown) {
    const prev = out.at(-1);
    if (typeof prev === "number" && n - prev === 2) out.push(prev + 1);
    else if (typeof prev === "number" && n - prev > 2) out.push("gap");
    out.push(n);
  }
  return out;
}
