import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Base backgrounds - utilizing CSS variables
        background: 'var(--tw-bg-background)', 
        'page-bg': 'var(--tw-bg-page-bg)',
        panel: 'var(--tw-bg-panel)',
        card: 'var(--tw-bg-card)',
        input: 'var(--tw-bg-input)',
        
        // Borders
        border: 'var(--tw-border-border)',
        'border-subtle': 'var(--tw-border-border-subtle)',
        
        // Text
        'text-primary': 'var(--tw-text-text-primary)',
        'text-secondary': 'var(--tw-text-text-secondary)',
        'text-muted': 'var(--tw-text-text-muted)',
        
        // Accents
        primary: 'var(--tw-primary)',
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      fontSize: {
        // Sidebar font sizes (unchanged - compact)
        'xs': ['10px', { lineHeight: '1.4' }],
        'sm': ['11px', { lineHeight: '1.4' }],
        // Global font sizes with improved line-height for readability
        'base': ['13px', { lineHeight: '1.6' }],      // was 12px
        'md': ['14px', { lineHeight: '1.6' }],        // was 13px
        'lg': ['15px', { lineHeight: '1.6' }],        // was 14px
        'xl': ['16px', { lineHeight: '1.6' }],        // was 15px
        '2xl': ['19px', { lineHeight: '1.5' }],       // was 18px
        '3xl': ['21px', { lineHeight: '1.5' }],       // was 20px
      },
      spacing: {
        'xs': '4px',
        'sm': '8px',
        'md': '12px',
        'lg': '16px',
      },
      borderRadius: {
        'sm': '4px',
        'DEFAULT': '8px',
        'lg': '10px',
        'xl': '12px',
      },
      transitionDuration: {
        'fast': '100ms',
        'normal': '150ms',
      },
    },
  },
  plugins: [],
}
export default config
