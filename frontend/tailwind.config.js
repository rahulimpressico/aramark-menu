/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
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
