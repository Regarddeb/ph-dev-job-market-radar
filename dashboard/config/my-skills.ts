// The owner's profile for /matches. Committed config, not stored in the DB, so the
// dashboard stays read-only (docs/SPEC.md §8). Edit freely; names must match `name` in
// prisma/data/skills.json exactly (lib/my-skills.test.ts checks this).

/** Skills to match. A posting matches when it is tagged with at least one of them. */
export const MY_SKILLS = [
  "Python",
  "TypeScript",
  "JavaScript",
  "React",
  "Next.js",
  "Node.js",
  "PostgreSQL",
  "SQL",
  "Docker",
  "Git",
] as const;

/**
 * Job types wanted. SPEC asks for part-time / freelance; remote contract work is included
 * because it is effectively freelance. Remove "contract" to follow SPEC strictly.
 */
export const MY_JOB_TYPES = ["part_time", "freelance", "contract"] as const;
