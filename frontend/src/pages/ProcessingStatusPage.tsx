import React, { useEffect, useState, useRef, useCallback } from "react"
import { getDocumentLibrary, getIngestStatus, retryIngest, pauseIngestion, resumeIngestion, restartIngestion, cancelIngestion } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { Pagination } from "../components/Pagination"

interface ProcDoc {
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

function processingStateColor(state: string): string {
  const s = state.toUpperCase()
  if (s === "COMPLETED") return "success"
  if (s === "PROCESSING" || s === "QUEUED" || s === "UPLOADED" || s === "RESUMED") return "warning"
  if (s === "FAILED" || s === "CANCELLED") return "error"
  if (s === "PAUSED" || s === "RETRYING") return "info"
  return "muted"
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

export const ProcessingStatusPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)

  const [documents, setDocuments] = useState<ProcDoc[]>([])
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
      const res = await getDocumentLibrary({ page, page_size: PAGE_SIZE })
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

      const newDocs = statuses
        .filter((s): s is PromiseFulfilledResult<ProcDoc> => s.status === "fulfilled")
        .map((s) => s.value)

      newDocs.sort((a, b) => {
        if (a.processing_state === "PROCESSING" && b.processing_state !== "PROCESSING") return -1
        if (a.processing_state !== "PROCESSING" && b.processing_state === "PROCESSING") return 1
        return b.elapsed - a.elapsed
      })

      setDocuments(newDocs)
    } catch (e: any) {
      setError(e.message ?? "Failed to fetch status")
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.processing_state === "PROCESSING" || d.processing_state === "QUEUED",
    )
    if (!hasProcessing) return
    const interval = setInterval(fetchStatus, 3000)
    return () => clearInterval(interval)
  }, [documents, fetchStatus])

  const handleAction = async (docId: string, action: string, fn: (id: string) => Promise<any>) => {
    try {
      setActioning((prev) => ({ ...prev, [`${docId}:${action}`]: true }))
      setError(null)
      await fn(docId)
      await fetchStatus()
    } catch (e: any) {
      setError(e.message ?? `${action} failed`)
    } finally {
      setActioning((prev) => ({ ...prev, [`${docId}:${action}`]: false }))
    }
  }

  const hasProcessing = documents.some(
    (d) => d.processing_state === "PROCESSING" || d.processing_state === "QUEUED",
  )

  const allDone = documents.length > 0 && documents.every(
    (d) => d.processing_state === "COMPLETED" || d.processing_state === "FAILED" || d.processing_state === "CANCELLED",
  )

  const pageContainer: React.CSSProperties = {
    padding: t.spacing.xl,
    maxWidth: 1200,
    margin: "0 auto",
  }

  const pageTitle: React.CSSProperties = {
    fontSize: 28,
    fontWeight: 800,
    color: t.colors.text,
    margin: 0,
    letterSpacing: "-0.02em",
  }

  const subtitle: React.CSSProperties = {
    margin: "4px 0 0",
    fontSize: 14,
    color: t.colors.textSecondary,
  }

  const card: React.CSSProperties = {
    background: t.colors.cardBg,
    borderRadius: 12,
    border: `1px solid ${t.colors.border}`,
    padding: "16px 20px",
    backdropFilter: "blur(10px)",
  }

  const btnGhost: React.CSSProperties = {
    background: "transparent",
    border: `1px solid ${t.colors.border}`,
    borderRadius: 8,
    padding: "6px 14px",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    color: t.colors.textSecondary,
  }

  const statusBadge: React.CSSProperties = (color: string) => ({
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "3px 10px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 700,
    backgroundColor: `${color}18`,
    border: `1px solid ${color}36`,
    color,
  })

  const progressBar: React.CSSProperties = {
    height: 4,
    borderRadius: 999,
    background: t.colors.surface,
    overflow: "hidden",
    width: "100%",
    maxWidth: 200,
  }

  const progressFill = (pct: number, color: string): React.CSSProperties => ({
    height: "100%",
    borderRadius: 999,
    background: color,
    transition: "width 0.5s ease",
    width: `${Math.min(100, Math.max(0, pct))}%`,
  })

  const getStatusColor = (ps: string): string => {
    const s = ps.toUpperCase()
    if (s === "COMPLETED") return t.colors.success
    if (s === "PROCESSING" || s === "QUEUED" || s === "UPLOADED" || s === "RESUMED") return t.colors.warning
    if (s === "FAILED" || s === "CANCELLED") return t.colors.error
    if (s === "PAUSED") return t.colors.info
    return t.colors.textMuted
  }

  return (
    <div style={pageContainer}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={pageTitle}>Processing Status</h1>
          <p style={subtitle}>
            Real-time ingest and processing status for your documents
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {hasProcessing && (
            <span style={{ fontSize: 12, color: t.colors.warning, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{
                width: 8, height: 8, borderRadius: "50%",
                backgroundColor: t.colors.warning,
                animation: "pulse 1.5s ease-in-out infinite",
              }} />
              Auto-refreshing
            </span>
          )}
          <button type="button" onClick={fetchStatus} disabled={loading} style={{ ...btnGhost, opacity: loading ? 0.6 : 1 }}>
            {loading ? "Loading…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          marginTop: 16, padding: "12px 16px", borderRadius: 12,
          background: `${t.colors.error}14`, border: `1px solid ${t.colors.error}28`,
          color: t.colors.error, fontSize: 13,
        }}>
          {error}
          <button type="button" onClick={() => setError(null)} style={{ ...btnGhost, marginLeft: 12, fontSize: 12, color: t.colors.error }}>
            Dismiss
          </button>
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        {loading ? (
          <div style={{ display: "grid", gap: 10 }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} style={{ ...card, height: 72, opacity: 0.5 }}>
                <div style={{ width: "40%", height: 14, borderRadius: 6, background: t.colors.surface, marginBottom: 10 }} />
                <div style={{ width: "60%", height: 14, borderRadius: 6, background: t.colors.surface }} />
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div style={{ ...card, textAlign: "center", padding: "48px 20px" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: t.colors.text, marginBottom: 8 }}>
              No processing activity yet
            </div>
            <div style={{ fontSize: 13, color: t.colors.textSecondary }}>
              Upload documents to see their processing status here.
            </div>
          </div>
        ) : allDone ? (
          <div style={{ ...card, textAlign: "center", padding: 32 }}>
            <div style={{
              width: 56, height: 56, borderRadius: "50%",
              background: `${t.colors.success}18`, border: `2px solid ${t.colors.success}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 16px",
            }}>
              <span style={{ color: t.colors.success, fontSize: 28 }}>✓</span>
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, color: t.colors.text, marginBottom: 4 }}>
              All documents processed
            </div>
            <div style={{ fontSize: 13, color: t.colors.textSecondary }}>
              {documents.length} document{documents.length !== 1 ? "s" : ""} fully processed.
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {documents.map((doc) => {
              const ps = doc.processing_state
              const color = getStatusColor(ps)
              const isFailed = ps === "FAILED"
              const isProcessing = ps === "PROCESSING" || ps === "QUEUED" || ps === "UPLOADED"
              const isPaused = ps === "PAUSED"
              const isCompleted = ps === "COMPLETED"
              const isCancelled = ps === "CANCELLED"

              const canPause = isProcessing
              const canResume = isPaused
              const canRestart = isCompleted || isFailed || isCancelled
              const canRetry = isFailed
              const canCancel = isProcessing || isPaused

              return (
                <div key={doc.id} style={{
                  ...card,
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  flexWrap: "wrap",
                }}>
                  <div style={{ width: 20, flexShrink: 0, textAlign: "center", fontSize: 16 }}>
                    {isFailed || isCancelled ? "❌" : isCompleted ? "✅" : isPaused ? "⏸" : "📄"}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 6 }}>
                      <span style={{ fontWeight: 600, color: t.colors.text, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {doc.filename}
                      </span>
                      <span style={statusBadge(color)}>● {ps}</span>
                      <span style={{ fontSize: 12, color: t.colors.textMuted }}>
                        {formatElapsed(doc.elapsed)}
                      </span>
                      {(doc.retry_count ?? 0) > 0 && (
                        <span style={{ fontSize: 11, color: t.colors.textMuted }}>
                          retry #{doc.retry_count}
                        </span>
                      )}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={progressBar}>
                        <div style={progressFill(doc.percent, color)} />
                      </div>
                      <span style={{ fontSize: 12, color: t.colors.textSecondary, whiteSpace: "nowrap" }}>
                        {Math.round(doc.percent)}%
                      </span>
                      <span style={{ fontSize: 12, color: t.colors.textMuted, whiteSpace: "nowrap" }}>
                        {stepLabel(doc.step)}
                      </span>
                    </div>
                    {doc.error_message && (
                      <div style={{ fontSize: 12, color: t.colors.error, marginTop: 4 }}>
                        {doc.error_message}
                      </div>
                    )}
                  </div>

                  {/* ── Control Buttons ── */}
                  <div style={{ display: "flex", gap: 6, flexShrink: 0, flexWrap: "wrap" }}>
                    {canPause && (
                      <button
                        type="button"
                        onClick={() => handleAction(doc.id, "pause", pauseIngestion)}
                        disabled={actioning[`${doc.id}:pause`]}
                        style={{ ...btnGhost, color: t.colors.info, borderColor: `${t.colors.info}40`, opacity: actioning[`${doc.id}:pause`] ? 0.5 : 1 }}
                      >
                        {actioning[`${doc.id}:pause`] ? "…" : "⏸ Pause"}
                      </button>
                    )}
                    {canResume && (
                      <button
                        type="button"
                        onClick={() => handleAction(doc.id, "resume", resumeIngestion)}
                        disabled={actioning[`${doc.id}:resume`]}
                        style={{ ...btnGhost, color: t.colors.success, borderColor: `${t.colors.success}40`, opacity: actioning[`${doc.id}:resume`] ? 0.5 : 1 }}
                      >
                        {actioning[`${doc.id}:resume`] ? "…" : "▶ Resume"}
                      </button>
                    )}
                    {canRestart && (
                      <button
                        type="button"
                        onClick={() => handleAction(doc.id, "restart", restartIngestion)}
                        disabled={actioning[`${doc.id}:restart`]}
                        style={{ ...btnGhost, color: t.colors.warning, borderColor: `${t.colors.warning}40`, opacity: actioning[`${doc.id}:restart`] ? 0.5 : 1 }}
                      >
                        {actioning[`${doc.id}:restart`] ? "…" : "↻ Restart"}
                      </button>
                    )}
                    {canRetry && (
                      <button
                        type="button"
                        onClick={() => handleAction(doc.id, "retry", retryIngest)}
                        disabled={actioning[`${doc.id}:retry`]}
                        style={{ ...btnGhost, color: t.colors.warning, borderColor: `${t.colors.warning}40`, opacity: actioning[`${doc.id}:retry`] ? 0.5 : 1 }}
                      >
                        {actioning[`${doc.id}:retry`] ? "…" : "↺ Retry"}
                      </button>
                    )}
                    {canCancel && (
                      <button
                        type="button"
                        onClick={() => handleAction(doc.id, "cancel", cancelIngestion)}
                        disabled={actioning[`${doc.id}:cancel`]}
                        style={{ ...btnGhost, color: t.colors.error, borderColor: `${t.colors.error}40`, opacity: actioning[`${doc.id}:cancel`] ? 0.5 : 1 }}
                      >
                        {actioning[`${doc.id}:cancel`] ? "…" : "✕ Cancel"}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
        <Pagination page={page} totalPages={Math.ceil(total / PAGE_SIZE) || 1} total={total} onPageChange={setPage} />
      </div>
    </div>
  )
}
