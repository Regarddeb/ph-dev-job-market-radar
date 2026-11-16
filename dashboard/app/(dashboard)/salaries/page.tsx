import type { Metadata } from "next";

import { SalaryRange } from "@/components/charts/salary-range";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MIN_SAMPLE, SALARY_WINDOW_DAYS, getSkillSalaries } from "@/lib/queries/salaries";

export const metadata: Metadata = { title: "Salaries" };

export default async function SalariesPage() {
  const all = await getSkillSalaries();
  const charted = all.filter((s) => s.n >= MIN_SAMPLE);
  const small = all.filter((s) => s.n < MIN_SAMPLE);

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Salaries</h1>
        <p className="text-muted-foreground text-sm">
          Monthly pay in PHP for postings first seen in the last {SALARY_WINDOW_DAYS} days that
          state a salary with a period. Each posting counts at its midpoint, (min + max) / 2.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Median and range per skill</CardTitle>
          <CardDescription>
            Skills with at least {MIN_SAMPLE} salaried postings; n is the number of postings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {charted.length > 0 ? (
            <SalaryRange rows={charted} />
          ) : (
            <p className="text-muted-foreground text-sm">
              Not enough salaried postings yet for any skill.
            </p>
          )}
          {small.length > 0 && (
            <p className="text-muted-foreground mt-4 text-xs">
              Fewer than {MIN_SAMPLE} postings (not charted):{" "}
              {small.map((s) => `${s.name} (n=${s.n})`).join(", ")}.
            </p>
          )}
        </CardContent>
      </Card>

      <footer className="text-muted-foreground space-y-1 border-t pt-3 text-xs">
        <p>
          Exchange rates: ECB euro foreign exchange reference rates (European Central Bank),
          published for information purposes. PHP rates for other currencies are derived as cross
          rates (PHP per EUR ÷ currency per EUR), at the rate for the day each posting was first
          seen.
        </p>
      </footer>
    </section>
  );
}
