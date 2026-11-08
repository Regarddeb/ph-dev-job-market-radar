import { describe, expect, it } from "vitest";

import { DEFAULT_JOB_TYPES, filterRoles, skillCounts } from "@/lib/ph-filter";

const rows = [
  { id: 1, jobType: "part_time", skills: ["Python"] },
  { id: 2, jobType: "contract", skills: ["Go", "Python"] },
  { id: 3, jobType: "full_time", skills: ["Go"] },
  { id: 4, jobType: "unspecified", skills: [] },
];

describe("filterRoles", () => {
  it("defaults to everything except full-time", () => {
    expect(filterRoles(rows, DEFAULT_JOB_TYPES, []).map((r) => r.id)).toEqual([1, 2, 4]);
  });

  it("matches any selected skill (OR)", () => {
    expect(filterRoles(rows, DEFAULT_JOB_TYPES, ["Go"]).map((r) => r.id)).toEqual([2]);
    const all = ["part_time", "contract", "full_time", "unspecified"];
    expect(filterRoles(rows, all, ["Go", "Python"]).map((r) => r.id)).toEqual([1, 2, 3]);
  });

  it("returns nothing when no job type is selected", () => {
    expect(filterRoles(rows, [], [])).toEqual([]);
  });
});

describe("skillCounts", () => {
  it("orders by frequency, then name", () => {
    expect(skillCounts(rows)).toEqual([
      { name: "Go", n: 2 },
      { name: "Python", n: 2 },
    ]);
  });
});
