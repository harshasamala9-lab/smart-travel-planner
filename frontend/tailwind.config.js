/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Brand — deep travel navy
        navy: {
          50: '#f2f6fc',
          100: '#e2ecf9',
          200: '#c2d8f2',
          300: '#91bbe8',
          400: '#5b97db',
          500: '#3778cd',
          600: '#255eb2',
          700: '#1e4b90',
          800: '#1c4176',
          900: '#0f2c56',
          950: '#0a1c39',
        },
        // Primary — ocean teal
        ocean: {
          50: '#effefa',
          100: '#c7fff0',
          200: '#90fbdf',
          300: '#53f0cb',
          400: '#22deb5',
          500: '#06c19b',
          600: '#009b7f',
          700: '#027c68',
          800: '#056254',
          900: '#065145',
          950: '#002e26',
        },
        // Accent — warm sand / gold
        sand: {
          50: '#fdf9ec',
          100: '#f9efcb',
          200: '#f2dc96',
          300: '#ecc45f',
          400: '#e7ab35',
          500: '#db8b20',
          600: '#c26c19',
          700: '#a14f19',
          800: '#833f1b',
          900: '#6d351a',
          950: '#3e1a0b',
        },
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 1px 2px rgba(15,44,86,0.06), 0 8px 24px -8px rgba(15,44,86,0.12)',
        lift: '0 2px 4px rgba(15,44,86,0.08), 0 16px 40px -12px rgba(15,44,86,0.22)',
        glow: '0 0 0 1px rgba(6,193,155,0.15), 0 8px 32px -8px rgba(6,193,155,0.35)',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      keyframes: {
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'gentle-float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        'spin-slow': {
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s infinite',
        'fade-up': 'fade-up 0.4s ease-out both',
        'slide-in': 'slide-in 0.3s ease-out both',
        'gentle-float': 'gentle-float 5s ease-in-out infinite',
        'spin-slow': 'spin-slow 2.4s linear infinite',
      },
    },
  },
  plugins: [],
};
