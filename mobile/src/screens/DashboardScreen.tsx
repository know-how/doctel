import React from "react"
import { View, Text, ScrollView, Pressable, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface DashboardScreenProps {
  onNavigate: (tab: "chat" | "upload" | "global-chat" | "models" | "projects" | "sessions" | "status") => void
}

interface DashboardTile {
  id: string
  title: string
  description: string
  icon: string
  action: "chat" | "upload" | "global-chat" | "models" | "projects" | "sessions" | "status"
  colorKey: "primary" | "success" | "warning" | "accent" | "secondary" | "primaryHover"
}

const tiles: DashboardTile[] = [
  { id: "upload", title: "Upload Document", description: "Upload and process documents", icon: "⬆️", action: "upload", colorKey: "primary" },
  { id: "chat", title: "Chat with Document", description: "Ask questions about your documents", icon: "💬", action: "chat", colorKey: "success" },
  { id: "global-chat", title: "Global Chat", description: "Chat across all documents", icon: "🌍", action: "global-chat", colorKey: "warning" },
  { id: "models", title: "AI Models", description: "Manage and select AI models", icon: "🤖", action: "models", colorKey: "accent" },
  { id: "projects", title: "My Projects", description: "Organize your documents", icon: "📁", action: "projects", colorKey: "secondary" },
  { id: "sessions", title: "Chat History", description: "View your chat sessions", icon: "📋", action: "sessions", colorKey: "primaryHover" },
]

export function DashboardScreen({ onNavigate }: DashboardScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768
  const columns = isTablet ? 2 : 1

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xxl }}>
      <View style={{ marginBottom: 28, paddingVertical: t.spacing.sm }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: c.text, marginBottom: 6, letterSpacing: -0.5 }}>
          Welcome to DocIntel
        </Text>
        <Text style={{ fontSize: 15, color: c.textSecondary, lineHeight: 22 }}>
          Quick access to your AI document analysis tools
        </Text>
      </View>

      <View style={{ gap: t.spacing.sm, flexDirection: "row", flexWrap: "wrap" }}>
        {tiles.map((tile) => (
          <Pressable
            key={tile.id}
            onPress={() => onNavigate(tile.action)}
            style={({ pressed }) => [
              {
                backgroundColor: c[`${tile.colorKey}14`] || c.cardBg,
                borderRadius: t.radii.lg,
                padding: 18,
                flexDirection: "row",
                alignItems: "center",
                gap: t.spacing.md,
                opacity: pressed ? 0.75 : 1,
                borderWidth: 1,
                borderColor: c.border,
                width: isTablet ? `${50 - 2}%` : "100%",
                flexBasis: isTablet ? "48%" : "100%",
              },
            ]}
          >
            <View style={{ width: 48, height: 48, justifyContent: "center", alignItems: "center" }}>
              <Text style={{ fontSize: 32 }}>{tile.icon}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: 4 }}>
                {tile.title}
              </Text>
              <Text style={{ fontSize: 13, color: c.textMuted, lineHeight: 18 }}>
                {tile.description}
              </Text>
            </View>
            <Text style={{ fontSize: 20, color: c.primary, marginRight: 4 }}>→</Text>
          </Pressable>
        ))}
      </View>

      <View style={{ marginTop: t.spacing.xxl, paddingVertical: t.spacing.md, paddingHorizontal: t.spacing.sm, backgroundColor: c.primary + "10", borderRadius: t.radii.md, borderLeftWidth: 3, borderLeftColor: c.primary }}>
        <Text style={{ fontSize: 13, color: c.textSecondary, lineHeight: 20 }}>
          💡 <Text style={{ fontWeight: "600", color: c.text }}>Pro Tip:</Text> Use the navigation tabs at the top for quick access to any section
        </Text>
      </View>
    </ScrollView>
  )
}
