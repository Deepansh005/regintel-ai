/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-outfit)", "Outfit", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          900: "#0F0B1A", // Super deep purple-black
          800: "#1A1430",
          700: "#342861",
          600: "#4D3893",
          500: "#7C3AED", // Vivid Violet
          400: "#A78BFA",
          300: "#C4B5FD",
          100: "#EDE9FE",
          50: "#F5F3FF",
        },
        surface: {
          50: "#ffffff",
          100: "#f8fafc",
          200: "#f1f5f9",
          900: "#020617",
        }
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(124, 58, 237, 0.05)',
        'glass-hover': '0 12px 48px 0 rgba(124, 58, 237, 0.15), 0 0 0 1px rgba(124, 58, 237, 0.1)',
        'glow': '0 0 30px rgba(124, 58, 237, 0.4)',
        'float': '0 20px 40px -10px rgba(0,0,0,0.1)',
      },
      animation: {
        'gradient-x': 'gradient-x 10s ease infinite',
        'gradient-y': 'gradient-y 10s ease infinite',
        'gradient-xy': 'gradient-xy 10s ease infinite',
        'blob': 'blob 7s infinite',
        'aurora': 'aurora 20s linear infinite',
        'scrolling-logos': 'scrolling-logos 40s linear infinite',
      },
      keyframes: {
        'gradient-y': {
          '0%, 100%': {
              'background-size': '400% 400%',
              'background-position': 'center top'
          },
          '50%': {
              'background-size': '200% 200%',
              'background-position': 'center center'
          }
        },
        'gradient-x': {
          '0%, 100%': {
              'background-size': '200% 200%',
              'background-position': 'left center'
          },
          '50%': {
              'background-size': '200% 200%',
              'background-position': 'right center'
          }
        },
        'gradient-xy': {
          '0%, 100%': {
              'background-size': '400% 400%',
              'background-position': 'left center'
          },
          '50%': {
              'background-size': '200% 200%',
              'background-position': 'right center'
          }
        },
        'blob': {
          '0%': {
            transform: 'translate(0px, 0px) scale(1)',
          },
          '33%': {
            transform: 'translate(30px, -50px) scale(1.1)',
          },
          '66%': {
            transform: 'translate(-20px, 20px) scale(0.9)',
          },
          '100%': {
            transform: 'translate(0px, 0px) scale(1)',
          },
        },
        'aurora': {
          '0%': { 'background-position': '50% 50%, 50% 50%' },
          '100%': { 'background-position': '350% 50%, 350% 50%' },
        },
        'scrolling-logos': {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        }
      }
    },
  },
  plugins: [],
};