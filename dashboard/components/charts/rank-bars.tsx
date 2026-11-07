import { percent } from "@/lib/format";

export type RankItem = { key: string; label: string; n: number };

/**
 * Ranked horizontal bars, largest first, one hue (part-to-whole where the parts are
 * compared). Every bar is direct-labeled with its count and share, so no legend is needed.
 */
export function RankBars({ items, total }: { items: RankItem[]; total: number }) {
  const max = Math.max(1, ...items.map((i) => i.n));
  return (
    <ul className="space-y-2" aria-label="Counts by category">
      {items.map((item) => (
        <li
          key={item.key}
          className="grid grid-cols-[7rem_1fr_5.5rem] items-center gap-3 text-sm"
          title={`${item.label}: ${item.n} of ${total} (${percent(item.n, total)})`}
        >
          <span className="text-muted-foreground truncate">{item.label}</span>
          <span className="bg-chart-grid/40 h-3 rounded-sm">
            <span
              className="bg-chart-1 block h-3 rounded-sm"
              style={{ width: `${(100 * item.n) / max}%` }}
            />
          </span>
          <span className="text-right tabular-nums">
            {item.n} <span className="text-muted-foreground">({percent(item.n, total)})</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
