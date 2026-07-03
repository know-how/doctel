import React, { useEffect, useState } from "react"
import { updateIntegrationSettings } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface ApiKeyEntry {
  id: string
  name: string
  prefix: string
  created: string
  last_used?: string
}

const mockApiKeys: ApiKeyEntry[] = [
  { id: "1", name: "Production API Key", prefix: "dci_pk_", created: "2025-01-10", last_used: "2025-04-28" },
  { id: "2", name: "Testing API Key", prefix: "dci_tk_", created: "2025-02-15", last_used: "2025-04-20" },
]

function mask(key: string): string {
  if (key.length <= 8) return "••••••••"
  return key.slice(0, 4) + "••••" + key.slice(-4)
}

export const AdminIntegrationsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [storageType, setStorageType] = useState("local")
  const [s3Bucket, setS3Bucket] = useState("")
  const [s3Region, setS3Region] = useState("")
  const [s3Endpoint, setS3Endpoint] = useState("")
  const [webhookUrl, setWebhookUrl] = useState("")
  const [webhookEvents, setWebhookEvents] = useState<Set<string>>(new Set(["document.ingested"]))
  const [showNewApiKey, setShowNewApiKey] = useState(false)
  const [newKeyName, setNewKeyName] = useState("")
  const [apiKeys] = useState<ApiKeyEntry[]>(mockApiKeys)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const toggleWebhookEvent = (evt: string) => {
    setWebhookEvents((prev) => {
      const next = new Set(prev)
      if (next.has(evt)) next.delete(evt)
      else next.add(evt)
      return next
    })
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      setSuccessMsg(null)
      await updateIntegrationSettings({
        storage: { type: storageType, bucket: s3Bucket, region: s3Region, endpoint: s3Endpoint },
        webhooks: { url: webhookUrl, events: Array.from(webhookEvents) },
      })
      setSuccessMsg("Integration settings saved successfully.")
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Integrations</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Manage API keys, storage, and webhook configurations.</p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}
      {successMsg && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.success + "18", color: c.success, fontSize: 13 }}>
          {successMsg}
        </div>
      )}

      {/* API Keys */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.md }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: c.text }}>API keys</h3>
          <button
            onClick={() => setShowNewApiKey(!showNewApiKey)}
            style={{
              padding: "6px 14px",
              borderRadius: t.radii.sm,
              border: "none",
              backgroundColor: c.primary,
              color: "#FFFFFF",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            + New key
          </button>
        </div>

        {showNewApiKey && (
          <div style={{ marginBottom: t.spacing.md, display: "flex", gap: 8 }}>
            <input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name..."
              style={{
                flex: 1,
                padding: "8px 10px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
              }}
            />
            <button
              onClick={() => { setShowNewApiKey(false); setNewKeyName("") }}
              style={{
                padding: "8px 14px",
                borderRadius: t.radii.sm,
                border: "none",
                backgroundColor: c.primary,
                color: "#FFFFFF",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              Create
            </button>
          </div>
        )}

        <div style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, overflow: "hidden" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr 1fr 1fr",
              gap: 12,
              padding: "8px 14px",
              backgroundColor: c.surface,
              borderBottom: `1px solid ${c.border}`,
              fontWeight: 700,
              fontSize: 11,
              color: c.textSecondary,
            }}
          >
            <div>Name</div><div>API Key</div><div>Created</div><div>Last used</div>
          </div>
          {apiKeys.map((key) => (
            <div
              key={key.id}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr",
                gap: 12,
                padding: "10px 14px",
                fontSize: 13,
                color: c.text,
                borderBottom: `1px solid ${c.border}`,
              }}
            >
              <div style={{ fontWeight: 600 }}>{key.name}</div>
              <div style={{ fontFamily: "monospace", fontSize: 12, color: c.textMuted }}>
                {key.prefix}{mask("abcdefghijklmnop")}
              </div>
              <div style={{ fontSize: 12, color: c.textSecondary }}>{key.created}</div>
              <div style={{ fontSize: 12, color: c.textSecondary }}>{key.last_used ?? "—"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Storage */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Storage integration</h3>
        <div style={{ display: "grid", gap: 12 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>Storage type</label>
            <select
              value={storageType}
              onChange={(e) => setStorageType(e.target.value)}
              style={{
                padding: "8px 10px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
                minWidth: 200,
              }}
            >
              <option value="local" style={{ backgroundColor: c.bgSecondary, color: c.text }}>Local filesystem</option>
              <option value="s3" style={{ backgroundColor: c.bgSecondary, color: c.text }}>Amazon S3</option>
              <option value="minio" style={{ backgroundColor: c.bgSecondary, color: c.text }}>MinIO</option>
            </select>
          </div>
          {storageType !== "local" && (
            <>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>Bucket</label>
                <input
                  value={s3Bucket}
                  onChange={(e) => setS3Bucket(e.target.value)}
                  placeholder="my-docintel-bucket"
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: t.radii.sm,
                    border: `1px solid ${c.border}`,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 13,
                    boxSizing: "border-box",
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>Region</label>
                <input
                  value={s3Region}
                  onChange={(e) => setS3Region(e.target.value)}
                  placeholder="us-east-1"
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: t.radii.sm,
                    border: `1px solid ${c.border}`,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 13,
                    boxSizing: "border-box",
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>Endpoint (optional)</label>
                <input
                  value={s3Endpoint}
                  onChange={(e) => setS3Endpoint(e.target.value)}
                  placeholder="https://s3.example.com"
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: t.radii.sm,
                    border: `1px solid ${c.border}`,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 13,
                    boxSizing: "border-box",
                  }}
                />
              </div>
            </>
          )}
        </div>
      </div>

      {/* Webhooks */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Webhook configuration</h3>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>Webhook URL</label>
          <input
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="https://example.com/webhook"
            style={{
              width: "100%",
              padding: "8px 10px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
              boxSizing: "border-box",
            }}
          />
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 6 }}>Events</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {[
              "document.ingested",
              "document.analyzed",
              "output.created",
              "model.pulled",
              "user.invited",
            ].map((evt) => (
              <label
                key={evt}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 12px",
                  borderRadius: t.radii.full,
                  border: `1px solid ${webhookEvents.has(evt) ? c.primary : c.border}`,
                  backgroundColor: webhookEvents.has(evt) ? c.surfaceActive : c.surface,
                  cursor: "pointer",
                  fontSize: 12,
                  color: c.text,
                }}
              >
                <input
                  type="checkbox"
                  checked={webhookEvents.has(evt)}
                  onChange={() => toggleWebhookEvent(evt)}
                  style={{ accentColor: c.primary }}
                />
                {evt}
              </label>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        style={{
          padding: "10px 20px",
          borderRadius: t.radii.md,
          border: "none",
          backgroundColor: c.primary,
          color: "#FFFFFF",
          cursor: saving ? "default" : "pointer",
          fontWeight: 600,
          fontSize: 14,
          opacity: saving ? 0.5 : 1,
        }}
      >
        {saving ? "Saving..." : "Save integration settings"}
      </button>
    </div>
  )
}
