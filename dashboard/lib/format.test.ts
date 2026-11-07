import { describe, expect, it } from "vitest";

import { change, enumLabel, percent, phpCompact, phpFull } from "@/lib/format";
import { toWeeklySeries } from "@/lib/queries/skills-series";

describe("phpCompact / phpFull", () => {
  it.each([
    [950, "₱950"],
    [52_514, "₱53k"],
    [682_679, "₱683k"],
    [1_000_000, "₱1M"],
    [1_312_845, "₱1.3M"],
  ])("%d -> %s", (value, text) => {
    expect(phpCompact(value)).toBe(text);
  });

  it("formats full amounts with separators", () => {
    expect(phpFull(682_679.25)).toBe("₱682,679");
  });
});

describe("percent", () => {
  it("rounds to a whole percent", () => expect(percent(7, 39)).toBe("18%"));
  it("shows a dash for an empty total", () => expect(percent(0, 0)).toBe("—"));
});

describe("change", () => {
  it.each([
    [12, 10, "+20%"],
    [5, 10, "-50%"],
    [10, 10, "0%"],
    [3, 0, "new"],
    [0, 0, "—"],
  ])("%d vs %d -> %s", (current, previous, text) => {
    expect(change(current, previous)).toBe(text);
  });
});

describe("enumLabel", () => {
  it("humanizes enum values", () => {
    expect(enumLabel("full_time")).toBe("Full time");
    expect(enumLabel("unspecified")).toBe("Unspecified");
  });
});

describe("toWeeklySeries", () => {
  it("fills missing skills with 0 and sorts weeks", () => {
    const rows = [
      { week: "2026-11-02", name: "Python", n: 4 },
      { week: "2026-10-26", name: "Go", n: 1 },
    ];
    expect(toWeeklySeries(rows, ["Python", "Go"])).toEqual([
      { week: "2026-10-26", Python: 0, Go: 1 },
      { week: "2026-11-02", Python: 4, Go: 0 },
    ]);
  });
});
