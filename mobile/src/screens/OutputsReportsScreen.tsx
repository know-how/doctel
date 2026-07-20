import React from "react"
import { View, Text, Pressable, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function OutputsReportsScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const reports = [
    { icon: "📊", name: "Usage Summary", desc: "Monthly platform usage metrics", period: "This Month" },
    { icon: "🤖", name: "Model Performance", desc: "Latency, throughput, and error rates", period: "Last 7 Days" },
    { icon: "📄", name: "Document Processing", desc: "Documents ingested, analyzed, and stored", period: "This Quarter" },
    { icon: "👥", name: "User Activity", desc: "Active users, sessions, and engagement", period: "This Month" },
    { icon: "🔍", name: "Search Analytics", desc: "Top queries, results, and accuracy", period: "Last 30 Days" },
    { icon: "💰", name: "Cost Analysis", desc: "API usage costs by provider and model", period: "This Month" },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Reports
      </Text>

      <View style={isTablet ? { flexDirection: "row", flexWrap: "wrap", gap: t.spacing.sm } : undefined}>
        {reports.map((r) => (
          <Pressable key={r.name} style={isTablet ? { width: "48%", marginBottom: t.spacing.sm } : { marginBottom: t.spacing.sm }}>
            <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm, marginBottom: t.spacing.xs }}>
                <Text style={{ fontSize: 24 }}>{r.icon}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: "700", color: c.text }}>{r.name}</Text>
                  <Text style={{ fontSize: 12, color: c.textMuted }}>{r.desc}</Text>
                </View>
              </View>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: t.spacing.xs }}>
                <Text style={{ fontSize: 11, color: c.textMuted }}>{r.period}</Text>
                <Text style={{ fontSize: 12, color: c.primary, fontWeight: "600" }}>View →</Text>
              </View>
            </View>
          </Pressable>
        ))}
      </View>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginTop: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
          Generate Custom Report
        </Text>
        <Text style={{ fontSize: 12, color: c.textMuted, marginBottom: t.spacing.sm }}>
          Select metrics, filters, and date range to create a tailored report.
        </Text>
        <Pressable style={{ backgroundColor: c.primary, borderRadius: t.radii.md, paddingVertical: t.spacing.md - 2, alignItems: "center" }}>
          <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>Create Report</Text>
        </Pressable>
      </View>
    </ScrollView>
  )
}
