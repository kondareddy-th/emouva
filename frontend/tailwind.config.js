/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Background surfaces (banker's-green "Greenroom" system) ──
        base: '#0C110E',
        surface: {
          1: '#0F1511',
          2: '#131B16',
          3: '#151E18',
          4: '#1D2721',
        },

        // ── Text (bright, readability-first scale) ──
        'text-primary': '#F7FAF6',
        'text-secondary': '#C4CEC1',   // was #A69E8C (~4.9:1 → ~10:1)
        'text-tertiary': '#93A08F',    // was #6E675A (~3.3:1 → ~6.5:1)

        // ── Semantic data colors ──
        gain: '#7FE3A9',               // phosphor mint
        loss: '#F2937F',
        accent: {
          DEFAULT: '#CFAE62',
          hover: '#DBBC72',
        },
        warning: '#DFB65A',
        info: '#85BFC9',
      },
      borderColor: {
        DEFAULT: 'rgba(180, 220, 190, 0.11)',
        strong: 'rgba(180, 220, 190, 0.22)',
        subtle: 'rgba(180, 220, 190, 0.07)',
      },
      fontFamily: {
        sans: ['"Instrument Sans"', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'JetBrains Mono', 'SF Mono', 'monospace'],
        serif: ['"EB Garamond"', 'Georgia', 'serif'],
      },
      fontSize: {
        display: ['32px', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '600' }],
        title: ['20px', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        heading: ['16px', { lineHeight: '1.4', letterSpacing: '-0.006em', fontWeight: '500' }],
        body: ['14px', { lineHeight: '1.5', letterSpacing: '0', fontWeight: '400' }],
        label: ['13px', { lineHeight: '1.4', letterSpacing: '0.01em', fontWeight: '500' }],
        caption: ['12px', { lineHeight: '1.4', letterSpacing: '0.02em', fontWeight: '400' }],
      },
      borderRadius: {
        sm: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        'glow-gain': '0 0 20px rgba(127, 227, 169, 0.15)',
        'glow-loss': '0 0 20px rgba(242, 147, 127, 0.15)',
        'glow-accent': '0 0 20px rgba(207, 174, 98, 0.15)',
        'card': '0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2)',
        'card-hover': '0 4px 12px rgba(0, 0, 0, 0.4)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.19, 1, 0.22, 1)',
      },
    },
  },
  plugins: [],
}
