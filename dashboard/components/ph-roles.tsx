"use client";

import { useMemo, useState } from "react";

import { PostingCard, PostingList } from "@/components/posting-card";
import { DEFAULT_JOB_TYPES, JOB_TYPE_OPTIONS, filterRoles, skillCounts } from "@/lib/ph-filter";
import type { PhRole } from "@/lib/queries/ph-friendly";

const MAX_SKILL_CHIPS = 24;
/** Roles shown at first, and added by each "Show more". */
const PAGE = 20;

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
      className="hover:bg-muted aria-pressed:bg-foreground aria-pressed:text-background focus-visible:ring-ring/50 rounded-md border px-2.5 py-1 text-xs outline-none focus-visible:ring-3 aria-pressed:border-transparent"
    >
      {children}
    </button>
  );
}

/** Filters (job type, skills) and the list of PH-friendly roles. Filtering is local. */
export function PhRoles({ roles }: { roles: PhRole[] }) {
  const [jobTypes, setJobTypes] = useState(() => new Set(DEFAULT_JOB_TYPES));
  const [skills, setSkills] = useState(() => new Set<string>());
  const [limit, setLimit] = useState(PAGE);
  const chips = useMemo(() => skillCounts(roles).slice(0, MAX_SKILL_CHIPS), [roles]);
  const matched = filterRoles(roles, jobTypes, skills);
  const shown = matched.slice(0, limit);

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="mb-1.5 text-sm font-medium">Job type</legend>
          {JOB_TYPE_OPTIONS.map((o) => (
            <Chip
              key={o.value}
              on={jobTypes.has(o.value)}
              onClick={() => {
                setJobTypes((s) => toggle(s, o.value));
                setLimit(PAGE);
              }}
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
              onClick={() => {
                setSkills((s) => toggle(s, c.name));
                setLimit(PAGE);
              }}
            >
              {c.name} <span className="opacity-60">{c.n}</span>
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
        {matched.length} of {roles.length} PH-friendly roles match.
      </p>

      {matched.length === 0 ? (
        <p className="text-muted-foreground text-sm">No roles match these filters.</p>
      ) : (
        <>
          <PostingList>
            {shown.map((r) => (
              <PostingCard key={r.id} p={r} highlight={skills} />
            ))}
          </PostingList>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted-foreground text-sm tabular-nums">
              Showing {shown.length} of {matched.length}
            </p>
            {shown.length < matched.length && (
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE)}
                className="hover:bg-muted focus-visible:ring-ring/50 h-9 rounded-lg border px-3 text-sm outline-none focus-visible:ring-3"
              >
                Show {Math.min(PAGE, matched.length - shown.length)} more
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
