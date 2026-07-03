import React, { useEffect, useState } from "react"
import { getTeamMembers, updateMemberRole } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface Member {
  id: number
  display_name?: string
  email?: string
  role: string
  avatar?: string
  joined_at?: string
}

interface ActivityItem {
  id: number
  user: string
  action: string
  timestamp: string
}

const ROLE_COLORS: Record<string, string> = {
  admin: "#EF4444",
  analyst: "#5B88FF",
  viewer: "#22C55E",
}

const AVAILABLE_ROLES = ["admin", "analyst", "viewer"]

const mockActivity: ActivityItem[] = [
  { id: 1, user: "Alice Johnson", action: "uploaded 3 documents to Project Alpha", timestamp: "2025-04-28 14:22" },
  { id: 2, user: "Bob Smith", action: "ran extraction on invoice_2025.pdf", timestamp: "2025-04-28 11:05" },
  { id: 3, user: "Carol White", action: "created new project 'Q2 Review'", timestamp: "2025-04-27 16:48" },
  { id: 4, user: "Alice Johnson", action: "changed Bob Smith's role to analyst", timestamp: "2025-04-27 10:15" },
]

export const CollaborationTeamPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("analyst")
  const [inviting, setInviting] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const loadMembers = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await getTeamMembers()
      setMembers(res.members ?? res.items ?? res ?? [])
    } catch (e: any) {
      setError(e.message ?? "Failed to load team members")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMembers()
  }, [])

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      setError(null)
      await updateMemberRole(userId, role)
      setMembers((prev) => prev.map((m) => (m.id === userId ? { ...m, role } : m)))
      setSuccessMsg(`Role updated to ${role}`)
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Failed to update role")
    }
  }

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return
    try {
      setInviting(true)
      setError(null)
      // In a real implementation this would call an invite API
      await new Promise((r) => setTimeout(r, 600))
      setSuccessMsg(`Invitation sent to ${inviteEmail}`)
      setInviteEmail("")
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Invite failed")
    } finally {
      setInviting(false)
    }
  }

  const roleBadge = (role: string) => {
    const col = ROLE_COLORS[role] ?? c.textMuted
    return (
      <span
        style={{
          display: "inline-block",
          padding: "2px 10px",
          borderRadius: t.radii.full,
          fontSize: 11,
          fontWeight: 700,
          textTransform: "capitalize",
          backgroundColor: col + "18",
          color: col,
          border: `1px solid ${col}44`,
        }}
      >
        {role}
      </span>
    )
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Team</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Manage team members and their roles.</p>
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

      {/* Invite form */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.sm} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Invite member</h3>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="Email address"
            type="email"
            style={{
              flex: 2,
              padding: "8px 12px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
              minWidth: 200,
            }}
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            style={{
              padding: "8px 10px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
            }}
          >
            {AVAILABLE_ROLES.map((r) => (
              <option key={r} value={r} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{r}</option>
            ))}
          </select>
          <button
            onClick={handleInvite}
            disabled={inviting || !inviteEmail.trim()}
            style={{
              padding: "8px 18px",
              borderRadius: t.radii.sm,
              border: "none",
              backgroundColor: c.primary,
              color: "#FFFFFF",
              cursor: inviting || !inviteEmail.trim() ? "default" : "pointer",
              fontWeight: 600,
              fontSize: 13,
              opacity: inviting || !inviteEmail.trim() ? 0.5 : 1,
            }}
          >
            {inviting ? "Sending..." : "Send invite"}
          </button>
        </div>
      </div>

      {/* Members list */}
      <div style={{ marginBottom: t.spacing.xl }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>
          Members ({members.length})
        </h3>

        {loading ? (
          <div style={{ display: "grid", gap: t.spacing.sm }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, padding: t.spacing.md, backgroundColor: c.cardBg, height: 48 }} />
            ))}
          </div>
        ) : members.length === 0 ? (
          <div style={{ textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary, color: c.textSecondary }}>
            No team members yet. Invite someone to get started.
          </div>
        ) : (
          <div style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, overflow: "hidden" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 100px 80px",
                gap: 12,
                padding: "8px 14px",
                backgroundColor: c.surface,
                borderBottom: `1px solid ${c.border}`,
                fontWeight: 700,
                fontSize: 11,
                color: c.textSecondary,
              }}
            >
              <div>Name</div><div>Email</div><div>Role</div><div>Actions</div>
            </div>
            {members.map((m) => (
              <div
                key={m.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "2fr 1fr 100px 80px",
                  gap: 12,
                  padding: "10px 14px",
                  alignItems: "center",
                  borderBottom: `1px solid ${c.border}`,
                  fontSize: 13,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, color: c.text }}>
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: "50%",
                      backgroundColor: c.surfaceActive,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                      fontSize: 13,
                      color: c.primary,
                    }}
                  >
                    {(m.display_name ?? m.email ?? "?")[0].toUpperCase()}
                  </div>
                  <span style={{ fontWeight: 600 }}>{m.display_name ?? m.email ?? "Unknown"}</span>
                </div>
                <div style={{ color: c.textSecondary, fontSize: 12 }}>{m.email ?? "—"}</div>
                <div>{roleBadge(m.role)}</div>
                <div>
                  <select
                    value={m.role}
                    onChange={(e) => handleRoleChange(m.id, e.target.value)}
                    style={{
                      padding: "4px 6px",
                      borderRadius: t.radii.sm,
                      border: `1px solid ${c.border}`,
                      backgroundColor: c.inputBg,
                      color: c.text,
                      fontSize: 12,
                      width: "100%",
                    }}
                  >
                    {AVAILABLE_ROLES.map((r) => (
                      <option key={r} value={r} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{r}</option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Activity log */}
      <div>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Recent activity</h3>
        <div style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, overflow: "hidden" }}>
          {mockActivity.map((a, i) => (
            <div
              key={a.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 14px",
                borderBottom: i < mockActivity.length - 1 ? `1px solid ${c.border}` : "none",
                fontSize: 13,
              }}
            >
              <span style={{ fontWeight: 600, color: c.text }}>{a.user}</span>
              <span style={{ color: c.textSecondary }}>{a.action}</span>
              <span style={{ marginLeft: "auto", fontSize: 11, color: c.textMuted }}>{a.timestamp}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
