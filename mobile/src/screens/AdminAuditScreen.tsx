import React from "react"
import { View, Text, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminAuditScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const auditEntries = [
    { time: "2026-07-20 09:23:14", user: "ec_admin", action: "Updated model routing rules", type: "config" },
    { time: "2026-07-20 08:15:42", user: "manager_12", action: "Deleted document batch #342", type: "delete" },
    { time: "2026-07-19 23:45:01", user: "system", action: "Scheduled maintenance — vector re-index", type: "system" },
    { time: "2026-07-19 18:30:22", user: "ec_admin", action: "Added new provider: OpenAI", type: "config" },
    { time: "2026-07-19 14:12:08", user: "analyst_34", action: "Exported analysis report", type: "export" },
    { time: "2026-07-19 11:07:33", user: "ec_admin", action: "Modified RBAC permissions for Viewer role", type: "security" },
    { time: "2026-07-19 09:00:12", user: "system", action: "Daily health check completed — all OK", type: "system" },
  ]

  const typeColors: Record<string, string> = {
    config: c.primary,
    delete: c.error,
    system: c.textMuted,
    export: c.success,
    security: c.warning,
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.md }}>
        <Text style={{ fontSize: 24, fontWeight: "800", color: c.text }}>
          Audit Log
        </Text>
        <Text style={{ fontSize: 12, color: c.textMuted }}>7 recent entries</Text>
      </View>

      {auditEntries.map((entry, idx) => (
        <View key={idx} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border, borderLeftWidth: 3, borderLeftColor: typeColors[entry.type] || c.textMuted }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: t.spacing.xs }}>
            <Text style={{ fontSize: 12, color: c.textMuted }}>{entry.time}</Text>
            <View style={{ backgroundColor: (typeColors[entry.type] || c.textMuted) + "18", borderRadius: t.radii.sm, paddingHorizontal: 6, paddingVertical: 1 }}>
              <Text style={{ fontSize: 9, fontWeight: "700", color: typeColors[entry.type] || c.textMuted }}>{entry.type.toUpperCase()}</Text>
            </View>
          </View>
          <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{entry.action}</Text>
          <Text style={{ fontSize: 12, color: c.primary }}>by {entry.user}</Text>
        </View>
      ))}
    </ScrollView>
  )
}
