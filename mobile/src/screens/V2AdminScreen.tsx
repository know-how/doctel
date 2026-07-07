import React, { useEffect, useState } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { useModel } from "../context/ModelContext"
import { v2GetHealth, v2GetRoutingStatus, v2ListProviders } from "../api/client"
import type { V2HealthResponse, V2RoutingStatusResponse } from "../types/api"

export function V2AdminScreen({ onNavigate }: { onNavigate?: (path: string) => void }) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const { v2Providers, v2AutoRouting } = useModel()

  const [health, setHealth] = useState<V2HealthResponse | null>(null)
  const [routing, setRouting] = useState<V2RoutingStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError("")
      const [healthRes, routingRes] = await Promise.all([
        v2GetHealth().catch(() => null),
        v2GetRoutingStatus().catch(() => null),
      ])
      if (healthRes) setHealth(healthRes)
      if (routingRes) setRouting(routingRes)
    } catch (err: any) {
      setError(err.message || "Failed to load V2 dashboard")
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: 12, color: c.textMuted }}>Loading V2 dashboard...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Model Management v2
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {/* Health Summary */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>🩺 Health Summary</Text>
        {health ? (
          <View>
            <HealthRow label="Total Providers" value={String(v2Providers.length)} c={c} t={t} />
            <HealthRow label="Total Requests" value={String(health.system?.totalRequests ?? "—")} c={c} t={t} />
            <HealthRow label="Success Rate" value={health.system?.successRate != null ? `${(health.system.successRate * 100).toFixed(1)}%` : "—"} c={c} t={t} />
            <HealthRow label="Avg Latency" value={health.system?.avgLatencyMs != null ? `${health.system.avgLatencyMs}ms` : "—"} c={c} t={t} />
            {health.system?.lastChecked ? (
              <HealthRow label="Last Checked" value={new Date(health.system.lastChecked).toLocaleString()} c={c} t={t} />
            ) : null}
          </View>
        ) : (
          <Text style={{ color: c.textMuted, fontSize: 13 }}>No health data available</Text>
        )}
      </View>

      {/* Auto-Routing Status */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>🔀 Auto-Routing</Text>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <Text style={{ color: c.text, fontSize: 14 }}>
            Status:{" "}
            <Text style={{ fontWeight: "700", color: routing?.automaticRouting ?? v2AutoRouting ? c.success : c.error }}>
              {routing?.automaticRouting ?? v2AutoRouting ? "Enabled" : "Disabled"}
            </Text>
          </Text>
          <View
            style={{
              width: 12,
              height: 12,
              borderRadius: 6,
              backgroundColor: routing?.automaticRouting ?? v2AutoRouting ? c.success : c.error,
            }}
          />
        </View>
      </View>

      {/* Providers Summary */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>🏪 Providers</Text>
        {v2Providers.length > 0 ? (
          v2Providers.map((p, i) => (
            <View
              key={p.id || i}
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                paddingVertical: t.spacing.xs,
                borderBottomWidth: i < v2Providers.length - 1 ? 1 : 0,
                borderBottomColor: c.border,
              }}
            >
              <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
                <Text style={{ fontSize: 16 }}>{p.icon || "🏪"}</Text>
                <Text style={{ color: c.text, fontSize: 14, fontWeight: "600" }}>{p.name}</Text>
              </View>
              <Text style={{ color: c.textMuted, fontSize: 12 }}>
                {p.models?.length ?? 0} models
              </Text>
            </View>
          ))
        ) : (
          <Text style={{ color: c.textMuted, fontSize: 13 }}>No providers configured</Text>
        )}
      </View>

      {/* Quick Links */}
      <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>Quick Links</Text>
      <View style={{ flexDirection: isTablet ? "row" : "column", gap: t.spacing.sm }}>
        {[
          { label: "📦 Model Catalog", path: "/admin/v2" },
          { label: "🏪 Providers", path: "/admin/v2/providers" },
          { label: "🔀 Task Mapping", path: "/admin/v2/task-mapping" },
        ].map((link) => (
          <Pressable
            key={link.label}
            onPress={() => onNavigate?.(link.path)}
            style={{
              flex: isTablet ? 1 : undefined,
              backgroundColor: c.cardBg,
              borderRadius: t.radii.md,
              padding: t.spacing.md,
              borderWidth: 1,
              borderColor: c.border,
            }}
          >
            <Text style={{ fontSize: 15, fontWeight: "600", color: c.text }}>{link.label}</Text>
          </Pressable>
        ))}
      </View>
    </ScrollView>
  )
}

function HealthRow({ label, value, c, t }: { label: string; value: string; c: any; t: any }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 }}>
      <Text style={{ color: c.textMuted, fontSize: 13 }}>{label}</Text>
      <Text style={{ color: c.text, fontSize: 13, fontWeight: "600" }}>{value}</Text>
    </View>
  )
}
