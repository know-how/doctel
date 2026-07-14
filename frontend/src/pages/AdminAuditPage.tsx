/**
 * AdminAuditPage.tsx - System Audit Log Viewer
 *
 * View system audit entries tracking configuration changes and
 * administrative actions across the platform.
 */

import React, { useEffect, useState, useCallback } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { v2GetAudit } from "../api/client"
import type { V2AuditEntry } from "../types/api"

export const AdminAuditPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [entries, setEntries] = useState<V2AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await v2GetAudit()
      setEntries(res.audit ?? [])
      setTotal(res.total ?? 0)
    } catch (e: any) {
      setError(e.message ?? "Failed to load audit log")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString()
    } catch {
      return ts
    }
  }

  const getActionColor = (action: string) => {
    const a = action.toLowerCase()
    if (a.includes("delete") || a.includes("remove")) return c.error
    if (a.includes("create") || a.includes("add")) return c.success
    if (a.includes("update") || a.includes("edit") || a.includes("change"))
      return c.warning
    return c.primary
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: c.text,
              margin: 0,
            }}
          >
            📋 Audit Log
          </h1>
          <p style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}>
            Track configuration changes and system events
          </p>
        </div>
        <div style={{ fontSize: 13, color: c.textMuted }}>
          {total} {total === 1 ? "entry" : "entries"}
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "10px 14px",
            background: c.error + "15",
            border: `1px solid ${c.error}30`,
            borderRadius: 8,
            color: c.error,
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          {error}
          <button
            onClick={() => setError(null)}
            style={{
              marginLeft: 12,
              background: "none",
              border: "none",
              color: c.error,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: c.textMuted }}>
          Loading audit log...
        </div>
      ) : entries.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            color: c.textMuted,
            background: c.surface,
            borderRadius: 12,
            border: `1px solid ${c.border}`,
          }}
        >
          <div style={{ fontSize: 40, marginBottom: 12 }}>📭</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>No audit entries yet</div>
          <div style={{ fontSize: 13, marginTop: 4 }}>
            Administrative actions will be recorded here
          </div>
        </div>
      ) : (
        <div
          style={{
            background: c.surface,
            border: `1px solid ${c.border}`,
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr
                style={{
                  fontSize: 12,
                  color: c.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                  borderBottom: `1px solid ${c.border}`,
                }}
              >
                <th style={{ padding: "12px 16px", textAlign: "left" }}>
                  Timestamp
                </th>
                <th style={{ padding: "12px 16px", textAlign: "left" }}>
                  Action
                </th>
                <th style={{ padding: "12px 16px", textAlign: "left" }}>
                  Entity
                </th>
                <th style={{ padding: "12px 16px", textAlign: "left" }}>
                  User
                </th>
                <th style={{ padding: "12px 16px", textAlign: "left" }}>
                  Details
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  style={{
                    borderBottom: `1px solid ${c.border}50`,
                    fontSize: 13,
                    color: c.text,
                  }}
                >
                  <td
                    style={{
                      padding: "12px 16px",
                      whiteSpace: "nowrap",
                      color: c.textMuted,
                      fontSize: 12,
                    }}
                  >
                    {formatTime(entry.timestamp)}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: getActionColor(entry.action) + "15",
                        color: getActionColor(entry.action),
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>
                      {entry.entityType}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: c.textMuted,
                        fontFamily: "monospace",
                      }}
                    >
                      {entry.entityId}
                    </div>
                  </td>
                  <td
                    style={{
                      padding: "12px 16px",
                      color: c.textSecondary,
                    }}
                  >
                    {entry.userName || entry.userId}
                  </td>
                  <td
                    style={{
                      padding: "12px 16px",
                      color: c.textMuted,
                      fontSize: 12,
                      maxWidth: 200,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {entry.details
                      ? JSON.stringify(entry.details).slice(0, 60)
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
