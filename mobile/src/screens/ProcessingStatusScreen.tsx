import React, { useEffect, useState, useRef, useCallback } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getDocumentLibrary, getIngestStatus, retryIngest } from "../api/client"
import { AnimatedRobot } from "../components/AnimatedRobot"

interface ProcessingItem {
  id: string
  filename: string
  status: string
  processing_state: string
  step: string
  percent: number
  message: string
  error_message?: string
  elapsed: number
  pause_requested?: boolean
  cancel_requested?: boolean
  retry_count?: number
}

function stepLabel(step: string): string {
  const map: Record<string, string> = {
    uploaded: "Uploaded",
    queued: "Queued",
    dequeued: "Dequeued",
    extract: "Extracting",
    chunk: "Chunking",
    embed: "Embedding",
    summarize: "Summarizing",
    done: "Complete",
    failed: "Failed",
  }
  return map[step?.toLowerCase()] || step || "—"
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

function getStatusColor(ps: string, colors: any): string {
  const s = ps.toUpperCase()
  if (s === "COMPLETED") return colors.success
  if (s === "PROCESSING" || s === "QUEUED" || s === "UPLOADED" || s === "RESUMED") return colors.warning
  if (s === "FAILED" || s === "CANCELLED") return colors.error
  if (s === "PAUSED") return colors.info || colors.accent
  return colors.textMuted
}

export function ProcessingStatusScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [items, setItems] = useState<ProcessingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actioning, setActioning] = useState<Record<string, boolean>>({})
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const startTimes = useRef<Record<string, number>>({})

  const PAGE_SIZE = 20

  const fetchStatus = useCallback(async () => {
    try {
      setError(null)
      setLoading(true)

      const res = await getDocumentLibrary({ page: String(page), page_size: String(PAGE_SIZE) })
      const docs = res.documents || res.items || []
      setTotal(res.total || docs.length)
      const now = Date.now()

      const statuses = await Promise.allSettled(
        docs.map(async (doc: any) => {
          if (!startTimes.current[doc.id]) {
            startTimes.current[doc.id] = now
          }
          try {
            const st = await getIngestStatus(doc.id)
            return {
              id: doc.id,
              filename: doc.filename,
              status: st.status || doc.status || "unknown",
              processing_state: st.processing_state || st.status?.toUpperCase() || "UPLOADED",
              step: st.step || st.status || "—",
              percent: st.percent ?? 0,
              message: st.message || "",
              error_message: st.error_message,
              pause_requested: st.pause_requested,
              cancel_requested: st.cancel_requested,
              retry_count: st.retry_count,
              elapsed: (now - (startTimes.current[doc.id] || now)) / 1000,
            }
          } catch {
            return {
              id: doc.id,
              filename: doc.filename,
              status: doc.status || "unknown",
              processing_state: "UPLOADED",
              step: "—",
              percent: 0,
              message: "",
              elapsed: (now - (startTimes.current[doc.id] || now)) / 1000,
            }
          }
        }),
      )

      const newItems = statuses
        .filter((s): s is PromiseFulfilledResult<ProcessingItem> => s.status === "fulfilled")
        .map((s) => s.value)

      newItems.sort((a, b) => {
        if ((a.processing_state === "PROCESSING" || a.processing_state === "QUEUED" || a.processing_state === "UPLOADED") &&
            !(b.processing_state === "PROCESSING" || b.processing_state === "QUEUED" || b.processing_state === "UPLOADED")) return -1
        if (!(a.processing_state === "PROCESSING" || a.processing_state === "QUEUED" || a.processing_state === "UPLOADED") &&
            (b.processing_state === "PROCESSING" || b.processing_state === "QUEUED" || b.processing_state === "UPLOADED")) return 1
        return b.elapsed - a.elapsed
      })

      setItems(newItems)
    } catch (err: any) {
      setError(err.message || "Failed to fetch processing status")
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  // Auto-refresh while items are processing
  useEffect(() => {
    const hasProcessing = items.some(
      (d) => d.processing_state === "PROCESSING" || d.processing_state === "QUEUED" || d.processing_state === "UPLOADED",
    )
    if (!hasProcessing) return
    const interval = setInterval(fetchStatus, 3000)
    return () => clearInterval(interval)
  }, [items, fetchStatus])

  const handleRetry = async (docId: string) => {
    try {
      setActioning((prev) => ({ ...prev, [`${docId}:retry`]: true }))
      await retryIngest(docId)
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || "Retry failed")
    } finally {
      setActioning((prev) => ({ ...prev, [`${docId}:retry`]: false }))
    }
  }

  const hasProcessing = items.some(
    (d) => d.processing_state === "PROCESSING" || d.processing_state === "QUEUED" || d.processing_state === "UPLOADED",
  )

  const allDone = items.length > 0 && items.every(
    (d) => d.processing_state === "COMPLETED" || d.processing_state === "FAILED" || d.processing_state === "CANCELLED",
  )

  const totalPages = Math.ceil(total / PAGE_SIZE)

  if (loading && items.length === 0) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <AnimatedRobot size={100} state="processing" />
        <Text style={{ marginTop: 16, color: c.textMuted, fontSize: 14 }}>Loading processing status...</Text>
      </View>
    )
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.bg }}
      contentContainerStyle={{
        padding: isTablet ? 24 : 16,
        paddingBottom: 40,
        maxWidth: isTablet ? 800 : undefined,
        alignSelf: "center",
        width: "100%",
      }}
    >
      {/* Page Header */}
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12, marginBottom: 20 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, letterSpacing: -0.3 }}>Processing Status</Text>
          <Text style={{ fontSize: 13, color: c.textSecondary, marginTop: 2 }}>Real-time ingest and processing status for your documents</Text>
        </View>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          {hasProcessing && (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
              <View style={{
                width: 8, height: 8, borderRadius: 4,
                backgroundColor: c.warning,
              }} />
              <Text style={{ fontSize: 11, color: c.warning, fontWeight: "600" }}>Auto-refreshing</Text>
            </View>
          )}
          <Pressable
            onPress={fetchStatus}
            disabled={loading}
            style={{
              paddingVertical: 8,
              paddingHorizontal: 14,
              borderRadius: 8,
              borderWidth: 1,
              borderColor: c.border,
            }}
          >
            <Text style={{ fontSize: 12, fontWeight: "600", color: c.textSecondary }}>
              {loading ? "Loading…" : "↻ Refresh"}
            </Text>
          </Pressable>
        </View>
      </View>

      {/* Error banner */}
      {error && (
        <View style={{
          backgroundColor: c.error + "14",
          borderRadius: 12,
          padding: 12,
          marginBottom: 16,
          borderWidth: 1,
          borderColor: c.error + "28",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}>
          <Text style={{ color: c.error, fontSize: 13, flex: 1 }}>{error}</Text>
          <Pressable onPress={() => setError(null)} style={{ marginLeft: 12 }}>
            <Text style={{ color: c.error, fontWeight: "600", fontSize: 12 }}>Dismiss</Text>
          </Pressable>
        </View>
      )}

      {/* Loading skeleton */}
      {loading && items.length > 0 && (
        <View style={{ gap: 10, marginBottom: 16 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <View key={i} style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 16,
              opacity: 0.5,
            }}>
              <View style={{ width: "40%", height: 14, borderRadius: 6, backgroundColor: c.surface, marginBottom: 10 }} />
              <View style={{ width: "60%", height: 14, borderRadius: 6, backgroundColor: c.surface }} />
            </View>
          ))}
        </View>
      )}

      {/* All done state */}
      {!loading && allDone && (
        <View style={{
          backgroundColor: c.cardBg,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: c.border,
          padding: 32,
          alignItems: "center",
        }}>
          <View style={{
            width: 56,
            height: 56,
            borderRadius: 28,
            backgroundColor: c.success + "18",
            borderWidth: 2,
            borderColor: c.success,
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 16,
          }}>
            <Text style={{ color: c.success, fontSize: 28 }}>✓</Text>
          </View>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: 4 }}>All documents processed</Text>
          <Text style={{ fontSize: 13, color: c.textSecondary }}>
            {items.length} document{items.length !== 1 ? "s" : ""} fully processed.
          </Text>
        </View>
      )}

      {/* Empty state */}
      {!loading && items.length === 0 && (
        <View style={{
          backgroundColor: c.cardBg,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: c.border,
          padding: 48,
          alignItems: "center",
        }}>
          <Text style={{ fontSize: 40, marginBottom: 12 }}>📋</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: 8 }}>No processing activity yet</Text>
          <Text style={{ fontSize: 13, color: c.textSecondary, textAlign: "center" }}>Upload documents to see their processing status here.</Text>
        </View>
      )}

      {/* Document list */}
      {items.length > 0 && !allDone && (
        <View style={{ gap: 8 }}>
          {items.map((doc) => {
            const ps = doc.processing_state
            const color = getStatusColor(ps, c)
            const isFailed = ps === "FAILED"
            const isProcessing = ps === "PROCESSING" || ps === "QUEUED" || ps === "UPLOADED" || ps === "RESUMED"
            const isPaused = ps === "PAUSED"
            const isCompleted = ps === "COMPLETED"
            const isCancelled = ps === "CANCELLED"
            const canRetry = isFailed

            return (
              <View key={doc.id} style={{
                backgroundColor: c.cardBg,
                borderRadius: 12,
                borderWidth: 1,
                borderColor: c.border,
                padding: 14,
              }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                  {/* Status icon */}
                  <View style={{ width: 24, alignItems: "center" }}>
                    <Text style={{ fontSize: 16 }}>
                      {isFailed || isCancelled ? "❌" : isCompleted ? "✅" : isPaused ? "⏸" : isProcessing ? "🔄" : "📄"}
                    </Text>
                  </View>

                  {/* Info */}
                  <View style={{ flex: 1, minWidth: 0 }}>
                    {/* File name + status badge row */}
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                      <Text style={{ fontWeight: "600", color: c.text, fontSize: 14, flex: 1 }} numberOfLines={1}>
                        {doc.filename}
                      </Text>
                      <View style={{
                        backgroundColor: color + "18",
                        borderRadius: 999,
                        paddingHorizontal: 8,
                        paddingVertical: 2,
                        borderWidth: 1,
                        borderColor: color + "36",
                      }}>
                        <Text style={{ fontSize: 10, fontWeight: "700", color }}>● {ps}</Text>
                      </View>
                      <Text style={{ fontSize: 11, color: c.textMuted }}>
                        {formatElapsed(doc.elapsed)}
                      </Text>
                      {(doc.retry_count ?? 0) > 0 && (
                        <Text style={{ fontSize: 10, color: c.textMuted }}>retry #{doc.retry_count}</Text>
                      )}
                    </View>

                    {/* Progress bar + step */}
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                      <View style={{
                        flex: 1,
                        height: 4,
                        borderRadius: 999,
                        backgroundColor: c.surface,
                        overflow: "hidden",
                        maxWidth: 200,
                      }}>
                        <View style={{
                          height: "100%",
                          borderRadius: 999,
                          backgroundColor: color,
                          width: `${Math.min(100, Math.max(0, doc.percent))}%`,
                        }} />
                      </View>
                      <Text style={{ fontSize: 11, color: c.textSecondary }}>
                        {Math.round(doc.percent)}%
                      </Text>
                      <Text style={{ fontSize: 11, color: c.textMuted }}>
                        {stepLabel(doc.step)}
                      </Text>
                    </View>

                    {/* Error message */}
                    {doc.error_message && (
                      <Text style={{ fontSize: 11, color: c.error, marginTop: 4 }}>{doc.error_message}</Text>
                    )}
                  </View>

                  {/* Action buttons */}
                  <View style={{ gap: 4 }}>
                    {canRetry && (
                      <Pressable
                        onPress={() => handleRetry(doc.id)}
                        disabled={actioning[`${doc.id}:retry`]}
                        style={{
                          paddingVertical: 4,
                          paddingHorizontal: 10,
                          borderRadius: 6,
                          borderWidth: 1,
                          borderColor: c.error + "40",
                          opacity: actioning[`${doc.id}:retry`] ? 0.5 : 1,
                        }}
                      >
                        <Text style={{ color: c.error, fontSize: 11, fontWeight: "600" }}>
                          {actioning[`${doc.id}:retry`] ? "…" : "Retry"}
                        </Text>
                      </Pressable>
                    )}
                  </View>
                </View>
              </View>
            )
          })}
        </View>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <View style={{ flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 12, marginTop: 20 }}>
          <Pressable
            onPress={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{
              paddingVertical: 8,
              paddingHorizontal: 14,
              borderRadius: 8,
              borderWidth: 1,
              borderColor: c.border,
              opacity: page <= 1 ? 0.4 : 1,
            }}
          >
            <Text style={{ fontSize: 13, color: c.text }}>← Prev</Text>
          </Pressable>
          <Text style={{ fontSize: 12, color: c.textMuted }}>Page {page} of {totalPages}</Text>
          <Pressable
            onPress={() => setPage((p) => p + 1)}
            disabled={page >= totalPages}
            style={{
              paddingVertical: 8,
              paddingHorizontal: 14,
              borderRadius: 8,
              borderWidth: 1,
              borderColor: c.border,
              opacity: page >= totalPages ? 0.4 : 1,
            }}
          >
            <Text style={{ fontSize: 13, color: c.text }}>Next →</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  )
}
