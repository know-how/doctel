import React, { useEffect, useState, useCallback } from "react"
import {
  getMyProjects,
  getMyDocuments,
  getDocumentLibrary,
  overrideDocumentProjectAPI,
  deleteDocument,
  getProjectMembers,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface ProjectItem {
  id: string
  name: string
  role: string
  member_count?: number
}

interface DocItem {
  id: string
  filename: string
  project_id: string | null
  project_name: string
  status: string
  is_public?: boolean
  created_at: string
  uploaded_by_me?: boolean
  download_url?: string
  view_url?: string
}

interface ProjectMemberInfo {
  id: number
  display_name: string
  email: string
  role: string
  role_in_project: string
}

const FILE_ICON: Record<string, string> = {
  pdf: "📕", docx: "📘", doc: "📘", txt: "📄", xlsx: "📊", xls: "📊",
  csv: "📊", pptx: "📙", ppt: "📙", png: "🖼️", jpg: "🖼️", jpeg: "🖼️",
}
function fileIcon(filename: string): string {
  const ext = (filename.split(".").pop() || "").toLowerCase()
  return FILE_ICON[ext] || "📎"
}

function statusBadge(status: string, c: ReturnType<typeof getTokens>["colors"]): React.CSSProperties {
  const map: Record<string, string> = {
    ready: c.success, completed: c.success, processed: c.success,
    processing: c.warning, queued: c.warning, ingested: c.secondary,
    uploaded: c.primary, failed: c.error, error: c.error,
  }
  const color = map[status?.toLowerCase()] ?? c.textMuted
  return {
    display: "inline-flex", alignItems: "center", gap: 4,
    padding: "2px 8px", borderRadius: 999, fontSize: 10, fontWeight: 700,
    backgroundColor: color + "18", border: `1px solid ${color}30`, color,
  }
}

export const SharedDocumentsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [sharedWithMe, setSharedWithMe] = useState<DocItem[]>([])
  const [myWorkspaceDocs, setMyWorkspaceDocs] = useState<DocItem[]>([])
  const [allDocuments, setAllDocuments] = useState<DocItem[]>([])
  const [projectMembers, setProjectMembers] = useState<Record<string, ProjectMemberInfo[]>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProject, setSelectedProject] = useState<string>("all")
  const [searchTerm, setSearchTerm] = useState("")
  const [activeTab, setActiveTab] = useState<"shared" | "my">("shared")

  const [shareModalOpen, setShareModalOpen] = useState(false)
  const [shareDocId, setShareDocId] = useState<string>("")
  const [shareTargetProject, setShareTargetProject] = useState<string>("")
  const [shareLoading, setShareLoading] = useState(false)
  const [shareError, setShareError] = useState<string | null>(null)
  const [shareSuccess, setShareSuccess] = useState<string | null>(null)

  const [unshareLoading, setUnshareLoading] = useState<string | null>(null)
  const [expandedProject, setExpandedProject] = useState<string | null>(null)
  const [membersLoading, setMembersLoading] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [projRes, myDocsRes, libRes] = await Promise.all([
        getMyProjects(),
        getMyDocuments(1, 200),
        getDocumentLibrary({ page_size: 200 }),
      ])
      const projectList: ProjectItem[] = projRes.projects || []
      setProjects(projectList)

      const myDocs: DocItem[] = (myDocsRes.documents ?? myDocsRes.items ?? [])
      const libDocs: DocItem[] = (libRes.documents ?? libRes.items ?? [])

      const libIds = new Set(libDocs.map((d: DocItem) => d.id))

      const sharedDocs = myDocs.filter((d: DocItem) => {
        const uploaded_by_me = (d as any).uploaded_by_me !== false
        return !uploaded_by_me && !libIds.has(d.id) && d.project_id
      })

      const ownWorkspaceDocs = libDocs.filter((d: DocItem) => {
        if (!(d as any).uploaded_by_me) return true
        return !!d.project_id
      })

      setSharedWithMe(sharedDocs)
      setMyWorkspaceDocs(ownWorkspaceDocs)
      setAllDocuments(libDocs)
    } catch (e: any) {
      setError(e.message ?? "Failed to load shared documents")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const loadMembers = async (projectId: string) => {
    if (projectMembers[projectId]) {
      setExpandedProject(expandedProject === projectId ? null : projectId)
      return
    }
    try {
      setMembersLoading(projectId)
      const res = await getProjectMembers(projectId)
      setProjectMembers((prev) => ({ ...prev, [projectId]: res.members || [] }))
      setExpandedProject(projectId)
    } catch {
    } finally {
      setMembersLoading(null)
    }
  }

  const filteredShared = sharedWithMe
    .filter((d) => selectedProject === "all" || d.project_id === selectedProject)
    .filter((d) => !searchTerm.trim() || d.filename.toLowerCase().includes(searchTerm.toLowerCase()))

  const filteredMyDocs = myWorkspaceDocs
    .filter((d) => selectedProject === "all" || d.project_id === selectedProject)
    .filter((d) => !searchTerm.trim() || d.filename.toLowerCase().includes(searchTerm.toLowerCase()))

  const handleShare = async () => {
    if (!shareDocId || !shareTargetProject) return
    try {
      setShareLoading(true)
      setShareError(null)
      setShareSuccess(null)
      await overrideDocumentProjectAPI(shareDocId, shareTargetProject)
      setShareSuccess("Document shared successfully!")
      setShareModalOpen(false)
      await loadData()
    } catch (e: any) {
      setShareError(e.message ?? "Failed to share document")
    } finally {
      setShareLoading(false)
    }
  }

  const handleUnshare = async (docId: string) => {
    try {
      setUnshareLoading(docId)
      setError(null)
      await overrideDocumentProjectAPI(docId, "__none__")
      await loadData()
    } catch (e: any) {
      const msg = e.message ?? "Failed to unshare document"
      setError(msg)
    } finally {
      setUnshareLoading(null)
    }
  }

  const handleDelete = async (docId: string, filename: string) => {
    if (!window.confirm(`Delete "${filename}"?`)) return
    try {
      await deleteDocument(docId)
      await loadData()
    } catch (e: any) {
      setError(e.message ?? "Failed to delete document")
    }
  }

  const openShareModal = (docId: string) => {
    setShareDocId(docId)
    setShareTargetProject("")
    setShareError(null)
    setShareSuccess(null)
    setShareModalOpen(true)
  }

  const btnPrimary: React.CSSProperties = {
    background: `linear-gradient(135deg, ${c.primary}, ${c.primaryHover})`,
    color: "#FFFFFF", border: "none", borderRadius: t.radii.md,
    padding: "10px 20px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
  }
  const btnGhost: React.CSSProperties = {
    background: "transparent", border: `1px solid ${c.border}`, color: c.textSecondary,
    borderRadius: t.radii.md, padding: "8px 16px", fontSize: 13, fontWeight: 600,
    cursor: "pointer", fontFamily: "inherit",
  }
  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 18px", fontSize: 13, fontWeight: active ? 700 : 500,
    color: active ? c.primary : c.textSecondary,
    borderBottom: active ? `2px solid ${c.primary}` : "2px solid transparent",
    background: "transparent", borderLeft: "none", borderRight: "none", borderTop: "none",
    cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s ease",
  })

  const getMemberCount = (projectId: string): number => {
    const proj = projects.find((p) => p.id === projectId)
    return proj?.member_count ?? projectMembers[projectId]?.length ?? 0
  }

  const renderDocRow = (doc: DocItem, showActions: "shared" | "my") => {
    const projName = projects.find((p) => p.id === doc.project_id)?.name || doc.project_name || "Unknown"
    const isUnsharing = unshareLoading === doc.id
    const memberCount = doc.project_id ? getMemberCount(doc.project_id) : 0

    return (
      <div
        key={doc.id}
        style={{
          display: "flex", alignItems: "center", gap: 14,
          padding: "14px 18px", borderRadius: t.radii.lg,
          border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
          transition: "all 0.15s ease",
        }}
      >
        <span style={{ fontSize: 24, flexShrink: 0 }}>{fileIcon(doc.filename)}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: c.text, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {doc.filename}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, flexWrap: "wrap" as const }}>
            <span style={statusBadge(doc.status, c)}>● {doc.status}</span>
            <span style={statusBadge(doc.is_public ? "completed" : "uploaded", c)}>
              {doc.is_public ? "🌐 Public" : "🔒 Private"}
            </span>
            <span style={{ fontSize: 11, color: c.textMuted }}>
              Workspace: <strong style={{ color: c.textSecondary }}>{projName}</strong>
            </span>
            {doc.project_id && memberCount > 0 && (
              <span
                style={{ fontSize: 11, color: c.primary, cursor: "pointer", textDecoration: "underline" }}
                onClick={() => loadMembers(doc.project_id!)}
              >
                {memberCount} member{memberCount !== 1 ? "s" : ""}
              </span>
            )}
            {doc.created_at && (
              <span style={{ fontSize: 11, color: c.textMuted }}>
                {new Date(doc.created_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button
            onClick={() => openShareModal(doc.id)}
            style={{
              padding: "6px 12px", borderRadius: t.radii.sm, fontSize: 12, fontWeight: 600,
              border: `1px solid ${c.primary}`, backgroundColor: "transparent",
              color: c.primary, cursor: "pointer", fontFamily: "inherit",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = c.primary; e.currentTarget.style.color = "#fff" }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; e.currentTarget.style.color = c.primary }}
          >
            Re-share
          </button>
          <button
            onClick={() => handleUnshare(doc.id)}
            disabled={isUnsharing}
            style={{
              padding: "6px 12px", borderRadius: t.radii.sm, fontSize: 12, fontWeight: 600,
              border: `1px solid ${c.warning}40`, backgroundColor: "transparent",
              color: c.warning, cursor: isUnsharing ? "not-allowed" : "pointer", fontFamily: "inherit",
              opacity: isUnsharing ? 0.5 : 1,
            }}
            onMouseEnter={(e) => { if (!isUnsharing) { e.currentTarget.style.backgroundColor = c.warning; e.currentTarget.style.color = "#fff" } }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; e.currentTarget.style.color = c.warning }}
          >
            {isUnsharing ? "..." : "Unshare"}
          </button>
          {showActions === "my" && (
            <button
              onClick={() => handleDelete(doc.id, doc.filename)}
              style={{
                padding: "6px 10px", borderRadius: t.radii.sm, fontSize: 12, fontWeight: 600,
                border: `1px solid ${c.error}40`, backgroundColor: "transparent",
                color: c.error, cursor: "pointer", fontFamily: "inherit",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = c.error; e.currentTarget.style.color = "#fff" }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; e.currentTarget.style.color = c.error }}
            >
              ✕
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Shared Documents</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
          Manage document sharing across your workspaces. See who has access to your documents.
        </p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
          <button style={{ ...btnGhost, marginLeft: 12, fontSize: 12, color: c.error, borderColor: `${c.error}40` }} onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {shareSuccess && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.success + "18", color: c.success, fontSize: 13 }}>
          {shareSuccess}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${c.border}`, marginBottom: t.spacing.md }}>
        <button style={tabStyle(activeTab === "shared")} onClick={() => setActiveTab("shared")}>
          Shared with me ({sharedWithMe.length})
        </button>
        <button style={tabStyle(activeTab === "my")} onClick={() => setActiveTab("my")}>
          My workspace documents ({myWorkspaceDocs.length})
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: t.spacing.lg, alignItems: "center" }}>
        <input
          type="text"
          placeholder="Search documents..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            flex: 1, minWidth: 180, padding: "8px 14px", borderRadius: t.radii.md,
            border: `1px solid ${c.border}`, backgroundColor: c.inputBg,
            color: c.text, fontSize: 13, fontFamily: "inherit", outline: "none",
          }}
        />
        <select
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
          style={{
            padding: "8px 14px", borderRadius: t.radii.md,
            border: `1px solid ${c.border}`, backgroundColor: c.inputBg,
            color: c.text, fontSize: 13, fontFamily: "inherit",
          }}
        >
          <option value="all">All Workspaces</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        {activeTab === "my" && (
          <button onClick={() => openShareModal("")} style={btnPrimary}>
            Share a Document
          </button>
        )}
      </div>

      {/* Project member expansion */}
      {expandedProject && projectMembers[expandedProject] && (
        <div style={{
          marginBottom: t.spacing.lg, padding: 16, borderRadius: t.radii.lg,
          border: `1px solid ${c.primary}30`, backgroundColor: c.surface,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: c.text }}>
              Members of "{projects.find((p) => p.id === expandedProject)?.name || expandedProject}"
            </span>
            <button
              onClick={() => setExpandedProject(null)}
              style={{ background: "none", border: "none", color: c.textMuted, cursor: "pointer", fontSize: 18, lineHeight: 1 }}
            >
              ✕
            </button>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {projectMembers[expandedProject].map((m) => (
              <div
                key={m.id}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "6px 12px", borderRadius: t.radii.md,
                  backgroundColor: c.inputBg, border: `1px solid ${c.border}`,
                }}
              >
                <span style={{
                  width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                  backgroundColor: c.primary + "20", color: c.primary, fontSize: 12, fontWeight: 700,
                }}>
                  {(m.display_name || m.email || "??").charAt(0).toUpperCase()}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: c.text }}>{m.display_name || m.email || `User ${m.id}`}</div>
                  <div style={{ fontSize: 10, color: c.textMuted }}>{m.role_in_project || m.role}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {membersLoading && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.surface, color: c.textSecondary, fontSize: 13, textAlign: "center" }}>
          Loading members...
        </div>
      )}

      {/* Share Modal */}
      {shareModalOpen && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2000,
            backdropFilter: "blur(4px)",
          }}
          onClick={() => setShareModalOpen(false)}
        >
          <div
            style={{
              width: 480, maxWidth: "95vw", maxHeight: "90vh", overflow: "auto",
              borderRadius: 16, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary,
              padding: 24,
              boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ margin: "0 0 16px 0", fontSize: 18, fontWeight: 700, color: c.text }}>
              Share a Document
            </h2>
            <p style={{ fontSize: 13, color: c.textSecondary, margin: "0 0 16px 0" }}>
              Move a document into a workspace so all workspace members can access it.
            </p>

            {shareError && (
              <div style={{ padding: "8px 12px", marginBottom: 12, borderRadius: 8, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
                {shareError}
              </div>
            )}

            <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
              Document
            </label>
            <select
              value={shareDocId}
              onChange={(e) => setShareDocId(e.target.value)}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 10,
                border: `1px solid ${c.border}`, backgroundColor: c.inputBg,
                color: c.text, fontSize: 13, fontFamily: "inherit",
                marginBottom: 16, boxSizing: "border-box",
              }}
            >
              <option value="" style={{ backgroundColor: c.bgSecondary, color: c.text }}>-- Select a document --</option>
              {allDocuments.map((d) => (
                <option key={d.id} value={d.id} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{d.filename}</option>
              ))}
            </select>

            <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
              Share to Workspace
            </label>
            <select
              value={shareTargetProject}
              onChange={(e) => setShareTargetProject(e.target.value)}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 10,
                border: `1px solid ${c.border}`, backgroundColor: c.inputBg,
                color: c.text, fontSize: 13, fontFamily: "inherit",
                marginBottom: 20, boxSizing: "border-box",
              }}
            >
              <option value="" style={{ backgroundColor: c.bgSecondary, color: c.text }}>-- Select workspace --</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id} style={{ backgroundColor: c.bgSecondary, color: c.text }}>
                  {p.name} ({p.member_count ?? "..."} members)
                </option>
              ))}
            </select>

            {shareTargetProject && projects.find((p) => p.id === shareTargetProject) && (
              <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, backgroundColor: c.surface, border: `1px solid ${c.border}` }}>
                <span style={{ fontSize: 12, color: c.textSecondary }}>
                  {projects.find((p) => p.id === shareTargetProject)!.member_count ?? 0} member(s) in this workspace will gain access to this document.
                </span>
              </div>
            )}

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button
                onClick={() => setShareModalOpen(false)}
                style={{ ...btnGhost, padding: "10px 20px" }}
              >
                Cancel
              </button>
              <button
                onClick={handleShare}
                disabled={!shareDocId || !shareTargetProject || shareLoading}
                style={{
                  ...btnPrimary,
                  opacity: !shareDocId || !shareTargetProject || shareLoading ? 0.5 : 1,
                  cursor: !shareDocId || !shareTargetProject || shareLoading ? "not-allowed" : "pointer",
                }}
              >
                {shareLoading ? "Sharing..." : "Share"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div style={{ display: "grid", gap: t.spacing.md }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{
              borderRadius: t.radii.lg, border: `1px solid ${c.border}`,
              padding: t.spacing.lg, backgroundColor: c.cardBg, minHeight: 72,
            }}>
              <div style={{ height: 14, width: "40%", backgroundColor: c.surfaceHover, borderRadius: 4, marginBottom: 8 }} />
              <div style={{ height: 10, width: "70%", backgroundColor: c.surfaceHover, borderRadius: 4 }} />
            </div>
          ))}
        </div>
      ) : activeTab === "shared" ? (
        filteredShared.length === 0 ? (
          <div style={{
            textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg,
            border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
          }}>
            <div style={{ fontSize: 48, marginBottom: t.spacing.md }}>🔗</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: c.text, marginBottom: 4 }}>No shared documents</div>
            <div style={{ fontSize: 13, color: c.textSecondary }}>
              {sharedWithMe.length === 0
                ? "Documents shared with you by team members will appear here."
                : "No documents match your current filter."}
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gap: t.spacing.sm }}>
            {filteredShared.map((doc) => renderDocRow(doc, "shared"))}
          </div>
        )
      ) : filteredMyDocs.length === 0 ? (
        <div style={{
          textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg,
          border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
        }}>
          <div style={{ fontSize: 48, marginBottom: t.spacing.md }}>📁</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: c.text, marginBottom: 4 }}>No workspace documents</div>
          <div style={{ fontSize: 13, color: c.textSecondary }}>
            Share a document to a workspace to make it accessible to your team.
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: t.spacing.sm }}>
          {filteredMyDocs.map((doc) => renderDocRow(doc, "my"))}
        </div>
      )}

      {/* Summary footer */}
      {!loading && (
        <div style={{ marginTop: t.spacing.lg, textAlign: "center", fontSize: 13, color: c.textMuted }}>
          {activeTab === "shared"
            ? `Showing ${filteredShared.length} of ${sharedWithMe.length} document${sharedWithMe.length !== 1 ? "s" : ""} shared with you`
            : `Showing ${filteredMyDocs.length} of ${myWorkspaceDocs.length} document${myWorkspaceDocs.length !== 1 ? "s" : ""} in your workspaces`
          }
          {selectedProject !== "all" && ` in ${projects.find((p) => p.id === selectedProject)?.name || "workspace"}`}
        </div>
      )}
    </div>
  )
}