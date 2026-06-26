"use client";

import { useEffect, useState } from "react";

// Persisted in localStorage (not a cookie — no SSR personalization needed,
// this is a single-operator-team dashboard, not a multi-visitor site) and
// applied via the `dark` class on <html> (tailwind.config.ts: darkMode:
// "class"). The inline script in app/layout.tsx's <head> applies the
// stored preference before React hydrates, so there's no flash-of-wrong-
// theme on reload — this component only needs to handle the toggle click.
export function ThemeToggle() {
  const [isDark, setIsDark] = useState<boolean | null>(null);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("af-theme", next ? "dark" : "light");
    setIsDark(next);
  }

  // Avoid rendering a guess before we know the real state (hydration-safe).
  if (isDark === null) return <button aria-hidden className="w-16 h-8" />;

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="text-sm px-3 py-1.5 rounded-md border border-black/10 dark:border-white/10
                 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
    >
      {isDark ? "Light" : "Dark"}
    </button>
  );
}
