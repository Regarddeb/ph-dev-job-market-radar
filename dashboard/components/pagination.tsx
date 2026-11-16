import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { PAGE_SIZE, type PostingFilters, pageItems, postingsHref } from "@/lib/postings-params";

const BASE =
  "inline-flex h-9 min-w-9 items-center justify-center gap-1 rounded-lg border px-2.5 text-sm tabular-nums";
const OFF = `${BASE} text-muted-foreground opacity-50`;

/** Page links for /postings. Every page is a real URL, so it can be shared or bookmarked. */
export function Pagination({
  filters,
  page,
  pages,
  total,
}: {
  filters: PostingFilters;
  page: number;
  pages: number;
  total: number;
}) {
  const from = (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);
  const href = (n: number) => postingsHref({ ...filters, page: n });

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3"
    >
      <p className="text-muted-foreground text-sm tabular-nums">
        Showing {from}–{to} of {total}
      </p>
      {pages > 1 && (
        <ul className="flex flex-wrap items-center gap-1.5">
          <li>
            {page > 1 ? (
              <Link href={href(page - 1)} rel="prev" className={`${BASE} hover:bg-muted`}>
                <ChevronLeft className="size-4" aria-hidden />
                <span className="max-sm:sr-only">Previous</span>
              </Link>
            ) : (
              <span aria-disabled="true" className={OFF}>
                <ChevronLeft className="size-4" aria-hidden />
                <span className="max-sm:sr-only">Previous</span>
              </span>
            )}
          </li>
          {pageItems(page, pages).map((item, i) =>
            item === "gap" ? (
              <li key={`gap-${i}`} aria-hidden className="text-muted-foreground px-1">
                …
              </li>
            ) : (
              <li key={item}>
                <Link
                  href={href(item)}
                  aria-label={`Page ${item}`}
                  aria-current={item === page ? "page" : undefined}
                  className={`${BASE} hover:bg-muted aria-[current=page]:bg-foreground aria-[current=page]:text-background aria-[current=page]:border-transparent`}
                >
                  {item}
                </Link>
              </li>
            ),
          )}
          <li>
            {page < pages ? (
              <Link href={href(page + 1)} rel="next" className={`${BASE} hover:bg-muted`}>
                <span className="max-sm:sr-only">Next</span>
                <ChevronRight className="size-4" aria-hidden />
              </Link>
            ) : (
              <span aria-disabled="true" className={OFF}>
                <span className="max-sm:sr-only">Next</span>
                <ChevronRight className="size-4" aria-hidden />
              </span>
            )}
          </li>
        </ul>
      )}
    </nav>
  );
}
