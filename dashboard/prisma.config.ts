// Prisma CLI config (migrate, generate, seed).
// Local dev reads the single repo-root .env; CI passes env vars directly.
import { config } from "dotenv";
import { defineConfig } from "prisma/config";

config({ path: "../.env", quiet: true });

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
    seed: "tsx prisma/seed.ts",
  },
  datasource: {
    // Migrations need the owner role on Neon's DIRECT (non-pooled) endpoint.
    // Left undefined for `prisma generate`, which needs no database.
    url: process.env.MIGRATE_DATABASE_URL,
  },
});
