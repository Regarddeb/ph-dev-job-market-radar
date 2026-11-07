# Source registry

The single source of truth for which job sites the scraper may touch. `/add-source` refuses anything not marked **Allowed** here.

**Process.** Before implementing an adapter, re-verify the source's terms, robots.txt and API docs, then fill in "Terms checked" (YYYY-MM-DD) and the terms URL. Candidates go through the `source-researcher` subagent first. Re-check every ~90 days, or when a source changes behaviour.

**Statuses**
- `Allowed`: OK to implement and run.
- `Candidate`: not yet vetted.
- `Unclear`: terms are ambiguous, so don't implement.
- `Rejected` / `Forbidden`: never implement.

## Allowed

| Source | Kind | Access | Rules | Status | Terms checked | Terms URL |
| --- | --- | --- | --- | --- | --- | --- |
| Remote OK | api | `https://remoteok.com/api` (optional `?tags=`) | Returns only the latest ~100. The first array element is a legal notice; skip it. API ToS (in that element): "Please link back (with follow, and without nofollow!) to the URL on Remote OK and mention Remote OK as a source … If you do not we'll have to suspend API access." Don't use the logo (registered trademark); do use the name "Remote OK". robots.txt: `User-agent: *` → `Allow: /`, `Content-Signal: search=yes,ai-train=no` (named AI crawlers are blocked; we're not an AI crawler, and the app makes no AI use). Poll once daily. | Allowed | 2026-11-06 | `https://remoteok.com/api` (legal notice) |
| HN "Who is Hiring?" | api + html | Official HN API `https://hacker-news.firebaseio.com/v0/` (items, `user/whoishiring.json`); comment bodies parsed with BeautifulSoup | API README: "There is currently no rate limit." MIT-licensed docs; no stated usage restrictions. `news.ycombinator.com` robots.txt has `Crawl-delay: 30`, so only the API is fetched (never the HTML site). Still be polite (≥ 1 s between requests). Link to the comment `https://news.ycombinator.com/item?id=<id>`. Also the 5-year backfill source. | Allowed | 2026-11-06 | `https://github.com/HackerNews/API` |
| We Work Remotely | rss | Programming-category RSS feeds | Verify the terms first. Link back to the listing. | Allowed (verify terms) | _not yet re-verified_ | |

## Reference data (not job sources)

| Source | Kind | Access | Rules | Status | Terms checked | Terms URL |
| --- | --- | --- | --- | --- | --- | --- |
| ECB euro foreign exchange reference rates | xml / csv | `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml` daily (`scraper/fx.py`); `eurofxref-hist.zip` once for history (`--history`) | Published "for information purposes only" (that's our use: converting stated salaries for comparison). Free reuse on condition that "the ECB must be cited as the source" and changes are disclosed. Our change: PHP per unit of X is a cross rate, PHP/EUR ÷ X/EUR. So any page showing PHP-converted salaries must say "Exchange rates: ECB euro reference rates (USD→PHP etc. derived as cross rates)". robots.txt: `/stats/eurofxref/` not disallowed, `Crawl-delay: 5` (honoured; one request per run). Updated ~16:00 CET on TARGET working days. | Allowed | 2026-11-07 | `https://www.ecb.europa.eu/services/disclaimer/html/index.en.html` |

## Unclear: don't implement until resolved

_None._

## Candidates (vet with `source-researcher` before use)

| Source | Kind | Access | Notes | Status | Terms checked | Terms URL |
| --- | --- | --- | --- | --- | --- | --- |
| Himalayas | api | official feed/API | Remote-first; may include APAC-friendly roles | Candidate | | |
| Arbeitnow | api | official job board API | EU-heavy; check PH relevance | Candidate | | |
| Greenhouse boards | api | public Job Board API per company | Needs a curated list of company boards | Candidate | | |
| Lever boards | api | public Postings API per company | Needs a curated list of company boards | Candidate | | |

## Forbidden: never scrape, fetch, or add

| Source | Reason |
| --- | --- |
| JobStreet / JobsDB / SEEK | Terms prohibit scraping, and robots rules forbid it without written consent |
| LinkedIn | Terms prohibit scraping |
| Indeed | Terms prohibit scraping |
| Upwork | Terms prohibit scraping |
| OnlineJobs.ph | No API; employer data is behind a login |
| Remotive | Excluded by the project owner on 2026-11-06. Its Terms of Use (§8, March 2026) forbid automated access "without our written permission", and robots.txt has `Disallow: /api/*`, even though its API page invites public use. Not worth the ambiguity: Remote OK and HN cover the need. |

A PreToolUse hook blocks shell commands that reference these domains (Remotive included), and `.claude/settings.json` denies WebFetch to them.
