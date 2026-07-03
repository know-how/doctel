/**
 * Utility Styles for Modern Components
 * Reusable style objects for consistent UI patterns
 */

import { theme } from "./theme"

export const utilityStyles = {
  // ===== GLASS MORPHISM =====
  glass: {
    background: "rgba(255, 255, 255, 0.08)",
    backdropFilter: "blur(10px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: theme.borderRadius.lg,
  },

  glassLight: {
    background: "rgba(255, 255, 255, 0.12)",
    backdropFilter: "blur(12px)",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    borderRadius: theme.borderRadius.lg,
  },

  glassDark: {
    background: "rgba(15, 17, 23, 0.6)",
    backdropFilter: "blur(8px)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    borderRadius: theme.borderRadius.lg,
  },

  // ===== CARDS =====
  card: {
    background: "linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.04) 100%)",
    backdropFilter: "blur(10px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing[6],
    boxShadow: theme.shadows.md,
    transition: `all ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
    cursor: "pointer",
  },

  cardHover: {
    background: "linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.06) 100%)",
    boxShadow: theme.shadows.lg,
    transform: "translateY(-4px)",
    border: "1px solid rgba(255, 255, 255, 0.15)",
  },

  // ===== BUTTONS =====
  button: {
    padding: `${theme.spacing[3]} ${theme.spacing[6]}`,
    borderRadius: theme.borderRadius.md,
    border: "none",
    fontSize: theme.typography.fontSize.base,
    fontWeight: theme.typography.fontWeight.semibold,
    cursor: "pointer",
    transition: `all ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: theme.spacing[2],
    outline: "none",
  },

  buttonPrimary: {
    background: "linear-gradient(135deg, #5B88FF 0%, #4A6FE8 100%)",
    color: "#FFFFFF",
    boxShadow: "0 0 20px rgba(95, 136, 255, 0.3)",
  },

  buttonPrimaryHover: {
    boxShadow: "0 0 30px rgba(95, 136, 255, 0.5)",
    transform: "translateY(-2px)",
  },

  buttonSecondary: {
    background: "linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)",
    color: "#E5E7EB",
    border: "1px solid rgba(255, 255, 255, 0.2)",
  },

  buttonSecondaryHover: {
    background: "linear-gradient(135deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.08) 100%)",
    border: "1px solid rgba(255, 255, 255, 0.3)",
  },

  buttonGhost: {
    background: "transparent",
    color: "#5B88FF",
    border: "1px solid #5B88FF",
  },

  buttonGhostHover: {
    background: "rgba(91, 136, 255, 0.1)",
    boxShadow: "0 0 15px rgba(91, 136, 255, 0.2)",
  },

  // ===== BADGES =====
  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: theme.spacing[2],
    padding: `${theme.spacing[1]} ${theme.spacing[3]}`,
    borderRadius: theme.borderRadius.full,
    fontSize: theme.typography.fontSize.xs,
    fontWeight: theme.typography.fontWeight.semibold,
    background: "linear-gradient(135deg, rgba(91, 136, 255, 0.2) 0%, rgba(31, 231, 255, 0.1) 100%)",
    border: "1px solid rgba(91, 136, 255, 0.3)",
    color: "#1FE7FF",
  },

  // ===== INPUTS =====
  input: {
    padding: `${theme.spacing[3]} ${theme.spacing[4]}`,
    borderRadius: theme.borderRadius.md,
    border: "1px solid rgba(255, 255, 255, 0.1)",
    background: "rgba(255, 255, 255, 0.05)",
    color: "#E5E7EB",
    fontSize: theme.typography.fontSize.base,
    fontFamily: theme.typography.fontFamily.sans,
    transition: `all ${theme.transitions.duration.fast} ${theme.transitions.timing.easeOut}`,
    backdropFilter: "blur(4px)",
  },

  inputFocus: {
    border: "1px solid #5B88FF",
    background: "rgba(91, 136, 255, 0.08)",
    boxShadow: "0 0 15px rgba(91, 136, 255, 0.2)",
  },

  // ===== TEXT STYLES =====
  heading1: {
    fontSize: theme.typography.fontSize["5xl"],
    fontWeight: theme.typography.fontWeight.bold,
    lineHeight: theme.typography.lineHeight.tight,
    letterSpacing: theme.typography.letterSpacing.tight,
    color: "#FFFFFF",
  },

  heading2: {
    fontSize: theme.typography.fontSize["4xl"],
    fontWeight: theme.typography.fontWeight.bold,
    lineHeight: theme.typography.lineHeight.tight,
    letterSpacing: theme.typography.letterSpacing.tight,
    color: "#FFFFFF",
  },

  heading3: {
    fontSize: theme.typography.fontSize["3xl"],
    fontWeight: theme.typography.fontWeight.semibold,
    lineHeight: theme.typography.lineHeight.snug,
    letterSpacing: theme.typography.letterSpacing.tight,
    color: "#F3F4F6",
  },

  heading4: {
    fontSize: theme.typography.fontSize["2xl"],
    fontWeight: theme.typography.fontWeight.semibold,
    lineHeight: theme.typography.lineHeight.snug,
    color: "#F3F4F6",
  },

  heading5: {
    fontSize: theme.typography.fontSize.lg,
    fontWeight: theme.typography.fontWeight.semibold,
    lineHeight: theme.typography.lineHeight.snug,
    color: "#E5E7EB",
  },

  bodyLarge: {
    fontSize: theme.typography.fontSize.lg,
    fontWeight: theme.typography.fontWeight.normal,
    lineHeight: theme.typography.lineHeight.relaxed,
    color: "#D1D5DB",
  },

  body: {
    fontSize: theme.typography.fontSize.base,
    fontWeight: theme.typography.fontWeight.normal,
    lineHeight: theme.typography.lineHeight.normal,
    color: "#D1D5DB",
  },

  bodySmall: {
    fontSize: theme.typography.fontSize.sm,
    fontWeight: theme.typography.fontWeight.normal,
    lineHeight: theme.typography.lineHeight.normal,
    color: "#9CA3AF",
  },

  caption: {
    fontSize: theme.typography.fontSize.xs,
    fontWeight: theme.typography.fontWeight.normal,
    lineHeight: theme.typography.lineHeight.tight,
    color: "#6B7280",
  },

  // ===== FLEXBOX UTILITIES =====
  flexCenter: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },

  flexBetween: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },

  flexCol: {
    display: "flex",
    flexDirection: "column" as const,
  },

  flexColCenter: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
  },

  // ===== GRID UTILITIES =====
  grid: {
    display: "grid",
    gap: theme.spacing[6],
  },

  gridCol2: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: theme.spacing[6],
  },

  gridCol3: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: theme.spacing[6],
  },

  // ===== OVERFLOW & TEXT =====
  truncate: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },

  lineClamp2: {
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
  },

  lineClamp3: {
    display: "-webkit-box",
    WebkitLineClamp: 3,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
  },

  // ===== FOCUS STATES =====
  focusRing: {
    outline: "2px solid #5B88FF",
    outlineOffset: "2px",
  },

  // ===== LOADING & DISABLED =====
  loading: {
    opacity: 0.6,
    pointerEvents: "none" as const,
  },

  disabled: {
    opacity: 0.5,
    pointerEvents: "none" as const,
    cursor: "not-allowed",
  },
}

export type UtilityStyles = typeof utilityStyles
