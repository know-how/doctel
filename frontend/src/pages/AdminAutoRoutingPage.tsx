/**
 * AdminAutoRoutingPage.tsx - Auto-Routing Configuration
 *
 * View and toggle automatic model routing, which selects the best
 * model for each task based on capabilities and availability.
 */

import React, { useEffect, useState, useCallback } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  v2GetRoutingStatus,
  v2ToggleRouting,
  v2GetTaskMapping,
} from "../api/client"

export const AdminAutoRoutingPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [routingEnabled, setRoutingEnabled] = useState(true)
  const [configuredTasks, setConfiguredTasks] = useState(0)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [routingRes, mappingRes] = await Promise.all([
        v2GetRoutingStatus(),
        v2GetTaskMapping().catch(() => null),
      ])
      setRoutingEnabled(routingRes.automaticRouting ?? true)
      if (mappingRes?.taskMapping) {
        setConfiguredTasks(Object.keys(mappingRes.taskMapping).length)
      }
    } catch (e: any) {
      setError(e.message ?? "Failed to load routing status")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleToggle = async () => {
    try {
      setToggling(true)
      setError(null)
      setSuccessMsg(null)
      const newState = !routingEnabled
      const res = await v2ToggleRouting(newState)
      setRoutingEnabled(res.automaticRouting ?? newState)
      setSuccessMsg(
        `Auto-routing ${res.automaticRouting ? "enabled" : "disabled"} successfully.`
      )
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Failed to toggle routing")
    } finally {
      setToggling(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 700, color: c.text, margin: 0 }}
        >
          🚦 Auto Routing
        </h1>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}>
          Automatically select the optimal model for each task type based on
          capability, cost, and availability
        </p>
      </div>

      {error && (
        <div
          style={{
            padding: "10px 14px",
            background: c.error + "15",
            border: `1px solid ${c.error}30`,
            borderRadius: 8,
            color: c.error,
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          {error}
          <button
            onClick={() => setError(null)}
            style={{
              marginLeft: 12,
              background: "none",
              border: "none",
              color: c.error,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div
          style={{
            padding: "10px 14px",
            background: c.success + "15",
            border: `1px solid ${c.success}30`,
            borderRadius: 8,
            color: c.success,
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          {successMsg}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: c.textMuted }}>
          Loading routing status...
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Toggle Card */}
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.border}`,
              borderRadius: 12,
              padding: 24,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div
                style={{ fontSize: 16, fontWeight: 600, color: c.text }}
              >
                Automatic Routing
              </div>
              <div
                style={{ fontSize: 13, color: c.textMuted, marginTop: 4 }}
              >
                {routingEnabled
                  ? "The system will automatically select the best model for each task."
                  : "Manual model selection is required for each task type."}
              </div>
            </div>
            <button
              onClick={handleToggle}
              disabled={toggling}
              style={{
                position: "relative",
                width: 52,
                height: 28,
                borderRadius: 14,
                border: "none",
                background: routingEnabled ? c.primary : c.border,
                cursor: toggling ? "not-allowed" : "pointer",
                transition: "background 0.2s",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  top: 3,
                  left: routingEnabled ? 26 : 3,
                  width: 22,
                  height: 22,
                  borderRadius: 11,
                  background: "#FFFFFF",
                  transition: "left 0.2s",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                }}
              />
            </button>
          </div>

          {/* Stats Card */}
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.border}`,
              borderRadius: 12,
              padding: 24,
            }}
          >
            <div
              style={{ fontSize: 14, fontWeight: 600, color: c.text, marginBottom: 16 }}
            >
              Routing Configuration
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 16,
              }}
            >
              <div
                style={{
                  background: c.background,
                  borderRadius: 8,
                  padding: 16,
                  textAlign: "center",
                }}
              >
                <div
                  style={{ fontSize: 28, fontWeight: 700, color: c.primary }}
                >
                  {configuredTasks}
                </div>
                <div style={{ fontSize: 12, color: c.textMuted, marginTop: 4 }}>
                  Configured Task Mappings
                </div>
              </div>
              <div
                style={{
                  background: c.background,
                  borderRadius: 8,
                  padding: 16,
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    fontSize: 28,
                    fontWeight: 700,
                    color: routingEnabled ? c.success : c.warning,
                  }}
                >
                  {routingEnabled ? "Active" : "Inactive"}
                </div>
                <div style={{ fontSize: 12, color: c.textMuted, marginTop: 4 }}>
                  Routing Status
                </div>
              </div>
            </div>
          </div>

          {/* Info Card */}
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.border}`,
              borderRadius: 12,
              padding: 24,
            }}
          >
            <div
              style={{ fontSize: 14, fontWeight: 600, color: c.text, marginBottom: 12 }}
            >
              How It Works
            </div>
            <ul
              style={{
                margin: 0,
                padding: "0 0 0 18px",
                fontSize: 13,
                color: c.textSecondary,
                lineHeight: 1.8,
              }}
            >
              <li>
                Each task type (chat, vision, embedding, etc.) can be mapped to
                a specific model.
              </li>
              <li>
                When auto-routing is enabled, the system uses your task mappings
                to select the right model automatically.
              </li>
              <li>
                Configure task mappings in the{" "}
                <strong>Task Mapping</strong> section.
              </li>
              <li>
                If a task type has no mapping, the system falls back to the
                default chat model.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
