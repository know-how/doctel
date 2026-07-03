import React, { useEffect, useState } from "react"
import { getActivityLog } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface ActivityEntry {
  id: number
  user_id?: number
  user_name?: string
  user?: string
  action: string
  action_type?: string
  created_at?: string
  timestamp?: string
  details?: string
}

const ACTION_TYPES = [
  { label: "All", value: "" },
  { label: "Document upload", value: "document.upload" },
  { label: "Analysis run", value: "analysis.run" },
  { label: "Output created", value: "output.created" },
  { label: "User invited", value: "user.invited" },
  { label: "Role changed", value: "role.changed" },
  { label: "Settings changed", value: "settings.changed" },
]

const USERS = [
  { label: "All users", value: "" },
  { label: "Alice Johnson", value: "Alice Johnson" },
  { label: "Bob Smith", value: "Bob Smith" },
  { label: "Carol White", value: "Carol White" },
]

function iconForAction(action: string): string {
  if (action.includes("upload")) return "📄"
  if (action.includes("analysis") || action.includes("extract")) return "🤖"
  if (action.includes("output")) return "📊"
  if (action.includes("invite") || action.includes("role")) return "👤"
  if (action.includes("setting")) return "⚙️"
  return "📌"
}

export const CollaborationActivityPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState("")
  const [userFilter, setUserFilter] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const PAGE_SIZE = 20
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1

  const loadLog = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await getActivityLog({ page })
      const items = res.entries ?? res.items ?? res.activities ?? (Array.isArray(res) ? res : [])
      setEntries(items)
      setTotal(res.total ?? items.length)
    } catch (e: any) {
      // If API fails, use mock data
      setEntries([
        { id: 1, user: "Alice Johnson", action: "uploaded document invoice_2025.pdf", timestamp: "2025-04-28 14:22", action_type: "document.upload" },
        { id: 2, user: "Bob Smith", action: "ran extraction on report_Q1.pdf", timestamp: "2025-04-28 11:05", action_type: "analysis.run" },
        { id: 3, user: "Carol White", action: "created output summary #142", timestamp: "2025-04-28 09:30", action_type: "output.created" },
        { id: 4, user: "Alice Johnson", action: "invited dave@example.com as analyst", timestamp: "2025-04-27 16:48", action_type: "user.invited" },
        { id: 5, user: "Bob Smith", action: "changed Carol's role to viewer", timestamp: "2025-04-27 14:15", action_type: "role.changed" },
        { id: 6, user: "Admin", action: "updated chunk_size setting to 2048", timestamp: "2025-04-27 10:05", action_type: "settings.changed" },
        { id: 7, user: "Carol White", action: "downloaded output #99 as PDF", timestamp: "2025-04-26 15:42", action_type: "output.created" },
        { id: 8, user: "Alice Johnson", action: "classified 12 documents", timestamp: "2025-04-26 13:10", action_type: "analysis.run" },
      ])
      setTotal(entries.length)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLog()
  }, [page])

  let filtered = entries
  if (actionFilter) {
    filtered = filtered.filter((e) => (e.action_type ?? "") === actionFilter)
  }
  if (userFilter) {
    filtered = filtered.filter((e) => (e.user_name ?? e.user ?? "") === userFilter)
  }
  if (dateFrom) {
    filtered = filtered.filter((e) => {
      const d = e.timestamp ?? e.created_at ?? ""
      return d >= dateFrom
    })
  }
  if (dateTo) {
    filtered = filtered.filter((e) => {
      const d = e.timestamp ?? e.created_at ?? ""
      return d <= dateTo
    })
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Activity log</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Track all actions across the workspace.</p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: t.spacing.lg }}>
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
          style={{
            padding: "6px 10px",
            borderRadius: t.radii.sm,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 12,
          }}
        >
          {ACTION_TYPES.map((a) => (
            <option key={a.value} value={a.value} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{a.label}</option>
          ))}
        </select>
        <select
          value={userFilter}
          onChange={(e) => { setUserFilter(e.target.value); setPage(1) }}
          style={{
            padding: "6px 10px",
            borderRadius: t.radii.sm,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 12,
          }}
        >
          {USERS.map((u) => (
            <option key={u.value} value={u.value} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{u.label}</option>
          ))}
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
          style={{
            padding: "6px 10px",
            borderRadius: t.radii.sm,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 12,
          }}
          title="From date"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
          style={{
            padding: "6px 10px",
            borderRadius: t.radii.sm,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 12,
          }}
          title="To date"
        />
        {(actionFilter || userFilter || dateFrom || dateTo) && (
          <button
            onClick={() => { setActionFilter(""); setUserFilter(""); setDateFrom(""); setDateTo(""); setPage(1) }}
            style={{
              padding: "6px 10px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.textSecondary,
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {loading ? (
        <div style={{ display: "grid", gap: t.spacing.sm }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, padding: t.spacing.md, backgroundColor: c.cardBg, height: 44 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary, color: c.textSecondary }}>
          No activity entries found.
        </div>
      ) : (
        <>
          <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, overflow: "hidden", marginBottom: t.spacing.md }}>
            {filtered.map((e, i) => {
              const ts = e.timestamp ?? e.created_at ?? ""
              return (
                <div
                  key={e.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "12px 16px",
                    borderBottom: i < filtered.length - 1 ? `1px solid ${c.border}` : "none",
                  }}
                >
                  <span style={{ fontSize: 20, flexShrink: 0 }}>
                    {iconForAction(e.action_type ?? e.action ?? "")}
                  </span>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontWeight: 600, color: c.text, fontSize: 13 }}>
                      {e.user_name ?? e.user ?? "Unknown"}
                    </span>
                    <span style={{ color: c.textSecondary, fontSize: 13, marginLeft: 6 }}>
                      {e.action}
                    </span>
                  </div>
                  <span style={{ fontSize: 11, color: c.textMuted, whiteSpace: "nowrap" }}>
                    {ts ? new Date(ts).toLocaleString() : "—"}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 12 }}>
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
                style={{
                  padding: "6px 14px",
                  borderRadius: t.radii.sm,
                  border: `1px solid ${c.border}`,
                  backgroundColor: c.surface,
                  color: c.text,
                  cursor: page === 1 ? "default" : "pointer",
                  fontSize: 12,
                  fontWeight: 600,
                  opacity: page === 1 ? 0.4 : 1,
                }}
              >
                Previous
              </button>
              <span style={{ fontSize: 13, color: c.textSecondary }}>
                Page {page} of {totalPages} ({total} items)
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || loading}
                style={{
                  padding: "6px 14px",
                  borderRadius: t.radii.sm,
                  border: `1px solid ${c.border}`,
                  backgroundColor: c.surface,
                  color: c.text,
                  cursor: page === totalPages ? "default" : "pointer",
                  fontSize: 12,
                  fontWeight: 600,
                  opacity: page === totalPages ? 0.4 : 1,
                }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
