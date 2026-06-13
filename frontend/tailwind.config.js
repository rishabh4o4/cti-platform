/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "var(--border)",
        background: "var(--background)",
        surface: "var(--surface)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "#ffffff",
        },
        critical: "var(--critical)",
        high: "var(--high)",
        medium: "var(--medium)",
        low: "var(--low)",
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
        }
      },
    },
  },
  plugins: [],
}
