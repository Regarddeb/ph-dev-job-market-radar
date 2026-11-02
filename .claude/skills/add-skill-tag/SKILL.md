---
name: add-skill-tag
description: Add a skill (e.g. a language, framework or tool) to the skill-tagging dictionary, with regex aliases and positive and negative tests. Use when the user wants a new skill tracked or an alias fixed.
arguments: [skill, category]
argument-hint: "[skill] [language|framework|database|tool|cloud]"
---

# Add skill tag: $skill ($category)

`category` must be one of `language`, `framework`, `database`, `tool` or `cloud`. Refuse anything else.

## 1. Check for duplicates

- Search `dashboard/prisma/seed.ts` for an existing skill or alias that covers `$skill` (case-insensitive, including spelling variants). If one exists, extend its aliases instead of adding a new skill.

## 2. Design aliases (regex, case-insensitive, matched over title + description)

- Every alias uses word boundaries. Escape metacharacters: `C\+\+`, `C#` → `\bC#(?!\w)`, `\.NET\b`, `\bNode\.?js\b`.
- Cover the common spellings: `Next.js` / `NextJS` / `Next JS`, `PostgreSQL` / `Postgres`, `k8s` for Kubernetes.
- **Ambiguous names need context.** These include Go, R, C, Swift, Rust, Dart, Spring, Rails, Express, Flask, Ruby, Java (vs JavaScript), Scala, Elm, Julia, Chef, Puppet and Salt. Use one of:
  - a disambiguating form: `\bgolang\b`, `\bgo (developer|engineer|programming)\b`, `\bR (programming|language)\b`, `\bSpring Boot\b`
  - a list context: `(?<=[,/(]\s?)Go(?=\s?[,/)])`, i.e. "Python, Go, Rust"
  - mark the alias `requirements_only` (if the seed supports it), so it only matches inside a requirements section that BeautifulSoup extracted
- Avoid catastrophic backtracking: no nested quantifiers like `(a+)+` and no unbounded `.*` between alternatives.

## 3. Add to the seed

- Add the skill and its aliases to the skills data in `dashboard/prisma/seed.ts`, in the same shape as the existing entries. The seed must stay idempotent (upsert by name).

## 4. Tests: `scraper/tests/test_skills.py`

Every alias gets **both**:
- **Positive** cases: realistic snippets that must tag `$skill`, e.g. "Senior Golang Engineer", "Stack: Python, Go, Postgres".
- **Negative** cases: snippets that must NOT tag it, e.g. "go-to person", "Go live", "Let's go!", "r/programming", "C-level", "Spring 2025 intake", "Swift delivery", "Rust-proof", "JavaScript" for Java.
- Use `pytest.mark.parametrize`. Keep the cases close to real job-ad phrasing.

## 5. Verify

- `uv run --project scraper pytest scraper/tests/test_skills.py -q`
- If saved fixtures exist, run the tagger over them and report how many postings gain or lose the tag. Big jumps usually mean a false positive.
- Report: aliases added, test counts (positive and negative), and any fixture impact.
