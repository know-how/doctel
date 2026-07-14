/**
 * AdminRBACPage.tsx - Role-Based Access Control
 *
 * View and manage user roles and permissions across the system.
 * Assign predefined roles (admin, editor, viewer) and configure
 * granular permission sets.
 */

import React from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export const AdminRBACPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 700, color: c.text, margin: 0 }}
        >
          🛡️ RBAC
        </h1>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}>
          Role-Based Access Control — manage user roles and permissions
        </p>
      </div>

      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.border}`,
          borderRadius: 12,
          padding: 24,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 40, marginBottom: 12 }}>🛡️</div>
        <div style={{ fontSize: 16, fontWeight: 600, color: c.text }}>
          Role Management
        </div>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "8px 0 0 0" }}>
          Assign roles to users and configure granular permission sets.
          Roles available: Admin, Editor, Viewer.
        </p>
      </div>
    </div>
  )
}
