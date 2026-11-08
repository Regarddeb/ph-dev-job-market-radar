import type { Metadata } from "next";

import { MY_JOB_TYPES, MY_SKILLS } from "@/config/my-skills";
import { enumLabel } from "@/lib/format";
import { postedLabel, textOrEmpty } from "@/lib/format-posting";
import { type MatchRow, getMatches } from "@/lib/queries/matches";

export const metadata: Metadata = { title: "Matches · PH Dev Job Market Radar" };

function MatchCard({ m }: { m: MatchRow }) {
  const posted = postedLabel(m.postedAt, m.firstSeenAt);
  return (
    <li className="ring-foreground/10 space-y-2 rounded-xl p-4 ring-1">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="font-medium">{m.title}</h3>
        <span className="text-muted-foreground text-sm">{posted.text}</span>
      </div>
      <p className="text-muted-foreground text-sm">
        {/* Only what the posting states; missing parts are left out, not shown as "—". */}
        {[
          m.company,
          m.locationText,
          m.jobType === "unspecified" ? null : enumLabel(m.jobType),
          m.salaryRaw,
        ]
          .filter(Boolean)
          .join(" · ") || textOrEmpty(null)}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ul className="flex flex-wrap gap-1.5" aria-label="Your matching skills">
          {m.matched.map((skill) => (
            <li key={skill} className="bg-muted rounded-md px-2 py-0.5 text-xs">
              {skill}
            </li>
          ))}
        </ul>
        {/* Followed link (no nofollow/noreferrer): attribution per each source's terms. */}
        <a
          href={m.sourceUrl}
          target="_blank"
          rel="noopener"
          className="hover:text-foreground text-sm underline underline-offset-4"
        >
          via {m.sourceName}
        </a>
      </div>
    </li>
  );
}

function Section({
  title,
  description,
  rows,
  empty,
}: {
  title: string;
  description: string;
  rows: MatchRow[];
  empty: string;
}) {
  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">
          {title} <span className="text-muted-foreground">({rows.length})</span>
        </h2>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">{empty}</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((m) => (
            <MatchCard key={m.id} m={m} />
          ))}
        </ul>
      )}
    </section>
  );
}

export default async function MatchesPage() {
  const { matches, unstated } = await getMatches([...MY_SKILLS], [...MY_JOB_TYPES]);
  const wanted = MY_JOB_TYPES.map(enumLabel).join(", ").toLowerCase();

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Matches for me</h1>
        <p className="text-muted-foreground text-sm">
          Active postings that accept Philippines-based applicants and use at least one of my
          skills, newest first. PH-eligible means the posting says so (worldwide, APAC, or the
          Philippines named); unknown eligibility isn&apos;t counted.
        </p>
        <p className="text-muted-foreground text-xs">
          Skills: {MY_SKILLS.join(", ")} · Job types: {wanted}
        </p>
      </header>

      <Section
        title="Matches"
        description={`PH-eligible, ${wanted}, and at least one matching skill.`}
        rows={matches}
        empty="No matching postings right now. New ones arrive with the daily scrape."
      />
      <Section
        title="Worth a look"
        description="PH-eligible with a matching skill, but the posting doesn't state its job type."
        rows={unstated}
        empty="None right now."
      />
    </div>
  );
}
