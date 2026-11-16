import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Pagination } from "@/components/pagination";
import { PostingCard, PostingList } from "@/components/posting-card";
import { PostingsFilters } from "@/components/postings-filters";
import { activeFilterCount, parseFilters } from "@/lib/postings-params";
import { getPostingFacets, getPostingsPage } from "@/lib/queries/postings";

export const metadata: Metadata = { title: "Postings" };

export default function PostingsPage({ searchParams }: PageProps<"/postings">) {
  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Postings</h1>
        <p className="text-muted-foreground max-w-prose text-sm">
          Developer roles listed in each source&apos;s latest crawl, newest first, with duplicates
          hidden. Each title links to the original posting.
        </p>
      </header>
      {/* The filters come from the URL, which is only known per request: the header above is
          the static shell and the results stream in. */}
      <Suspense fallback={<ResultsSkeleton />}>
        <Results searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function Results({ searchParams }: Pick<PageProps<"/postings">, "searchParams">) {
  const filters = parseFilters(await searchParams);
  const [{ rows, total, page, pages }, facets] = await Promise.all([
    getPostingsPage(filters),
    getPostingFacets(),
  ]);
  const narrowed = activeFilterCount(filters) > 0;
  const highlight = new Set(filters.skills);

  return (
    <>
      <PostingsFilters filters={filters} facets={facets}>
        <p className="text-sm" aria-live="polite">
          <span className="font-medium tabular-nums">{total}</span>{" "}
          <span className="text-muted-foreground">
            {narrowed
              ? `of ${facets.total} active postings match`
              : total === 1
                ? "active posting"
                : "active postings"}
          </span>
        </p>

        {rows.length === 0 ? (
          <div className="ring-foreground/10 space-y-2 rounded-xl px-4 py-12 text-center ring-1">
            <p className="font-medium">
              {narrowed ? "No postings match these filters" : "No active postings yet"}
            </p>
            {narrowed && (
              <p className="text-muted-foreground text-sm">
                Try removing a filter, or{" "}
                <Link href="/postings" className="text-foreground underline underline-offset-4">
                  clear them all
                </Link>
                .
              </p>
            )}
          </div>
        ) : (
          <>
            <PostingList>
              {rows.map((p) => (
                <PostingCard key={p.id} p={p} highlight={highlight} />
              ))}
            </PostingList>
            <Pagination filters={filters} page={page} pages={pages} total={total} />
          </>
        )}
      </PostingsFilters>

      {facets.sources.length > 0 && (
        <footer className="text-muted-foreground border-t pt-3 text-xs">
          <p className="font-medium">Data sources</p>
          <ul className="mt-1 space-y-0.5">
            {facets.sources.map((s) => (
              <li key={s.slug}>{s.attributionText}</li>
            ))}
          </ul>
        </footer>
      )}
    </>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading postings">
      <div className="bg-muted/60 h-44 animate-pulse rounded-xl motion-reduce:animate-none" />
      <div className="ring-foreground/10 divide-y rounded-xl ring-1">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="space-y-2.5 px-5 py-4">
            <div className="bg-muted h-4 w-2/5 animate-pulse rounded motion-reduce:animate-none" />
            <div className="bg-muted/70 h-3 w-1/4 animate-pulse rounded motion-reduce:animate-none" />
            <div className="bg-muted/70 h-3 w-3/5 animate-pulse rounded motion-reduce:animate-none" />
          </div>
        ))}
      </div>
    </div>
  );
}
