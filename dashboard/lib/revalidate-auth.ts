import { timingSafeEqual } from "node:crypto";

/** Constant-time check of a `Bearer <secret>` header against REVALIDATE_SECRET. */
export function isAuthorized(header: string | null, secret: string | undefined): boolean {
  if (!secret || !header?.startsWith("Bearer ")) return false;
  const given = Buffer.from(header.slice("Bearer ".length));
  const expected = Buffer.from(secret);
  return given.length === expected.length && timingSafeEqual(given, expected);
}
