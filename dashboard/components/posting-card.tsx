import { ArrowUpRight, Banknote, Building2, CircleCheck, MapPin } from "lucide-react";

import { enumLabel, phpRange } from "@/lib/format";
import { postedLabel } from "@/lib/format-posting";

/** The fields a posting row needs; both /postings and /ph-friendly rows satisfy it. */
export type PostingCardData = {
  title: string;
  company: string | null;
  locationText: string | null;
  jobType: string;
  workSetup: string;
  seniority: string;
  phEligible: boolean | null;
  salaryRaw: string | null;
  salaryMinPhpMonthly: number | null;
  salaryMaxPhpMonthly: number | null;
  postedAt: Date | null;
  firstSeenAt: Date;
  sourceUrl: string;
  sourceName: string;
  skills: string[];
};

const LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  onsite: "On-site",
};

/**
 * One posting in a list. Shows only what the posting states: unknown fields are left out
 * rather than shown as "unspecified". No hooks, so it renders on the server or the client.
 */
export function PostingCard({
  p,
  highlight,
}: {
  p: PostingCardData;
  /** Skill names to emphasise (the visitor's selected filters). */
  highlight?: ReadonlySet<string>;
}) {
  const posted = postedLabel(p.postedAt, p.firstSeenAt);
  const php = phpRange(p.salaryMinPhpMonthly, p.salaryMaxPhpMonthly);
  const tags = [p.workSetup, p.jobType, p.seniority]
    .filter((v) => v !== "unspecified")
    .map((v) => LABELS[v] ?? enumLabel(v));

  return (
    <li className="group hover:bg-muted/40 grid gap-2 px-4 py-4 transition-colors sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <h3 className="min-w-0 text-base leading-snug font-medium break-words">
          {/* Followed link (no nofollow/noreferrer): attribution per each source's terms. */}
          <a
            href={p.sourceUrl}
            target="_blank"
            rel="noopener"
            className="focus-visible:ring-ring/50 rounded-sm underline-offset-4 outline-none group-hover:underline focus-visible:ring-3"
          >
            {p.title}
          </a>
        </h3>
        <span className="text-muted-foreground shrink-0 text-xs sm:text-sm">{posted.text}</span>
      </div>

      {(p.company || p.locationText) && (
        <p className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {p.company && (
            <span className="text-foreground inline-flex items-center gap-1.5">
              <Building2 className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
              {p.company}
            </span>
          )}
          {p.locationText && (
            <span className="inline-flex min-w-0 items-center gap-1.5">
              <MapPin className="size-3.5 shrink-0" aria-hidden />
              <span className="break-words">{p.locationText}</span>
            </span>
          )}
        </p>
      )}

      {p.salaryRaw && (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
          <Banknote className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
          <span className="break-words">{p.salaryRaw}</span>
          {php && (
            <span className="text-muted-foreground" title="Converted at ECB reference rates">
              ≈ {php} / month
            </span>
          )}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <ul className="flex flex-wrap items-center gap-1.5" aria-label="Details and skills">
          {p.phEligible && (
            <li className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs whitespace-nowrap">
              <CircleCheck className="text-status-good size-3.5" aria-hidden />
              PH-friendly
            </li>
          )}
          {tags.map((t) => (
            <li
              key={t}
              className="text-muted-foreground rounded-md border px-2 py-0.5 text-xs whitespace-nowrap"
            >
              {t}
            </li>
          ))}
          {p.skills.map((skill) => (
            <li
              key={skill}
              className={`rounded-md px-2 py-0.5 text-xs whitespace-nowrap ${
                highlight?.has(skill) ? "bg-foreground text-background" : "bg-muted"
              }`}
            >
              {skill}
            </li>
          ))}
        </ul>
        <a
          href={p.sourceUrl}
          target="_blank"
          rel="noopener"
          className="text-muted-foreground hover:text-foreground ml-auto inline-flex items-center gap-0.5 text-sm whitespace-nowrap underline underline-offset-4"
        >
          via {p.sourceName}
          <ArrowUpRight className="size-3.5" aria-hidden />
        </a>
      </div>
    </li>
  );
}

/** The bordered, divided list that PostingCards sit in. */
export function PostingList({ children }: { children: React.ReactNode }) {
  return (
    <ul className="bg-card ring-foreground/10 divide-y overflow-hidden rounded-xl ring-1">
      {children}
    </ul>
  );
}
