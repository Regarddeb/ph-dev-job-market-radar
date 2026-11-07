import { describe, expect, it } from "vitest";

import { EMPTY, formatManilaDate, postedLabel, textOrEmpty } from "@/lib/format-posting";

describe("formatManilaDate", () => {
  it("uses the Manila calendar day, not UTC", () => {
    // 2026-11-06 17:07 UTC is 2026-11-07 01:07 in Manila (UTC+8).
    expect(formatManilaDate(new Date("2026-11-06T17:07:00Z"))).toBe("Nov 7, 2026");
  });
});

describe("postedLabel", () => {
  const firstSeen = new Date("2026-11-06T17:07:00Z");

  it("shows posted_at when present", () => {
    expect(postedLabel(new Date("2026-11-01T04:00:00Z"), firstSeen)).toEqual({
      text: "Nov 1, 2026",
      isFallback: false,
    });
  });

  it("falls back to first_seen_at and labels it", () => {
    expect(postedLabel(null, firstSeen)).toEqual({
      text: "first seen Nov 7, 2026",
      isFallback: true,
    });
  });
});

describe("textOrEmpty", () => {
  it.each([null, undefined, "", "   "])("shows a dash for %j", (value) => {
    expect(textOrEmpty(value)).toBe(EMPTY);
  });

  it("trims real values", () => {
    expect(textOrEmpty("  $90k - $130k ")).toBe("$90k - $130k");
  });
});
