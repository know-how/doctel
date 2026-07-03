/**
 * Modern Futuristic Theme System
 * Comprehensive design tokens for a stunning, contemporary UI
 */

export const theme = {
  // ============= COLORS =============
  colors: {
    // Primary: Deep navy to vibrant blue gradient
    primary: {
      "50": "#F0F4FF",
      "100": "#E6ECFF",
      "200": "#C7DAFF",
      "300": "#A8C8FF",
      "400": "#7FA8FF",
      "500": "#5B88FF",
      "600": "#4A6FE8",
      "700": "#3C5AD1",
      "800": "#2E45B4",
      "900": "#1A2A7A",
      "950": "#0F1640",
    },

    // Secondary: Vibrant cyan to electric blue
    secondary: {
      "50": "#F0FDFF",
      "100": "#E1FAFF",
      "200": "#B3F5FF",
      "300": "#85F1FF",
      "400": "#57ECFF",
      "500": "#1FE7FF",
      "600": "#00D9E9",
      "700": "#00B8D4",
      "800": "#0097B2",
      "900": "#007A94",
      "950": "#003F52",
    },

    // Accent: Vibrant orange to red
    accent: {
      "50": "#FFF5F0",
      "100": "#FFEBDC",
      "200": "#FFD1B8",
      "300": "#FFB795",
      "400": "#FF9D72",
      "500": "#FF8349",
      "600": "#F36F21",
      "700": "#D1520F",
      "800": "#AE3F0B",
      "900": "#8B2C08",
      "950": "#4A1605",
    },

    // Success: Modern green
    success: {
      "50": "#F0FDF4",
      "100": "#DCFCE7",
      "200": "#BBFBDB",
      "300": "#86EFAC",
      "400": "#4ADE80",
      "500": "#22C55E",
      "600": "#16A34A",
      "700": "#15803D",
      "800": "#166534",
      "900": "#145231",
    },

    // Warning: Warm amber
    warning: {
      "50": "#FFFBEB",
      "100": "#FEF3C7",
      "200": "#FDE68A",
      "300": "#FCD34D",
      "400": "#FBBF24",
      "500": "#F59E0B",
      "600": "#D97706",
      "700": "#B45309",
      "800": "#92400E",
      "900": "#78350F",
    },

    // Error: Deep red
    error: {
      "50": "#FEF2F2",
      "100": "#FEE2E2",
      "200": "#FECACA",
      "300": "#FCA5A5",
      "400": "#F87171",
      "500": "#EF4444",
      "600": "#DC2626",
      "700": "#B91C1C",
      "800": "#991B1B",
      "900": "#7F1D1D",
    },

    // Grayscale: Modern neutrals
    gray: {
      "50": "#FAFBFC",
      "100": "#F3F4F6",
      "150": "#EBEBF0",
      "200": "#E5E7EB",
      "300": "#D1D5DB",
      "400": "#9CA3AF",
      "500": "#6B7280",
      "600": "#4B5563",
      "700": "#374151",
      "800": "#1F2937",
      "900": "#111827",
      "950": "#0B0E17",
    },

    // Special colors
    surface: "#FFFFFF",
    surfaceAlt: "#F8FAFC",
    background: "#0F1117",
    backdropDark: "rgba(15, 17, 23, 0.7)",
    backdropLight: "rgba(255, 255, 255, 0.05)",
  },

  // ============= TYPOGRAPHY =============
  typography: {
    // Font families
    fontFamily: {
      sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
      mono: "'Fira Code', 'IBM Plex Mono', 'Courier New', monospace",
    },

    // Font sizes
    fontSize: {
      xs: "12px",
      sm: "13px",
      base: "14px",
      lg: "16px",
      xl: "18px",
      "2xl": "20px",
      "3xl": "24px",
      "4xl": "32px",
      "5xl": "40px",
      "6xl": "48px",
    },

    // Font weights
    fontWeight: {
      thin: 100,
      extralight: 200,
      light: 300,
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800,
      black: 900,
    },

    // Line heights
    lineHeight: {
      none: 1,
      tight: 1.25,
      snug: 1.375,
      normal: 1.5,
      relaxed: 1.625,
      loose: 2,
    },

    // Letter spacing
    letterSpacing: {
      tighter: "-0.05em",
      tight: "-0.025em",
      normal: "0em",
      wide: "0.025em",
      wider: "0.05em",
      widest: "0.1em",
    },
  },

  // ============= SPACING =============
  spacing: {
    "0": "0px",
    "1": "4px",
    "2": "8px",
    "3": "12px",
    "4": "16px",
    "5": "20px",
    "6": "24px",
    "8": "32px",
    "10": "40px",
    "12": "48px",
    "16": "64px",
    "20": "80px",
    "24": "96px",
  },

  // ============= BORDER RADIUS =============
  borderRadius: {
    none: "0px",
    xs: "4px",
    sm: "6px",
    base: "8px",
    md: "12px",
    lg: "16px",
    xl: "20px",
    "2xl": "24px",
    "3xl": "32px",
    full: "9999px",
  },

  // ============= SHADOWS =============
  shadows: {
    none: "none",
    xs: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    sm: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
    base: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    md: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
    lg: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
    xl: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
    "2xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
    glow: "0 0 20px rgba(95, 136, 255, 0.4)",
    glowStrong: "0 0 40px rgba(95, 136, 255, 0.6)",
    glowCyan: "0 0 20px rgba(31, 231, 255, 0.3)",
    inner: "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
    elevate: "0 20px 40px -15px rgba(15, 17, 23, 0.3)",
  },

  // ============= TRANSITIONS & ANIMATIONS =============
  transitions: {
    duration: {
      fastest: "50ms",
      faster: "100ms",
      fast: "150ms",
      normal: "200ms",
      slow: "300ms",
      slower: "400ms",
      slowest: "600ms",
    },
    timing: {
      linear: "linear",
      ease: "ease",
      easeIn: "cubic-bezier(0.4, 0, 1, 1)",
      easeOut: "cubic-bezier(0, 0, 0.2, 1)",
      easeInOut: "cubic-bezier(0.4, 0, 0.2, 1)",
      spring: "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
      bounce: "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
    },
  },

  // ============= GRADIENTS =============
  gradients: {
    primary: "linear-gradient(135deg, #5B88FF 0%, #4A6FE8 100%)",
    primaryGlow: "linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)",
    secondary: "linear-gradient(135deg, #1FE7FF 0%, #00B8D4 100%)",
    accent: "linear-gradient(135deg, #FF8349 0%, #F36F21 100%)",
    success: "linear-gradient(135deg, #22C55E 0%, #10B981 100%)",
    darkBg: "linear-gradient(135deg, #0F1117 0%, #1A1F35 100%)",
    dark: "linear-gradient(135deg, #111827 0%, #0F1117 100%)",
    glassDark: "linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)",
    glassLight: "linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.08) 100%)",
  },

  // ============= BREAKPOINTS =============
  breakpoints: {
    xs: 320,
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    "2xl": 1536,
  },

  // ============= Z-INDEX =============
  zIndex: {
    hide: -1,
    auto: "auto",
    base: 0,
    dropdown: 1000,
    sticky: 1100,
    fixed: 1200,
    backdrop: 1300,
    offcanvas: 1400,
    modal: 1500,
    popover: 1600,
    tooltip: 1700,
  },
}

export type Theme = typeof theme
