import React, { useEffect, useState, useCallback } from "react"
import { getDocumentLibrary, getWorkspaces, downloadDocumentFileApi } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

const FILE_TYPE_ICON: Record<string, string> = {
  pdf: "📕",
  docx: "📘",
  doc: "📘",
  txt: "📄",
  png: "🖼️",
  jpg: "🖼️",
  jpeg: "🖼️",
}

function fileIcon(filename: string): string {
  const ext = (filename.split(".").pop() || "").toLowerCase()
  return FILE_TYPE_ICON[ext] || "📎"
}

function statusColor(s: string, t: ReturnType<typeof getTokens>): string {
  const map: Record<string, string> = {
    ready: t.colors.success,
    completed: t.colors.success,
    processed: t.colors.success,
    processing: t.colors.warning,
    queued: t.colors.warning,
    failed: t.colors.error,
    error: t.colors.error,
  }
  return map[s?.toLowerCase()] ?? t.colors.textMuted
}

interface DocItem {
  id: string
  filename: string
  project_id: string | null
  project_name: string
  status: string
  doc_type?: string | null
  is_public?: boolean
  created_at: string
  tags?: string[]
  download_url?: string
}

interface Workspace {
  id: string
  name: string
}

export const DocumentLibraryPage: React.FC<{
  onOpenDocument?: (documentId: string) => void
  initialProjectId?: string | null
}> = ({ onOpenDocument, initialProjectId }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocItem[]>([])
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [search, setSearch] = useState("")
  const [projectFilter, setProjectFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [tagFilter, setTagFilter] = useState("")
  const [visibilityFilter, setVisibilityFilter] = useState("")
  const [page, setPage] = useState(1)
  const [totalDocs, setTotalDocs] = useState(0)
  const pageSize = 20

  useEffect(() => {
    if (initialProjectId) setProjectFilter(initialProjectId)
  }, [initialProjectId])

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const filters: any = { page: page, page_size: pageSize }
      if (search) filters.search = search
      if (projectFilter) filters.project_id = projectFilter
      if (statusFilter) filters.status = statusFilter
      if (tagFilter) filters.tag = tagFilter
      if (visibilityFilter) filters.visibility = visibilityFilter
      const [docsRes, wsRes] = await Promise.all([getDocumentLibrary(filters), getWorkspaces()])
      setDocuments(docsRes.documents || docsRes.items || [])
      setTotalDocs(docsRes.total || (docsRes.documents || []).length)
      setWorkspaces(wsRes.projects || wsRes.workspaces || [])
    } catch (e: any) {
      setError(e.message ?? "Failed to load documents")
    } finally {
      setLoading(false)
    }
  }, [search, projectFilter, statusFilter, tagFilter, visibilityFilter, page])

  useEffect(() => { fetchData() }, [fetchData])

  const handleDownload = async (doc: DocItem) => {
    try {
      const blob = await downloadDocumentFileApi(doc.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = doc.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e.message ?? "Download failed")
    }
  }

  const allTags = [...new Set(documents.flatMap((d) => d.tags || []))].sort()
  const totalPages = Math.ceil(totalDocs / pageSize)

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

  const inputBase: React.CSSProperties = {
    padding: "10px 14px",
    borderRadius: 8,
    border: `1px solid ${t.colors.border}`,
    background: t.colors.inputBg,
    color: t.colors.text,
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
    boxSizing: "border-box",
  }

  const selectStyle: React.CSSProperties = {
    ...inputBase,
    cursor: "pointer",
    minWidth: 140,
  }

  const chipRow: React.CSSProperties = {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
    marginTop: 16,
  }

  const chipActive: React.CSSProperties = {
    padding: "6px 14px",
    borderRadius: 999,
    border: "none",
    background: t.colors.primary,
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  }

  const chipInactive: React.CSSProperties = {
    ...chipActive,
    background: "transparent",
    border: `1px solid ${t.colors.border}`,
    color: t.colors.textSecondary,
  }

  const cardBase: React.CSSProperties = {
    background: t.colors.cardBg,
    borderRadius: 12,
    border: `1px solid ${t.colors.border}`,
    padding: "18px 20px",
    backdropFilter: "blur(10px)",
  }

  const btnPrimary: React.CSSProperties = {
    background: t.colors.primary,
    color: "#FFFFFF",
    border: "none",
    borderRadius: 8,
    padding: "7px 16px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  }

  const btnGhost: React.CSSProperties = {
    ...btnPrimary,
    background: "transparent",
    border: `1px solid ${t.colors.border}`,
    color: t.colors.textSecondary,
  }

  const badge: React.CSSProperties = (color: string) => ({
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

  const skeleton: React.CSSProperties = {
    ...cardBase,
    height: 80,
    opacity: 0.5,
  }

  const skeletonShimmer: React.CSSProperties = {
    width: "100%",
    height: 14,
    borderRadius: 6,
    background: t.colors.surface,
    marginBottom: 10,
  }

  return (
    <div style={pageContainer}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={pageTitle}>Document Library</h1>
          <p style={subtitle}>Browse, filter and manage all uploaded documents</p>
        </div>
        <button type="button" onClick={fetchData} disabled={loading} style={{ ...btnGhost, opacity: loading ? 0.6 : 1 }}>
          {loading ? "Loading…" : "↻ Refresh"}
        </button>
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
        <input
          type="text"
          placeholder="Search by filename…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ ...inputBase, width: "100%", maxWidth: 400 }}
        />
      </div>

      <div style={chipRow}>
        <select value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)} style={selectStyle}>
          <option value="">All Projects</option>
          {workspaces.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={selectStyle}>
          <option value="">All Status</option>
          <option value="ready">Ready</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
        <select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} style={selectStyle}>
          <option value="" style={{ backgroundColor: t.colors.bgSecondary, color: t.colors.text }}>All Tags</option>
          {allTags.map((tag) => (
            <option key={tag} value={tag} style={{ backgroundColor: t.colors.bgSecondary, color: t.colors.text }}>{tag}</option>
          ))}
        </select>
        <select value={visibilityFilter} onChange={(e) => setVisibilityFilter(e.target.value)} style={selectStyle}>
          <option value="">All Visibility</option>
          <option value="public">🌐 Public</option>
          <option value="private">🔒 Private</option>
        </select>
      </div>

      <div style={{ marginTop: 20, display: "grid", gap: 10 }}>
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} style={skeleton}>
              <div style={skeletonShimmer} />
              <div style={{ ...skeletonShimmer, width: "60%" }} />
            </div>
          ))
        ) : documents.length === 0 ? (
          <div style={{ ...cardBase, textAlign: "center", padding: "48px 20px" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📂</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: t.colors.text, marginBottom: 8 }}>
              No documents found
            </div>
            <div style={{ fontSize: 13, color: t.colors.textSecondary }}>
              {search || projectFilter || statusFilter || tagFilter
                ? "Try adjusting your filters."
                : "Upload your first document to get started."}
            </div>
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              style={{
                ...cardBase,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 14,
                flexWrap: "wrap",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0, flex: 1 }}>
                <span style={{ fontSize: 24, flexShrink: 0 }}>{fileIcon(doc.filename)}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: t.colors.text, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {doc.filename}
                  </div>
                  <div style={{ fontSize: 12, color: t.colors.textSecondary, marginTop: 2, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span>{doc.project_name || "—"}</span>
                    <span>•</span>
                    <span>{new Date(doc.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</span>
                    <span style={badge(statusColor(doc.status, t))}>● {doc.status}</span>
                    <span style={badge(doc.is_public ? t.colors.secondary : t.colors.textMuted)}>
                      {doc.is_public ? "🌐 Public" : "🔒 Private"}
                    </span>
                    {doc.doc_type && (
                      <span style={{
                        padding: "2px 8px", borderRadius: 999, fontSize: 10, fontWeight: 700,
                        textTransform: "uppercase", letterSpacing: "0.3px",
                        backgroundColor: "rgba(16,185,129,0.1)",
                        border: "1px solid rgba(16,185,129,0.2)",
                        color: "#34D399",
                      }}>
                        {doc.doc_type}
                      </span>
                    )}
                    {(doc.tags || []).map((tag) => (
                      <span key={tag} style={{
                        padding: "2px 8px", borderRadius: 999, fontSize: 10,
                        backgroundColor: t.colors.surface, color: t.colors.textSecondary,
                      }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                <button type="button" onClick={() => onOpenDocument?.(doc.id)} style={btnPrimary}>Open</button>
                <button type="button" onClick={() => handleDownload(doc)} style={btnGhost}>↓ Download</button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`Delete "${doc.filename}"?`)) {
                      import("../api/client").then((m) => m.deleteDocument(doc.id)).then(() => fetchData()).catch((e: any) => setError(e.message ?? "Delete failed"))
                    }
                  }}
                  style={{ ...btnGhost, color: t.colors.error, borderColor: `${t.colors.error}40` }}
                >✕</button>
              </div>
            </div>
          ))
        )}
        {totalPages > 1 && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, marginTop: 16 }}>
            <button type="button" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} style={{ ...btnGhost, opacity: page <= 1 ? 0.4 : 1, padding: "8px 16px" }}>← Prev</button>
            <span style={{ fontSize: 13, color: t.colors.textSecondary }}>Page {page} of {totalPages} ({totalDocs} docs)</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ ...btnGhost, opacity: page >= totalPages ? 0.4 : 1, padding: "8px 16px" }}>Next →</button>
          </div>
        )}
      </div>
    </div>
  )
}
