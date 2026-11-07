import { RankBars } from "@/components/charts/rank-bars";
import { StatTile } from "@/components/stat-tile";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { enumLabel, percent } from "@/lib/format";
import { getOverview } from "@/lib/queries/overview";

export default async function OverviewPage() {
  const o = await getOverview();
  const toItems = (rows: { key: string; n: number }[]) =>
    rows.map((r) => ({ key: r.key, label: enumLabel(r.key), n: r.n }));

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="text-muted-foreground text-sm">
          Remote developer postings from allowed sources, duplicates removed. Active = listed in the
          source&apos;s latest crawl.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Active postings" value={String(o.active)} />
        <StatTile label="New this week" value={String(o.newThisWeek)} sub="first seen, 7 days" />
        <StatTile
          label="With salary"
          value={percent(o.withSalary, o.active)}
          sub={`${o.withSalary} of ${o.active} state one`}
        />
        <StatTile
          label="Remote + PH-eligible"
          value={percent(o.remotePhEligible, o.active)}
          sub={`${o.remotePhEligible} of ${o.active}; unknown counts as no`}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Job type</CardTitle>
            <CardDescription>
              Active postings. Unspecified = the posting doesn&apos;t say.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RankBars items={toItems(o.jobTypes)} total={o.active} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Work setup</CardTitle>
            <CardDescription>Active postings.</CardDescription>
          </CardHeader>
          <CardContent>
            <RankBars items={toItems(o.workSetups)} total={o.active} />
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
