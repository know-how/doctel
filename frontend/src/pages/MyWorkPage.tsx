import React, { useEffect, useState } from "react"
import { getMyDocuments, getMyProjects, listChatSessions, downloadDocumentFileApi } from "../api/client"
import { colors } from "../theme/colors"

export const MyWorkPage: React.FC<{
  onOpenDocument: (documentId: string) => void
}> = ({ onOpenDocument }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [projects, setProjects] = useState<{ id: string; name: string; role: string }[]>([])
  const [documents, setDocuments] = useState<
    {
      id: string
      filename: string
      project_id: string | null
      project_name: string
      status: string
      created_at: string
      download_url: string
      view_url: string
    }[]
  >([])
  const [sessions, setSessions] = useState<
    { session_id: string; project_id: string | null; model: string; started_at: string; title?: string; updated_at?: string }[]
  >([])

  const refresh = async () => {
    try {
      setLoading(true)
      setError(null)
      const [p, d, s] = await Promise.all([
        getMyProjects(),
        getMyDocuments(),
        listChatSessions(),
      ])
      setProjects(p.projects || [])
      setDocuments(d.documents || [])
      setSessions(s.sessions || [])
    } catch (e: any) {
      setError(e.message ?? "Failed to load history")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const download = async (docId: string, filename: string) => {
    try {
      setError(null)
      const blob = await downloadDocumentFileApi(docId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename || docId
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e.message ?? "Download failed")
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 800, color: colors.textPrimary }}>
            My Work
          </div>
          <div style={{ fontSize: 13, color: colors.textMuted }}>
            Projects, uploads, and recent sessions.
          </div>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: `1px solid ${colors.border}`,
            backgroundColor: "#FFFFFF",
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error && <div style={{ color: colors.danger, fontSize: 13 }}>{error}</div>}

      <div
        style={{
          backgroundColor: "#FFFFFF",
          borderRadius: 12,
          border: `1px solid ${colors.border}`,
          padding: 12,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 10 }}>My Projects</div>
        {projects.length === 0 ? (
          <div style={{ color: colors.textMuted, fontSize: 13 }}>No projects yet.</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {projects.map((p) => (
              <div
                key={p.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "10px 10px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                }}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: colors.textMuted }}>Role: {p.role}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div
        style={{
          backgroundColor: "#FFFFFF",
          borderRadius: 12,
          border: `1px solid ${colors.border}`,
          padding: 12,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 10 }}>My Documents</div>
        {documents.length === 0 ? (
          <div style={{ color: colors.textMuted, fontSize: 13 }}>No documents yet.</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {documents.map((d) => (
              <div
                key={d.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "10px 10px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                  alignItems: "center",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {d.filename}
                  </div>
                  <div style={{ fontSize: 12, color: colors.textMuted }}>
                    {d.project_name || "No project"} • {d.status}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  <button
                    type="button"
                    onClick={() => onOpenDocument(d.id)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 10,
                      border: `1px solid ${colors.border}`,
                      backgroundColor: "#FFFFFF",
                      cursor: "pointer",
                    }}
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => download(d.id, d.filename)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 10,
                      border: `1px solid ${colors.border}`,
                      backgroundColor: "#FFFFFF",
                      cursor: "pointer",
                    }}
                  >
                    Download
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div
        style={{
          backgroundColor: "#FFFFFF",
          borderRadius: 12,
          border: `1px solid ${colors.border}`,
          padding: 12,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Recent Sessions</div>
        {sessions.length === 0 ? (
          <div style={{ color: colors.textMuted, fontSize: 13 }}>No sessions yet.</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {sessions.map((s) => (
              <div
                key={s.session_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "10px 10px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                }}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>{s.title || "Conversation"}</div>
                  <div style={{ fontSize: 12, color: colors.textMuted }}>
                    {s.model || "default"} • {s.updated_at || s.started_at || ""}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

