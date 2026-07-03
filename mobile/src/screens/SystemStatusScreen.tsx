import React, { useEffect, useState } from "react"
import { View, Text, ScrollView, Pressable, RefreshControl, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getBootstrapStatus, getIngestStatus } from "../api/client"

interface StatusItem {
  name: string
  status: "ready" | "pending" | "failed"
  details?: string
  progress?: number
}

interface SystemStatusScreenProps {
  onBack?: () => void
}

export function SystemStatusScreen({ onBack }: SystemStatusScreenProps) {
  const [status, setStatus] = useState<StatusItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState("")
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  useEffect(() => {
    loadStatus()
  }, [])

  const loadStatus = async () => {
    try {
      setError("")
      const [bootstrapRes] = await Promise.all([
        getBootstrapStatus().catch(() => ({})),
      ])

      const items: StatusItem[] = []

      if (bootstrapRes.status) {
        items.push({
          name: "🔧 Bootstrap",
          status: bootstrapRes.status === "completed" ? "ready" : "pending",
          details: bootstrapRes.message || bootstrapRes.status,
          progress: bootstrapRes.progress,
        })
      }

      if (bootstrapRes.models_loaded !== undefined) {
        items.push({
          name: "🤖 Models",
          status: bootstrapRes.models_loaded ? "ready" : "pending",
          details: bootstrapRes.models_loaded
            ? "All models loaded"
            : "Loading models...",
        })
      }

      if (bootstrapRes.rag_ready !== undefined) {
        items.push({
          name: "📚 Vector Store",
          status: bootstrapRes.rag_ready ? "ready" : "pending",
          details: bootstrapRes.rag_ready
            ? "Ready for queries"
            : "Initializing...",
        })
      }

      if (items.length === 0) {
        items.push({
          name: "ℹ️ System Status",
          status: "ready",
          details: "All systems operational",
        })
      }

      setStatus(items)
    } catch (e: any) {
      setError(e.message || "Failed to load system status")
      console.error("Status load error:", e)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadStatus()
    setRefreshing(false)
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <View
        style={{
          paddingHorizontal: t.spacing.md,
          paddingVertical: t.spacing.sm,
          borderBottomWidth: 1,
          borderBottomColor: c.border,
          backgroundColor: c.cardBg,
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "700", color: c.text }}>
          🔧 System Status
        </Text>
        {onBack && (
          <Pressable onPress={onBack}>
            <Text style={{ fontSize: 14, color: c.primary }}>← Back</Text>
          </Pressable>
        )}
      </View>

      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
        contentContainerStyle={{ paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm }}
      >
        {error && (
          <View
            style={{
              backgroundColor: c.error + "14",
              borderRadius: t.radii.md,
              padding: t.spacing.sm,
              marginBottom: t.spacing.sm,
            }}
          >
            <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
          </View>
        )}

        {loading ? (
          <View style={{ alignItems: "center", marginTop: t.spacing.xl }}>
            <ActivityIndicator size="large" color={c.primary} />
            <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading status...</Text>
          </View>
        ) : (
          <View style={{ flexDirection: isTablet ? "row" : "column", flexWrap: isTablet ? "wrap" : "nowrap", gap: t.spacing.sm }}>
            {status.map((item, idx) => (
              <View
                key={idx}
                style={{
                  backgroundColor: c.cardBg,
                  borderRadius: t.radii.md,
                  borderWidth: 1,
                  borderColor: c.border,
                  paddingHorizontal: t.spacing.sm,
                  paddingVertical: t.spacing.sm,
                  marginBottom: isTablet ? 0 : t.spacing.sm,
                  width: isTablet ? "48%" : "100%",
                }}
              >
                <View
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: t.spacing.sm,
                  }}
                >
                  <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>
                    {item.name}
                  </Text>
                  <View
                    style={{
                      paddingHorizontal: t.spacing.sm,
                      paddingVertical: t.spacing.xs,
                      borderRadius: t.radii.sm,
                      backgroundColor:
                        item.status === "ready"
                          ? c.success + "18"
                          : item.status === "pending"
                            ? c.warning + "18"
                            : c.error + "14",
                    }}
                  >
                    <Text
                      style={{
                        fontSize: 11,
                        fontWeight: "600",
                        color:
                          item.status === "ready"
                            ? c.success
                            : item.status === "pending"
                              ? c.warning
                              : c.error,
                      }}
                    >
                      {item.status === "ready"
                        ? "✓ Ready"
                        : item.status === "pending"
                          ? "⏳ Pending"
                          : "✗ Failed"}
                    </Text>
                  </View>
                </View>

                {item.details && (
                  <Text
                    style={{
                      fontSize: 12,
                      color: c.textMuted,
                      marginBottom: item.progress !== undefined ? t.spacing.sm : 0,
                    }}
                  >
                    {item.details}
                  </Text>
                )}

                {item.progress !== undefined && (
                  <View
                    style={{
                      backgroundColor: c.bgSecondary,
                      borderRadius: t.radii.sm,
                      height: 4,
                      overflow: "hidden",
                    }}
                  >
                    <View
                      style={{
                        height: 4,
                        backgroundColor: c.primary,
                        width: `${Math.min(item.progress, 100)}%`,
                      }}
                    />
                  </View>
                )}
              </View>
            ))}

            <View
              style={{
                backgroundColor: c.primary + "14",
                borderRadius: t.radii.md,
                borderWidth: 1,
                borderColor: c.primary + "28",
                paddingHorizontal: t.spacing.sm,
                paddingVertical: t.spacing.sm,
                marginTop: t.spacing.sm,
                width: isTablet ? "100%" : "100%",
              }}
            >
              <Text style={{ fontSize: 12, color: c.primary }}>
                ℹ️ System status is automatically checked when you log in. If you notice issues, try logging out and back in.
              </Text>
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  )
}