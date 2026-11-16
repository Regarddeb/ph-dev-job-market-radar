import { describe, expect, it } from "vitest";

import {
  DEFAULT_FILTERS,
  activeFilterCount,
  pageCount,
  pageItems,
  parseFilters,
  postingsHref,
  toQueryString,
} from "@/lib/postings-params";

describe("parseFilters", () => {
  it("returns the defaults for an empty URL", () => {
    expect(parseFilters({})).toEqual(DEFAULT_FILTERS);
  });

  it("reads comma lists and repeated params, sorted and de-duplicated", () => {
    const f = parseFilters({ type: "part_time,contract,part_time", skill: ["Python", "Go"] });
    expect(f.types).toEqual(["contract", "part_time"]);
    expect(f.skills).toEqual(["Go", "Python"]);
  });

  it("drops unknown values instead of failing", () => {
    const f = parseFilters({
      type: "full_time,ceo",
      setup: "moon",
      sort: "random",
      page: "-3",
      source: "Remote OK; drop table",
      ph: "yes",
    });
    expect(f).toEqual({ ...DEFAULT_FILTERS, types: ["full_time"] });
  });

  it("trims and caps the search text", () => {
    expect(parseFilters({ q: "  rust  " }).q).toBe("rust");
    expect(parseFilters({ q: "x".repeat(500) }).q).toHaveLength(80);
  });
});

describe("toQueryString / postingsHref", () => {
  it("leaves defaults out", () => {
    expect(postingsHref(DEFAULT_FILTERS)).toBe("/postings");
  });

  it("round-trips through parseFilters", () => {
    const f = {
      ...DEFAULT_FILTERS,
      q: "data engineer",
      types: ["contract" as const],
      setups: ["remote" as const],
      skills: ["C#", "Go"],
      source: "hn_hiring",
      ph: true,
      salary: true,
      sort: "salary" as const,
      page: 3,
    };
    const params = Object.fromEntries(new URLSearchParams(toQueryString(f)));
    expect(parseFilters(params)).toEqual(f);
  });
});

describe("activeFilterCount", () => {
  it("ignores sort and page", () => {
    expect(activeFilterCount({ ...DEFAULT_FILTERS, sort: "salary", page: 4 })).toBe(0);
    expect(
      activeFilterCount({ ...DEFAULT_FILTERS, q: "go", skills: ["Go", "Rust"], ph: true }),
    ).toBe(4);
  });
});

describe("pagination", () => {
  it("counts pages, never fewer than one", () => {
    expect(pageCount(0)).toBe(1);
    expect(pageCount(25)).toBe(1);
    expect(pageCount(26)).toBe(2);
  });

  it("shows every page when there are few", () => {
    expect(pageItems(1, 1)).toEqual([1]);
    expect(pageItems(2, 4)).toEqual([1, 2, 3, 4]);
  });

  it("collapses long ranges around the current page", () => {
    expect(pageItems(6, 12)).toEqual([1, "gap", 5, 6, 7, "gap", 12]);
    expect(pageItems(1, 12)).toEqual([1, 2, "gap", 12]);
    expect(pageItems(12, 12)).toEqual([1, "gap", 11, 12]);
  });

  it("fills a one-page hole rather than showing a gap", () => {
    expect(pageItems(3, 12)).toEqual([1, 2, 3, 4, "gap", 12]);
    expect(pageItems(4, 12)).toEqual([1, 2, 3, 4, 5, "gap", 12]);
  });
});
