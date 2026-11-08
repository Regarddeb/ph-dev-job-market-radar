import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { MY_JOB_TYPES, MY_SKILLS } from "@/config/my-skills";

const dictionary = JSON.parse(
  readFileSync(resolve(__dirname, "../prisma/data/skills.json"), "utf-8"),
) as { skills: { name: string }[] };
const known = new Set(dictionary.skills.map((s) => s.name));

describe("config/my-skills", () => {
  it("only names skills that exist in the dictionary (a typo would match nothing)", () => {
    expect(MY_SKILLS.filter((name) => !known.has(name))).toEqual([]);
  });

  it("has no duplicates", () => {
    expect(new Set(MY_SKILLS).size).toBe(MY_SKILLS.length);
  });

  it("only uses job_type enum values the schema defines", () => {
    const allowed = ["full_time", "part_time", "contract", "freelance", "unspecified"];
    expect(MY_JOB_TYPES.every((t) => allowed.includes(t))).toBe(true);
  });
});
