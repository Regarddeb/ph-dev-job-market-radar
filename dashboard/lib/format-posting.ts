// Pure display helpers for posting rows. No DB or Next imports, so they unit-test cleanly.

const MANILA_DATE = new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila",
  year: "numeric",
  month: "short",
  day: "numeric",
});

export const EMPTY = "—";

/** Formats a date as a calendar day in Manila time, e.g. "Nov 7, 2026". */
export function formatManilaDate(date: Date): string {
  return MANILA_DATE.format(date);
}

/**
 * The date to show in the "Posted" column. Falls back to when we first saw the
 * posting if the source didn't give a posted date, and says so (never guessed).
 */
export function postedLabel(
  postedAt: Date | null,
  firstSeenAt: Date,
): { text: string; isFallback: boolean } {
  if (postedAt) return { text: formatManilaDate(postedAt), isFallback: false };
  return { text: `first seen ${formatManilaDate(firstSeenAt)}`, isFallback: true };
}

/** Trims a nullable text field, showing an em dash when empty. */
export function textOrEmpty(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : EMPTY;
}
