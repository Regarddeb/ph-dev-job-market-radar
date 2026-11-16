import type { Metadata } from "next";

import { PhRoles } from "@/components/ph-roles";
import { getPhFriendlyRoles } from "@/lib/queries/ph-friendly";

export const metadata: Metadata = { title: "PH-friendly roles" };

export default async function PhFriendlyPage() {
  const roles = await getPhFriendlyRoles();

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">PH-friendly roles</h1>
        <p className="text-muted-foreground text-sm">
          Active remote developer postings that say they accept Philippines-based applicants: the
          Philippines named, or worldwide, anywhere, Asia or APAC hiring. Postings that don&apos;t
          say are left out. By default the list shows part-time, freelance, contract and
          job-type-not-stated roles; switch on Full-time to see everything.
        </p>
      </header>
      {roles.length === 0 ? (
        <p className="text-muted-foreground">No PH-friendly postings right now.</p>
      ) : (
        <PhRoles roles={roles} />
      )}
    </section>
  );
}
