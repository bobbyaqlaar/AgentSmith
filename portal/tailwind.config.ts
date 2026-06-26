import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semantic status colors used consistently across status badges
        // (tenant health, MAJOR/CRITICAL issues, DLQ entry status) — see
        // components/ui/Badge.tsx.
        success: { light: "#15803d", dark: "#4ade80" },
        warning: { light: "#b45309", dark: "#fbbf24" },
        danger: { light: "#b91c1c", dark: "#f87171" },
      },
    },
  },
  plugins: [],
};

export default config;
