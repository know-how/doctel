import React from "react"
import { View, Text, Pressable, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminAutoRoutingScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const rules = [
    { id: "1", name: "Simple Chat", match: "chat, low-temp", model: "llama3.2:3b", priority: "high" },
    { id: "2", name: "Document Analysis", match: "context > 8k, json", model: "qwen3:4b", priority: "medium" },
    { id: "3", name: "Code Generation", match: "code, structured", model: "codellama:7b", priority: "low" },
    { id: "4", name: "Fallback", match: "catch-all", model: "llama3.2:3b", priority: "lowest" },
  ]

  const priorityColors: Record<string, string> = {
    high: c.error + "18",
    medium: c.warning + "18",
    low: c.primary + "14",
    lowest: c.bgSecondary,
  }

  const priorityTextColors: Record<string, string> = {
    high: c.error,
    medium: c.warning,
    low: c.primary,
    lowest: c.textMuted,
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Auto Routing
      </Text>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
          Routing Strategy
        </Text>
        <Text style={{ fontSize: 13, color: c.textMuted, marginBottom: t.spacing.sm }}>
          Requests are routed to the best model based on task type, context size, and capability requirements.
        </Text>
        <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, padding: t.spacing.sm, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 16 }}>⚡</Text>
          <Text style={{ fontSize: 13, color: c.text, flex: 1 }}>Intelligent routing enabled — 4 active rules</Text>
        </View>
      </View>

      <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
        Routing Rules
      </Text>
      {rules.map((rule) => (
        <View key={rule.id} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.xs }}>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{rule.name}</Text>
            <View style={{ backgroundColor: priorityColors[rule.priority], borderRadius: t.radii.sm, paddingHorizontal: 8, paddingVertical: 2 }}>
              <Text style={{ fontSize: 10, fontWeight: "700", color: priorityTextColors[rule.priority] }}>{rule.priority.toUpperCase()}</Text>
            </View>
          </View>
          <Text style={{ fontSize: 12, color: c.textMuted }}>Match: {rule.match}</Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.xs, marginTop: t.spacing.xs }}>
            <Text style={{ fontSize: 12, color: c.primary, fontWeight: "600" }}>→ {rule.model}</Text>
          </View>
        </View>
      ))}

      <Pressable
        style={{
          backgroundColor: c.primary,
          borderRadius: t.radii.md,
          paddingVertical: t.spacing.md - 2,
          alignItems: "center",
          marginTop: t.spacing.sm,
        }}
      >
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>+ Add Rule</Text>
      </Pressable>
    </ScrollView>
  )
}
