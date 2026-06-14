/** @type {import('tailwindcss').Config} */
// Cache invalidation timestamp: 1781215481384
module.exports = {
  content: [
    './src/templates/**/*.html',
    'src/templates/**/*.html',
    'src/templates/mubil/**/*.html',
    'C:/Users/imanol/projects/imanol/saas/maps/src/templates/**/*.html',
    './src/apps/**/templates/**/*.html',
    'src/apps/**/templates/**/*.html',
    './src/apps/**/*.py',
    'src/apps/**/*.py',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#6366f1',
        primary_hover: '#4f46e5',
        estrata: {
          teal: '#10B0A0',
          teal_light: '#5EE8E0',
          teal_dark: '#0A8278',
          navy: '#103040',
          navy_deep: '#0A1B26',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
};
