import Link from "next/link";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/postings", label: "Postings" },
  { href: "/skills", label: "Skills" },
  { href: "/salaries", label: "Salaries" },
  { href: "/matches", label: "Matches" },
  { href: "/ops", label: "Ops" },
] as const;

export function Nav() {
  return (
    <nav className="flex flex-wrap gap-4 border-b px-6 py-3 text-sm">
      <span className="font-semibold">PH Dev Job Market Radar</span>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className="text-muted-foreground hover:text-foreground">
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
