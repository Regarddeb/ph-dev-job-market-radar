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

const MANILA_DATE_TIME = new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/** "Nov 8, 1:07 PM" in Manila time. */
export function manilaDateTime(date: Date): string {
  return MANILA_DATE_TIME.format(date);
}

/** 14.9 MB, 1.2 GB (binary units, as Postgres reports sizes). */
export function bytes(value: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = value;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v >= 10 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}
