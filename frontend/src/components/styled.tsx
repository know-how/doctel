/**
 * Modern Styled Components Library
 * Reusable, beautiful components following the futuristic design system
 */

import React from "react"
import { theme } from "../theme/theme"
import { utilityStyles } from "../theme/utilityStyles"
import { animations } from "../theme/animations"

// ===== BUTTON COMPONENT =====
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
  loading?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      icon,
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    const sizeStyles = {
      sm: {
        padding: `${theme.spacing[2]} ${theme.spacing[4]}`,
        fontSize: theme.typography.fontSize.sm,
      },
      md: {
        padding: `${theme.spacing[3]} ${theme.spacing[6]}`,
        fontSize: theme.typography.fontSize.base,
      },
      lg: {
        padding: `${theme.spacing[4]} ${theme.spacing[8]}`,
        fontSize: theme.typography.fontSize.lg,
      },
    }

    const variantStyles = {
      primary: { ...utilityStyles.buttonPrimary },
      secondary: { ...utilityStyles.buttonSecondary },
      ghost: { ...utilityStyles.buttonGhost },
      danger: {
        background: `linear-gradient(135deg, #EF4444 0%, #DC2626 100%)`,
        color: "#FFFFFF",
        boxShadow: "0 0 15px rgba(239, 68, 68, 0.3)",
      },
    }

    return (
      <button
        ref={ref}
        {...props}
        disabled={disabled || loading}
        style={{
          ...utilityStyles.button,
          ...sizeStyles[size],
          ...variantStyles[variant],
          opacity: disabled || loading ? 0.6 : 1,
          pointerEvents: disabled || loading ? "none" : "auto",
          ...animations.hoverTransition,
          ...props.style,
        }}
        onMouseEnter={(e) => {
          if (!disabled && !loading) {
            if (variant === "primary") {
              (e.currentTarget as HTMLButtonElement).style.boxShadow =
                `0 0 30px rgba(91, 136, 255, 0.5)`
            } else if (variant === "secondary") {
              (e.currentTarget as HTMLButtonElement).style.boxShadow = utilityStyles.cardHover.boxShadow
            } else if (variant === "ghost") {
              (e.currentTarget as HTMLButtonElement).style.boxShadow =
                `0 0 15px rgba(91, 136, 255, 0.2)`
            }
            ;(e.currentTarget as HTMLButtonElement).style.transform = "translateY(-2px)"
          }
        }}
        onMouseLeave={(e) => {
          if (variant === "primary") {
            (e.currentTarget as HTMLButtonElement).style.boxShadow =
              `0 0 20px rgba(91, 136, 255, 0.3)`
          } else if (variant === "secondary") {
            (e.currentTarget as HTMLButtonElement).style.boxShadow = utilityStyles.card.boxShadow
          } else {
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "none"
          }
          ;(e.currentTarget as HTMLButtonElement).style.transform = "translateY(0)"
        }}
      >
        {loading && (
          <div
            style={{
              width: 16,
              height: 16,
              borderRadius: "50%",
              border: "2px solid rgba(255,255,255,0.3)",
              borderTopColor: "#FFFFFF",
              animation: `spin 1s linear infinite`,
            }}
          />
        )}
        {icon && !loading && <span>{icon}</span>}
        <span>{children}</span>
      </button>
    )
  },
)

Button.displayName = "Button"

// ===== CARD COMPONENT =====
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean
  children: React.ReactNode
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ hover = true, children, ...props }, ref) => {
    const [isHovered, setIsHovered] = React.useState(false)

    return (
      <div
        ref={ref}
        {...props}
        style={{
          ...utilityStyles.card,
          ...(hover && isHovered && utilityStyles.cardHover),
          ...animations.hoverTransition,
          ...props.style,
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {children}
      </div>
    )
  },
)

Card.displayName = "Card"

// ===== INPUT COMPONENT =====
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  icon?: React.ReactNode
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, ...props }, ref) => {
    const [isFocused, setIsFocused] = React.useState(false)

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: theme.spacing[2] }}>
        {label && (
          <label
            style={{
              fontSize: theme.typography.fontSize.sm,
              fontWeight: theme.typography.fontWeight.semibold,
              color: theme.colors.gray[300],
            }}
          >
            {label}
          </label>
        )}
        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
          }}
        >
          {icon && (
            <div
              style={{
                position: "absolute",
                left: theme.spacing[4],
                display: "flex",
                alignItems: "center",
                color: theme.colors.gray[400],
              }}
            >
              {icon}
            </div>
          )}
          <input
            ref={ref}
            {...props}
            style={{
              ...utilityStyles.input,
              ...(isFocused && utilityStyles.inputFocus),
              ...(error && {
                borderColor: theme.colors.error[500],
                background: `rgba(239, 68, 68, 0.05)`,
              }),
              paddingLeft: icon ? 48 : undefined,
              width: "100%",
              ...animations.smoothTransition,
              ...props.style,
            }}
            onFocus={(e) => {
              setIsFocused(true)
              props.onFocus?.(e)
            }}
            onBlur={(e) => {
              setIsFocused(false)
              props.onBlur?.(e)
            }}
          />
        </div>
        {error && (
          <span
            style={{
              fontSize: theme.typography.fontSize.xs,
              color: theme.colors.error[400],
              fontWeight: theme.typography.fontWeight.medium,
            }}
          >
            {error}
          </span>
        )}
      </div>
    )
  },
)

Input.displayName = "Input"

// ===== BADGE COMPONENT =====
interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "primary" | "success" | "warning" | "error" | "secondary"
  children: React.ReactNode
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = "primary", children, ...props }, ref) => {
    const variantStyles = {
      primary: {
        background: `linear-gradient(135deg, rgba(91, 136, 255, 0.2) 0%, rgba(31, 231, 255, 0.1) 100%)`,
        border: `1px solid rgba(91, 136, 255, 0.3)`,
        color: theme.colors.secondary[200],
      },
      success: {
        background: `linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(16, 185, 129, 0.1) 100%)`,
        border: `1px solid rgba(34, 197, 94, 0.3)`,
        color: theme.colors.success[300],
      },
      warning: {
        background: `linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(217, 119, 6, 0.1) 100%)`,
        border: `1px solid rgba(245, 158, 11, 0.3)`,
        color: theme.colors.warning[300],
      },
      error: {
        background: `linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(220, 38, 38, 0.1) 100%)`,
        border: `1px solid rgba(239, 68, 68, 0.3)`,
        color: theme.colors.error[300],
      },
      secondary: {
        background: `linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)`,
        border: `1px solid rgba(255, 255, 255, 0.2)`,
        color: theme.colors.gray[300],
      },
    }

    return (
      <span
        ref={ref}
        {...props}
        style={{
          ...utilityStyles.badge,
          ...variantStyles[variant],
          ...props.style,
        }}
      >
        {children}
      </span>
    )
  },
)

Badge.displayName = "Badge"

// ===== GLASS PANEL COMPONENT =====
interface GlassPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  intensity?: "light" | "medium" | "dark"
}

export const GlassPanel = React.forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ intensity = "medium", children, ...props }, ref) => {
    const intensityStyles = {
      light: utilityStyles.glassLight,
      medium: utilityStyles.glass,
      dark: utilityStyles.glassDark,
    }

    return (
      <div
        ref={ref}
        {...props}
        style={{
          ...intensityStyles[intensity],
          padding: theme.spacing[6],
          ...animations.fadeIn,
          ...props.style,
        }}
      >
        {children}
      </div>
    )
  },
)

GlassPanel.displayName = "GlassPanel"

// ===== DIVIDER COMPONENT =====
interface DividerProps {
  variant?: "solid" | "dashed" | "dotted"
  color?: "primary" | "secondary" | "muted"
  margin?: "sm" | "md" | "lg"
}

export const Divider: React.FC<DividerProps> = ({
  variant = "solid",
  color = "muted",
  margin = "md",
}) => {
  const colorMap = {
    primary: "rgba(91, 136, 255, 0.2)",
    secondary: "rgba(31, 231, 255, 0.15)",
    muted: "rgba(255, 255, 255, 0.1)",
  }

  const marginMap = {
    sm: theme.spacing[4],
    md: theme.spacing[6],
    lg: theme.spacing[8],
  }

  return (
    <div
      style={{
        height: 1,
        background: colorMap[color],
        borderStyle: variant === "solid" ? "solid" : variant,
        borderColor: colorMap[color],
        margin: `${marginMap[margin]} 0`,
      }}
    />
  )
}

// ===== SPINNER COMPONENT =====
interface SpinnerProps {
  size?: "sm" | "md" | "lg"
  color?: "primary" | "secondary" | "white"
}

export const Spinner: React.FC<SpinnerProps> = ({ size = "md", color = "primary" }) => {
  const sizeMap = {
    sm: 20,
    md: 40,
    lg: 60,
  }

  const colorMap = {
    primary: "#5B88FF",
    secondary: "#1FE7FF",
    white: "#FFFFFF",
  }

  return (
    <div
      style={{
        width: sizeMap[size],
        height: sizeMap[size],
        borderRadius: "50%",
        border: `3px solid rgba(255, 255, 255, 0.1)`,
        borderTopColor: colorMap[color],
        animation: `spin 1s linear infinite`,
      }}
    />
  )
}

// ===== TEXT COMPONENT =====
interface TextProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?:
    | "heading1"
    | "heading2"
    | "heading3"
    | "heading4"
    | "heading5"
    | "bodyLarge"
    | "body"
    | "bodySmall"
    | "caption"
  color?: keyof typeof theme.colors.gray | "primary" | "secondary" | "error"
  children: React.ReactNode
  as?: keyof JSX.IntrinsicElements
}

export const Text = React.forwardRef<HTMLSpanElement, TextProps>(
  ({ variant = "body", color = "gray", children, as = "span", ...props }, ref) => {
    const variantStyles = {
      heading1: utilityStyles.heading1,
      heading2: utilityStyles.heading2,
      heading3: utilityStyles.heading3,
      heading4: utilityStyles.heading4,
      heading5: utilityStyles.heading5,
      bodyLarge: utilityStyles.bodyLarge,
      body: utilityStyles.body,
      bodySmall: utilityStyles.bodySmall,
      caption: utilityStyles.caption,
    }

    const colorMap = {
      primary: theme.colors.primary[400],
      secondary: theme.colors.secondary[400],
      error: theme.colors.error[400],
      50: theme.colors.gray[50],
      100: theme.colors.gray[100],
      200: theme.colors.gray[200],
      300: theme.colors.gray[300],
      400: theme.colors.gray[400],
      500: theme.colors.gray[500],
      600: theme.colors.gray[600],
      700: theme.colors.gray[700],
      800: theme.colors.gray[800],
      900: theme.colors.gray[900],
      950: theme.colors.gray[950],
    }

    const Component = as as any

    return (
      <Component
        ref={ref}
        {...props}
        style={{
          ...variantStyles[variant],
          color: colorMap[color as any] || colorMap[300],
          ...props.style,
        }}
      >
        {children}
      </Component>
    )
  },
)

Text.displayName = "Text"
