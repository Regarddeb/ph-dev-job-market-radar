import { describe, expect, it } from "vitest";

import { isAuthorized } from "./revalidate-auth";

describe("isAuthorized", () => {
  it("accepts the exact bearer secret", () => {
    expect(isAuthorized("Bearer s3cret", "s3cret")).toBe(true);
  });

  it("rejects a wrong, missing or malformed header", () => {
    expect(isAuthorized("Bearer nope", "s3cret")).toBe(false);
    expect(isAuthorized(null, "s3cret")).toBe(false);
    expect(isAuthorized("s3cret", "s3cret")).toBe(false);
  });

  it("rejects everything when no secret is configured", () => {
    expect(isAuthorized("Bearer ", undefined)).toBe(false);
    expect(isAuthorized("Bearer ", "")).toBe(false);
  });
});
