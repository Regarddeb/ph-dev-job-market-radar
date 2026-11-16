import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { RankBars } from "@/components/charts/rank-bars";
import { PostingCard, PostingList } from "@/components/posting-card";
import { StatTile } from "@/components/stat-tile";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { enumLabel, percent } from "@/lib/format";
import { DEFAULT_FILTERS } from "@/lib/postings-params";
import { getOverview } from "@/lib/queries/overview";
import { getPostingsPage } from "@/lib/queries/postings";

/** Newest postings previewed on the overview. */
const LATEST = 5;

export default async function OverviewPage() {
  const [o, latest] = await Promise.all([getOverview(), getPostingsPage(DEFAULT_FILTERS)]);
  const toItems = (rows: { key: string; n: number }[]) =>
    rows.map((r) => ({ key: r.key, label: enumLabel(r.key), n: r.n }));

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          The remote developer job market, from the Philippines
        </h1>
        <p className="text-muted-foreground max-w-prose text-sm">
          Developer postings collected once a day from public job sources, with duplicates removed:
          which skills are in demand, what roles pay, and which ones accept PH-based applicants.
          Active means listed in the source&apos;s latest crawl.
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

      {latest.rows.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold tracking-tight">Latest postings</h2>
            <Link
              href="/postings"
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm underline underline-offset-4"
            >
              Browse all {latest.total}
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </div>
          <PostingList>
            {latest.rows.slice(0, LATEST).map((p) => (
              <PostingCard key={p.id} p={p} />
            ))}
          </PostingList>
        </div>
      )}
    </section>
  );
}
