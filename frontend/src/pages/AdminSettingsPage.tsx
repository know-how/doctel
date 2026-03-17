import React, { useEffect, useMemo, useState } from "react"
import {
  adminBackupSettings,
  adminGetSettings,
  adminGetSettingsAudit,
  adminPatchSettings,
  adminTestSettings,
} from "../api/client"
import { colors } from "../theme/colors"

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

  return (
    <div style={{ display: "grid", gridTemplateColumns: "240px minmax(0, 1fr)", gap: 16 }}>
      <div
        style={{
          backgroundColor: "#FFFFFF",
          borderRadius: 12,
          border: `1px solid ${colors.border}`,
          padding: 10,
          height: "calc(100vh - 64px - 48px)",
          overflowY: "auto",
        }}
      >
        <div style={{ fontWeight: 800, marginBottom: 10, color: colors.textPrimary }}>
          System Settings
        </div>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setActive(c.id)}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "10px 10px",
              borderRadius: 10,
              border: `1px solid ${colors.border}`,
              backgroundColor: active === c.id ? "#E7F0FF" : "#FFFFFF",
              cursor: "pointer",
              marginBottom: 8,
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
        {restartKeys.length > 0 && (
          <div
            style={{
              backgroundColor: "#FFF5D6",
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              padding: 12,
            }}
          >
            <div style={{ fontWeight: 800, color: colors.textPrimary }}>Restart recommended</div>
            <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
              Some changed keys may require a restart: {restartKeys.slice(0, 6).join(", ")}
              {restartKeys.length > 6 ? "…" : ""}
            </div>
          </div>
        )}

        <div
          style={{
            backgroundColor: "#FFFFFF",
            borderRadius: 12,
            border: `1px solid ${colors.border}`,
            padding: 12,
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontWeight: 800, color: colors.textPrimary }}>
              {categories.find((c) => c.id === active)?.label}
            </div>
            <div style={{ fontSize: 12, color: colors.textMuted }}>
              Effective settings = defaults + config.yaml + DB overrides.
            </div>
            {active !== "audit" && (
              <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
                Sources in this view: default {sourceSummary.default} • file {sourceSummary.file} • db{" "}
                {sourceSummary.db}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              style={{
                padding: "8px 10px",
                borderRadius: 10,
                border: `1px solid ${colors.border}`,
                backgroundColor: "#FFFFFF",
                cursor: loading ? "default" : "pointer",
                opacity: loading ? 0.6 : 1,
              }}
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={backup}
              disabled={loading}
              style={{
                padding: "8px 10px",
                borderRadius: 10,
                border: `1px solid ${colors.border}`,
                backgroundColor: "#FFFFFF",
                cursor: loading ? "default" : "pointer",
                opacity: loading ? 0.6 : 1,
              }}
            >
              Backup
            </button>
          </div>
        </div>

        {backupPath && (
          <div style={{ fontSize: 12, color: colors.textMuted }}>
            Backup written: {backupPath}
          </div>
        )}

        {error && <div style={{ color: colors.danger, fontSize: 13 }}>{error}</div>}

        {active === "audit" ? (
          <div
            style={{
              backgroundColor: "#FFFFFF",
              borderRadius: 12,
              border: `1px solid ${colors.border}`,
              padding: 12,
              height: "calc(100vh - 64px - 48px - 120px)",
              overflowY: "auto",
            }}
          >
            {auditRows.length === 0 ? (
              <div style={{ fontSize: 13, color: colors.textMuted }}>No audit entries.</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {auditRows.map((r) => (
                  <div
                    key={r.id}
                    style={{
                      border: `1px solid ${colors.border}`,
                      borderRadius: 12,
                      padding: 10,
                    }}
                  >
                    <div style={{ fontWeight: 800 }}>{r.key}</div>
                    <div style={{ fontSize: 12, color: colors.textMuted }}>
                      {r.changed_at} • user_id={r.changed_by_user_id}
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 8 }}>
                      <pre style={{ margin: 0, fontSize: 11, whiteSpace: "pre-wrap" }}>{r.old_value}</pre>
                      <pre style={{ margin: 0, fontSize: 11, whiteSpace: "pre-wrap" }}>{r.new_value}</pre>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              spellCheck={false}
              style={{
                width: "100%",
                minHeight: "calc(100vh - 64px - 48px - 220px)",
                borderRadius: 12,
                border: `1px solid ${colors.border}`,
                padding: 12,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: 12,
                backgroundColor: "#0F172A",
                color: "#E2E8F0",
                outline: "none",
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />

            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div style={{ fontSize: 12, color: colors.textMuted }}>
                Sources map is available per key; this editor saves the JSON shown.
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={test}
                  disabled={loading}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    cursor: loading ? "default" : "pointer",
                    opacity: loading ? 0.6 : 1,
                  }}
                >
                  Test & Validate
                </button>
                <button
                  type="button"
                  onClick={save}
                  disabled={loading}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "none",
                    backgroundColor: colors.primary,
                    color: "#FFFFFF",
                    cursor: loading ? "default" : "pointer",
                    opacity: loading ? 0.6 : 1,
                  }}
                >
                  Save
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
