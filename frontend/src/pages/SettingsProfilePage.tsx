import React, { useEffect, useState } from "react"
import { getMe, updateUserProfile } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export const SettingsProfilePage: React.FC = () => {
  const { theme, toggleTheme, isDark } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  useEffect(() => {
    const loadProfile = async () => {
      try {
        setLoading(true)
        setError(null)
        const me = await getMe()
        setDisplayName(me.display_name ?? me.name ?? "")
        setEmail(me.email ?? "")
      } catch (e: any) {
        setError(e.message ?? "Failed to load profile")
      } finally {
        setLoading(false)
      }
    }
    loadProfile()
  }, [])

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      setSuccessMsg(null)
      await updateUserProfile({ display_name: displayName, email })
      setSuccessMsg("Profile updated successfully.")
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 640, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Profile</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Manage your personal information and preferences.</p>
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

      {loading ? (
        <div style={{ display: "grid", gap: t.spacing.md }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, height: 56 }} />
          ))}
        </div>
      ) : (
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
          <div style={{ marginBottom: t.spacing.lg }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 4 }}>
              Display name
            </label>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your display name"
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: t.radii.md,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 14,
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: t.spacing.lg }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 4 }}>
              Email
            </label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              type="email"
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: t.radii.md,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 14,
                boxSizing: "border-box",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 4 }}>
              Theme preference
            </label>
            <div
              onClick={toggleTheme}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                borderRadius: t.radii.md,
                border: `1px solid ${c.border}`,
                backgroundColor: c.surface,
                cursor: "pointer",
                userSelect: "none",
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 24,
                  borderRadius: 12,
                  backgroundColor: isDark ? c.primary : c.border,
                  position: "relative",
                  transition: "background-color 0.2s",
                }}
              >
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    backgroundColor: "#FFFFFF",
                    position: "absolute",
                    top: 2,
                    left: isDark ? 22 : 2,
                    transition: "left 0.2s",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                  }}
                />
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: c.text }}>
                {isDark ? "Dark" : "Light"} mode
              </div>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving || loading}
        style={{
          padding: "10px 20px",
          borderRadius: t.radii.md,
          border: "none",
          backgroundColor: c.primary,
          color: "#FFFFFF",
          cursor: saving || loading ? "default" : "pointer",
          fontWeight: 600,
          fontSize: 14,
          opacity: saving || loading ? 0.5 : 1,
        }}
      >
        {saving ? "Saving..." : "Save profile"}
      </button>
    </div>
  )
}
