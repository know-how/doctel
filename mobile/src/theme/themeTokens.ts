export interface ThemeTokens {
  colors: {
    bg: string; bgSecondary: string; bgTertiary: string;
    surface: string; surfaceHover: string; surfaceActive: string;
    border: string; borderFocus: string;
    text: string; textSecondary: string; textMuted: string;
    primary: string; primaryHover: string; secondary: string;
    accent: string; success: string; warning: string; error: string;
    cardBg: string; inputBg: string; overlay: string;
    sidebar: string; sidebarBorder: string;
  };
  radii: { sm: number; md: number; lg: number; xl: number; full: number };
  spacing: { xs: number; sm: number; md: number; lg: number; xl: number; xxl: number };
  fontFamily: string;
}

const darkTokens: ThemeTokens = {
  colors: {
    bg: "#0F1117", bgSecondary: "#1A1F35", bgTertiary: "#141824",
    surface: "rgba(255,255,255,0.05)", surfaceHover: "rgba(255,255,255,0.08)", surfaceActive: "rgba(91,136,255,0.12)",
    border: "rgba(255,255,255,0.08)", borderFocus: "rgba(91,136,255,0.4)",
    text: "#FFFFFF", textSecondary: "rgba(255,255,255,0.6)", textMuted: "rgba(255,255,255,0.35)",
    primary: "#5B88FF", primaryHover: "#4A6FE8", secondary: "#1FE7FF",
    accent: "#FBBF24", success: "#22C55E", warning: "#F59E0B", error: "#EF4444",
    cardBg: "rgba(255,255,255,0.03)", inputBg: "rgba(255,255,255,0.06)", overlay: "rgba(0,0,0,0.6)",
    sidebar: "#0D101C", sidebarBorder: "rgba(91,136,255,0.08)",
  },
  radii: { sm: 6, md: 10, lg: 16, xl: 24, full: 9999 },
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 },
  fontFamily: "'Inter', -apple-system, sans-serif",
}

const lightTokens: ThemeTokens = {
  colors: {
    bg: "#F4F7FC", bgSecondary: "#E8EDF4", bgTertiary: "#FFFFFF",
    surface: "rgba(0,0,0,0.03)", surfaceHover: "rgba(0,0,0,0.05)", surfaceActive: "rgba(91,136,255,0.10)",
    border: "rgba(0,0,0,0.08)", borderFocus: "rgba(91,136,255,0.5)",
    text: "#0A1628", textSecondary: "rgba(10,22,40,0.65)", textMuted: "rgba(10,22,40,0.4)",
    primary: "#0B4EA2", primaryHover: "#003087", secondary: "#0097B2",
    accent: "#F36F21", success: "#16A34A", warning: "#D97706", error: "#DC2626",
    cardBg: "rgba(255,255,255,0.8)", inputBg: "rgba(0,0,0,0.03)", overlay: "rgba(0,0,0,0.3)",
    sidebar: "#FFFFFF", sidebarBorder: "rgba(0,0,0,0.06)",
  },
  radii: { sm: 6, md: 10, lg: 16, xl: 24, full: 9999 },
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 },
  fontFamily: "'Inter', -apple-system, sans-serif",
}

export const tokens: Record<string, ThemeTokens> = { light: lightTokens, dark: darkTokens }
export const getTokens = (theme: string) => tokens[theme] || darkTokens
