/**
 * Runs in <head> before first paint (see app/layout.tsx): the saved choice wins, otherwise
 * the system preference. Keeps the prerendered shell free of a flash of the wrong theme.
 * components/theme-toggle.tsx writes the same "theme" key.
 */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("theme");if(t==="dark"||(!t&&matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")}catch(e){}`;
