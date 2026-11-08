"use client";

import { useMemo, useState } from "react";

import { enumLabel } from "@/lib/format";
import { postedLabel } from "@/lib/format-posting";
import { DEFAULT_JOB_TYPES, JOB_TYPE_OPTIONS, filterRoles, skillCounts } from "@/lib/ph-filter";
import type { PhRole } from "@/lib/queries/ph-friendly";

const MAX_SKILL_CHIPS = 24;

function toggle(set: Set<string>, value: string): Set<string> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className="aria-pressed:border-foreground/40 aria-pressed:bg-muted rounded-md border px-2.5 py-1 text-xs"
    >
      {children}
    </button>
  );
}

/** Filters (job type, skills) and the list of PH-friendly roles. Filtering is local. */
export function PhRoles({ roles }: { roles: PhRole[] }) {
  const [jobTypes, setJobTypes] = useState(() => new Set(DEFAULT_JOB_TYPES));
  const [skills, setSkills] = useState(() => new Set<string>());
  const chips = useMemo(() => skillCounts(roles).slice(0, MAX_SKILL_CHIPS), [roles]);
  const shown = filterRoles(roles, jobTypes, skills);

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="mb-1.5 text-sm font-medium">Job type</legend>
          {JOB_TYPE_OPTIONS.map((o) => (
            <Chip
              key={o.value}
              on={jobTypes.has(o.value)}
              onClick={() => setJobTypes((s) => toggle(s, o.value))}
            >
              {o.label}
            </Chip>
          ))}
        </fieldset>
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="mb-1.5 text-sm font-medium">
            Skills <span className="text-muted-foreground font-normal">(any of)</span>
          </legend>
          {chips.map((c) => (
            <Chip
              key={c.name}
              on={skills.has(c.name)}
              onClick={() => setSkills((s) => toggle(s, c.name))}
            >
              {c.name} <span className="text-muted-foreground">{c.n}</span>
            </Chip>
          ))}
          {skills.size > 0 && (
            <button
              type="button"
              onClick={() => setSkills(new Set())}
              className="text-muted-foreground text-xs underline underline-offset-4"
            >
              Clear skills
            </button>
          )}
        </fieldset>
      </div>

      <p className="text-muted-foreground text-sm" aria-live="polite">
        Showing {shown.length} of {roles.length} PH-friendly roles.
      </p>

      {shown.length === 0 ? (
        <p className="text-muted-foreground text-sm">No roles match these filters.</p>
      ) : (
        <ul className="space-y-3">
          {shown.map((r) => (
            <RoleCard key={r.id} r={r} selected={skills} />
          ))}
        </ul>
      )}
    </div>
  );
}

function RoleCard({ r, selected }: { r: PhRole; selected: Set<string> }) {
  const posted = postedLabel(r.postedAt, r.firstSeenAt);
  // Only what the posting states; missing parts are left out rather than shown as "—".
  const meta = [
    r.company,
    r.locationText,
    r.jobType === "unspecified" ? "Job type not stated" : enumLabel(r.jobType),
    r.salaryRaw,
  ].filter(Boolean);
  return (
    <li className="ring-foreground/10 space-y-2 rounded-xl p-4 ring-1">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="font-medium">{r.title}</h3>
        <span className="text-muted-foreground text-sm">{posted.text}</span>
      </div>
      <p className="text-muted-foreground text-sm">{meta.join(" · ")}</p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ul className="flex flex-wrap gap-1.5" aria-label="Skills">
          {r.skills.map((skill) => (
            <li
              key={skill}
              className={`rounded-md px-2 py-0.5 text-xs ${
                selected.has(skill) ? "bg-foreground text-background" : "bg-muted"
              }`}
            >
              {skill}
            </li>
          ))}
        </ul>
        {/* Followed link (no nofollow/noreferrer): attribution per each source's terms. */}
        <a
          href={r.sourceUrl}
          target="_blank"
          rel="noopener"
          className="hover:text-foreground text-sm underline underline-offset-4"
        >
          via {r.sourceName}
        </a>
      </div>
    </li>
  );
}
