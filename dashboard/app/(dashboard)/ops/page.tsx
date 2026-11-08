import type { Metadata } from "next";

import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { bytes, manilaDateTime, percent } from "@/lib/format";
import {
  DB_LIMIT_BYTES,
  DB_WARN_BYTES,
  STALE_HOURS,
  getOpsData,
  type SourceHealth,
} from "@/lib/queries/ops";

export const metadata: Metadata = { title: "Ops · PH Dev Job Market Radar" };

function health(s: SourceHealth) {
  if (!s.isActive) return <span className="text-muted-foreground text-sm">Inactive</span>;
  if (!s.lastStatus) return <StatusBadge status="none" />;
  if (s.lastStatus === "failed") return <StatusBadge status="failed" />;
  if (s.stale) return <StatusBadge status="stale" label={`Stale (> ${STALE_HOURS} h)`} />;
  return <StatusBadge status={s.lastStatus} />;
}

export default async function OpsPage() {
  const ops = await getOpsData();
  const overWarn = ops.dbBytes > DB_WARN_BYTES;
  const share = Math.min(1, ops.dbBytes / DB_LIMIT_BYTES);

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Ops</h1>
        <p className="text-muted-foreground text-sm">
          Crawl health and database size, as of {manilaDateTime(ops.checkedAt)} (Manila). Times are
          Manila time.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Database size</CardTitle>
          <CardDescription>
            Neon free tier: 1 GB per project; writes stop at the cap. Warning above 800 MB.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold">{bytes(ops.dbBytes)}</span>
            <span className="text-muted-foreground text-sm">
              of 1 GB ({percent(ops.dbBytes, DB_LIMIT_BYTES)})
            </span>
            {overWarn && <StatusBadge status="warning" label="Above 800 MB" />}
          </div>
          {/* Meter: one ramp, with a tick at the 800 MB warning line. */}
          <div
            className="bg-chart-grid/50 relative h-2.5 rounded-full"
            role="meter"
            aria-valuemin={0}
            aria-valuemax={DB_LIMIT_BYTES}
            aria-valuenow={ops.dbBytes}
            aria-label="Database size against the 1 GB limit"
          >
            <span
              className={`block h-2.5 rounded-full ${overWarn ? "bg-status-warning" : "bg-chart-1"}`}
              style={{ width: `${Math.max(share * 100, 0.5)}%` }}
            />
            <span
              className="bg-muted-foreground absolute -top-1 h-4.5 w-0.5"
              style={{ left: `${(100 * DB_WARN_BYTES) / DB_LIMIT_BYTES}%` }}
              title="800 MB warning line"
            />
          </div>
          <p className="text-muted-foreground text-xs">
            Largest tables: {ops.tables.map((t) => `${t.name} ${bytes(t.bytes)}`).join(" · ")}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sources</CardTitle>
          <CardDescription>
            Flagged when an active source has no successful crawl in {STALE_HOURS} hours (GitHub
            disables scheduled workflows after 60 days without repo activity).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Health</TableHead>
                <TableHead>Last run</TableHead>
                <TableHead>Last success</TableHead>
                <TableHead className="text-right">Active postings</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ops.sources.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell>{health(s)}</TableCell>
                  <TableCell>{s.lastStartedAt ? manilaDateTime(s.lastStartedAt) : "—"}</TableCell>
                  <TableCell>
                    {s.lastOkAt
                      ? `${manilaDateTime(s.lastOkAt)} (${s.hoursSinceOk} h ago)`
                      : "never"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{s.activePostings}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent crawl runs</CardTitle>
          <CardDescription>
            Last 20. Found = relevant postings parsed; an incremental HN run finds only new
            comments.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Started</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Pages</TableHead>
                <TableHead className="text-right">Found</TableHead>
                <TableHead className="text-right">New</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ops.runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{manilaDateTime(r.startedAt)}</TableCell>
                  <TableCell>{r.source}</TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{r.pagesFetched}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.postingsFound}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.postingsNew}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.durationSeconds === null ? "—" : `${r.durationSeconds} s`}
                  </TableCell>
                  <TableCell className="text-muted-foreground max-w-xs text-xs whitespace-normal">
                    {r.error ?? ""}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
