import React from "react"
import { View, Text, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminDiagnosticsScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const checks = [
    { icon: "✅", label: "Database Connection", detail: "PostgreSQL · 2ms latency", status: "passed" },
    { icon: "✅", label: "Vector DB (Chroma)", detail: "1,234 collections · 4.2M vectors", status: "passed" },
    { icon: "✅", label: "Model API (Ollama)", detail: "4 models loaded · responding", status: "passed" },
    { icon: "⚠️", label: "Disk Space", detail: "/data 72% used (will need attention soon)", status: "warning" },
    { icon: "✅", label: "Memory Usage", detail: "5.2 GB / 16 GB", status: "passed" },
    { icon: "✅", label: "Worker Pool", detail: "4 active workers · 0 queued", status: "passed" },
    { icon: "❌", label: "OpenAI Adapter", detail: "API key not configured", status: "failed" },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        System Diagnostics
      </Text>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>Overall Status</Text>
        <View style={{ backgroundColor: "#34D39918", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 4, flexDirection: "row", alignItems: "center", gap: 4 }}>
          <Text style={{ fontSize: 12 }}>🟢</Text>
          <Text style={{ fontSize: 13, fontWeight: "700", color: "#34D399" }}>5/7 PASSED</Text>
        </View>
      </View>

      {checks.map((check) => (
        <View key={check.label} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 18 }}>{check.icon}</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{check.label}</Text>
            <Text style={{ fontSize: 12, color: c.textMuted }}>{check.detail}</Text>
          </View>
        </View>
      ))}
    </ScrollView>
  )
}
