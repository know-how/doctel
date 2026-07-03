const darkTokens = {
  colors: {
    bg: "#0F1117",
    bgSecondary: "#1A1F35",
    bgTertiary: "#141824",
    surface: "rgba(255,255,255,0.05)",
    surfaceHover: "rgba(255,255,255,0.08)",
    surfaceActive: "rgba(91,136,255,0.12)",
    border: "rgba(255,255,255,0.08)",
    borderFocus: "rgba(91,136,255,0.4)",
    text: "#FFFFFF",
    textSecondary: "rgba(255,255,255,0.6)",
    textMuted: "rgba(255,255,255,0.35)",
    primary: "#5B88FF",
    primaryHover: "#4A6FE8",
    secondary: "#1FE7FF",
    accent: "#FBBF24",
    success: "#22C55E",
    warning: "#F59E0B",
    error: "#EF4444",
    sidebar: "rgba(13,16,28,0.98)",
    sidebarBorder: "rgba(91,136,255,0.08)",
    cardBg: "rgba(255,255,255,0.03)",
    glass: "rgba(255,255,255,0.05)",
    inputBg: "rgba(255,255,255,0.06)",
    overlay: "rgba(0,0,0,0.6)",
  },
  gradients: {
    bg: "linear-gradient(135deg, #0F1117 0%, #1A1F35 100%)",
    sidebar: "linear-gradient(180deg, rgba(13,16,28,0.98) 0%, rgba(20,24,40,0.98) 100%)",
    cardHover: "linear-gradient(135deg, rgba(91,136,255,0.05) 0%, rgba(31,231,255,0.03) 100%)",
  },
  shadows: {
    sm: "0 1px 3px rgba(0,0,0,0.3)",
    md: "0 4px 12px rgba(0,0,0,0.4)",
    lg: "0 8px 32px rgba(0,0,0,0.5)",
    glow: "0 0 20px rgba(91,136,255,0.3)",
    glowCyan: "0 0 20px rgba(31,231,255,0.3)",
  },
  radii: { sm: "6px", md: "10px", lg: "16px", xl: "24px", full: "9999px" },
  spacing: { xs: "4px", sm: "8px", md: "16px", lg: "24px", xl: "32px", xxl: "48px" },
  font: { sans: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif" },
}

const lightTokens = {
  colors: {
    bg: "#F4F7FC",
    bgSecondary: "#E8EDF4",
    bgTertiary: "#FFFFFF",
    surface: "rgba(0,0,0,0.03)",
    surfaceHover: "rgba(0,0,0,0.05)",
    surfaceActive: "rgba(91,136,255,0.10)",
    border: "rgba(0,0,0,0.08)",
    borderFocus: "rgba(91,136,255,0.5)",
    text: "#0A1628",
    textSecondary: "rgba(10,22,40,0.65)",
    textMuted: "rgba(10,22,40,0.4)",
    primary: "#0B4EA2",
    primaryHover: "#003087",
    secondary: "#0097B2",
    accent: "#F36F21",
    success: "#16A34A",
    warning: "#D97706",
    error: "#DC2626",
    sidebar: "rgba(255,255,255,0.97)",
    sidebarBorder: "rgba(0,0,0,0.06)",
    cardBg: "rgba(255,255,255,0.8)",
    glass: "rgba(255,255,255,0.7)",
    inputBg: "rgba(0,0,0,0.03)",
    overlay: "rgba(0,0,0,0.3)",
  },
  gradients: {
    bg: "linear-gradient(135deg, #F4F7FC 0%, #E8EDF4 100%)",
    sidebar: "linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(245,248,252,0.97) 100%)",
    cardHover: "linear-gradient(135deg, rgba(11,78,162,0.03) 0%, rgba(0,151,178,0.02) 100%)",
  },
  shadows: {
    sm: "0 1px 3px rgba(0,0,0,0.06)",
    md: "0 4px 12px rgba(0,0,0,0.08)",
    lg: "0 8px 32px rgba(0,0,0,0.1)",
    glow: "0 0 20px rgba(11,78,162,0.15)",
    glowCyan: "0 0 20px rgba(0,151,178,0.15)",
  },
  radii: darkTokens.radii,
  spacing: darkTokens.spacing,
  font: darkTokens.font,
}

export type ThemeTokens = typeof darkTokens

export const tokens: Record<"light" | "dark", ThemeTokens> = {
  dark: darkTokens,
  light: lightTokens,
}

export function getTokens(theme: "light" | "dark"): ThemeTokens {
  return tokens[theme]
}
