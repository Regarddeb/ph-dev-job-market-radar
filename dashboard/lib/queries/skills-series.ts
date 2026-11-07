// Pure shaping for the weekly trend chart (no DB or server-only imports, so it unit-tests).

export type TrendPoint = { week: string } & Record<string, number | string>;
export type WeekRow = { week: string; name: string; n: number };

/** One point per week (oldest first), every skill present (0 when no new postings). */
export function toWeeklySeries(rows: WeekRow[], skills: string[]): TrendPoint[] {
  const weeks = [...new Set(rows.map((r) => r.week))].sort();
  return weeks.map((week) => {
    const point: TrendPoint = { week };
    for (const name of skills) point[name] = 0;
    for (const r of rows) if (r.week === week) point[r.name] = r.n;
    return point;
  });
}
