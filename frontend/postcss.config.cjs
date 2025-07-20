// frontend/tailwind.config.js

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",               // ✅ Needed for Vite (not CRA)
    "./src/**/*.{js,jsx,ts,tsx}", // ✅ Covers your React components
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
