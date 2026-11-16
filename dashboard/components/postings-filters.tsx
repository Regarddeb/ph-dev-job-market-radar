"use client";

import { Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import {
  DEFAULT_FILTERS,
  JOB_TYPES,
  type PostingFilters,
  SORTS,
  WORK_SETUPS,
  activeFilterCount,
  postingsHref,
} from "@/lib/postings-params";
import type { PostingFacets } from "@/lib/queries/postings";

const SEARCH_DEBOUNCE_MS = 350;

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

function toggled<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value].sort();
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={label} className="grid gap-1.5 sm:grid-cols-[5.5rem_1fr]">
      <span className="text-muted-foreground pt-1 text-xs font-medium">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

/**
 * Filter controls for /postings. The URL is the state: every change navigates to the new
 * query string (page reset to 1), so a filtered view can be shared and the server does the
 * filtering and paging. `children` is the server-rendered result list, dimmed while the next
 * one loads.
 */
export function PostingsFilters({
  filters,
  facets,
  children,
}: {
  filters: PostingFilters;
  facets: PostingFacets;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [text, setText] = useState(filters.q);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const go = (next: Partial<PostingFilters>) => {
    if (timer.current) clearTimeout(timer.current);
    const href = postingsHref({ ...filters, ...next, page: 1 });
    startTransition(() => router.push(href, { scroll: false }));
  };

  const onSearch = (value: string) => {
    setText(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => go({ q: value.trim() }), SEARCH_DEBOUNCE_MS);
  };

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  const active = activeFilterCount(filters);
  // A selected skill outside the top list still needs a chip, so it can be switched off.
  const skillChips = [
    ...facets.skills,
    ...filters.skills
      .filter((s) => !facets.skills.some((f) => f.name === s))
      .map((name) => ({ name, n: null })),
  ];

  return (
    <div className="space-y-5">
      <div className="bg-card ring-foreground/10 space-y-3 rounded-xl p-4 ring-1">
        <div className="flex flex-wrap gap-2">
          <form
            role="search"
            className="relative min-w-48 flex-1"
            onSubmit={(e) => {
              e.preventDefault();
              go({ q: text.trim() });
            }}
          >
            <Search
              className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2"
              aria-hidden
            />
            <input
              type="search"
              value={text}
              onChange={(e) => onSearch(e.target.value)}
              placeholder="Search title or company"
              aria-label="Search postings by title or company"
              maxLength={80}
              className="bg-background focus-visible:ring-ring/50 focus-visible:border-ring h-9 w-full rounded-lg border pr-3 pl-8 text-sm outline-none focus-visible:ring-3"
            />
          </form>
          {facets.sources.length > 1 && (
            <select
              value={filters.source}
              onChange={(e) => go({ source: e.target.value })}
              aria-label="Source"
              className="bg-background focus-visible:ring-ring/50 h-9 rounded-lg border px-2 text-sm outline-none focus-visible:ring-3"
            >
              <option value="">All sources</option>
              {facets.sources.map((s) => (
                <option key={s.slug} value={s.slug}>
                  {s.name} ({s.n})
                </option>
              ))}
            </select>
          )}
          <select
            value={filters.sort}
            onChange={(e) => go({ sort: e.target.value as PostingFilters["sort"] })}
            aria-label="Sort order"
            className="bg-background focus-visible:ring-ring/50 h-9 rounded-lg border px-2 text-sm outline-none focus-visible:ring-3"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <Group label="Show only">
          <Chip on={filters.ph} onClick={() => go({ ph: !filters.ph })}>
            PH-friendly
          </Chip>
          <Chip on={filters.salary} onClick={() => go({ salary: !filters.salary })}>
            States a salary
          </Chip>
        </Group>
        <Group label="Work setup">
          {WORK_SETUPS.map((o) => (
            <Chip
              key={o.value}
              on={filters.setups.includes(o.value)}
              onClick={() => go({ setups: toggled(filters.setups, o.value) })}
            >
              {o.label}
            </Chip>
          ))}
        </Group>
        <Group label="Job type">
          {JOB_TYPES.map((o) => (
            <Chip
              key={o.value}
              on={filters.types.includes(o.value)}
              onClick={() => go({ types: toggled(filters.types, o.value) })}
            >
              {o.label}
            </Chip>
          ))}
        </Group>
        {skillChips.length > 0 && (
          <Group label="Skills (any)">
            {skillChips.map((s) => (
              <Chip
                key={s.name}
                on={filters.skills.includes(s.name)}
                onClick={() => go({ skills: toggled(filters.skills, s.name) })}
              >
                {s.name}
                {s.n !== null && <span className="ml-1 opacity-60">{s.n}</span>}
              </Chip>
            ))}
          </Group>
        )}

        {active > 0 && (
          <button
            type="button"
            onClick={() => {
              setText("");
              go({ ...DEFAULT_FILTERS, sort: filters.sort });
            }}
            className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs underline underline-offset-4"
          >
            <X className="size-3.5" aria-hidden />
            Clear {active} {active === 1 ? "filter" : "filters"}
          </button>
        )}
      </div>

      <div
        aria-busy={pending}
        className="space-y-5 transition-opacity aria-busy:opacity-50 motion-reduce:transition-none"
      >
        {children}
      </div>
    </div>
  );
}
