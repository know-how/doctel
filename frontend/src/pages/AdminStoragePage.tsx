/**
 * AdminStoragePage.tsx - Storage Management
 *
 * Manage document storage, vector database (ChromaDB) capacity,
 * and file retention policies.
 */

import React from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export const AdminStoragePage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 700, color: c.text, margin: 0 }}
        >
          💾 Storage
        </h1>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}>
          Manage document storage, vector database capacity, and file retention
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
        <div style={{ fontSize: 40, marginBottom: 12 }}>💾</div>
        <div style={{ fontSize: 16, fontWeight: 600, color: c.text }}>
          Storage Management
        </div>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "8px 0 0 0" }}>
          Configure document storage locations, vector database (ChromaDB)
          settings, and retention policies here.
        </p>
      </div>
    </div>
  )
}
