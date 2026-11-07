"use client";

import { useState } from "react";
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TrendPoint } from "@/lib/queries/skills-series";

/** Up to four lines at once: the palette's four slots, each with a legend entry. */
const SLOTS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)"];
const MAX_SELECTED = SLOTS.length;

type Props = { skills: string[]; data: TrendPoint[] };

/**
 * Weekly new postings for skills the viewer picks (up to 4). Color follows the skill: a
 * skill keeps its slot while selected, so deselecting one never repaints the others.
 */
export function TrendChart({ skills, data }: Props) {
  // slot index -> skill (null = free). Starts with the top skills in slots 1..n.
  const [slots, setSlots] = useState<(string | null)[]>(() =>
    SLOTS.map((_, i) => skills[i] ?? null),
  );
  const selected = slots
    .map((name, i) => (name ? { name, color: SLOTS[i] } : null))
    .filter((s): s is { name: string; color: string } => s !== null);

  function toggle(name: string) {
    setSlots((prev) => {
      const at = prev.indexOf(name);
      if (at >= 0) return prev.map((s, i) => (i === at ? null : s));
      const free = prev.indexOf(null);
      if (free < 0) return prev; // full: deselect one first
      return prev.map((s, i) => (i === free ? name : s));
    });
  }

  const formatWeek = (w: string) =>
    new Date(`${w}T00:00:00`).toLocaleDateString("en-PH", { month: "short", day: "numeric" });

  return (
    <div className="space-y-4">
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Skills to show (up to {MAX_SELECTED})</legend>
        {skills.map((name) => {
          const slot = slots.indexOf(name);
          const on = slot >= 0;
          const full = !on && !slots.includes(null);
          return (
            <button
              key={name}
              type="button"
              aria-pressed={on}
              disabled={full}
              onClick={() => toggle(name)}
              className="aria-pressed:bg-muted flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs disabled:opacity-40"
              title={full ? `Deselect a skill to add ${name} (max ${MAX_SELECTED})` : undefined}
            >
              <span
                className="size-2.5 rounded-full border"
                style={on ? { background: SLOTS[slot], borderColor: SLOTS[slot] } : undefined}
              />
              {name}
            </button>
          );
        })}
      </fieldset>

      {data.length < 2 ? (
        <p className="text-muted-foreground text-sm">
          The trend needs at least two weeks of data; it fills in as the daily scrape runs.
        </p>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 8, right: 72, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
              <XAxis
                dataKey="week"
                tickFormatter={formatWeek}
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--chart-grid)" }}
              />
              <YAxis
                allowDecimals={false}
                width={32}
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                labelFormatter={(w) => `Week of ${formatWeek(String(w))}`}
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              {selected.map(({ name, color }) => (
                <Line
                  key={name}
                  dataKey={name}
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, stroke: "var(--background)", strokeWidth: 2 }}
                  isAnimationActive={false}
                >
                  {/* Direct label at the line's end: identity never relies on color alone. */}
                  <LabelList
                    dataKey={name}
                    content={({ x, y, index }) =>
                      index === data.length - 1 ? (
                        <text
                          x={Number(x) + 6}
                          y={Number(y)}
                          dy={4}
                          fontSize={12}
                          fill="var(--foreground)"
                        >
                          {name}
                        </text>
                      ) : null
                    }
                  />
                </Line>
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <details className="text-sm">
        <summary className="text-muted-foreground cursor-pointer">Show as table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left tabular-nums">
            <thead>
              <tr className="border-b">
                <th className="py-1 pr-4 font-medium">Week of</th>
                {selected.map(({ name }) => (
                  <th key={name} className="py-1 pr-4 font-medium">
                    {name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((point) => (
                <tr key={point.week} className="border-b last:border-0">
                  <td className="py-1 pr-4">{formatWeek(point.week)}</td>
                  {selected.map(({ name }) => (
                    <td key={name} className="py-1 pr-4">
                      {point[name]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
