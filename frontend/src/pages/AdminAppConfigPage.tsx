import React, { useEffect, useState, useCallback } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface SettingSchema {
  default: any
  type: string
  description: string
  secret?: boolean
}

interface SettingValue {
  key: string
  value: any
  type: string
  description: string
  is_secret: boolean
}

interface EffectiveSetting extends SettingValue {
  source: string
  database_value: any
  file_value: any
  default_value: any
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"

const sectionLabels: Record<string, string> = {
  app: "Application",
  ollama: "Ollama / Local LLM",
  api: "External API Keys",
  routing: "Model Routing",
  rag: "RAG / Document Processing",
  auth: "Authentication",
  email: "Email / SMTP",
}

const typeIcons: Record<string, string> = {
  string: "📝",
  int: "🔢",
  bool: "☑️",
}

export const AdminAppConfigPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [schema, setSchema] = useState<Record<string, SettingSchema>>({})
  const [settings, setSettings] = useState<Record<string, any>>({})
  const [effectiveSettings, setEffectiveSettings] = useState<Record<string, EffectiveSetting>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [activeSection, setActiveSection] = useState<string>("app")
  const [editedValues, setEditedValues] = useState<Record<string, any>>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})

  const getAuthHeaders = () => {
    const token = localStorage.getItem("access_token")
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
  }

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setMessage(null)

      // Load schema
      const schemaRes = await fetch(`${API_BASE}/api/admin/config/schema`, {
        headers: getAuthHeaders(),
      })
      if (!schemaRes.ok) throw new Error("Failed to load schema")
      const schemaData = await schemaRes.json()
      setSchema(schemaData.schema || {})

      // Load current settings
      const settingsRes = await fetch(`${API_BASE}/api/admin/config/settings`, {
        headers: getAuthHeaders(),
      })
      if (!settingsRes.ok) throw new Error("Failed to load settings")
      const settingsData = await settingsRes.json()
      setSettings(settingsData.settings || {})

      // Load effective settings (with source info)
      const effectiveData: Record<string, EffectiveSetting> = {}
      for (const key of Object.keys(schemaData.schema || {})) {
        try {
          const effRes = await fetch(`${API_BASE}/api/admin/config/effective/${key}`, {
            headers: getAuthHeaders(),
          })
          if (effRes.ok) {
            effectiveData[key] = await effRes.json()
          }
        } catch (e) {
          // Ignore individual failures
        }
      }
      setEffectiveSettings(effectiveData)
    } catch (e: any) {
      setMessage({ type: "error", text: e.message || "Failed to load configuration" })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleValueChange = (key: string, value: any) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }))
  }

  const saveSetting = async (key: string) => {
    const value = editedValues[key]
    if (value === undefined) return

    setSaving((prev) => ({ ...prev, [key]: true }))
    setMessage(null)

    try {
      const res = await fetch(`${API_BASE}/api/admin/config/setting/${key}`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ value }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to save setting")
      }

      setMessage({ type: "success", text: `Saved ${key}` })
      setEditedValues((prev) => {
        const next = { ...prev }
        delete next[key]
        return next
      })

      // Refresh effective settings for this key
      const effRes = await fetch(`${API_BASE}/api/admin/config/effective/${key}`, {
        headers: getAuthHeaders(),
      })
      if (effRes.ok) {
        const effData = await effRes.json()
        setEffectiveSettings((prev) => ({ ...prev, [key]: effData }))
      }

      // Update local settings
      setSettings((prev) => ({ ...prev, [key]: value }))
    } catch (e: any) {
      setMessage({ type: "error", text: e.message || `Failed to save ${key}` })
    } finally {
      setSaving((prev) => ({ ...prev, [key]: false }))
    }
  }

  const resetSetting = async (key: string) => {
    if (!confirm(`Reset ${key} to default? This will remove the database override.`)) {
      return
    }

    setSaving((prev) => ({ ...prev, [key]: true }))
    setMessage(null)

    try {
      const res = await fetch(`${API_BASE}/api/admin/config/setting/${key}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to reset setting")
      }

      const data = await res.json()
      setMessage({ type: "success", text: `Reset ${key} to default: ${data.default_value}` })

      // Refresh
      await loadData()
    } catch (e: any) {
      setMessage({ type: "error", text: e.message || `Failed to reset ${key}` })
    } finally {
      setSaving((prev) => ({ ...prev, [key]: false }))
    }
  }

  const getSections = () => {
    const sections = new Set<string>()
    Object.keys(schema).forEach((key) => {
      const section = key.split(".")[0]
      sections.add(section)
    })
    return Array.from(sections).sort()
  }

  const getSettingsForSection = (section: string) => {
    return Object.entries(schema)
      .filter(([key]) => key.startsWith(`${section}.`))
      .sort(([a], [b]) => a.localeCompare(b))
  }

  const renderInput = (key: string, meta: SettingSchema, currentValue: any) => {
    const editedValue = editedValues[key]
    const displayValue = editedValue !== undefined ? editedValue : currentValue
    const isSecret = meta.secret
    const showValue = !isSecret || showSecrets[key]

    if (meta.type === "bool") {
      return (
        <select
          value={displayValue === true ? "true" : displayValue === false ? "false" : ""}
          onChange={(e) => handleValueChange(key, e.target.value === "true")}
          style={{
            padding: "8px 10px",
            borderRadius: 6,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
            width: "100%",
          }}
        >
          <option value="true">True</option>
          <option value="false">False</option>
        </select>
      )
    }

    if (meta.type === "int") {
      return (
        <input
          type="number"
          value={displayValue ?? ""}
          onChange={(e) => handleValueChange(key, parseInt(e.target.value) || 0)}
          style={{
            padding: "8px 10px",
            borderRadius: 6,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
            width: "100%",
            boxSizing: "border-box",
          }}
        />
      )
    }

    // String type (default)
    return (
      <div style={{ display: "flex", gap: 8 }}>
        <input
          type={showValue ? "text" : "password"}
          value={displayValue ?? ""}
          onChange={(e) => handleValueChange(key, e.target.value)}
          placeholder={meta.default}
          style={{
            flex: 1,
            padding: "8px 10px",
            borderRadius: 6,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
            boxSizing: "border-box",
          }}
        />
        {isSecret && (
          <button
            onClick={() => setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }))}
            style={{
              padding: "8px 12px",
              backgroundColor: c.buttonSecondaryBg,
              color: c.buttonSecondaryText,
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {showSecrets[key] ? "🙈" : "👁️"}
          </button>
        )}
      </div>
    )
  }

  const getSourceBadge = (key: string) => {
    const effective = effectiveSettings[key]
    if (!effective) return null

    const colors: Record<string, string> = {
      database: "#22C55E",
      "environment/file": "#5B88FF",
      default: "#9CA3AF",
    }

    return (
      <span
        style={{
          fontSize: 11,
          padding: "2px 6px",
          borderRadius: 4,
          backgroundColor: colors[effective.source] || "#6B7280",
          color: "#fff",
          fontWeight: 500,
        }}
      >
        {effective.source}
      </span>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: 24, color: c.text }}>
        <div>Loading configuration...</div>
      </div>
    )
  }

  const sections = getSections()

  return (
    <div style={{ padding: 24, color: c.text, maxWidth: 1200 }}>
      <h1 style={{ margin: "0 0 8px", fontSize: 24, fontWeight: 600 }}>Application Configuration</h1>
      <p style={{ margin: "0 0 24px", color: c.textMuted, fontSize: 14 }}>
        Manage all application settings centrally. Database values override environment variables and config files.
      </p>

      {message && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: 8,
            marginBottom: 24,
            backgroundColor: message.type === "success" ? "#DCFCE7" : "#FEE2E2",
            color: message.type === "success" ? "#166534" : "#991B1B",
            border: `1px solid ${message.type === "success" ? "#86EFAC" : "#FECACA"}`,
          }}
        >
          {message.text}
        </div>
      )}

      <div style={{ display: "flex", gap: 24 }}>
        {/* Sidebar */}
        <div style={{ width: 220, flexShrink: 0 }}>
          <div
            style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              overflow: "hidden",
            }}
          >
            {sections.map((section) => (
              <button
                key={section}
                onClick={() => setActiveSection(section)}
                style={{
                  width: "100%",
                  padding: "12px 16px",
                  textAlign: "left",
                  backgroundColor: activeSection === section ? c.buttonPrimaryBg : "transparent",
                  color: activeSection === section ? c.buttonPrimaryText : c.text,
                  border: "none",
                  cursor: "pointer",
                  fontSize: 14,
                  fontWeight: activeSection === section ? 500 : 400,
                  transition: "all 0.15s",
                }}
              >
                {sectionLabels[section] || section}
              </button>
            ))}
          </div>

          <button
            onClick={loadData}
            style={{
              width: "100%",
              marginTop: 16,
              padding: "10px 16px",
              backgroundColor: c.buttonSecondaryBg,
              color: c.buttonSecondaryText,
              border: "none",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            🔄 Refresh All
          </button>
        </div>

        {/* Main content */}
        <div style={{ flex: 1 }}>
          <div
            style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              padding: 24,
            }}
          >
            <h2 style={{ margin: "0 0 20px", fontSize: 18, fontWeight: 600 }}>
              {sectionLabels[activeSection] || activeSection}
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {getSettingsForSection(activeSection).map(([key, meta]) => {
                const currentValue = settings[key]
                const hasChanges = editedValues[key] !== undefined && editedValues[key] !== currentValue
                const isSaving = saving[key]

                return (
                  <div
                    key={key}
                    style={{
                      padding: 16,
                      borderRadius: 8,
                      backgroundColor: hasChanges ? "#FEF3C7" : c.inputBg,
                      border: `1px solid ${hasChanges ? "#F59E0B" : c.border}`,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 14, fontFamily: "monospace", fontWeight: 500 }}>
                        {typeIcons[meta.type] || "⚙️"} {key}
                      </span>
                      {getSourceBadge(key)}
                      {hasChanges && (
                        <span
                          style={{
                            fontSize: 11,
                            padding: "2px 6px",
                            borderRadius: 4,
                            backgroundColor: "#F59E0B",
                            color: "#fff",
                            fontWeight: 500,
                          }}
                        >
                          modified
                        </span>
                      )}
                    </div>

                    <p style={{ margin: "0 0 12px", fontSize: 13, color: c.textMuted }}>
                      {meta.description}
                    </p>

                    <div style={{ marginBottom: 12 }}>
                      {renderInput(key, meta, currentValue)}
                    </div>

                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        onClick={() => saveSetting(key)}
                        disabled={!hasChanges || isSaving}
                        style={{
                          padding: "8px 16px",
                          backgroundColor: hasChanges ? c.buttonPrimaryBg : c.buttonSecondaryBg,
                          color: hasChanges ? c.buttonPrimaryText : c.textMuted,
                          border: "none",
                          borderRadius: 6,
                          cursor: hasChanges ? "pointer" : "not-allowed",
                          fontSize: 13,
                          fontWeight: 500,
                          opacity: isSaving ? 0.6 : 1,
                        }}
                      >
                        {isSaving ? "Saving..." : "💾 Save"}
                      </button>

                      <button
                        onClick={() => resetSetting(key)}
                        disabled={isSaving}
                        style={{
                          padding: "8px 16px",
                          backgroundColor: "transparent",
                          color: c.textMuted,
                          border: `1px solid ${c.border}`,
                          borderRadius: 6,
                          cursor: "pointer",
                          fontSize: 13,
                        }}
                      >
                        🔄 Reset to Default
                      </button>

                      <span style={{ marginLeft: "auto", fontSize: 12, color: c.textMuted }}>
                        Default: {meta.secret ? "***" : String(meta.default)}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Legend */}
          <div
            style={{
              marginTop: 24,
              padding: 16,
              backgroundColor: c.cardBg,
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              fontSize: 13,
              color: c.textMuted,
            }}
          >
            <strong>Source Legend:</strong>
            <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
              <span>
                <span style={{ color: "#22C55E", fontWeight: 600 }}>● database</span> — Value from database (highest priority)
              </span>
              <span>
                <span style={{ color: "#5B88FF", fontWeight: 600 }}>● environment/file</span> — Value from .env or config.yaml
              </span>
              <span>
                <span style={{ color: "#9CA3AF", fontWeight: 600 }}>● default</span> — Hardcoded fallback value
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminAppConfigPage
