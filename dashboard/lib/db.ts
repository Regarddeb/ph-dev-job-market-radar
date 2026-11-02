import "server-only";

import { PrismaNeon } from "@prisma/adapter-neon";

import { PrismaClient } from "@/lib/generated/prisma/client";

// The dashboard only ever reads. On Vercel, DATABASE_URL is the read-only role.
// Locally, prefer the read-only URL so dev matches production.
function connectionString(): string {
  const url = process.env.JOBRADAR_READONLY_DATABASE_URL ?? process.env.DATABASE_URL;
  if (!url) {
    throw new Error("Set DATABASE_URL (read-only role) for the dashboard.");
  }
  return url;
}

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export function db(): PrismaClient {
  if (!globalForPrisma.prisma) {
    const adapter = new PrismaNeon({ connectionString: connectionString() });
    globalForPrisma.prisma = new PrismaClient({ adapter });
  }
  return globalForPrisma.prisma;
}
