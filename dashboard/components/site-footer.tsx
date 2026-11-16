const LINK = "hover:text-foreground underline underline-offset-4";

/** Shown on every page: where the data comes from, and the ECB citation its terms require. */
export function SiteFooter() {
  return (
    <footer className="text-muted-foreground mt-12 border-t text-xs">
      <div className="mx-auto w-full max-w-6xl space-y-1.5 px-4 py-6 sm:px-6">
        <p>
          Job data from{" "}
          <a href="https://remoteok.com" target="_blank" rel="noopener" className={LINK}>
            Remote OK
          </a>
          ,{" "}
          <a href="https://jobicy.com" target="_blank" rel="noopener" className={LINK}>
            Jobicy
          </a>{" "}
          and the{" "}
          <a href="https://news.ycombinator.com" target="_blank" rel="noopener" className={LINK}>
            Hacker News
          </a>{" "}
          &quot;Who is hiring?&quot; threads, refreshed once a day. Every posting links back to its
          source; fields a posting doesn&apos;t state are left blank, never guessed.
        </p>
        <p>
          Exchange rates: ECB euro reference rates (USD→PHP etc. derived as cross rates), at the
          rate for the day each posting was first seen.
        </p>
        <p>
          An independent, informational portfolio project, not affiliated with the sources.{" "}
          <a
            href="https://github.com/Regarddeb/ph-dev-job-market-radar"
            target="_blank"
            rel="noopener"
            className={LINK}
          >
            Source code on GitHub
          </a>
          .
        </p>
      </div>
    </footer>
  );
}
