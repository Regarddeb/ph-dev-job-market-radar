"use client";

import { Moon, Sun } from "lucide-react";

/** Both icons are rendered and CSS picks one, so the button needs no state to hydrate. */
export function ThemeToggle() {
  return (
    <button
      type="button"
      aria-label="Switch between light and dark theme"
      title="Switch theme"
      onClick={() => {
        const dark = document.documentElement.classList.toggle("dark");
        try {
          localStorage.setItem("theme", dark ? "dark" : "light");
        } catch {
          // Storage can be blocked; the choice then lasts for this page only.
        }
      }}
      className="text-muted-foreground hover:text-foreground hover:bg-muted focus-visible:ring-ring/50 inline-flex size-8 items-center justify-center rounded-lg outline-none focus-visible:ring-3"
    >
      <Sun className="hidden size-4 dark:block" aria-hidden />
      <Moon className="size-4 dark:hidden" aria-hidden />
    </button>
  );
}
