/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: "#0a0e1a",
          panel: "#101628",
          inset: "#0c1222",
          elevated: "#151d32",
        },
        ink: {
          DEFAULT: "#eaf2fb",
          secondary: "#9aabc4",
          muted: "#6f819c",
          faint: "#4d5d78",
        },
        line: {
          DEFAULT: "#1f2a44",
          soft: "#172038",
          strong: "#2a3860",
        },
        accent: {
          DEFAULT: "#22d3ee",
        },
        decision: {
          allow: "#34d399",
          review: "#fbbf24",
          restrict: "#fb923c",
          block: "#f87171",
        },
        risk: {
          low: "#34d399",
          medium: "#fbbf24",
          high: "#fb923c",
          critical: "#f87171",
        },
        trust: {
          trusted: "#34d399",
          restricted: "#fbbf24",
          untrusted: "#f87171",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        panel: "0 18px 40px rgba(2, 6, 23, 0.45)",
        glow: "0 0 24px rgba(34, 211, 238, 0.18)",
      },
      keyframes: {
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        "pulse-soft": "pulse-soft 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
