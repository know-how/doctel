import React, { useEffect, useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

/* ── Types ─────────────────────────────────────────────── */

interface SystemStatus {
  frontend: ServiceStatus
  backend: ServiceStatus
  database: ServiceStatus
  websocket: ServiceStatus
  startup: any
  cache: any
  services: Record<string, ServiceStatus>
  system?: any
}

interface ServiceStatus {
  status: "healthy" | "degraded" | "offline" | "pending" | "unknown"
  message?: string
  error?: string
  hint?: string
  latency_ms?: number
}

/* ── Helpers ───────────────────────────────────────────── */

const statusColors: Record<string, string> = {
  healthy: "#22C55E",
  degraded: "#F59E0B",
  offline: "#EF4444",
  pending: "#5B88FF",
  unknown: "#9CA3AF",
}

const statusIcons: Record<string, string> = {
  healthy: "✅",
  degraded: "⚠️",
  offline: "❌",
  pending: "⟳",
  unknown: "❓",
}

function ServiceRow({ name, info }: { name: string; info: ServiceStatus }) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const col = statusColors[info.status] || c.textMuted

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "8px 12px",
      borderRadius: 8,
      border: `1px solid ${c.border}`,
      backgroundColor: c.cardBg,
    }}>
      <span style={{ fontSize: 16 }}>{statusIcons[info.status] || "❓"}</span>
      <span style={{ fontWeight: 600, fontSize: 13, color: c.text, minWidth: 130 }}>{name}</span>
      <span style={{
        padding: "1px 8px",
        borderRadius: 9999,
        fontSize: 10,
        fontWeight: 700,
        backgroundColor: col + "18",
        color: col,
        border: `1px solid ${col}33`,
        textTransform: "capitalize",
      }}>
        {info.status}
      </span>
      {info.latency_ms !== undefined && info.latency_ms !== null && (
        <span style={{ fontSize: 10, color: c.textMuted }}>{info.latency_ms.toFixed(0)}ms</span>
      )}
      <span style={{ fontSize: 11, color: c.textSecondary, flex: 1, textAlign: "right" }}>
        {info.message || ""}
      </span>
    </div>
  )
}

/* ── Page Component ────────────────────────────────────── */

export const SystemStatusPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const loadStatus = async () => {
    try {
      setError(null)
      const res = await fetch("/api/system/status", {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("docintel_auth_token") || ""}`,
        },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setStatus(data)
    } catch (e: any) {
      setError(e.message || "Failed to load status")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(loadStatus, 30000)
    return () => clearInterval(interval)
  }, [autoRefresh])

  const allServices = status ? {
    "Frontend": status.frontend,
    "Backend API": status.backend,
    "Database": status.database,
    "WebSocket": status.websocket,
    ...(status.services || {}),
  } : {}

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: c.text, display: "flex", alignItems: "center", gap: 10 }}>
            <span>📊</span> System Status
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
            Real-time health monitoring for all platform services.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontSize: 11, color: c.textSecondary, display: "flex", alignItems: "center", gap: 4 }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{ accentColor: c.primary }}
            />
            Auto-refresh
          </label>
          <button
            onClick={loadStatus}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.text,
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            ⟳ Refresh
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          padding: "8px 12px", marginBottom: 12, borderRadius: 8,
          backgroundColor: c.error + "18", color: c.error, fontSize: 12, fontWeight: 600,
        }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 48, color: c.textSecondary }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          Loading system status...
        </div>
      ) : status ? (
        <>
          {/* Service Status Cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 20 }}>
            {Object.entries(allServices).map(([name, info]) => (
              <ServiceRow key={name} name={name} info={info} />
            ))}
          </div>

          {/* Startup Summary */}
          {status.startup && (
            <div style={{
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              backgroundColor: c.cardBg,
              padding: 16,
              marginBottom: 20,
            }}>
              <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: c.text }}>Startup Summary</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, fontSize: 12, color: c.textSecondary }}>
                <div>
                  <div style={{ fontWeight: 600, color: c.text }}>Critical</div>
                  <div>{status.startup.critical_ready ? "✅ Ready" : "⚠️ Not ready"}</div>
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: c.text }}>Healthy</div>
                  <div style={{ color: "#22C55E" }}>{status.startup.healthy}/{status.startup.total}</div>
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: c.text }}>Uptime</div>
                  <div>{Math.floor((status.startup.uptime_seconds || 0) / 60)}m {(status.startup.uptime_seconds || 0) % 60}s</div>
                </div>
              </div>

              {/* Startup services detail */}
              {status.startup.services && status.startup.services.length > 0 && (
                <div style={{ marginTop: 10, borderTop: `1px solid ${c.border}`, paddingTop: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 6 }}>Service Startup Timeline</div>
                  {status.startup.services.map((svc: any) => {
                    const col = statusColors[svc.status] || c.textMuted
                    return (
                      <div key={svc.name} style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "4px 8px", borderRadius: 6, marginBottom: 2,
                        backgroundColor: c.surface, fontSize: 11,
                      }}>
                        <span style={{
                          width: 8, height: 8, borderRadius: "50%",
                          backgroundColor: col, flexShrink: 0,
                        }} />
                        <span style={{ fontWeight: 600, color: c.text, minWidth: 120 }}>{svc.name}</span>
                        <span style={{
                          padding: "1px 6px", borderRadius: 4,
                          fontSize: 9, fontWeight: 700, textTransform: "capitalize",
                          backgroundColor: col + "18", color: col,
                        }}>
                          {svc.status}
                        </span>
                        {svc.critical && <span style={{ fontSize: 9, color: c.primary }}>critical</span>}
                        {svc.duration_ms && <span style={{ color: c.textMuted }}>{svc.duration_ms.toFixed(0)}ms</span>}
                        {svc.error && <span style={{ color: c.error, marginLeft: "auto" }}>{svc.error}</span>}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Cache Stats */}
          {status.cache && (
            <div style={{
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              backgroundColor: c.cardBg,
              padding: 16,
              marginBottom: 20,
            }}>
              <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: c.text }}>Cache Statistics</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12, color: c.textSecondary }}>
                <div>Size: <strong style={{ color: c.text }}>{status.cache.size}</strong> / {status.cache.max_entries} entries</div>
                <div>Hit Rate: <strong style={{ color: "#22C55E" }}>{status.cache.hit_rate_percent}%</strong></div>
                <div>Hits: <strong style={{ color: c.text }}>{status.cache.hits}</strong></div>
                <div>Misses: <strong style={{ color: c.text }}>{status.cache.misses}</strong></div>
                <div>Tags: <strong style={{ color: c.text }}>{status.cache.tags}</strong></div>
                <div>TTL: <strong style={{ color: c.text }}>{status.cache.default_ttl_seconds}s</strong></div>
              </div>
            </div>
          )}

          {/* System Info */}
          {status.system && (
            <div style={{
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              backgroundColor: c.cardBg,
              padding: 16,
            }}>
              <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: c.text }}>System Information</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12, color: c.textSecondary }}>
                <div>Database: <strong style={{ color: c.text }}>{status.system.mysql ? "MySQL" : "SQLite"}</strong></div>
                <div>Python: <strong style={{ color: c.text }}>{status.system.python_version}</strong></div>
                <div>Platform: <strong style={{ color: c.text }}>{status.system.platform}</strong></div>
                <div>Base: <strong style={{ color: c.text }} style={{ fontSize: 10 }}>{status.system.base_dir}</strong></div>
              </div>
            </div>
          )}
        </>
      ) : (
        <div style={{
          textAlign: "center", padding: "48px 24px", borderRadius: 16,
          border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📡</div>
          <h3 style={{ margin: "0 0 8px", color: c.text }}>Unable to Load Status</h3>
          <p style={{ margin: "0 0 16px", fontSize: 13, color: c.textSecondary }}>
            Could not retrieve system status from the backend.
          </p>
          <button onClick={loadStatus} style={{
            padding: "8px 20px", borderRadius: 8, border: "none",
            backgroundColor: c.primary, color: "#FFF", fontWeight: 600,
            fontSize: 13, cursor: "pointer",
          }}>
            Retry
          </button>
        </div>
      )}
    </div>
  )
}
