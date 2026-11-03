/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Vuexy Signature Palette (Tezlify Design System)
        vuexy: {
          primary: "#7367F0",
          "primary-hover": "#685DD8",
          "primary-light": "#EAE8FD",
          success: "#28C76F",
          "success-light": "#DFF7E9",
          danger: "#EA5455",
          "danger-light": "#FCEAEA",
          warning: "#FF9F43",
          "warning-light": "#FFF3E8",
          info: "#00CFE8",
          "info-light": "#E0F9FC",
          // Dark theme surfaces
          "dark-bg": "#25293C",
          "dark-card": "#2F3349",
          "dark-card-elevated": "#363B53",
          "dark-border": "rgba(255, 255, 255, 0.08)",
          "dark-text": "#DBD7EC",
          "dark-muted": "#7E7F96",
          // Light theme surfaces
          "light-bg": "#F8F7FA",
          "light-card": "#FFFFFF",
          "light-border": "rgba(47, 43, 61, 0.12)",
          "light-text": "#4B465C",
          "light-heading": "#2F2B3D",
          "light-muted": "#82868B",
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'vuexy-card': '0 2px 9px 0 rgba(47, 43, 61, 0.08)',
        'vuexy-card-dark': '0 2px 14px 0 rgba(15, 20, 34, 0.4)',
        'vuexy-primary': '0 2px 6px 0 rgba(115, 103, 240, 0.48)',
        'vuexy-success': '0 2px 6px 0 rgba(40, 199, 111, 0.48)',
        'glow-primary': '0 0 60px -12px rgba(115, 103, 240, 0.4)',
      },
      borderRadius: {
        'vuexy': '0.625rem', // 10px Vuexy card border radius
      },
    },
  },
  plugins: [],
}
