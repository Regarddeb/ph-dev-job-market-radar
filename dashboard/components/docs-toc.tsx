"use client";

import { useEffect, useRef, useState } from "react";

export type TocItem = { id: string; label: string };

/** A section counts as current once its top passes this many pixels below the viewport top
 *  (clear of the sticky header and, on small screens, this bar). */
const ACTIVE_LINE_PX = 170;

/**
 * "On this page" navigation that marks the section being read.
 * - lg and up: a sticky list in the right-hand column.
 * - smaller screens: a sticky row under the site header that scrolls sideways and keeps the
 *   current section's link in view.
 */
export function DocsToc({ items }: { items: readonly TocItem[] }) {
  const [active, setActive] = useState(items[0]?.id ?? "");
  const listRef = useRef<HTMLUListElement>(null);
  const navRef = useRef<HTMLElement>(null);

  // The bar sits right under the site header, whose height changes with the screen width
  // (its links take a second row on phones), so measure it instead of hard-coding it.
  useEffect(() => {
    const header = document.querySelector<HTMLElement>("body > header");
    const nav = navRef.current;
    if (!header || !nav) return;
    const apply = () => nav.style.setProperty("--docs-toc-top", `${header.offsetHeight - 1}px`);
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      let current = items[0]?.id ?? "";
      for (const item of items) {
        const el = document.getElementById(item.id);
        if (el && el.getBoundingClientRect().top <= ACTIVE_LINE_PX) current = item.id;
      }
      // At the very bottom the last section may be too short to reach the line.
      const atBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      if (atBottom && items.length > 0) current = items[items.length - 1].id;
      setActive(current);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [items]);

  // Small screens: keep the current link visible in the sideways-scrolling row. Only the
  // row itself is scrolled, never the page.
  useEffect(() => {
    const list = listRef.current;
    const link = list?.querySelector<HTMLElement>('[aria-current="location"]');
    if (!list || !link || list.scrollWidth <= list.clientWidth) return;
    const target = link.offsetLeft - (list.clientWidth - link.offsetWidth) / 2;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    list.scrollTo({ left: Math.max(0, target), behavior: reduce ? "auto" : "smooth" });
  }, [active]);

  return (
    <nav
      ref={navRef}
      aria-label="On this page"
      className="bg-background/90 sticky top-[var(--docs-toc-top)] z-30 -mx-4 border-b backdrop-blur [--docs-toc-top:6.5rem] sm:-mx-6 md:[--docs-toc-top:3.05rem] lg:top-20 lg:order-last lg:mx-0 lg:self-start lg:border-b-0 lg:bg-transparent lg:backdrop-blur-none"
    >
      <p className="text-muted-foreground mb-2 hidden text-xs font-medium tracking-wide uppercase lg:block">
        On this page
      </p>
      <ul
        ref={listRef}
        className="relative flex [scrollbar-width:none] gap-1 overflow-x-auto px-4 py-2 text-sm sm:px-6 lg:flex-col lg:gap-0 lg:overflow-visible lg:border-l lg:p-0"
      >
        {items.map((item) => (
          <li key={item.id} className="shrink-0">
            <a
              href={`#${item.id}`}
              aria-current={item.id === active ? "location" : undefined}
              className="text-muted-foreground hover:text-foreground aria-[current=location]:text-foreground aria-[current=location]:bg-muted lg:aria-[current=location]:border-chart-1 block rounded-md px-2.5 py-1 whitespace-nowrap aria-[current=location]:font-medium lg:-ml-px lg:rounded-none lg:border-l-2 lg:border-transparent lg:py-1.5 lg:pl-3 lg:aria-[current=location]:bg-transparent"
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
