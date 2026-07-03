import React, { useEffect, useState } from "react"
import { getMyDocuments, getMyProjects, listChatSessions, downloadDocumentFileApi, overrideDocumentProjectAPI, retryIngest } from "../api/client"
import { theme } from "../theme/theme"
import { Pagination } from "../components/Pagination"

/* ── Helpers ── */
const glass = (alpha = 0.07): React.CSSProperties => ({
  background: `rgba(255,255,255,${alpha})`,
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 16,
})

const card: React.CSSProperties = {
  ...glass(0.05),
  padding: "20px 24px",
  marginBottom: 0,
}

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: "rgba(255,255,255,0.35)",
  marginBottom: 6,
}

const valueStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: "#E5E7EB",
}

const mutedText: React.CSSProperties = {
  fontSize: 13,
  color: "rgba(255,255,255,0.45)",
}

const btnOutline: React.CSSProperties = {
  padding: "7px 16px",
  borderRadius: 10,
  border: "1px solid rgba(255,255,255,0.12)",
  background: "rgba(255,255,255,0.05)",
  color: "#D1D5DB",
  fontSize: 13,
  cursor: "pointer",
  fontFamily: "inherit",
  transition: "all 0.2s ease",
}

const btnPrimary: React.CSSProperties = {
  padding: "7px 16px",
  borderRadius: 10,
  border: "none",
  background: "linear-gradient(135deg, #5B88FF, #4A6FE8)",
  color: "#FFFFFF",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  fontFamily: "inherit",
  boxShadow: "0 4px 12px rgba(91,136,255,0.3)",
  transition: "all 0.2s ease",
}

const inputStyle: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 10,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(0,0,0,0.25)",
  color: "#E5E7EB",
  fontSize: 13,
  fontFamily: "inherit",
  outline: "none",
  width: "100%",
  boxSizing: "border-box" as const,
}

const statusColors: Record<string, string> = {
  ready: "#22C55E",
  completed: "#22C55E",
  failed: "#EF4444",
  processing: "#F59E0B",
  uploaded: "#5B88FF",
}

function statusColor(s: string) {
  return statusColors[s?.toLowerCase()] ?? "rgba(255,255,255,0.4)"
}

export const MyWorkPage: React.FC<{
  onOpenDocument: (documentId: string) => void
}> = ({ onOpenDocument }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const getIsNarrow = () => (typeof window !== "undefined" ? window.innerWidth < 980 : false)
  const [isNarrow, setIsNarrow] = useState(getIsNarrow)
  const [repositories, setRepositories] = useState<{ id: string; name: string; role: string }[]>([])
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
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedRepoFilter, setSelectedRepoFilter] = useState<string | null>(null)
  const [selectedDocs, setSelectedDocs] = useState<string[]>([])
  const [bulkActionLoading, setBulkActionLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<"overview" | "documents" | "sessions">("overview")
  const [docPage, setDocPage] = useState(1)
  const [docTotal, setDocTotal] = useState(0)
  const [sessPage, setSessPage] = useState(1)
  const [sessTotal, setSessTotal] = useState(0)

  const refresh = async () => {
    try {
      setLoading(true)
      setError(null)
      const [p, d, s] = await Promise.all([getMyProjects(), getMyDocuments(1, 50), listChatSessions(undefined, 50)])
      setRepositories(p.projects || [])
      setDocuments(d.documents || [])
      setDocTotal(d.total || (d.documents || []).length)
      setSessions(s.sessions || [])
      setSessTotal(s.total || (s.sessions || []).length)
    } catch (e: any) {
      setError(e.message ?? "Failed to load history")
    } finally {
      setLoading(false)
    }
  }

  const loadDocPage = async (p: number) => {
    setDocPage(p)
    try {
      const d = await getMyDocuments(p, 20)
      setDocuments(d.documents || [])
      setDocTotal(d.total || (d.documents || []).length)
    } catch (e: any) { setError(e.message ?? "Failed to load documents") }
  }

  const loadSessPage = async (p: number) => {
    setSessPage(p)
    try {
      const s = await listChatSessions(undefined, 20, p)
      setSessions(s.sessions || [])
      setSessTotal(s.total || (s.sessions || []).length)
    } catch (e: any) { setError(e.message ?? "Failed to load sessions") }
  }

  useEffect(() => { refresh() }, [])

  useEffect(() => {
    const onResize = () => setIsNarrow(getIsNarrow())
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
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

  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesRepo = !selectedRepoFilter || doc.project_id === selectedRepoFilter
    return matchesSearch && matchesRepo
  })

  const sessionsByRepo = sessions.reduce(
    (acc, session) => {
      const projId = session.project_id || "uncategorized"
      if (!acc[projId]) acc[projId] = []
      acc[projId].push(session)
      return acc
    },
    {} as Record<string, typeof sessions>
  )

  const totalDocs = documents.length
  const totalSessions = sessions.length
  const recentDocs = [...documents]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)
  const allModels = [...new Set(sessions.map((s) => s.model))].filter(Boolean)

  const tabs = [
    { id: "overview" as const, label: "Overview", icon: "📊" },
    { id: "documents" as const, label: `Documents (${totalDocs})`, icon: "📄" },
    { id: "sessions" as const, label: `Sessions (${totalSessions})`, icon: "💬" },
  ]

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}>
            My Work
          </h1>
          <p style={{ margin: "4px 0 0", ...mutedText }}>
            Repositories, documents, and conversation history
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          style={{ ...btnOutline, opacity: loading ? 0.6 : 1 }}
        >
          {loading ? "Refreshing…" : "↻ Refresh"}
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: 12,
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.2)",
            color: "#F87171",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
        {[
          { label: "Repositories", value: repositories.length, icon: "🗂️", color: "#5B88FF" },
          { label: "Documents", value: totalDocs, icon: "📄", color: "#1FE7FF" },
          { label: "Conversations", value: totalSessions, icon: "💬", color: "#A78BFA" },
          { label: "AI Models Used", value: allModels.length, icon: "🧠", color: "#22C55E" },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              ...card,
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "16px 20px",
            }}
          >
            <div
              style={{
                fontSize: 24,
                width: 44,
                height: 44,
                borderRadius: 12,
                background: `${stat.color}18`,
                border: `1px solid ${stat.color}30`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              {stat.icon}
            </div>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#FFFFFF" }}>{stat.value}</div>
              <div style={{ ...labelStyle, marginBottom: 0 }}>{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: 4,
          borderRadius: 14,
          background: "rgba(0,0,0,0.3)",
          border: "1px solid rgba(255,255,255,0.06)",
          width: "fit-content",
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "8px 18px",
              borderRadius: 11,
              border: "none",
              background:
                activeTab === tab.id
                  ? "linear-gradient(135deg, rgba(91,136,255,0.25) 0%, rgba(31,231,255,0.1) 100%)"
                  : "transparent",
              color: activeTab === tab.id ? "#FFFFFF" : "rgba(255,255,255,0.4)",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 7,
              fontFamily: "inherit",
              transition: "all 0.2s ease",
              whiteSpace: "nowrap",
            }}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── Overview tab ── */}
      {activeTab === "overview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Repositories */}
          <div style={card}>
            <div style={{ fontWeight: 700, fontSize: 16, color: "#FFFFFF", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <span>🗂️</span> My Repositories
            </div>
            {repositories.length === 0 ? (
              <div style={mutedText}>No repositories yet. Create one by uploading a document.</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {repositories.map((r) => {
                  const repoDocs = documents.filter((d) => d.project_id === r.id)
                  const repoSessions = sessions.filter((s) => s.project_id === r.id)
                  return (
                    <div
                      key={r.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 12,
                        padding: "14px 16px",
                        borderRadius: 12,
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.07)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: 10,
                            background: "rgba(91,136,255,0.15)",
                            border: "1px solid rgba(91,136,255,0.25)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 16,
                          }}
                        >
                          🗂️
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, color: "#E5E7EB", fontSize: 14 }}>{r.name}</div>
                          <div style={mutedText}>
                            Role: <span style={{ color: "#5B88FF" }}>{r.role}</span>
                          </div>
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 16, flexShrink: 0 }}>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 18, fontWeight: 800, color: "#FFFFFF" }}>{repoDocs.length}</div>
                          <div style={{ ...labelStyle, marginBottom: 0 }}>Docs</div>
                        </div>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 18, fontWeight: 800, color: "#FFFFFF" }}>{repoSessions.length}</div>
                          <div style={{ ...labelStyle, marginBottom: 0 }}>Chats</div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Recent uploads */}
          {recentDocs.length > 0 && (
            <div style={card}>
              <div style={{ fontWeight: 700, fontSize: 16, color: "#FFFFFF", marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
                <span>🕐</span> Recent Uploads
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                {recentDocs.map((d) => (
                  <div
                    key={d.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 12,
                      padding: "12px 14px",
                      borderRadius: 10,
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                      <span style={{ fontSize: 20, flexShrink: 0 }}>📄</span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, color: "#E5E7EB", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {d.filename}
                        </div>
                        <div style={mutedText}>
                          {d.project_name || "No repository"} •{" "}
                          <span style={{ color: statusColor(d.status) }}>●</span>{" "}
                          {d.status}
                        </div>
                      </div>
                    </div>
                    <button type="button" onClick={() => onOpenDocument(d.id)} style={btnPrimary}>
                      Open
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Documents tab ── */}
      {activeTab === "documents" && (
        <div style={card}>
          <div style={{ fontWeight: 700, fontSize: 16, color: "#FFFFFF", marginBottom: 16 }}>My Documents</div>

          {/* Filters & bulk */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr auto auto",
              gap: 10,
              marginBottom: 16,
            }}
          >
            <input
              type="text"
              placeholder="Search documents…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={inputStyle}
            />
            <select
              value={selectedRepoFilter || ""}
              onChange={(e) => setSelectedRepoFilter(e.target.value || null)}
              style={{ ...inputStyle, cursor: "pointer" }}
            >
              <option value="">All Repositories</option>
              {repositories.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <select
              value=""
              onChange={async (e) => {
                const v = e.target.value
                if (!v) return
                if (selectedDocs.length === 0) { setError("No documents selected"); return }
                try {
                  setBulkActionLoading(true)
                  await Promise.all(selectedDocs.map((id) => overrideDocumentProjectAPI(id, v)))
                  await refresh()
                  setSelectedDocs([])
                } catch (err: any) {
                  setError(err.message ?? "Failed to move documents")
                } finally {
                  setBulkActionLoading(false)
                }
              }}
              style={{ ...inputStyle, cursor: "pointer", minWidth: 160 }}
            >
              <option value="">Move to repository…</option>
              {repositories.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={async () => {
                if (selectedDocs.length === 0) return setError("No documents selected")
                try {
                  setBulkActionLoading(true)
                  await Promise.all(selectedDocs.map((id) => retryIngest(id)))
                  await refresh()
                  setSelectedDocs([])
                } catch (err: any) {
                  setError(err.message ?? "Retry failed")
                } finally {
                  setBulkActionLoading(false)
                }
              }}
              disabled={bulkActionLoading}
              style={{ ...btnOutline, whiteSpace: "nowrap" }}
            >
              ↺ Retry Ingest
            </button>
          </div>

          {/* Select all */}
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={selectedDocs.length > 0 && selectedDocs.length === filteredDocuments.length}
              onChange={(e) => {
                if (e.target.checked) setSelectedDocs(filteredDocuments.map((d) => d.id))
                else setSelectedDocs([])
              }}
              style={{ accentColor: "#5B88FF", width: 16, height: 16 }}
            />
            <span style={mutedText}>{selectedDocs.length} selected</span>
          </label>

          {filteredDocuments.length === 0 ? (
            <div style={mutedText}>
              {searchQuery || selectedRepoFilter ? "No documents match your filters." : "No documents yet."}
            </div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {filteredDocuments.map((d) => (
                <div
                  key={d.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 12,
                    padding: "14px 16px",
                    borderRadius: 12,
                    background: selectedDocs.includes(d.id) ? "rgba(91,136,255,0.07)" : "rgba(255,255,255,0.03)",
                    border: `1px solid ${selectedDocs.includes(d.id) ? "rgba(91,136,255,0.25)" : "rgba(255,255,255,0.07)"}`,
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                    <input
                      type="checkbox"
                      checked={selectedDocs.includes(d.id)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedDocs((s) => [...s, d.id])
                        else setSelectedDocs((s) => s.filter((x) => x !== d.id))
                      }}
                      style={{ accentColor: "#5B88FF", width: 16, height: 16, flexShrink: 0 }}
                    />
                    <span style={{ fontSize: 20, flexShrink: 0 }}>📄</span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, color: "#E5E7EB", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 14 }}>
                        {d.filename}
                      </div>
                      <div style={mutedText}>
                        {d.project_name || "No repository"} •{" "}
                        <span style={{ color: statusColor(d.status), fontWeight: 600 }}>● {d.status}</span>
                        {" "}• {new Date(d.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                    <button type="button" onClick={() => onOpenDocument(d.id)} style={btnPrimary}>Open</button>
                    <button type="button" onClick={() => download(d.id, d.filename)} style={btnOutline}>↓</button>
                  </div>
                </div>
              ))}
            </div>
          )}
          <Pagination page={docPage} totalPages={Math.ceil(docTotal / 20) || 1} total={docTotal} onPageChange={loadDocPage} />
        </div>
      )}

      {/* ── Sessions tab ── */}
      {activeTab === "sessions" && (
        <div style={card}>
          <div style={{ fontWeight: 700, fontSize: 16, color: "#FFFFFF", marginBottom: 16 }}>Recent Sessions</div>
          {sessions.length === 0 ? (
            <div style={mutedText}>No sessions yet.</div>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {Object.entries(sessionsByRepo).map(([repoId, repoSessions]) => {
                const repoName =
                  repoId === "uncategorized"
                    ? "Uncategorized"
                    : repositories.find((r) => r.id === repoId)?.name || "Unknown Repository"
                return (
                  <div key={repoId}>
                    <div
                      style={{
                        ...labelStyle,
                        marginBottom: 10,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span>🗂️</span>
                      <span>{repoName}</span>
                    </div>
                    <div style={{ display: "grid", gap: 8 }}>
                      {repoSessions.map((s) => (
                        <div
                          key={s.session_id}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: 12,
                            padding: "14px 16px",
                            borderRadius: 12,
                            background: "rgba(255,255,255,0.03)",
                            border: "1px solid rgba(255,255,255,0.07)",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div
                              style={{
                                width: 36,
                                height: 36,
                                borderRadius: 10,
                                background: "rgba(167,139,250,0.15)",
                                border: "1px solid rgba(167,139,250,0.2)",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                fontSize: 16,
                                flexShrink: 0,
                              }}
                            >
                              💬
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, color: "#E5E7EB", fontSize: 14 }}>
                                {s.title || "Conversation"}
                              </div>
                              <div style={mutedText}>
                                {s.model || "default"} •{" "}
                                {s.updated_at
                                  ? new Date(s.updated_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
                                  : s.started_at || ""}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          <Pagination page={sessPage} totalPages={Math.ceil(sessTotal / 20) || 1} total={sessTotal} onPageChange={loadSessPage} />
        </div>
      )}
    </div>
  )
}
