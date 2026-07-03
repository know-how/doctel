import React, { useState } from "react"
import { updateUserSecurity } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface Session {
  id: string
  device: string
  ip: string
  location: string
  last_active: string
  current: boolean
}

const mockSessions: Session[] = [
  { id: "1", device: "Chrome on Windows", ip: "192.168.1.100", location: "Harare, ZW", last_active: "2025-04-28 14:30", current: true },
  { id: "2", device: "Safari on iPhone", ip: "10.0.0.45", location: "Harare, ZW", last_active: "2025-04-27 08:15", current: false },
  { id: "3", device: "Firefox on MacOS", ip: "172.16.0.22", location: "Bulawayo, ZW", last_active: "2025-04-25 17:00", current: false },
]

export const SettingsSecurityPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [sessions] = useState<Session[]>(mockSessions)

  const handleChangePassword = async () => {
    try {
      setError(null)
      setSuccessMsg(null)

      if (!currentPassword || !newPassword || !confirmPassword) {
        setError("All password fields are required.")
        return
      }
      if (newPassword.length < 8) {
        setError("New password must be at least 8 characters.")
        return
      }
      if (newPassword !== confirmPassword) {
        setError("New passwords do not match.")
        return
      }

      setSaving(true)
      await updateUserSecurity({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      setSuccessMsg("Password updated successfully.")
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Password change failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 640, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Security</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Manage your password and active sessions.</p>
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

      {/* Change password */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Change password</h3>

        <div style={{ marginBottom: t.spacing.md }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 4 }}>
            Current password
          </label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Enter current password"
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

        <div style={{ marginBottom: t.spacing.md }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 4 }}>
            New password
          </label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Min. 8 characters"
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
            Confirm new password
          </label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Re-enter new password"
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

        <button
          onClick={handleChangePassword}
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
          {saving ? "Saving..." : "Update password"}
        </button>
      </div>

      {/* Two-factor status */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Two-factor authentication</h3>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: c.text }}>Not enabled</div>
            <div style={{ fontSize: 12, color: c.textSecondary }}>Add an extra layer of security to your account.</div>
          </div>
          <button
            style={{
              padding: "8px 16px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Enable 2FA
          </button>
        </div>
      </div>

      {/* Active sessions */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Active sessions</h3>
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
            <div>Device</div><div>IP</div><div>Location</div><div>Last active</div>
          </div>
          {sessions.map((s) => (
            <div
              key={s.id}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr",
                gap: 12,
                padding: "10px 14px",
                fontSize: 12,
                color: c.text,
                borderBottom: `1px solid ${c.border}`,
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                {s.device}
                {s.current && (
                  <span
                    style={{
                      padding: "1px 6px",
                      borderRadius: t.radii.full,
                      fontSize: 10,
                      fontWeight: 700,
                      backgroundColor: c.success + "22",
                      color: c.success,
                    }}
                  >
                    Current
                  </span>
                )}
              </div>
              <div style={{ fontFamily: "monospace", fontSize: 11, color: c.textSecondary }}>{s.ip}</div>
              <div style={{ color: c.textSecondary }}>{s.location}</div>
              <div style={{ color: c.textSecondary }}>{s.last_active}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
