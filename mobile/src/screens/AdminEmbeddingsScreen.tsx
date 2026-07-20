import React, { useEffect, useState } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminEmbeddingsScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [loading, setLoading] = useState(true)
  const [models, setModels] = useState([
    { id: "nomic-embed-text", name: "Nomic Embed Text", provider: "ollama", status: "active", dimension: 768 },
    { id: "text-embedding-ada-002", name: "ADA-002", provider: "openai", status: "inactive", dimension: 1536 },
  ])

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 500)
    return () => clearTimeout(timer)
  }, [])

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading embeddings config...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Embeddings
      </Text>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
          Active Embedding Model
        </Text>
        <View style={{ backgroundColor: c.success + "18", borderRadius: t.radii.sm, padding: t.spacing.sm, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 18 }}>🧠</Text>
          <View>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>nomic-embed-text</Text>
            <Text style={{ fontSize: 12, color: c.textMuted }}>768 dimensions · ollama</Text>
          </View>
          <View style={{ marginLeft: "auto", backgroundColor: c.success + "28", borderRadius: t.radii.sm, paddingHorizontal: 8, paddingVertical: 2 }}>
            <Text style={{ fontSize: 11, fontWeight: "700", color: c.success }}>ACTIVE</Text>
          </View>
        </View>
      </View>

      <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
        Available Models
      </Text>
      {models.map((m) => (
        <View key={m.id} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 20 }}>📦</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{m.name}</Text>
            <Text style={{ fontSize: 12, color: c.textMuted }}>{m.provider} · {m.dimension}d</Text>
          </View>
          <View style={{ backgroundColor: m.status === "active" ? c.success + "18" : c.bgSecondary, borderRadius: t.radii.sm, paddingHorizontal: 8, paddingVertical: 2 }}>
            <Text style={{ fontSize: 11, fontWeight: "700", color: m.status === "active" ? c.success : c.textMuted }}>{m.status.toUpperCase()}</Text>
          </View>
        </View>
      ))}

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginTop: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
          Vector Database
        </Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 18 }}>🗄️</Text>
          <View>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>ChromaDB</Text>
            <Text style={{ fontSize: 12, color: c.textMuted }}>Connected · 1,234 vectors indexed</Text>
          </View>
          <View style={{ marginLeft: "auto", backgroundColor: c.success + "18", borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 }}>
            <Text style={{ fontSize: 11, fontWeight: "700", color: c.success }}>HEALTHY</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  )
}
