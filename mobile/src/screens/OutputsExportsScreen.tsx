import React from "react"
import { View, Text, Pressable, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function OutputsExportsScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const exports = [
    { id: "1", type: "PDF", name: "Summary Report — Jul 2026", date: "2026-07-19", size: "2.4 MB", status: "completed" },
    { id: "2", type: "CSV", name: "Extraction — Transformer Data", date: "2026-07-18", size: "1.1 MB", status: "completed" },
    { id: "3", type: "JSON", name: "Classification — Asset Register", date: "2026-07-16", size: "4.7 MB", status: "completed" },
    { id: "4", type: "PDF", name: "Comparison — Load Profiles Q2", date: "2026-07-15", size: "3.2 MB", status: "completed" },
    { id: "5", type: "CSV", name: "Batch Export — Documents 200-250", date: "2026-07-20", size: "—", status: "processing" },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Exports
      </Text>

      {exports.map((exp) => (
        <View key={exp.id} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
                <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, paddingHorizontal: 6, paddingVertical: 2 }}>
                  <Text style={{ fontSize: 10, fontWeight: "700", color: c.primary }}>{exp.type}</Text>
                </View>
                <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, flex: 1 }} numberOfLines={1}>{exp.name}</Text>
              </View>
              <View style={{ flexDirection: "row", gap: t.spacing.md, marginTop: t.spacing.xs }}>
                <Text style={{ fontSize: 11, color: c.textMuted }}>{exp.date}</Text>
                <Text style={{ fontSize: 11, color: c.textMuted }}>{exp.size}</Text>
              </View>
            </View>
            <View style={{ backgroundColor: exp.status === "completed" ? c.success + "18" : c.warning + "18", borderRadius: t.radii.sm, paddingHorizontal: 8, paddingVertical: 2 }}>
              <Text style={{ fontSize: 10, fontWeight: "700", color: exp.status === "completed" ? c.success : c.warning }}>{exp.status.toUpperCase()}</Text>
            </View>
          </View>
          <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: t.spacing.sm, marginTop: t.spacing.sm, borderTopWidth: 1, borderTopColor: c.bgSecondary, paddingTop: t.spacing.sm }}>
            <Pressable style={{ backgroundColor: c.primary, borderRadius: t.radii.sm, paddingVertical: 5, paddingHorizontal: 10 }}>
              <Text style={{ color: "#FFFFFF", fontSize: 11, fontWeight: "600" }}>Download</Text>
            </Pressable>
            <Pressable style={{ backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, paddingVertical: 5, paddingHorizontal: 10 }}>
              <Text style={{ color: c.text, fontSize: 11, fontWeight: "600" }}>Share</Text>
            </Pressable>
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
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>New Export</Text>
      </Pressable>
    </ScrollView>
  )
}
