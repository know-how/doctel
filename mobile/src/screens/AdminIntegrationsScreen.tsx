import React from "react"
import { View, Text, Pressable, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminIntegrationsScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const integrations = [
    { icon: "🤖", name: "OpenAI", desc: "GPT-4o, text-embedding-ada-002", status: "disconnected" },
    { icon: "🦙", name: "Ollama", desc: "Local models (llama3, qwen3, nomic)", status: "connected" },
    { icon: "☁️", name: "HuggingFace", desc: "Model inference via HF endpoints", status: "connected" },
    { icon: "📧", name: "SMTP", desc: "Email notifications via ZETDC mail", status: "configured" },
    { icon: "🗄️", name: "PostgreSQL", desc: "Primary database", status: "connected" },
    { icon: "🔍", name: "ChromaDB", desc: "Vector similarity search", status: "connected" },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Integrations
      </Text>

      {integrations.map((int) => (
        <View key={int.name} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 24 }}>{int.icon}</Text>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
              <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{int.name}</Text>
              <View style={{ backgroundColor: int.status === "connected" ? c.success + "18" : int.status === "configured" ? c.warning + "18" : c.error + "14", borderRadius: t.radii.sm, paddingHorizontal: 6, paddingVertical: 1 }}>
                <Text style={{ fontSize: 10, fontWeight: "700", color: int.status === "connected" ? c.success : int.status === "configured" ? c.warning : c.error }}>{int.status.toUpperCase()}</Text>
              </View>
            </View>
            <Text style={{ fontSize: 12, color: c.textMuted }}>{int.desc}</Text>
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
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>+ Add Integration</Text>
      </Pressable>
    </ScrollView>
  )
}
