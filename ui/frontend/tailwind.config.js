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
        'accent-green': '#10b981',
        'accent-violet': '#7c3aed',

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
        'glow-green': '0 0 20px rgba(16, 185, 129, 0.3)',
        'glow-blue': '0 0 20px rgba(59, 130, 246, 0.3)',
      },
      backgroundImage: {
        'gradient-triad': 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(6, 182, 212, 0.08) 50%, rgba(124, 58, 237, 0.08) 100%)',
        'gradient-triad-strong': 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 182, 212, 0.12) 50%, rgba(124, 58, 237, 0.15) 100%)',
        'gradient-header': 'linear-gradient(90deg, rgba(16, 185, 129, 0.12) 0%, rgba(6, 182, 212, 0.10) 60%, rgba(124, 58, 237, 0.08) 100%)',
      },
    },
  },
  plugins: [],
}
