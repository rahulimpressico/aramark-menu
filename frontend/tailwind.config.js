/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  // Keep report blockquote colors in production (conditional classes can be purged)
  safelist: [
    "border-emerald-500/80",
    "bg-emerald-50/60",
    "border-amber-500/80",
    "bg-amber-50/50",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#e7212e",
        "primary-hover": "#c41d28",
        "footer-bg": "#022035",
      },
    },
  },
  plugins: [],
};
