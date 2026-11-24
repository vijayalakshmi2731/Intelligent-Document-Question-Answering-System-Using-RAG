import type { Config } from "tailwindcss";
export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["var(--font-inter)", "system-ui", "sans-serif"] },
      colors: { brand: { 50: "#eef2ff", 100: "#e0e7ff", 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca" } },
      boxShadow: { soft: "0 1px 2px rgba(16,24,40,.04), 0 8px 24px -8px rgba(16,24,40,.08)" },
      keyframes: { rise: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } } },
      animation: { rise: "rise .25s ease-out both" },
    },
  },
  plugins: [],
} satisfies Config;
