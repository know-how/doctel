import React from "react"
import { View, Text, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminRBACScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const roles = [
    { id: "admin", name: "Administrator", users: 3, permissions: "Full access to all features and settings", color: c.error },
    { id: "manager", name: "Manager", users: 12, permissions: "User management, reports, model configuration", color: c.warning },
    { id: "analyst", name: "Analyst", users: 45, permissions: "Document analysis, chat, outputs", color: c.primary },
    { id: "viewer", name: "Viewer", users: 120, permissions: "Read-only access to documents and outputs", color: c.textMuted },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Role-Based Access Control
      </Text>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
          Total Users
        </Text>
        <Text style={{ fontSize: 32, fontWeight: "800", color: c.text }}>180</Text>
        <Text style={{ fontSize: 12, color: c.textMuted }}>across 4 roles</Text>
      </View>

      {roles.map((role) => (
        <View key={role.id} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border, borderLeftWidth: 3, borderLeftColor: role.color }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.xs }}>
            <Text style={{ fontSize: 14, fontWeight: "700", color: c.text }}>{role.name}</Text>
            <View style={{ backgroundColor: role.color + "18", borderRadius: 12, paddingHorizontal: 8, paddingVertical: 2 }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: role.color }}>{role.users} users</Text>
            </View>
          </View>
          <Text style={{ fontSize: 12, color: c.textMuted }}>{role.permissions}</Text>
        </View>
      ))}
    </ScrollView>
  )
}
