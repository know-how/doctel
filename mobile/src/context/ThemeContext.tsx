import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { saveUserThemePreference } from "../api/client"
import { ThemeTokens, getTokens } from "../theme/themeTokens"

type ThemeName = "light" | "dark"

const THEME_KEY = "docintel_theme"

interface ThemeContextValue {
  theme: ThemeName
  toggleTheme: () => void
  isDark: boolean
  tokens: ThemeTokens
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

async function getInitialTheme(): Promise<ThemeName> {
  try {
    const stored = await AsyncStorage.getItem(THEME_KEY)
    if (stored === "light" || stored === "dark") return stored
  } catch {}
  return "dark"
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeName>("dark")

  useEffect(() => {
    getInitialTheme().then(setTheme)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next: ThemeName = prev === "dark" ? "light" : "dark"
      AsyncStorage.setItem(THEME_KEY, next).catch(() => {})
      saveUserThemePreference(next).catch(() => {})
      return next
    })
  }, [])

  return (
    <ThemeContext.Provider
      value={{
        theme,
        toggleTheme,
        isDark: theme === "dark",
        tokens: getTokens(theme),
      }}
    >
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
