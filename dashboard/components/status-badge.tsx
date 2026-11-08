import { CircleCheck, CircleX, LoaderCircle, TriangleAlert } from "lucide-react";

export type Status = "ok" | "failed" | "running" | "stale" | "warning" | "none";

const STYLES: Record<Status, { label: string; className: string; Icon: typeof CircleCheck }> = {
  ok: { label: "OK", className: "text-status-good", Icon: CircleCheck },
  failed: { label: "Failed", className: "text-status-critical", Icon: CircleX },
  running: { label: "Running", className: "text-muted-foreground", Icon: LoaderCircle },
  stale: { label: "Stale", className: "text-status-warning", Icon: TriangleAlert },
  warning: { label: "Warning", className: "text-status-warning", Icon: TriangleAlert },
  none: { label: "No runs", className: "text-muted-foreground", Icon: TriangleAlert },
};

/** Status always shows icon + text; the colour is never the only signal. */
export function StatusBadge({ status, label }: { status: Status; label?: string }) {
  const { label: fallback, className, Icon } = STYLES[status];
  return (
    <span className="inline-flex items-center gap-1 text-sm whitespace-nowrap">
      <Icon className={`size-4 ${className}`} aria-hidden />
      <span>{label ?? fallback}</span>
    </span>
  );
}
