import React, { useEffect, useState } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getMyDocuments, getProcessingStatus, retryIngest } from "../api/client"

interface ProcessingItem {
  id: string
  filename: string
  status: string
  percent: number
  message: string
  step: string
}

export function ProcessingStatusScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const statusBadgeColors: Record<string, string> = {
    completed: c.success + "18",
    processing: c.warning + "18",
    queued: c.primary + "14",
    failed: c.error + "14",
    pending: c.accent + "18",
  }

  const statusTextColors: Record<string, string> = {
    completed: c.success,
    processing: c.warning,
    queued: c.primary,
    failed: c.error,
    pending: c.accent,
  }

  const [items, setItems] = useState<ProcessingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 3000)
    return () => clearInterval(interval)
  }, [])

  const fetchStatus = async () => {
    try {
      setError("")
      const docsRes = await getMyDocuments()
      const docs = docsRes?.documents || []
      const statusPromises = docs.map(async (doc: any) => {
        try {
          const status = await getProcessingStatus(doc.id)
          return {
            id: doc.id,
            filename: doc.filename,
            status: status?.status || doc.status,
            percent: status?.percent ?? 0,
            message: status?.message || "",
            step: status?.current_step || status?.message || "",
          }
        } catch {
          return {
            id: doc.id,
            filename: doc.filename,
            status: doc.status || "unknown",
            percent: 0,
            message: "",
            step: "",
          }
        }
      })
      const results = await Promise.all(statusPromises)
      setItems(results)
    } catch (err: any) {
      setError(err.message || "Failed to load statuses")
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = async (docId: string) => {
    try {
      await retryIngest(docId)
      fetchStatus()
    } catch (err: any) {
      setError(err.message || "Retry failed")
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading processing status...</Text>
      </View>
    )
  }

  const allDone = items.length > 0 && items.every((item) => item.status === "completed")

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl, maxWidth: isTablet ? 800 : undefined, alignSelf: "center" }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.md }}>
        <Text style={{ fontSize: 24, fontWeight: "800", color: c.text }}>
          Processing Status
        </Text>
        <Pressable onPress={fetchStatus} style={{ padding: t.spacing.xs }}>
          <Text style={{ fontSize: 14, color: c.primary, fontWeight: "600" }}>Refresh</Text>
        </Pressable>
      </View>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {allDone ? (
        <View style={{ backgroundColor: c.success + "18", borderRadius: t.radii.sm, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.success + "28" }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>✅</Text>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.success }}>
            All documents processed
          </Text>
          <Text style={{ fontSize: 13, color: c.success, marginTop: t.spacing.xs }}>
            {items.length} document{items.length !== 1 ? "s" : ""} ready for analysis
          </Text>
        </View>
      ) : items.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.sm, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>📭</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
            No documents to process
          </Text>
          <Text style={{ fontSize: 13, color: c.textMuted }}>Upload documents to begin</Text>
        </View>
      ) : (
        <View style={{ flexDirection: isTablet ? "row" : "column", flexWrap: isTablet ? "wrap" : undefined, gap: t.spacing.sm }}>
          {items.map((item) => (
            <View
              key={item.id}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: t.radii.sm,
                padding: t.spacing.sm,
                marginBottom: isTablet ? 0 : 10,
                width: isTablet ? "48%" : "100%",
                borderWidth: 1,
                borderColor: c.border,
              }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.xs }}>
                <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, flex: 1 }} numberOfLines={1}>
                  📄 {item.filename}
                </Text>
                <View
                  style={{
                    backgroundColor: statusBadgeColors[item.status] || c.primary + "14",
                    borderRadius: t.radii.sm,
                    paddingHorizontal: t.spacing.sm,
                    paddingVertical: 3,
                    marginLeft: t.spacing.xs,
                  }}
                >
                  <Text style={{ fontSize: 11, color: statusTextColors[item.status] || c.primary, fontWeight: "600" }}>
                    {item.status}
                  </Text>
                </View>
              </View>

              <View style={{ backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, height: 8, marginBottom: 6, overflow: "hidden" }}>
                <View
                  style={{
                    backgroundColor: item.status === "failed" ? c.error : c.primary,
                    height: "100%",
                    width: `${Math.min(item.percent, 100)}%`,
                    borderRadius: t.radii.sm,
                  }}
                />
              </View>

              {item.step ? (
                <Text style={{ fontSize: 11, color: c.textMuted, marginBottom: t.spacing.xs }}>{item.step}</Text>
              ) : null}

              {item.status === "failed" && (
                <Pressable
                  onPress={() => handleRetry(item.id)}
                  style={{
                    backgroundColor: c.error + "14",
                    borderRadius: t.radii.sm,
                    paddingVertical: t.spacing.xs,
                    paddingHorizontal: t.spacing.sm,
                    alignSelf: "flex-start",
                    marginTop: t.spacing.xs,
                  }}
                >
                  <Text style={{ color: c.error, fontWeight: "600", fontSize: 12 }}>Retry</Text>
                </Pressable>
              )}
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  )
}