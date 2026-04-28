import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        space: {
          950: '#05080F',
          900: '#0A0F1A',
          800: '#111827',
          700: '#1A2332',
          600: '#243044',
          500: '#2E4058',
        },
        brand: {
          DEFAULT: '#10B981',  // Emerald — color del logo de ErsLabs
          50: '#ECFDF5',
          100: '#D1FAE5',
          200: '#A7F3D0',
          300: '#6EE7B7',
          400: '#34D399',
          500: '#10B981',
          600: '#059669',
          700: '#047857',
        },
        swarm: {
          DEFAULT: '#00D4FF',  // Cyan — el swarm de Sentinel V2
          400: '#00D4FF',
          300: '#4DE8FF',
          200: '#80F0FF',
          100: '#B0F8FF',
          500: '#00A8CC',
          600: '#007A99',
          700: '#004C66',
          800: '#003344',
          900: '#001A22',
        },
        human: {
          DEFAULT: '#FF6B35',  // Coral — puntos de control humanos
          400: '#FF6B35',
          300: '#FF8F66',
          200: '#FFB399',
          500: '#E55A26',
          600: '#CC4918',
        },
        terminal: {
          green: '#10FF88',
          amber: '#FFB800',
          red: '#FF4757',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-up': 'slide-up 0.6s ease-out',
        'fade-in': 'fade-in 0.8s ease-out',
        'scan-line': 'scan-line 3s linear infinite',
        'pulse-swarm': 'pulse-swarm 2s ease-in-out infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        glow: {
          '0%': { opacity: '0.4', filter: 'blur(8px)' },
          '100%': { opacity: '1', filter: 'blur(12px)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'pulse-swarm': {
          '0%, 100%': { opacity: '0.6', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.05)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
      backgroundImage: {
        'grid-space': 'linear-gradient(rgba(16, 185, 129, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(16, 185, 129, 0.03) 1px, transparent 1px)',
        'gradient-brand': 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
        'gradient-swarm': 'linear-gradient(135deg, #00D4FF 0%, #007A99 100%)',
        'gradient-human': 'linear-gradient(135deg, #FF6B35 0%, #CC4918 100%)',
      },
      boxShadow: {
        'brand-glow': '0 0 20px rgba(16, 185, 129, 0.3), 0 0 40px rgba(16, 185, 129, 0.1)',
        'swarm-glow': '0 0 20px rgba(0, 212, 255, 0.3), 0 0 40px rgba(0, 212, 255, 0.1)',
        'human-glow': '0 0 20px rgba(255, 107, 53, 0.3), 0 0 40px rgba(255, 107, 53, 0.1)',
        'terminal-glow': '0 0 10px rgba(16, 255, 136, 0.2)',
      },
    },
  },
  plugins: [],
}
export default config