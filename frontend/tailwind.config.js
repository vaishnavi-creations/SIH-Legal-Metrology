/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#05131f',
          900: '#071A2B', // Deep Navy
          800: '#0B2235', // Dark Navy
          700: '#12334e',
          600: '#1a4568',
        },
        packsure: {
          deep: '#071A2B',
          dark: '#0B2235',
          emerald: '#18B889',
          teal: '#20C997',
          mint: '#F0FDF9',
          warm: '#F8FAF9',
        },
        primary: {
          50: '#f0fdf9',
          100: '#ccfbf1',
          400: '#20c997',
          500: '#18b889',
          600: '#109b72',
          700: '#0c7a59',
          900: '#064e3b',
        }
      }
    },
  },
  plugins: [],
}
