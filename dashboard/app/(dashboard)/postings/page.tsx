import type { Metadata } from "next";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { postedLabel, textOrEmpty } from "@/lib/format-posting";
import { getActivePostings } from "@/lib/queries/postings";

export const metadata: Metadata = { title: "Postings · PH Dev Job Market Radar" };

export default async function PostingsPage() {
  const { rows, total, sources } = await getActivePostings();

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Postings</h1>
        <p className="text-muted-foreground text-sm">
          {rows.length === total
            ? `${total} active postings, newest first.`
            : `Newest ${rows.length} of ${total} active postings.`}{" "}
          Duplicates are hidden.
        </p>
      </header>

      {rows.length === 0 ? (
        <p className="text-muted-foreground">No active postings yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Salary</TableHead>
              <TableHead>Posted</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((p) => {
              const posted = postedLabel(p.postedAt, p.firstSeenAt);
              return (
                <TableRow key={p.id}>
                  <TableCell className="max-w-xs font-medium whitespace-normal">
                    {p.title}
                  </TableCell>
                  <TableCell className="max-w-48 whitespace-normal">
                    {textOrEmpty(p.company)}
                  </TableCell>
                  <TableCell className="max-w-48 whitespace-normal">
                    {textOrEmpty(p.locationText)}
                  </TableCell>
                  <TableCell>{textOrEmpty(p.salaryRaw)}</TableCell>
                  <TableCell className={posted.isFallback ? "text-muted-foreground" : undefined}>
                    {posted.text}
                  </TableCell>
                  <TableCell>
                    {/* Followed link (no nofollow/noreferrer): Remote OK's API terms require it. */}
                    <a
                      href={p.sourceUrl}
                      target="_blank"
                      rel="noopener"
                      className="hover:text-foreground underline underline-offset-4"
                    >
                      via {p.sourceName}
                    </a>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {sources.length > 0 && (
        <footer className="text-muted-foreground border-t pt-3 text-xs">
          <p className="font-medium">Data sources</p>
          <ul className="mt-1 space-y-0.5">
            {sources.map((s) => (
              <li key={s.id}>{s.attributionText}</li>
            ))}
          </ul>
        </footer>
      )}
    </section>
  );
}
