/**
 * AdminDepartmentsPage.tsx - Department Management
 *
 * Manage organizational departments, their document access
 * policies, and team membership.
 */

import React from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export const AdminDepartmentsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 700, color: c.text, margin: 0 }}
        >
          🏢 Departments
        </h1>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}>
          Manage organizational departments and team access policies
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
        <div style={{ fontSize: 40, marginBottom: 12 }}>🏢</div>
        <div style={{ fontSize: 16, fontWeight: 600, color: c.text }}>
          Department Management
        </div>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "8px 0 0 0" }}>
          Organize users into departments and manage document access
          policies per department.
        </p>
      </div>
    </div>
  )
}
