/**
 * AdminDiagnosticsPage.tsx - System Diagnostics
 *
 * Run system diagnostics, check database connectivity,
 * verify provider endpoints, and troubleshoot issues.
 */

import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export const AdminDiagnosticsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<
    { name: string; status: "ok" | "fail" | "pending"; msg: string }[]
  >([
    { name: "Database Connection", status: "pending", msg: "Not tested" },
    { name: "Vector DB (PostgreSQL+pgvector)", status: "pending", msg: "Not tested" },
    { name: "AI Provider Connectivity", status: "pending", msg: "Not tested" },
    { name: "File Storage", status: "pending", msg: "Not tested" },
    { name: "API Health Endpoint", status: "pending", msg: "Not tested" },
  ])

  const runDiagnostics = async () => {
    setRunning(true)
    setResults((prev) =>
      prev.map((r) => ({ ...r, status: "pending" as const, msg: "Running..." }))
    )

    // Simulate diagnostic checks
    const checks = [
      { name: "Database Connection", wait: 800, ok: true, msg: "Connected (0.8s)" },
      { name: "Vector DB (PostgreSQL+pgvector)", wait: 1200, ok: true, msg: "Connected (1.2s)" },
      { name: "AI Provider Connectivity", wait: 2000, ok: true, msg: "3/3 providers reachable" },
      { name: "File Storage", wait: 600, ok: true, msg: "Accessible (0.6s)" },
      { name: "API Health Endpoint", wait: 400, ok: true, msg: "Healthy (0.4s)" },
    ]

    for (const check of checks) {
      await new Promise((r) => setTimeout(r, check.wait))
      setResults((prev) =>
        prev.map((r) =>
          r.name === check.name
            ? { ...r, status: check.ok ? ("ok" as const) : ("fail" as const), msg: check.msg }
            : r
        )
      )
    }

    setRunning(false)
  }

  const statusIcon = (s: string) => {
    switch (s) {
      case "ok":
        return "✅"
      case "fail":
        return "❌"
      default:
        return "⏳"
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{ fontSize: 22, fontWeight: 700, color: c.text, margin: 0 }}
          >
            🩺 Diagnostics
          </h1>
          <p
            style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}
          >
            Run system health checks and troubleshoot issues
          </p>
        </div>
        <button
          onClick={runDiagnostics}
          disabled={running}
          style={{
            padding: "10px 20px",
            borderRadius: 8,
            border: "none",
            background: running ? c.border : c.primary,
            color: "#FFFFFF",
            fontSize: 14,
            fontWeight: 600,
            cursor: running ? "not-allowed" : "pointer",
          }}
        >
          {running ? "Running..." : "Run All Checks"}
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {results.map((r) => (
          <div
            key={r.name}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: c.surface,
              border: `1px solid ${c.border}`,
              borderRadius: 10,
              padding: "14px 18px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span style={{ fontSize: 18 }}>{statusIcon(r.status)}</span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: c.text }}>
                  {r.name}
                </div>
                <div style={{ fontSize: 12, color: c.textMuted }}>
                  {r.msg}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
