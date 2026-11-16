"use client";

import { Radar } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/postings", label: "Postings" },
  { href: "/ph-friendly", label: "PH-friendly" },
  { href: "/skills", label: "Skills" },
  { href: "/salaries", label: "Salaries" },
  { href: "/ops", label: "Status" },
  { href: "/docs", label: "How it works" },
] as const;

/** Sticky site header: brand, section links (current one marked) and the theme toggle. */
export function Nav() {
  const pathname = usePathname();
  const isCurrent = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <header className="bg-background/85 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 py-3 font-semibold tracking-tight">
          <Radar className="text-chart-1 size-5" aria-hidden />
          <span>
            PH Dev Job <span className="max-sm:hidden">Market </span>Radar
          </span>
        </Link>
        <div className="ml-auto md:order-last">
          <ThemeToggle />
        </div>
        {/* Below md the links take their own row and scroll sideways rather than wrap. */}
        <nav
          aria-label="Sections"
          className="-mx-4 flex w-screen gap-1 overflow-x-auto px-4 text-sm max-md:pb-2 sm:-mx-6 sm:px-6 md:mx-0 md:w-auto md:px-0"
        >
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={isCurrent(l.href) ? "page" : undefined}
              className="text-muted-foreground hover:text-foreground hover:bg-muted aria-[current=page]:text-foreground aria-[current=page]:bg-muted rounded-md px-2.5 py-1.5 whitespace-nowrap aria-[current=page]:font-medium"
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
