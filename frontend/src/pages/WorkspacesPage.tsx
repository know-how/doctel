import React, { useEffect, useState, useCallback, useMemo } from "react"
import { getWorkspaces, getMyDocuments, listChatSessions, createProject, updateProject, deleteProject, deleteDocument } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface Workspace {
  id: string
  name: string
  document_count?: number
  created_at?: string
  updated_at?: string
  last_activity?: string
}

interface DocItem {
  id: string
  filename: string
  project_id: string | null
  project_name: string
  status: string
  created_at: string
  tags?: string[]
}

interface SessionItem {
  session_id: string
  project_id: string | null
  document_id: string | null
  model: string
  started_at: string
  updated_at?: string
  title?: string
}

type TimelineItem = {
  kind: "document"
  data: DocItem
} | {
  kind: "session"
  data: SessionItem
}

const FILE_ICON: Record<string, string> = { pdf: "📕", docx: "📘", doc: "📘", txt: "📄", xlsx: "📊", xls: "📊", csv: "📊", pptx: "📙", ppt: "📙", png: "🖼️", jpg: "🖼️", jpeg: "🖼️" }
function fileIcon(filename: string): string {
  const ext = (filename.split(".").pop() || "").toLowerCase()
  return FILE_ICON[ext] || "📎"
}

function statusColor(status: string, t: ReturnType<typeof getTokens>): string {
  const map: Record<string, string> = {
    ready: t.colors.success, completed: t.colors.success, processed: t.colors.success,
    processing: t.colors.warning, queued: t.colors.warning, ingested: t.colors.secondary,
    uploaded: t.colors.primary, failed: t.colors.error, error: t.colors.error,
  }
  return map[status?.toLowerCase()] ?? t.colors.textMuted
}

function formatDate(iso: string): string {
  if (!iso) return "—"
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) } catch { return iso.slice(0, 10) }
}

function formatDateTime(iso: string): string {
  if (!iso) return "—"
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) } catch { return iso.slice(0, 16) }
}

const PAGE_SIZE = 20

export const WorkspacesPage: React.FC<{
  onNavigate?: (path: string) => void
  onOpenDocument?: (id: string) => void
}> = ({ onNavigate, onOpenDocument }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [documents, setDocuments] = useState<DocItem[]>([])
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [expandedRepos, setExpandedRepos] = useState<Record<string, boolean>>({})
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [showUncategorized, setShowUncategorized] = useState(true)
  const [docPage, setDocPage] = useState(1)
  const [docTotal, setDocTotal] = useState(0)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [wsRes, docsRes, sessRes] = await Promise.all([
        getWorkspaces(),
        getMyDocuments(docPage, PAGE_SIZE),
        listChatSessions(),
      ])
      setWorkspaces(wsRes.projects || wsRes.workspaces || [])
      setDocuments(docsRes.documents || [])
      setDocTotal(docsRes.total || (docsRes.documents || []).length)
      setSessions(sessRes.sessions || [])
    } catch (e: any) {
      setError(e.message ?? "Failed to load workspace data")
    } finally {
      setLoading(false)
    }
  }, [docPage])

  useEffect(() => { fetchAll() }, [fetchAll])

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) return
    const duplicate = workspaces.find((w) => w.name.toLowerCase().trim() === name.toLowerCase())
    if (duplicate) { setCreateError(`A workspace named "${duplicate.name}" already exists`); return }
    try { setCreating(true); setCreateError(null); await createProject({ name }); setNewName(""); await fetchAll() } catch (e: any) { setCreateError(e.message ?? "Failed to create workspace") } finally { setCreating(false) }
  }

  const handleRename = async (id: string) => {
    const name = editName.trim()
    if (!name) { setEditingId(null); return }
    const duplicate = workspaces.find((w) => w.id !== id && w.name.trim().toLowerCase() === name.toLowerCase())
    if (duplicate) { setError(`A workspace named "${duplicate.name}" already exists`); return }
    try { setRenaming(id); await updateProject(id, { name }); setEditingId(null); await fetchAll() } catch (e: any) { setError(e.message ?? "Failed to rename") } finally { setRenaming(null) }
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete workspace "${name}"? This will fail if there are documents in it.`)) return
    try { setDeleting(id); await deleteProject(id); await fetchAll() } catch (e: any) { setError(e.message ?? "Failed to delete workspace") } finally { setDeleting(null) }
  }

  const handleDeleteDoc = async (docId: string, filename: string) => {
    if (!window.confirm(`Delete "${filename}"?`)) return
    try { await deleteDocument(docId); await fetchAll() } catch (e: any) { setError(e.message ?? "Failed to delete document") }
  }

  const toggleExpand = (repoId: string) => setExpandedRepos((prev) => ({ ...prev, [repoId]: !prev[repoId] }))
  const expandAll = () => { const all: Record<string, boolean> = {}; workspaces.forEach((w) => all[w.id] = true); setExpandedRepos(all) }
  const collapseAll = () => setExpandedRepos({})

  const uncategorizedDocs = documents.filter((d) => !d.project_id || !workspaces.some((w) => w.id === d.project_id))
  const uncategorizedSessions = sessions.filter((s) => !s.project_id || !workspaces.some((w) => w.id === s.project_id))

  const getRepoTimeline = useCallback((repoId: string): TimelineItem[] => {
    const repoDocs = documents.filter((d) => d.project_id === repoId)
    const repoSessions = sessions.filter((s) => s.project_id === repoId)
    const items: TimelineItem[] = [
      ...repoDocs.map((d) => ({ kind: "document" as const, data: d })),
      ...repoSessions.map((s) => ({ kind: "session" as const, data: s })),
    ]
    items.sort((a, b) => {
      const aDate = a.kind === "document" ? a.data.created_at : (a.data.updated_at || a.data.started_at)
      const bDate = b.kind === "document" ? b.data.created_at : (b.data.updated_at || b.data.started_at)
      return new Date(bDate).getTime() - new Date(aDate).getTime()
    })
    return items.slice(0, PAGE_SIZE)
  }, [documents, sessions])

  const uncategorizedTimeline: TimelineItem[] = useMemo(() => {
    const items: TimelineItem[] = [
      ...uncategorizedDocs.map((d) => ({ kind: "document" as const, data: d })),
      ...uncategorizedSessions.map((s) => ({ kind: "session" as const, data: s })),
    ]
    items.sort((a, b) => {
      const aDate = a.kind === "document" ? a.data.created_at : (a.data.updated_at || a.data.started_at)
      const bDate = b.kind === "document" ? b.data.created_at : (b.data.updated_at || b.data.started_at)
      return new Date(bDate).getTime() - new Date(aDate).getTime()
    })
    return items.slice(0, PAGE_SIZE)
  }, [uncategorizedDocs, uncategorizedSessions])

  const totalPages = Math.ceil(docTotal / PAGE_SIZE)

  const pageContainer: React.CSSProperties = { padding: t.spacing.xl, maxWidth: 1200, margin: "0 auto" }
  const pageTitle: React.CSSProperties = { fontSize: 28, fontWeight: 800, color: t.colors.text, margin: 0, letterSpacing: "-0.02em" }
  const subtitle: React.CSSProperties = { margin: "4px 0 0", fontSize: 14, color: t.colors.textSecondary }
  const inputStyle: React.CSSProperties = { padding: "10px 14px", borderRadius: 8, border: `1px solid ${t.colors.border}`, background: t.colors.inputBg, color: t.colors.text, fontSize: 13, fontFamily: "inherit", outline: "none", width: "100%", boxSizing: "border-box" }
  const btnPrimary: React.CSSProperties = { background: t.colors.primary, color: "#FFFFFF", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap" }
  const btnGhost: React.CSSProperties = { ...btnPrimary, background: "transparent", border: `1px solid ${t.colors.border}`, color: t.colors.textSecondary }
  const btnSmall: React.CSSProperties = { padding: "5px 12px", borderRadius: 6, border: `1px solid ${t.colors.border}`, background: "transparent", color: t.colors.textSecondary, fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s ease" }
  const btnDanger: React.CSSProperties = { ...btnSmall, color: t.colors.error, borderColor: `${t.colors.error}40` }
  const repoCard: React.CSSProperties = { background: t.colors.cardBg, borderRadius: 12, border: `1px solid ${t.colors.border}`, overflow: "hidden", transition: "all 0.25s ease" }
  const timelineItem: React.CSSProperties = { display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderTop: `1px solid ${t.colors.border}`, transition: "background 0.15s ease", cursor: "default" }
  const badgeStyle = (color: string) => ({ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 999, fontSize: 10, fontWeight: 700, backgroundColor: `${color}18`, border: `1px solid ${color}30`, color })
  const paginationBtn: React.CSSProperties = { padding: "8px 14px", borderRadius: 8, border: `1px solid ${t.colors.border}`, background: t.colors.cardBg, color: t.colors.text, fontSize: 13, cursor: "pointer", fontFamily: "inherit" }

  const renderItem = (item: TimelineItem) => {
    if (item.kind === "document") {
      const d = item.data
      const sc = statusColor(d.status, t)
      return (
        <div key={d.id} style={{ ...timelineItem, cursor: "pointer" }} onClick={() => onOpenDocument?.(d.id)} onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.surfaceHover }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent" }}>
          <span style={{ fontSize: 20, flexShrink: 0 }}>{fileIcon(d.filename)}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, color: t.colors.text, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.filename}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3, flexWrap: "wrap" }}>
              <span style={badgeStyle(sc)}>● {d.status}</span>
              <span style={{ fontSize: 11, color: t.colors.textMuted }}>{formatDate(d.created_at)}</span>
            </div>
          </div>
          <button type="button" style={btnSmall} onClick={(e) => { e.stopPropagation(); handleDeleteDoc(d.id, d.filename) }} onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.error; e.currentTarget.style.color = "#FFF"; e.currentTarget.style.borderColor = t.colors.error }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.colors.textSecondary; e.currentTarget.style.borderColor = t.colors.border }}>✕</button>
          <button type="button" style={btnSmall} onClick={(e) => { e.stopPropagation(); onOpenDocument?.(d.id) }} onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.primary; e.currentTarget.style.color = "#FFF"; e.currentTarget.style.borderColor = t.colors.primary }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.colors.textSecondary; e.currentTarget.style.borderColor = t.colors.border }}>Open</button>
        </div>
      )
    }
    const s = item.data
    return (
      <div key={s.session_id} style={{ ...timelineItem, cursor: s.document_id ? "pointer" : "default" }} onClick={() => { if (s.document_id) onOpenDocument?.(s.document_id) }} onMouseEnter={(e) => { if (s.document_id) e.currentTarget.style.background = t.colors.surfaceHover }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent" }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, flexShrink: 0, background: `${t.colors.secondary}18`, border: `1px solid ${t.colors.secondary}30`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>💬</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: t.colors.text, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.title || "Conversation"}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: t.colors.textMuted, fontWeight: 500 }}>{s.model || "default"}</span>
            <span style={{ fontSize: 11, color: t.colors.textMuted }}>{formatDateTime(s.updated_at || s.started_at)}</span>
          </div>
        </div>
        {s.document_id && <button type="button" style={btnSmall} onClick={(e) => { e.stopPropagation(); onOpenDocument?.(s.document_id!) }} onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.secondary; e.currentTarget.style.color = "#000"; e.currentTarget.style.borderColor = t.colors.secondary }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.colors.textSecondary; e.currentTarget.style.borderColor = t.colors.border }}>Chat</button>}
      </div>
    )
  }

  const renderRepo = (ws: Workspace) => {
    const timeline = getRepoTimeline(ws.id)
    const isExpanded = expandedRepos[ws.id] ?? false
    const repoDocs = documents.filter((d) => d.project_id === ws.id)
    const repoSessions = sessions.filter((s) => s.project_id === ws.id)
    const isEditing = editingId === ws.id
    const isDeleting = deleting === ws.id

    return (
      <div key={ws.id} style={repoCard}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 20px", cursor: "pointer", userSelect: "none" }} onClick={() => toggleExpand(ws.id)}>
          <div style={{ width: 40, height: 40, borderRadius: 10, flexShrink: 0, background: `${t.colors.primary}14`, border: `1px solid ${t.colors.primary}28`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>{isExpanded ? "📂" : "🗂️"}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            {isEditing ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center" }} onClick={(e) => e.stopPropagation()}>
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleRename(ws.id); if (e.key === "Escape") setEditingId(null) }} style={{ ...inputStyle, flex: 1 }} autoFocus />
                <button type="button" style={{ ...btnSmall, background: t.colors.primary, color: "#FFF", borderColor: t.colors.primary }} onClick={() => handleRename(ws.id)} disabled={renaming === ws.id}>{renaming === ws.id ? "..." : "Save"}</button>
                <button type="button" style={btnSmall} onClick={() => setEditingId(null)}>Cancel</button>
              </div>
            ) : (
              <>
                <div style={{ fontWeight: 700, color: t.colors.text, fontSize: 15, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 8 }}>
                  {ws.name}
                  <span style={{ fontSize: 11, fontWeight: 600, color: t.colors.primary, background: `${t.colors.primary}14`, padding: "1px 8px", borderRadius: 10, whiteSpace: "nowrap", flexShrink: 0 }}>
                    {(ws.document_count ?? repoDocs.length)} doc{(ws.document_count ?? repoDocs.length) !== 1 ? "s" : ""}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: t.colors.textMuted, marginTop: 2 }}>
                  {repoSessions.length} chat{repoSessions.length !== 1 ? "s" : ""}
                  {ws.created_at && ` · Created ${formatDate(ws.created_at)}`}
                </div>
              </>
            )}
          </div>
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            {!isEditing && <>
              <button type="button" style={btnSmall} onClick={(e) => { e.stopPropagation(); setEditingId(ws.id); setEditName(ws.name) }} title="Rename" onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.surfaceHover }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent" }}>✎</button>
              <button type="button" style={btnDanger} onClick={(e) => { e.stopPropagation(); handleDelete(ws.id, ws.name) }} title="Delete" disabled={isDeleting} onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.error; e.currentTarget.style.color = "#FFF" }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.colors.error }}>{isDeleting ? "..." : "🗑"}</button>
              <button type="button" style={btnSmall} onClick={(e) => { e.stopPropagation(); onNavigate?.(`/documents/library?project_id=${ws.id}`) }} onMouseEnter={(e) => { e.currentTarget.style.background = t.colors.primary; e.currentTarget.style.color = "#FFF"; e.currentTarget.style.borderColor = t.colors.primary }} onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.colors.textSecondary; e.currentTarget.style.borderColor = t.colors.border }}>Library</button>
            </>}
            <span style={{ fontSize: 18, color: t.colors.textMuted, transition: "transform 0.2s ease", transform: isExpanded ? "rotate(180deg)" : "rotate(0)", display: "inline-block", lineHeight: 1 }}>▼</span>
          </div>
        </div>
        {isExpanded && (timeline.length === 0 ? (
          <div style={{ padding: "24px 20px", textAlign: "center", color: t.colors.textMuted, fontSize: 13, borderTop: `1px solid ${t.colors.border}` }}>No documents or conversations yet</div>
        ) : timeline.map(renderItem))}
      </div>
    )
  }

  return (
    <div style={pageContainer}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={pageTitle}>Workspaces</h1>
          <p style={subtitle}>Organize, manage, and explore your repositories</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" onClick={expandAll} style={{ ...btnGhost, fontSize: 12, padding: "8px 14px" }}>Expand All</button>
          <button type="button" onClick={collapseAll} style={{ ...btnGhost, fontSize: 12, padding: "8px 14px" }}>Collapse All</button>
          <button type="button" onClick={() => { setDocPage(1); fetchAll() }} disabled={loading} style={{ ...btnGhost, fontSize: 12, padding: "8px 14px", opacity: loading ? 0.6 : 1 }}>{loading ? "Loading…" : "↻ Refresh"}</button>
        </div>
      </div>

      {(error || createError) && <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: 12, background: `${t.colors.error}14`, border: `1px solid ${t.colors.error}28`, color: t.colors.error, fontSize: 13 }}>
        {error || createError}
        <button type="button" onClick={() => { setError(null); setCreateError(null) }} style={{ ...btnGhost, marginLeft: 12, fontSize: 12, color: t.colors.error }}>Dismiss</button>
      </div>}

      <div style={{ display: "flex", gap: 10, marginTop: 20, flexWrap: "wrap", padding: "16px 20px", borderRadius: 12, background: t.colors.cardBg, border: `1px solid ${t.colors.border}` }}>
        <input type="text" placeholder="New workspace name…" value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleCreate() }} style={{ ...inputStyle, flex: 1, minWidth: 200 }} />
        <button type="button" onClick={handleCreate} disabled={creating || !newName.trim()} style={{ ...btnPrimary, opacity: creating || !newName.trim() ? 0.5 : 1, cursor: !newName.trim() ? "not-allowed" : "pointer" }}>{creating ? "Creating…" : "Create Workspace"}</button>
      </div>

      {loading ? (
        <div style={{ marginTop: 20, display: "grid", gap: 12 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} style={{ ...repoCard, height: 100, opacity: 0.5, cursor: "default" }}>
              <div style={{ padding: "16px 20px" }}><div style={{ width: "30%", height: 14, borderRadius: 6, background: t.colors.surface, marginBottom: 10 }} /><div style={{ width: "60%", height: 14, borderRadius: 6, background: t.colors.surface }} /></div>
            </div>
          ))}
        </div>
      ) : workspaces.length === 0 && uncategorizedDocs.length === 0 && uncategorizedSessions.length === 0 ? (
        <div style={{ marginTop: 20, textAlign: "center", padding: "48px 20px", borderRadius: 12, background: t.colors.cardBg, border: `1px solid ${t.colors.border}` }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🗂️</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: t.colors.text, marginBottom: 8 }}>No workspaces yet</div>
          <div style={{ fontSize: 13, color: t.colors.textSecondary }}>Create your first workspace above to get started.</div>
        </div>
      ) : (
        <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 12 }}>
          {workspaces.map(renderRepo)}
          {(uncategorizedDocs.length > 0 || uncategorizedSessions.length > 0) && (
            <div style={repoCard}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 20px", cursor: "pointer", userSelect: "none" }} onClick={() => setShowUncategorized((v) => !v)}>
                <div style={{ width: 40, height: 40, borderRadius: 10, flexShrink: 0, background: `${t.colors.warning}14`, border: `1px solid ${t.colors.warning}28`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>📂</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, color: t.colors.text, fontSize: 15 }}>No Repository</div>
                  <div style={{ fontSize: 12, color: t.colors.textMuted, marginTop: 2 }}>{uncategorizedDocs.length} doc{uncategorizedDocs.length !== 1 ? "s" : ""} · {uncategorizedSessions.length} chat{uncategorizedSessions.length !== 1 ? "s" : ""} (uncategorized)</div>
                </div>
                <span style={{ fontSize: 18, color: t.colors.textMuted, transition: "transform 0.2s ease", transform: showUncategorized ? "rotate(180deg)" : "rotate(0)", display: "inline-block", lineHeight: 1 }}>▼</span>
              </div>
              {showUncategorized && uncategorizedTimeline.map(renderItem)}
            </div>
          )}
        </div>
      )}

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, marginTop: 20 }}>
          <button type="button" style={paginationBtn} disabled={docPage <= 1} onClick={() => { setDocPage((p) => Math.max(1, p - 1)) }}>← Prev</button>
          <span style={{ fontSize: 13, color: t.colors.textSecondary }}>Page {docPage} of {totalPages}</span>
          <button type="button" style={paginationBtn} disabled={docPage >= totalPages} onClick={() => { setDocPage((p) => p + 1) }}>Next →</button>
        </div>
      )}
    </div>
  )
}