// Pure display helpers for numbers. No DB or Next imports.

/** ₱683k, ₱1.2M: compact PHP for chart labels. */
export function phpCompact(value: number): string {
  if (value >= 1_000_000) return `₱${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 1_000) return `₱${Math.round(value / 1_000)}k`;
  return `₱${Math.round(value)}`;
}

/** ₱682,679: full PHP for tooltips and tables. */
export function phpFull(value: number): string {
  return `₱${Math.round(value).toLocaleString("en-PH")}`;
}

/** Share of a total as a whole percent; "—" when the total is 0. */
export function percent(part: number, total: number): string {
  return total > 0 ? `${Math.round((100 * part) / total)}%` : "—";
}

/**
 * Change from previous to current. "new" when previous is 0 (no finite % change), and
 * "—" when both are 0.
 */
export function change(current: number, previous: number): string {
  if (previous === 0) return current === 0 ? "—" : "new";
  const pct = Math.round((100 * (current - previous)) / previous);
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

/** "full_time" -> "Full time". */
export function enumLabel(value: string): string {
  const text = value.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
