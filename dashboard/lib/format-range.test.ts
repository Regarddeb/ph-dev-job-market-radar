import { describe, expect, it } from "vitest";

import { phpRange } from "@/lib/format";

describe("phpRange", () => {
  it("formats a range", () => {
    expect(phpRange(189526, 252701)).toBe("₱190k–₱253k");
  });

  it("shows one figure when both ends match or one is missing", () => {
    expect(phpRange(702977, 702977)).toBe("₱703k");
    expect(phpRange(null, 50000)).toBe("₱50k");
  });

  it("is null without a PHP amount (never a guess)", () => {
    expect(phpRange(null, null)).toBeNull();
  });
});
