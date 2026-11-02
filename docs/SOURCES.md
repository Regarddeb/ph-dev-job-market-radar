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
| Remotive | api | `https://remotive.com/api/remote-jobs?category=software-dev` | ≤ ~4 requests/day (poll once daily). Jobs are delayed 24 h. Don't resubmit listings to other job boards. Link back to the Remotive job URL and name Remotive as the source. | Allowed | _not yet re-verified_ | |
| Remote OK | api | `https://remoteok.com/api` (optional `?tags=`) | Returns only the latest ~100. The first array element is a legal notice; skip it. Use a followed (not nofollow) link back and name Remote OK as the source. | Allowed | _not yet re-verified_ | |
| We Work Remotely | rss | Programming-category RSS feeds | Verify the terms first. Link back to the listing. | Allowed (verify terms) | _not yet re-verified_ | |
| HN "Who is Hiring?" | api + html | Official HN API (Firebase); comment bodies parsed with BeautifulSoup | Polite request rate. Link to the comment. Also the 5-year backfill source. | Allowed | _not yet re-verified_ | |

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

A PreToolUse hook blocks shell commands that reference these domains, and `.claude/settings.json` denies WebFetch to them.
