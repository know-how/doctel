import React, { useEffect, useMemo, useState } from "react"
import {
  adminBackupSettings,
  adminGetSettings,
  adminGetSettingsAudit,
  adminPatchSettings,
  adminTestSettings,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { Badge, Button, Card, GlassPanel, Text } from "../components/styled"

type Category =
  | "models"
  | "rag"
  | "security"
  | "storage"
  | "ui"
  | "zetdc"
  | "diagnostics"
  | "audit"

const categories: { id: Category; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "rag", label: "RAG/Ingestion" },
  { id: "security", label: "Security/Auth/RBAC" },
  { id: "storage", label: "Storage" },
  { id: "ui", label: "UI/UX" },
  { id: "zetdc", label: "ZETDC Domain" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "audit", label: "Audit" },
]

export const AdminSettingsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const [active, setActive] = useState<Category>("models")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [effective, setEffective] = useState<any>(null)
  const [sources, setSources] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState("")
  const [restartMap, setRestartMap] = useState<Record<string, boolean>>({})
  const [auditRows, setAuditRows] = useState<any[]>([])
  const [backupPath, setBackupPath] = useState<string | null>(null)

  const sourceSummary = useMemo(() => {
    const prefix =
      active === "models"
        ? ["default_model", "available_models", "embed_model", "vision_model", "pull."]
        : active === "rag"
          ? ["chunk_size", "chunk_overlap", "top_k", "use_mmr", "max_context_tokens", "bootstrap."]
          : active === "security"
            ? ["security.", "rbac.", "auth."]
            : active === "storage"
              ? ["storage."]
              : active === "ui"
                ? ["ui."]
                : active === "zetdc"
                  ? ["zetdc."]
                  : active === "diagnostics"
                    ? ["diagnostics."]
                    : []
    const counts: Record<string, number> = { default: 0, file: 0, db: 0 }
    for (const [k, src] of Object.entries(sources || {})) {
      if (!prefix.some((p) => k === p || k.startsWith(p))) continue
      if (src === "db") counts.db += 1
      else if (src === "file") counts.file += 1
      else counts.default += 1
    }
    return counts
  }, [sources, active])

  const categoryObject = useMemo(() => {
    if (!effective) return {}
    if (active === "models") {
      const out: any = {}
      out.default_model = effective.default_model
      out.available_models = effective.available_models
      out.embed_model = effective.embed_model
      out.vision_model = effective.vision_model
      out.pull = effective.pull
      return out
    }
    if (active === "rag") {
      const out: any = {}
      out.chunk_size = effective.chunk_size
      out.chunk_overlap = effective.chunk_overlap
      out.top_k = effective.top_k
      out.use_mmr = effective.use_mmr
      out.max_context_tokens = effective.max_context_tokens
      out.bootstrap = effective.bootstrap
      return out
    }
    if (active === "security") {
      const out: any = {}
      out.security = effective.security
      out.rbac = effective.rbac
      out.auth = effective.auth
      return out
    }
    if (active === "storage") return { storage: effective.storage }
    if (active === "ui") return { ui: effective.ui }
    if (active === "zetdc") return { zetdc: effective.zetdc }
    if (active === "diagnostics") return { diagnostics: effective.diagnostics }
    return {}
  }, [effective, active])

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await adminGetSettings()
      setEffective(res.effective)
      setSources(res.sources || {})
    } catch (e: any) {
      setError(e.message ?? "Failed to load settings")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (active === "audit") return
    try {
      setDraft(JSON.stringify(categoryObject ?? {}, null, 2))
    } catch {
      setDraft("{}")
    }
  }, [active, categoryObject])

  useEffect(() => {
    const loadAudit = async () => {
      if (active !== "audit") return
      try {
        setLoading(true)
        setError(null)
        const res = await adminGetSettingsAudit(100)
        setAuditRows(res.audit || [])
      } catch (e: any) {
        setError(e.message ?? "Failed to load audit")
      } finally {
        setLoading(false)
      }
    }
    loadAudit()
  }, [active])

  const save = async () => {
    try {
      setError(null)
      const parsed = JSON.parse(draft || "{}")
      setLoading(true)
      const res = await adminPatchSettings(parsed)
      setEffective(res.effective)
      setSources(res.sources || {})
      setRestartMap(res.restart_recommended || {})
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setLoading(false)
    }
  }

  const test = async () => {
    try {
      setError(null)
      const parsed = JSON.parse(draft || "{}")
      setLoading(true)
      const res = await adminTestSettings(parsed)
      setRestartMap(res.restart_recommended || {})
    } catch (e: any) {
      setError(e.message ?? "Test failed")
    } finally {
      setLoading(false)
    }
  }

  const backup = async () => {
    try {
      setError(null)
      setLoading(true)
      const res = await adminBackupSettings()
      setBackupPath(res.path)
    } catch (e: any) {
      setError(e.message ?? "Backup failed")
    } finally {
      setLoading(false)
    }
  }

  const restartKeys = Object.entries(restartMap).filter(([, v]) => !!v).map(([k]) => k)

  const categoryIcons: Record<Category, string> = {
    models: "🤖",
    rag: "📚",
    security: "🔒",
    storage: "💾",
    ui: "🎨",
    zetdc: "⚡",
    diagnostics: "🔍",
    audit: "📋",
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "240px minmax(0, 1fr)", gap: t.spacing.lg, height: "100%" }}>
      {/* Sidebar */}
      <GlassPanel
        variant="medium"
        style={{
          padding: t.spacing.md,
          height: "calc(100vh - 64px - 48px)",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{
          fontSize: 15, fontWeight: 800, color: t.colors.text,
          marginBottom: t.spacing.md, padding: `${t.spacing.xs}px ${t.spacing.sm}px`,
          letterSpacing: "-0.2px",
          background: `linear-gradient(135deg, ${t.colors.text} 0%, ${t.colors.primary} 100%)`,
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}>
          ⚙️ System Settings
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
          {categories.map((c) => {
            const isActive = active === c.id
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => setActive(c.id)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 12px",
                  borderRadius: t.radii.md,
                  border: isActive
                    ? `1px solid ${t.colors.primary}40`
                    : `1px solid transparent`,
                  background: isActive
                    ? `linear-gradient(135deg, ${t.colors.primary}20, ${t.colors.primary}08)`
                    : "transparent",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  backdropFilter: isActive ? "blur(4px)" : "none",
                  boxShadow: isActive ? `0 0 20px ${t.colors.primary}15` : "none",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = `${t.colors.surface}80`
                    e.currentTarget.style.borderColor = `${t.colors.border}60`
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "transparent"
                    e.currentTarget.style.borderColor = "transparent"
                  }
                }}
              >
                <span style={{ fontSize: 16 }}>{categoryIcons[c.id]}</span>
                <span style={{
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? t.colors.text : t.colors.textSecondary,
                }}>
                  {c.label}
                </span>
                {isActive && (
                  <span style={{
                    marginLeft: "auto",
                    width: 6, height: 6, borderRadius: "50%",
                    background: t.colors.primary,
                    boxShadow: `0 0 10px ${t.colors.primary}`,
                  }} />
                )}
              </button>
            )
          })}
        </div>
      </GlassPanel>

      {/* Main content */}
      <div style={{ display: "flex", flexDirection: "column", gap: t.spacing.md, minWidth: 0 }}>

        {/* Restart warning */}
        {restartKeys.length > 0 && (
          <GlassPanel
            variant="light"
            style={{
              padding: t.spacing.md,
              border: `1px solid ${t.colors.accent}50`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 18 }}>🔄</span>
              <div>
                <div style={{ fontWeight: 700, color: t.colors.text, fontSize: 13 }}>
                  Restart recommended
                </div>
                <div style={{ fontSize: 12, color: t.colors.textMuted, marginTop: 2 }}>
                  Some changed keys may require a restart:{" "}
                  <span style={{ color: t.colors.accent }}>{restartKeys.slice(0, 6).join(", ")}{restartKeys.length > 6 ? "…" : ""}</span>
                </div>
              </div>
            </div>
          </GlassPanel>
        )}

        {/* Category header */}
        <GlassPanel
          variant="light"
          style={{
            padding: `${t.spacing.md}px ${t.spacing.lg}px`,
            display: "flex",
            justifyContent: "space-between",
            gap: t.spacing.md,
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 18 }}>{categoryIcons[active]}</span>
              <h2 style={{
                margin: 0, fontSize: 16, fontWeight: 700, color: t.colors.text,
                letterSpacing: "-0.2px",
              }}>
                {categories.find((c) => c.id === active)?.label}
              </h2>
            </div>
            <div style={{ fontSize: 12, color: t.colors.textMuted, marginTop: 4, marginLeft: 2 }}>
              Effective settings = defaults + config.yaml + DB overrides
            </div>
            {active !== "audit" && (
              <div style={{ fontSize: 11, color: t.colors.textMuted, marginTop: 2, marginLeft: 2 }}>
                <span style={{ color: t.colors.textSecondary }}>Sources:</span>{" "}
                <Badge variant="secondary" style={{ fontSize: 10 }}>default {sourceSummary.default}</Badge>{" "}
                <Badge variant="primary" style={{ fontSize: 10 }}>file {sourceSummary.file}</Badge>{" "}
                <Badge variant="success" style={{ fontSize: 10 }}>db {sourceSummary.db}</Badge>
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
              ⟳ Refresh
            </Button>
            <Button variant="secondary" size="sm" onClick={backup} disabled={loading}>
              💾 Backup
            </Button>
          </div>
        </GlassPanel>

        {backupPath && (
          <div style={{ fontSize: 12, color: t.colors.success, padding: `0 ${t.spacing.xs}px` }}>
            ✅ Backup written: {backupPath}
          </div>
        )}

        {error && (
          <GlassPanel variant="light" style={{ padding: t.spacing.sm, border: `1px solid ${t.colors.error}60` }}>
            <div style={{ color: t.colors.error, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
              <span>⚠️</span> {error}
            </div>
          </GlassPanel>
        )}

        {active === "audit" ? (
          <GlassPanel
            variant="medium"
            style={{
              padding: t.spacing.md,
              height: "calc(100vh - 64px - 48px - 120px)",
              overflowY: "auto",
            }}
          >
            {auditRows.length === 0 ? (
              <div style={{ fontSize: 13, color: t.colors.textMuted, textAlign: "center", padding: 40 }}>
                No audit entries found.
              </div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {auditRows.map((r) => (
                  <Card key={r.id} hover={false} style={{ padding: t.spacing.md }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span style={{ fontWeight: 700, color: t.colors.text, fontSize: 13 }}>{r.key}</span>
                      <Badge variant="secondary" style={{ fontSize: 10 }}>v{r.id}</Badge>
                    </div>
                    <div style={{ fontSize: 11, color: t.colors.textMuted, marginBottom: 8 }}>
                      {r.changed_at} • user_id={r.changed_by_user_id}
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: t.spacing.md }}>
                      <div style={{
                        background: `${t.colors.bgSecondary}90`,
                        borderRadius: t.radii.sm,
                        padding: t.spacing.sm,
                        border: `1px solid ${t.colors.error}30`,
                      }}>
                        <div style={{ fontSize: 10, color: t.colors.error, fontWeight: 600, marginBottom: 4 }}>OLD</div>
                        <pre style={{ margin: 0, fontSize: 11, whiteSpace: "pre-wrap", color: t.colors.textSecondary }}>{r.old_value}</pre>
                      </div>
                      <div style={{
                        background: `${t.colors.bgSecondary}90`,
                        borderRadius: t.radii.sm,
                        padding: t.spacing.sm,
                        border: `1px solid ${t.colors.success}30`,
                      }}>
                        <div style={{ fontSize: 10, color: t.colors.success, fontWeight: 600, marginBottom: 4 }}>NEW</div>
                        <pre style={{ margin: 0, fontSize: 11, whiteSpace: "pre-wrap", color: t.colors.text }}>{r.new_value}</pre>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </GlassPanel>
        ) : (
          <>
            <div style={{ position: "relative", flex: 1 }}>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                spellCheck={false}
                style={{
                  width: "100%",
                  minHeight: "calc(100vh - 64px - 48px - 220px)",
                  borderRadius: t.radii.lg,
                  border: `1px solid ${t.colors.border}`,
                  padding: t.spacing.lg,
                  fontFamily: "'SF Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace",
                  fontSize: 12.5,
                  lineHeight: 1.6,
                  backgroundColor: `${t.colors.bgSecondary}CC`,
                  color: "#E2E8F0",
                  outline: "none",
                  resize: "vertical",
                  boxSizing: "border-box",
                  backdropFilter: "blur(8px)",
                  tabSize: 2,
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = t.colors.primary
                  e.currentTarget.style.boxShadow = `0 0 20px ${t.colors.primary}20`
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = t.colors.border
                  e.currentTarget.style.boxShadow = "none"
                }}
              />
              <div style={{
                position: "absolute",
                top: 12, right: 12,
                fontSize: 10, color: t.colors.textMuted,
                background: `${t.colors.bgSecondary}80`,
                padding: "2px 8px",
                borderRadius: t.radii.sm,
                backdropFilter: "blur(4px)",
                pointerEvents: "none",
              }}>
                JSON
              </div>
            </div>

            <GlassPanel
              variant="light"
              style={{
                padding: `${t.spacing.sm}px ${t.spacing.md}px`,
                display: "flex",
                justifyContent: "space-between",
                gap: t.spacing.md,
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: 11, color: t.colors.textMuted }}>
                Edit the JSON configuration directly • sources map shown per key
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <Button variant="secondary" size="sm" onClick={test} disabled={loading}>
                  🧪 Test & Validate
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={save}
                  disabled={loading}
                  style={{ minWidth: 80, justifyContent: "center" }}
                >
                  {loading ? "⟳" : "💾 Save"}
                </Button>
              </div>
            </GlassPanel>
          </>
        )}
      </div>
    </div>
  )
}
