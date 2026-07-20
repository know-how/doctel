import React from "react"
import { View, Text, Pressable, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminSecurityScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const securityItems = [
    { icon: "🔐", label: "Authentication", desc: "OAuth 2.0 · JWT tokens · Session expiry: 24h", status: "enabled" },
    { icon: "🛡️", label: "Rate Limiting", desc: "100 req/min per user · IP-based throttling", status: "enabled" },
    { icon: "🔒", label: "Data Encryption", desc: "AES-256 at rest · TLS 1.3 in transit", status: "enabled" },
    { icon: "📋", label: "Audit Logging", desc: "All admin actions logged · 90 day retention", status: "enabled" },
    { icon: "🚫", label: "IP Allowlist", desc: "Not configured — open access", status: "disabled" },
    { icon: "🔑", label: "API Keys", desc: "8 active keys · 3 expired keys", status: "enabled" },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Security
      </Text>

      {securityItems.map((item) => (
        <View key={item.label} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
          <Text style={{ fontSize: 24 }}>{item.icon}</Text>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
              <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{item.label}</Text>
              <View style={{ backgroundColor: item.status === "enabled" ? c.success + "18" : c.warning + "18", borderRadius: t.radii.sm, paddingHorizontal: 6, paddingVertical: 1 }}>
                <Text style={{ fontSize: 10, fontWeight: "700", color: item.status === "enabled" ? c.success : c.warning }}>{item.status.toUpperCase()}</Text>
              </View>
            </View>
            <Text style={{ fontSize: 12, color: c.textMuted, marginTop: 1 }}>{item.desc}</Text>
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
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>Security Report</Text>
      </Pressable>
    </ScrollView>
  )
}
