// Seeds reference data: sources, skills, skill_aliases. Idempotent (upserts only).
// Run with: pnpm db:seed   (uses MIGRATE_DATABASE_URL, the owner role)
//
// Skills come from prisma/data/skills.json, shared with scraper/tests/test_skills.py.
// Skills removed from the JSON are NOT deleted (that would cascade to posting_skills);
// the seed reports them so they can be retired deliberately in a migration or by hand.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { PrismaNeon } from "@prisma/adapter-neon";
import { config } from "dotenv";

import { PrismaClient, SkillCategory, SourceKind } from "../lib/generated/prisma/client";

config({ path: join(import.meta.dirname, "../../.env"), quiet: true });

type SourceSeed = {
  slug: string;
  name: string;
  baseUrl: string;
  kind: SourceKind;
  attributionText: string;
  crawlIntervalMinutes: number;
  /** Flip to true in the same change that adds scraper/sources/<slug>.py (/add-source). */
  isActive: boolean;
  /** Filled in when terms are re-verified (docs/SOURCES.md). */
  termsUrl: string | null;
};

// Sources marked Allowed in docs/SOURCES.md. Slugs are Python module names.
const SOURCES: SourceSeed[] = [
  {
    slug: "remoteok",
    name: "Remote OK",
    baseUrl: "https://remoteok.com",
    kind: SourceKind.api,
    attributionText: "via Remote OK",
    crawlIntervalMinutes: 1440,
    isActive: true, // adapter: scraper/sources/remoteok.py (terms checked 2026-11-06)
    termsUrl: "https://remoteok.com/api",
  },
  {
    slug: "weworkremotely",
    name: "We Work Remotely",
    baseUrl: "https://weworkremotely.com",
    kind: SourceKind.rss,
    attributionText: "via We Work Remotely",
    crawlIntervalMinutes: 1440,
    isActive: false,
    termsUrl: null,
  },
  {
    slug: "hn_hiring",
    name: 'HN "Who is Hiring?"',
    baseUrl: "https://news.ycombinator.com",
    kind: SourceKind.api,
    attributionText: "via Hacker News",
    crawlIntervalMinutes: 1440,
    isActive: true,
    termsUrl: "https://github.com/HackerNews/API",
  },
];

type SkillSeed = {
  name: string;
  category: SkillCategory;
  aliases: { pattern: string; requirements_only?: boolean }[];
};

function loadSkills(): SkillSeed[] {
  const file = join(import.meta.dirname, "data", "skills.json");
  const data = JSON.parse(readFileSync(file, "utf8")) as { skills: SkillSeed[] };
  const categories = new Set<string>(Object.values(SkillCategory));
  for (const s of data.skills) {
    if (!categories.has(s.category)) throw new Error(`${s.name}: bad category ${s.category}`);
    if (s.aliases.length === 0) throw new Error(`${s.name}: no aliases`);
  }
  return data.skills;
}

// Sources moved to Forbidden in docs/SOURCES.md. Their rows are deleted only if nothing was
// ever crawled for them (deleting a crawled source would cascade to its data).
const RETIRED_SOURCES = ["remotive"]; // excluded 2026-11-06

async function seedSources(prisma: PrismaClient): Promise<void> {
  for (const { slug, ...fields } of SOURCES) {
    await prisma.source.upsert({ where: { slug }, create: { slug, ...fields }, update: fields });
  }
  console.log(`sources: ${SOURCES.length} upserted`);

  for (const slug of RETIRED_SOURCES) {
    const row = await prisma.source.findUnique({
      where: { slug },
      select: { id: true, _count: { select: { crawlRuns: true, rawPostings: true } } },
    });
    if (!row) continue;
    if (row._count.crawlRuns > 0 || row._count.rawPostings > 0) {
      await prisma.source.update({ where: { slug }, data: { isActive: false } });
      console.warn(`sources: ${slug} is retired but has data; deactivated, not deleted`);
    } else {
      await prisma.source.delete({ where: { slug } });
      console.log(`sources: retired ${slug} removed`);
    }
  }
}

async function seedSkills(prisma: PrismaClient): Promise<void> {
  const skills = loadSkills();
  let aliasCount = 0;
  let removedAliases = 0;

  for (const s of skills) {
    const skill = await prisma.skill.upsert({
      where: { name: s.name },
      create: { name: s.name, category: s.category },
      update: { category: s.category },
    });
    const patterns = s.aliases.map((a) => a.pattern);
    const removed = await prisma.skillAlias.deleteMany({
      where: { skillId: skill.id, pattern: { notIn: patterns } },
    });
    removedAliases += removed.count;
    for (const a of s.aliases) {
      const requirementsOnly = a.requirements_only ?? false;
      await prisma.skillAlias.upsert({
        where: { skillId_pattern: { skillId: skill.id, pattern: a.pattern } },
        create: { skillId: skill.id, pattern: a.pattern, requirementsOnly },
        update: { requirementsOnly },
      });
      aliasCount += 1;
    }
  }

  const names = new Set(skills.map((s) => s.name));
  const orphans = (await prisma.skill.findMany({ select: { name: true } }))
    .map((s) => s.name)
    .filter((n) => !names.has(n));

  console.log(
    `skills: ${skills.length} upserted, ${aliasCount} aliases, ${removedAliases} stale aliases removed`,
  );
  if (orphans.length > 0) {
    console.warn(`skills in DB but not in skills.json (left untouched): ${orphans.join(", ")}`);
  }
}

async function main(): Promise<void> {
  const connectionString = process.env.MIGRATE_DATABASE_URL;
  if (!connectionString) throw new Error("MIGRATE_DATABASE_URL is not set (see .env.example)");
  const prisma = new PrismaClient({ adapter: new PrismaNeon({ connectionString }) });
  try {
    await seedSources(prisma);
    await seedSkills(prisma);
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
