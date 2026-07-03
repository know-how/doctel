import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { saveUserThemePreference } from "../api/client"

type ThemeName = "light" | "dark"

const THEME_KEY = "docintel_theme"

interface ThemeContextValue {
  theme: ThemeName
  toggleTheme: () => void
  isDark: boolean
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function getInitialTheme(): ThemeName {
  if (typeof window === "undefined") return "dark"
  const stored = window.localStorage.getItem(THEME_KEY)
  if (stored === "light" || stored === "dark") return stored
  return "dark"
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeName>(getInitialTheme)

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next: ThemeName = prev === "dark" ? "light" : "dark"
      window.localStorage.setItem(THEME_KEY, next)
      saveUserThemePreference(next).catch(() => {
        // silently ignore API failures — local preference is already saved
      })
      return next
    })
  }, [])

  const value: ThemeContextValue = {
    theme,
    toggleTheme,
    isDark: theme === "dark",
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return ctx
}
