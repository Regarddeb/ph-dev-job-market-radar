// Seeds reference data: sources, skills, skill_aliases.
// Must be idempotent (upserts only). Filled in during build step 2.
// Run with: pnpm prisma db seed

async function main(): Promise<void> {
  console.log("seed: nothing to seed yet (schema arrives in build step 2)");
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
