// Pure filtering for the PH-friendly roles page (no React, so it unit-tests).

export type Filterable = { jobType: string; skills: string[] };

/** Job types a visitor can toggle, in display order. */
export const JOB_TYPE_OPTIONS = [
  { value: "part_time", label: "Part-time" },
  { value: "freelance", label: "Freelance" },
  { value: "contract", label: "Contract" },
  { value: "unspecified", label: "Not stated" },
  { value: "full_time", label: "Full-time" },
] as const;

/** Selected on first load: the site's focus is part-time / freelance work. */
export const DEFAULT_JOB_TYPES = ["part_time", "freelance", "contract", "unspecified"];

/**
 * Keep rows whose job type is selected and, when any skills are selected, that have at
 * least one of them (OR: "show me Python or Go roles").
 */
export function filterRoles<T extends Filterable>(
  rows: T[],
  jobTypes: Iterable<string>,
  skills: Iterable<string>,
): T[] {
  const types = new Set(jobTypes);
  const wanted = new Set(skills);
  return rows.filter(
    (r) => types.has(r.jobType) && (wanted.size === 0 || r.skills.some((s) => wanted.has(s))),
  );
}

/** Skills that appear in the rows, most common first (ties by name): the filter chips. */
export function skillCounts(rows: Filterable[]): { name: string; n: number }[] {
  const counts = new Map<string, number>();
  for (const r of rows) for (const s of r.skills) counts.set(s, (counts.get(s) ?? 0) + 1);
  return [...counts]
    .map(([name, n]) => ({ name, n }))
    .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
}
