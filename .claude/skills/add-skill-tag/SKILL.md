---
name: add-skill-tag
description: Add a skill (e.g. a language, framework or tool) to the skill-tagging dictionary, with regex aliases and positive and negative tests. Use when the user wants a new skill tracked or an alias fixed.
arguments: [skill, category]
argument-hint: "[skill] [language|framework|database|tool|cloud]"
---

# Add skill tag: $skill ($category)

`category` must be one of `language`, `framework`, `database`, `tool` or `cloud`. Refuse anything else.

The dictionary lives in **one file**, `dashboard/prisma/data/skills.json`:
- `prisma/seed.ts` loads it into `skills` / `skill_aliases`.
- `scraper/tests/test_skills.py` tests every entry.

Each entry has this shape:

```json
{
  "name": "Go",
  "category": "language",
  "aliases": [{ "pattern": "\\bgolang\\b" }, { "pattern": "...", "requirements_only": true }],
  "match": ["Senior Golang Engineer"],
  "no_match": ["Let's go!"]
}
```

## 1. Check for duplicates

- Search `skills.json` for an existing skill or alias that covers `$skill` (case-insensitive, including spelling variants). If one exists, extend its aliases instead of adding a new skill.

## 2. Design aliases (Python `re`, applied with IGNORECASE over title + description)

- Every alias uses word boundaries. Escape metacharacters: `c\+\+`, `(?<![\w#])c#(?![\w#])`, `(?<![\w.])\.net\b`, `\bnode\.?js\b`.
- In JSON every backslash is doubled (`\\b`).
- Cover the common spellings: `Next.js` / `NextJS` / `Next JS`, `PostgreSQL` / `Postgres`, `k8s` for Kubernetes.
- **Ambiguous names need context.** These include Go, R, C, Swift, Rust, Dart, Spring, Rails, Express, Flask, Ruby, Java (vs JavaScript), Scala, Elm, Julia, Chef, Puppet and Salt. Use one of:
  - a disambiguating form: `\bgolang\b`, `\bgo\s+(?:developer|engineer)\b`, `\b(?-i:R)\s+programming\b`, `\bspring\s*boot\b`
  - the project's list-context form, matching "Languages: Python, Go, Rust": `(?:^|[,/(:]\s*)(?-i:Go)(?=\s*(?:[,/)]|$))`. Use `(?-i:...)` to make the name case-sensitive.
  - `"requirements_only": true`, so the alias only matches inside a requirements section that BeautifulSoup extracted
- Watch for PH-specific collisions. `PHP` is also the peso: "PHP 50,000" must not tag the PHP language.
- Avoid catastrophic backtracking: no nested quantifiers like `(a+)+` and no unbounded `.*`. The test suite times every pattern against adversarial input.

## 3. Add the entry with its examples

- Add the skill to `skills.json` with `match` (≥ 1) and `no_match` (≥ 1) examples. Use realistic job-ad phrasing and cover **every alias**.
- Good negatives are the real-world collisions: "go-to person", "Go live", "Let's go!", "r/programming", "C-level", "Series C", "Spring 2026 intake", "SWIFT payments", "rust-proof", "JavaScript" for Java, "PHP 50,000".
- `test_skills.py` picks up the new entry automatically; you don't need to edit it.

## 4. Seed and verify

- `uv run --project scraper python -m pytest scraper/tests/test_skills.py -q`
- `cd dashboard && pnpm db:seed`. This is idempotent: it upserts skills, upserts aliases and removes aliases no longer listed.
- If saved fixtures exist, run the tagger over them and report how many postings gain or lose the tag. Big jumps usually mean a false positive.
- Report: aliases added, example counts (positive and negative), and any fixture impact.
