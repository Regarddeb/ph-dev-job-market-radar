import { phpCompact, phpFull } from "@/lib/format";
import type { SkillSalary } from "@/lib/queries/salaries";

/**
 * Range plot: per skill, a light bar from the lowest stated minimum to the highest stated
 * maximum, and a dot at the median midpoint. n is always shown next to the skill name.
 */
export function SalaryRange({ rows }: { rows: SkillSalary[] }) {
  const max = niceMax(Math.max(1, ...rows.map((r) => r.high)));
  const pos = (v: number) => `${(100 * v) / max}%`;
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max];
  return (
    <div className="space-y-3">
      <div className="text-muted-foreground flex gap-4 text-xs" aria-hidden>
        <span className="flex items-center gap-1.5">
          <span className="bg-chart-1 size-2.5 rounded-full" /> Median
        </span>
        <span className="flex items-center gap-1.5">
          <span className="bg-chart-1/30 h-2 w-5 rounded-sm" /> Range (lowest min to highest max)
        </span>
      </div>
      <ul className="space-y-2.5">
        {rows.map((r) => (
          <li
            key={r.name}
            className="grid grid-cols-[9rem_1fr_4rem] items-center gap-3 text-sm"
            title={`${r.name} (n=${r.n}): median ${phpFull(r.median)}/month, range ${phpFull(r.low)} to ${phpFull(r.high)}`}
          >
            <span className="truncate">
              {r.name} <span className="text-muted-foreground">n={r.n}</span>
            </span>
            <span className="relative h-3">
              <span className="bg-chart-grid/40 absolute inset-y-1 right-0 left-0 rounded-sm" />
              <span
                className="bg-chart-1/30 absolute inset-y-0.5 rounded-sm"
                style={{ left: pos(r.low), width: `calc(${pos(r.high)} - ${pos(r.low)})` }}
              />
              <span
                className="bg-chart-1 ring-background absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2"
                style={{ left: pos(r.median) }}
              />
            </span>
            <span className="text-right tabular-nums">{phpCompact(r.median)}</span>
          </li>
        ))}
      </ul>
      {/* Shared x-axis, aligned with the plot column above. */}
      <div className="text-muted-foreground grid grid-cols-[9rem_1fr_4rem] gap-3 text-xs">
        <span />
        <span className="border-chart-grid relative h-4 border-t" aria-hidden>
          {ticks.map((t, i) => (
            <span
              key={t}
              className={`absolute top-1 tabular-nums ${
                i === 0 ? "" : i === ticks.length - 1 ? "-translate-x-full" : "-translate-x-1/2"
              }`}
              style={{ left: pos(t) }}
            >
              {phpCompact(t)}
            </span>
          ))}
        </span>
        <span className="text-right">/month</span>
      </div>
    </div>
  );
}

/** Round the axis maximum up to a clean step (₱250k / ₱500k / ₱1M...). */
function niceMax(value: number): number {
  const step = 10 ** Math.floor(Math.log10(value)) / 4;
  return Math.ceil(value / step) * step;
}
