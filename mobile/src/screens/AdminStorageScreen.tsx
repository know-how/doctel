import React from "react"
import { View, Text, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminStorageScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const storageItems = [
    { label: "Vector Database", used: "2.4 GB", total: "10 GB", pct: 24, color: c.primary },
    { label: "Document Store", used: "1.8 GB", total: "50 GB", pct: 3.6, color: c.success },
    { label: "Model Cache", used: "4.2 GB", total: "20 GB", pct: 21, color: c.warning },
    { label: "Logs & Backups", used: "0.6 GB", total: "5 GB", pct: 12, color: c.accent },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Storage
      </Text>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.sm }}>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }}>Total Usage</Text>
          <Text style={{ fontSize: 20, fontWeight: "800", color: c.text }}>9.0 GB</Text>
        </View>
        <Text style={{ fontSize: 12, color: c.textMuted, marginBottom: t.spacing.sm }}>of 85 GB allocated</Text>
        <View style={{ height: 8, backgroundColor: c.bgSecondary, borderRadius: 4, overflow: "hidden", flexDirection: "row" }}>
          <View style={{ width: "28%", backgroundColor: c.primary }} />
          <View style={{ width: "22%", backgroundColor: c.success }} />
          <View style={{ width: "50%", backgroundColor: c.bgSecondary }} />
        </View>
      </View>

      {storageItems.map((item) => (
        <View key={item.label} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: t.spacing.xs }}>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{item.label}</Text>
            <Text style={{ fontSize: 13, color: c.textMuted }}>{item.used} / {item.total}</Text>
          </View>
          <View style={{ height: 6, backgroundColor: c.bgSecondary, borderRadius: 3, overflow: "hidden" }}>
            <View style={{ width: `${Math.min(item.pct, 100)}%`, height: "100%", backgroundColor: item.color, borderRadius: 3 }} />
          </View>
        </View>
      ))}
    </ScrollView>
  )
}
