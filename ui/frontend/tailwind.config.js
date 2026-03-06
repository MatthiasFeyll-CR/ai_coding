/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Background colors
        'bg-primary': '#0a0e1a',
        'bg-secondary': '#111827',
        'bg-tertiary': '#1f2937',
        'bg-hover': '#374151',

        // Accent colors
        'accent-cyan': '#06b6d4',
        'accent-purple': '#a855f7',
        'accent-blue': '#3b82f6',

        // Status colors
        'status-success': '#10b981',
        'status-warning': '#f59e0b',
        'status-error': '#ef4444',
        'status-idle': '#6b7280',

        // Text colors
        'text-primary': '#f9fafb',
        'text-secondary': '#9ca3af',
        'text-muted': '#6b7280',

        // Border colors
        'border-subtle': '#1f2937',
        'border-emphasis': '#374151',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(6, 182, 212, 0.3)',
        'glow-error': '0 0 20px rgba(239, 68, 68, 0.3)',
        'glow-purple': '0 0 20px rgba(168, 85, 247, 0.3)',
      },
    },
  },
  plugins: [],
}
