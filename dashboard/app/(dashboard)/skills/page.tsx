import type { Metadata } from "next";

import { CompareBars } from "@/components/charts/compare-bars";
import { TrendChart } from "@/components/charts/trend-chart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getSkillsData, TREND_WEEKS } from "@/lib/queries/skills";

export const metadata: Metadata = { title: "Skills · PH Dev Job Market Radar" };

export default async function SkillsPage() {
  const { asOf, comparison, trendSkills, trend } = await getSkillsData();

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Skills</h1>
        <p className="text-muted-foreground text-sm">
          New postings per skill (a posting can count for several skills).
          {asOf && ` Data through ${asOf} (Manila).`}
        </p>
      </header>

      {comparison.length === 0 ? (
        <p className="text-muted-foreground">No skill statistics yet.</p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Top skills: last 30 days vs the 30 before</CardTitle>
              <CardDescription>
                Rolling windows rather than calendar months, so early-month numbers aren&apos;t
                misleadingly small.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CompareBars rows={comparison} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Weekly trend</CardTitle>
              <CardDescription>
                New postings per week, last {TREND_WEEKS} weeks. Pick up to four skills.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <TrendChart skills={trendSkills} data={trend} />
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}
