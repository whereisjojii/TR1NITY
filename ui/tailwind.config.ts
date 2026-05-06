import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "Menlo",
          "ui-monospace",
          "monospace",
        ],
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
      colors: {
        // The Cockpit uses a dark "SOC" palette — high contrast for
        // long sessions and severity-aware accent colors.
        background: "hsl(222 18% 8%)",
        foreground: "hsl(210 20% 96%)",
        muted: "hsl(220 14% 18%)",
        "muted-foreground": "hsl(215 16% 65%)",
        border: "hsl(220 14% 22%)",
        accent: "hsl(195 90% 55%)",
        "accent-foreground": "hsl(220 30% 5%)",
        success: "hsl(150 70% 45%)",
        warning: "hsl(40 95% 55%)",
        danger: "hsl(0 80% 60%)",
        critical: "hsl(330 85% 65%)",
        "card-bg": "hsl(220 14% 12%)",
      },
      keyframes: {
        flash: {
          "0%": { backgroundColor: "hsl(195 90% 55% / 0.20)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        flash: "flash 1.2s ease-out 1",
      },
    },
  },
  plugins: [],
};

export default config;
