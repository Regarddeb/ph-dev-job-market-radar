/**
 * System diagram: who writes to the database and who only reads it. Inline SVG that takes
 * its colours from the theme tokens, so it follows light and dark mode. It is wider than a
 * phone, so its wrapper scrolls sideways there; the caption and the text around it carry
 * the same information.
 */
export function ArchitectureDiagram() {
  const box = "fill-card stroke-border";
  const line = "stroke-muted-foreground";
  const title = "fill-foreground text-[13px] font-medium";
  const note = "fill-muted-foreground text-[11px]";

  return (
    <figure className="space-y-2">
      <div className="ring-foreground/10 overflow-x-auto rounded-xl p-3 ring-1">
        <svg
          viewBox="0 0 860 330"
          role="img"
          aria-labelledby="arch-title arch-desc"
          className="h-auto w-full min-w-[640px]"
        >
          <title id="arch-title">System architecture</title>
          <desc id="arch-desc">
            A daily GitHub Actions job fetches three job sources and European Central Bank exchange
            rates, and writes to a Neon Postgres database. The Next.js dashboard on Vercel reads
            that database with a read-only role and serves cached pages to visitors. After each run
            the job calls the dashboard to refresh its cache.
          </desc>
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" className="fill-muted-foreground" />
            </marker>
          </defs>

          {/* Sources */}
          {[
            { y: 18, name: "Remote OK", how: "JSON API" },
            { y: 78, name: "Hacker News", how: "official API + HTML" },
            { y: 138, name: "Jobicy", how: "JSON API, cursor pages" },
            { y: 198, name: "ECB", how: "exchange rates (XML)" },
          ].map((s) => (
            <g key={s.name}>
              <rect x="10" y={s.y} width="170" height="46" rx="8" className={box} />
              <text x="24" y={s.y + 20} className={title}>
                {s.name}
              </text>
              <text x="24" y={s.y + 36} className={note}>
                {s.how}
              </text>
              <line
                x1="180"
                y1={s.y + 23}
                x2="262"
                y2={s.y + 23}
                className={line}
                markerEnd="url(#arrow)"
              />
            </g>
          ))}
          <text x="186" y="12" className={note}>
            fetch, once a day
          </text>

          {/* Scraper */}
          <rect x="266" y="18" width="200" height="226" rx="10" className={box} />
          <text x="282" y="42" className={title}>
            GitHub Actions
          </text>
          <text x="282" y="58" className={note}>
            Python scraper, 01:07 Manila
          </text>
          {[
            "exchange rates",
            "one step per source",
            "dedupe",
            "aggregate daily stats",
            "retention (trim old text)",
            "revalidate dashboard",
          ].map((step, i) => (
            <text key={step} x="282" y={86 + i * 26} className={note}>
              {i + 1}. {step}
            </text>
          ))}

          {/* Database */}
          <line x1="466" y1="100" x2="548" y2="100" className={line} markerEnd="url(#arrow)" />
          <text x="474" y="92" className={note}>
            writes
          </text>
          <rect x="552" y="52" width="140" height="96" rx="10" className={box} />
          <text x="566" y="78" className={title}>
            Neon Postgres
          </text>
          <text x="566" y="96" className={note}>
            Singapore
          </text>
          <text x="566" y="114" className={note}>
            schema owned by
          </text>
          <text x="566" y="130" className={note}>
            Prisma migrations
          </text>

          {/* Dashboard */}
          <line x1="622" y1="204" x2="622" y2="152" className={line} markerEnd="url(#arrow)" />
          <text x="630" y="182" className={note}>
            reads (read-only role)
          </text>
          <rect x="552" y="208" width="140" height="78" rx="10" className={box} />
          <text x="566" y="234" className={title}>
            Vercel
          </text>
          <text x="566" y="252" className={note}>
            Next.js dashboard,
          </text>
          <text x="566" y="268" className={note}>
            cached pages
          </text>

          {/* Revalidate */}
          <path
            d="M366,244 L366,266 L548,266"
            fill="none"
            className={line}
            strokeDasharray="4 3"
            markerEnd="url(#arrow)"
          />
          <text x="376" y="282" className={note}>
            POST /api/revalidate
          </text>

          {/* Visitor */}
          <line x1="692" y1="247" x2="756" y2="247" className={line} markerEnd="url(#arrow)" />
          <rect x="760" y="224" width="90" height="46" rx="8" className={box} />
          <text x="774" y="252" className={title}>
            Visitor
          </text>
        </svg>
      </div>
      <figcaption className="text-muted-foreground text-xs">
        Only the scheduled job writes. The website reads through a database role that can only run
        SELECT, and its pages are cached until the next run refreshes them (dashed line).
      </figcaption>
    </figure>
  );
}
