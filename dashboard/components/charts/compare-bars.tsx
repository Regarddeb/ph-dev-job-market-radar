import { change } from "@/lib/format";
import type { SkillComparison } from "@/lib/queries/skills";

/**
 * Emphasis bars: the current window in the accent hue, the previous window in gray as
 * context. Both bars are direct-labeled; the change column carries the comparison in text.
 */
export function CompareBars({ rows }: { rows: SkillComparison[] }) {
  const max = Math.max(1, ...rows.flatMap((r) => [r.current, r.previous]));
  return (
    <div className="space-y-3">
      <div className="text-muted-foreground flex gap-4 text-xs" aria-hidden>
        <span className="flex items-center gap-1.5">
          <span className="bg-chart-1 size-2.5 rounded-sm" /> Last 30 days
        </span>
        <span className="flex items-center gap-1.5">
          <span className="bg-chart-muted size-2.5 rounded-sm" /> Previous 30 days
        </span>
      </div>
      <ul className="space-y-2.5">
        {rows.map((r) => (
          <li
            key={r.name}
            className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-3 text-sm"
            title={`${r.name}: ${r.current} new postings in the last 30 days, ${r.previous} in the 30 before`}
          >
            <span className="truncate">{r.name}</span>
            <span className="space-y-0.5">
              <Bar value={r.current} max={max} className="bg-chart-1" />
              <Bar value={r.previous} max={max} className="bg-chart-muted" />
            </span>
            <span className="text-muted-foreground text-right tabular-nums">
              {change(r.current, r.previous)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Bar({ value, max, className }: { value: number; max: number; className: string }) {
  return (
    <span className="flex items-center gap-2">
      <span
        className={`block h-2 rounded-sm ${className}`}
        style={{ width: `${(100 * value) / max}%`, minWidth: value > 0 ? "2px" : 0 }}
      />
      <span className="text-muted-foreground text-xs tabular-nums">{value}</span>
    </span>
  );
}
