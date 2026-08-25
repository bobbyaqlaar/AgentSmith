import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  // No `theme.extend.colors`. Three semantic colours were declared here —
  // success/warning/danger, each with a light and dark value — under a comment
  // saying they were "used consistently across status badges, see
  // components/ui/Badge.tsx". Badge.tsx uses Tailwind's own palette classes
  // (`bg-green-100 dark:bg-green-900/40` …) and never referenced them, so
  // nothing in the portal ever emitted `text-success-light`. A declaration
  // nothing reads is worse than an absent one: the next person to add a status
  // colour reads that comment and believes there is a token to reuse.
  //
  // The one place the tones ARE defined is Badge.tsx's TONE_CLASSES map, which
  // is where a fourth tone should be added.
  theme: {},
  plugins: [],
};

export default config;
