import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f1c1a",
        moss: "#1f3d36",
        copper: "#c47a3a",
        sand: "#e8dfd2",
        mist: "#d7ebe4",
        signal: "#2a9d8f",
        danger: "#c23b22",
      },
      fontFamily: {
        display: ["var(--font-sora)", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      boxShadow: {
        panel: "0 24px 60px rgba(15, 28, 26, 0.12)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulsebar: {
          "0%, 100%": { transform: "scaleX(0.35)", opacity: "0.45" },
          "50%": { transform: "scaleX(1)", opacity: "1" },
        },
        scan: {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "100% 50%" },
        },
      },
      animation: {
        rise: "rise 0.55s ease-out both",
        pulsebar: "pulsebar 1.8s ease-in-out infinite",
        scan: "scan 8s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
