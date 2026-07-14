import React, { useEffect, useState, useCallback } from "react"
import {
  getEmbeddingStatus,
  getEmbeddingMismatches,
  reembedDocument,
  reembedMismatched,
  reembedAll,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { GlassPanel } from "../components/styled"
import type {
  EmbeddingStatusResponse,
  EmbeddingMismatchItem,
  ReembedBulkResponse,
} from "../types/api"

/* ─────────────────────────────────────────────────────────────
   Styles
   ───────────────────────────────────────────────────────────── */

const badgeStyle = (color: string, bgColor: string) => ({
  display: "inline-flex" as const,
  alignItems: "center",
  gap: 4,
  padding: "2px 8px",
  borderRadius: 9999,
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.3px",
  color,
  backgroundColor: bgColor,
  border: `1px solid ${color}33`,
})

const stateColors: Record<string, string> = {
  embedded: "#22C55E",
  pending: "#F59E0B",
  re_embed_required: "#EF4444",
  mismatch: "#F97316",
  ok: "#22C55E",
  error: "#EF4444",
}

/* ─────────────────────────────────────────────────────────────
   Sub-components
   ───────────────────────────────────────────────────────────── */

const StatusBadge: React.FC<{ label: string; colorKey: string }> = ({ label, colorKey }) => {
  const color = stateColors[colorKey] || "#9CA3AF"
  return <span style={badgeStyle(color, color + "18")}>{label}</span>
}

interface StatCardProps {
  label: string
  value: number | string
  color: string
  icon: string
}

const StatCard: React.FC<StatCardProps> = ({ label, value, color, icon }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  return (
    <GlassPanel
      variant="low"
      style={{
        padding: t.spacing.md,
        display: "flex",
        flexDirection: "column",
        gap: 4,
        minWidth: 140,
      }}
    >
      <div style={{ fontSize: 22 }}>{icon}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div style={{ fontSize: 11, color: c.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.3px" }}>
        {label}
      </div>
    </GlassPanel>
  )
}

/* ─────────────────────────────────────────────────────────────
   Main Page Component
   ───────────────────────────────────────────────────────────── */

export const AdminEmbeddingGovernancePage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  // ── State ──
  const [status, setStatus] = useState<EmbeddingStatusResponse | null>(null)
  const [mismatches, setMismatches] = useState<EmbeddingMismatchItem[]>([])
  const [mismatchesTotal, setMismatchesTotal] = useState(0)
  const [configuredInfo, setConfiguredInfo] = useState<{ provider: string; model: string; version: string } | null>(null)

  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null) // doc id or "bulk" or "all"
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // ── Data fetching ──
  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [statusData, mismatchesData] = await Promise.all([
        getEmbeddingStatus(),
        getEmbeddingMismatches(),
      ])
      setStatus(statusData)
      setMismatches(mismatchesData.documents)
      setMismatchesTotal(mismatchesData.total)
      setConfiguredInfo(mismatchesData.configured)
    } catch (err: any) {
      setError(err?.message || "Failed to load embedding governance data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ── Actions ──
  const handleReembedSingle = async (docId: number) => {
    setActionLoading(`doc-${docId}`)
    setError(null)
    setSuccessMsg(null)
    try {
      const result = await reembedDocument(docId)
      if (result.success) {
        if (result.chunks_reembedded === 0) {
          setError(`Document #${docId} re-embedded but has 0 chunks. The document may have no extractable text. Check the ingestion logs.`)
        } else {
          setSuccessMsg(`Document #${docId} re-embedded successfully (${result.chunks_reembedded} chunks)`)
        }
        await fetchData()
      } else {
        // Show detailed error for failed re-embed
        const errorMsg = result.error || `Failed to re-embed document #${docId}`
        if (errorMsg.includes("no chunks") || errorMsg.includes("no text")) {
          setError(`⚠️ ${errorMsg}\n\nRecommendation: Check if the original document ingestion completed successfully. You may need to re-upload the document.`)
        } else {
          setError(errorMsg)
        }
      }
    } catch (err: any) {
      setError(err?.message || `Error re-embedding document #${docId}`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleReembedMismatched = async () => {
    setActionLoading("bulk")
    setError(null)
    setSuccessMsg(null)
    try {
      const result: ReembedBulkResponse = await reembedMismatched()
      if (result.success) {
        setSuccessMsg(`Re-embedded ${result.reembedded.length} mismatched document(s)`)
        await fetchData()
      } else {
        setError("Bulk re-embed reported failure")
      }
    } catch (err: any) {
      setError(err?.message || "Error during bulk re-embed")
    } finally {
      setActionLoading(null)
    }
  }

  const handleReembedAll = async () => {
    if (!window.confirm("Are you sure you want to re-embed ALL documents? This may take a while.")) {
      return
    }
    setActionLoading("all")
    setError(null)
    setSuccessMsg(null)
    try {
      const result: ReembedBulkResponse = await reembedAll()
      if (result.success) {
        setSuccessMsg(`Re-embedded all ${result.reembedded.length} document(s)`)
        await fetchData()
      } else {
        setError("Full re-embed reported failure")
      }
    } catch (err: any) {
      setError(err?.message || "Error during full re-embed")
    } finally {
      setActionLoading(null)
    }
  }

  // ── Helpers ──
  const fmtDate = (d: string | null) => {
    if (!d) return "—"
    try {
      return new Date(d).toLocaleString()
    } catch {
      return d
    }
  }

  // ── Render ──
  if (loading && !status) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: c.textMuted }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <div>Loading embedding governance data…</div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: t.spacing.lg, display: "flex", flexDirection: "column", gap: t.spacing.lg, height: "100%", overflowY: "auto" }}>
      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: c.text }}>
            🧩 Embedding Governance
          </h2>
          <div style={{ fontSize: 12, color: c.textMuted, marginTop: 2 }}>
            Monitor and manage document embedding state across the system
          </div>
        </div>
        <button
          type="button"
          onClick={fetchData}
          disabled={loading}
          style={{
            padding: "6px 14px",
            borderRadius: 8,
            border: `1px solid ${c.border}`,
            background: c.surface,
            color: c.text,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {loading ? "⟳ Refreshing…" : "⟳ Refresh"}
        </button>
      </div>

      {/* ── Messages ── */}
      {error && (
        <div style={{
          padding: "10px 14px",
          borderRadius: 8,
          backgroundColor: "#EF4444" + "15",
          color: "#EF4444",
          border: "1px solid #EF4444" + "30",
          fontSize: 13,
          fontWeight: 600,
        }}>
          ❌ {error}
        </div>
      )}
      {successMsg && (
        <div style={{
          padding: "10px 14px",
          borderRadius: 8,
          backgroundColor: "#22C55E" + "15",
          color: "#22C55E",
          border: "1px solid #22C55E" + "30",
          fontSize: 13,
          fontWeight: 600,
        }}>
          ✅ {successMsg}
        </div>
      )}

      {/* ── Configured Model Info ── */}
      {configuredInfo && (
        <GlassPanel
          variant="low"
          style={{
            padding: t.spacing.md,
            display: "flex",
            alignItems: "center",
            gap: t.spacing.md,
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 700, color: c.text }}>🔧 Configured Embedding Model:</span>
          <StatusBadge label={configuredInfo.provider} colorKey="ok" />
          <span style={{ fontSize: 13, color: c.textSecondary }}>{configuredInfo.model}</span>
          <span style={{ fontSize: 11, color: c.textMuted }}>v{configuredInfo.version}</span>
        </GlassPanel>
      )}

      {/* ── Dashboard Stats ── */}
      {status && (
        <div style={{ display: "flex", gap: t.spacing.md, flexWrap: "wrap" }}>
          <StatCard label="Total Documents" value={status.total_documents} color={c.text} icon="📄" />
          <StatCard label="Embedded" value={status.embedded} color="#22C55E" icon="✅" />
          <StatCard label="Pending" value={status.pending} color="#F59E0B" icon="⏳" />
          <StatCard label="Version Mismatch" value={status.version_mismatch} color="#F97316" icon="🔄" />
          <StatCard label="Provider/Model Mismatch" value={status.provider_model_mismatch} color="#EF4444" icon="⚠️" />
        </div>
      )}

      {/* ── Bulk Actions ── */}
      <div style={{ display: "flex", gap: t.spacing.sm, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={handleReembedMismatched}
          disabled={actionLoading !== null || mismatches.length === 0}
          style={{
            padding: "8px 18px",
            borderRadius: 8,
            border: "none",
            background: mismatches.length > 0 ? "#F97316" : "#9CA3AF",
            color: "#fff",
            fontSize: 13,
            fontWeight: 700,
            cursor: mismatches.length > 0 ? "pointer" : "not-allowed",
            opacity: actionLoading === "bulk" ? 0.6 : 1,
          }}
        >
          {actionLoading === "bulk" ? "⟳ Re-embedding…" : `🔄 Re-embed Mismatched (${mismatches.length})`}
        </button>
        <button
          type="button"
          onClick={handleReembedAll}
          disabled={actionLoading !== null}
          style={{
            padding: "8px 18px",
            borderRadius: 8,
            border: `1px solid ${c.border}`,
            background: c.surface,
            color: c.text,
            fontSize: 13,
            fontWeight: 700,
            cursor: actionLoading === null ? "pointer" : "not-allowed",
            opacity: actionLoading === "all" ? 0.6 : 1,
          }}
        >
          {actionLoading === "all" ? "⟳ Re-embedding All…" : "⚠️ Re-embed All Documents"}
        </button>
      </div>

      {/* ── Mismatched Documents Table ── */}
      <GlassPanel
        variant="medium"
        style={{
          padding: t.spacing.md,
          display: "flex",
          flexDirection: "column",
          gap: t.spacing.sm,
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 800, color: c.text, marginBottom: 4 }}>
          ⚠️ Mismatched / Pending Documents
          <span style={{ fontSize: 12, fontWeight: 600, color: c.textMuted, marginLeft: 8 }}>
            ({mismatchesTotal} total)
          </span>
        </div>

        {mismatches.length === 0 ? (
          <div style={{ padding: "24px 0", textAlign: "center", color: c.textMuted, fontSize: 13 }}>
            ✅ All documents match the configured embedding model
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${c.border}`, color: c.textMuted, fontWeight: 700, textTransform: "uppercase", fontSize: 10, letterSpacing: "0.5px" }}>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>ID</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>Filename</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>Provider</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>Model</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>Version</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>Embedded At</th>
                  <th style={{ textAlign: "right", padding: "6px 8px" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {mismatches.map((doc) => {
                  const isBusy = actionLoading === `doc-${doc.id}`
                  return (
                    <tr
                      key={doc.id}
                      style={{
                        borderBottom: `1px solid ${c.border}40`,
                        color: c.text,
                        opacity: isBusy ? 0.5 : 1,
                      }}
                    >
                      <td style={{ padding: "8px", fontWeight: 700 }}>{doc.id}</td>
                      <td style={{ padding: "8px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {doc.filename}
                      </td>
                      <td style={{ padding: "8px" }}>
                        <StatusBadge label={doc.current_provider || "—"} colorKey={doc.current_provider ? "mismatch" : "pending"} />
                      </td>
                      <td style={{ padding: "8px" }}>{doc.current_model || "—"}</td>
                      <td style={{ padding: "8px" }}>{doc.current_version || "—"}</td>
                      <td style={{ padding: "8px", color: c.textMuted, fontSize: 11 }}>{fmtDate(doc.embedded_at)}</td>
                      <td style={{ padding: "8px", textAlign: "right" }}>
                        <button
                          type="button"
                          onClick={() => handleReembedSingle(doc.id)}
                          disabled={isBusy}
                          style={{
                            padding: "4px 10px",
                            borderRadius: 6,
                            border: "none",
                            background: isBusy ? "#9CA3AF" : "#5B88FF",
                            color: "#fff",
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: isBusy ? "not-allowed" : "pointer",
                          }}
                        >
                          {isBusy ? "⟳…" : "Re-embed"}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </GlassPanel>

      {/* ── Info Footer ── */}
      <div style={{ fontSize: 11, color: c.textMuted, lineHeight: 1.6, padding: "8px 0" }}>
        <strong>💡 Embedding Governance</strong> tracks which model and provider generated each document's
        embedding vectors. When the embedding model configuration changes, documents with outdated embeddings
        are flagged as mismatches and should be re-embedded to ensure consistent retrieval quality.
      </div>
    </div>
  )
}
