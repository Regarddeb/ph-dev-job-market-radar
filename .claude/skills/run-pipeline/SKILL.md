---
name: run-pipeline
description: Dry-run the scraper pipeline for one source and report fetch/parse results and field coverage.
disable-model-invocation: true
arguments: [source]
argument-hint: "[source-name]"
allowed-tools: Bash(uv run --project scraper python -m scraper.pipeline *)
---

# Run pipeline (dry run): $source

1. Check that `$source` has an adapter in `scraper/sources/` and is `Allowed` in `docs/SOURCES.md`. Otherwise stop.
2. From the **repo root** (not `scraper/`), run:

   ```
   uv run --project scraper python -m scraper.pipeline --source $source --dry-run
   ```

   `--dry-run` fetches and parses but writes nothing to the database. Run it **once**: sources may allow only a few requests per day. Don't re-run just to retry; reuse the output.
   To re-check parsing without the network, add `--fixture scraper/tests/fixtures/$source/<file>`.
3. Report as a compact table:

   | Metric | Value |
   | --- | --- |
   | Fetched (pages / items) | |
   | Parsed OK | |
   | Parse errors (count + first 3 messages) | |
   | % with salary (min or max PHP set) | |
   | % with seniority ≠ unspecified | |
   | % with ph_eligible set (true or false) | |
   | % with job_type ≠ unspecified | |
   | Avg skills per posting | |
   | Duplicates detected | |

4. Flag anything suspicious:
   - coverage that dropped sharply from earlier runs (possible site change → save a new fixture)
   - salaries outside about ₱5k–₱2M per month (likely a unit or period error)
   - a skill tagged on more than 60% of postings (likely an alias false positive)
   - any posting missing `source_url`

Never "fix" the data by editing fixtures or loosening rules to raise coverage. Unknown values stay NULL.
