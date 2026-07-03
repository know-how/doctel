/**
 * ConnectionToast.tsx – Floating toast notification for mid‑session
 * connection drops. Auto‑appears when !ok and auto‑dismisses when ok.
 *
 * Animates in/out with a slide‑down + fade transition.
 */

import React, { useEffect, useState } from "react"

interface Props {
  connected: boolean
  liveChecking: boolean
  error?: string
  backendRunning?: boolean
  ollamaRunning?: boolean
  hasExternalServices?: boolean
}

export const ConnectionToast: React.FC<Props> = ({
  connected,
  liveChecking,
  error,
  backendRunning = true,
  ollamaRunning = true,
  hasExternalServices = false,
}) => {
  const [visible, setVisible] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (!connected) {
      setVisible(true)
      setDismissed(false)
    } else if (visible) {
      // Auto‑dismiss after a short delay when reconnected
      const t = setTimeout(() => {
        setVisible(false)
        setDismissed(true)
      }, 2_000)
      return () => clearTimeout(t)
    }
  }, [connected, visible])

  // Don't render anything if connected (after initial gate passed)
  if (!visible && connected) return null
  // Don't render during the initial gate phase (handled by App.tsx overlay)
  if (!visible && !dismissed) return null

  return (
    <div
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        zIndex: 99999,
        maxWidth: 380,
        padding: "14px 20px",
        borderRadius: 12,
        background: connected
          ? "linear-gradient(135deg, #1a3a2a, #0d2818)"
          : "linear-gradient(135deg, #3a1a1a, #280d0d)",
        border: connected
          ? "1px solid rgba(46, 213, 115, 0.35)"
          : "1px solid rgba(255, 71, 71, 0.35)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        color: "#fff",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        fontSize: 13,
        lineHeight: 1.5,
        display: "flex",
        alignItems: "center",
        gap: 12,
        transition: "opacity 0.3s ease, transform 0.3s ease",
        opacity: 1,
        transform: "translateY(0)",
        pointerEvents: "auto",
      }}
    >
      {/* Icon */}
      <div style={{ fontSize: 20, flexShrink: 0 }}>
        {connected ? "✅" : liveChecking ? "⏳" : "⚠️"}
      </div>

      {/* Message */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {connected ? (
          <span style={{ fontWeight: 600, color: "#2ed573" }}>
            Connection restored
          </span>
        ) : liveChecking ? (
          <span style={{ fontWeight: 500, color: "rgba(255,255,255,0.8)" }}>
            Reconnecting…
          </span>
        ) : (
          <>
            <div style={{ fontWeight: 600, color: "#ff4747" }}>
              {!backendRunning
                ? "Backend Server Offline"
                : !ollamaRunning
                  ? "Local AI Models Offline"
                  : "Connection Lost"}
            </div>
            <div style={{ color: "rgba(255,255,255,0.6)", marginTop: 2, fontSize: 12 }}>
              {error || "Server is not responding. Retrying automatically…"}
            </div>
            {!backendRunning && (
              <div style={{ color: "rgba(255,255,255,0.4)", marginTop: 2, fontSize: 11 }}>
                💡 Start: <code style={{ fontFamily: "monospace" }}>python -m uvicorn app.main:app --host 127.0.0.1 --port 8000</code>
              </div>
            )}
            {backendRunning && !ollamaRunning && (
              <div style={{ color: "rgba(255,255,255,0.4)", marginTop: 2, fontSize: 11 }}>
                💡 Start: <code style={{ fontFamily: "monospace" }}>ollama serve</code>
                {hasExternalServices && " — or use an external model"}
              </div>
            )}
          </>
        )}
      </div>

      {/* Dismiss button (only when disconnected) */}
      {!connected && !liveChecking && (
        <button
          onClick={() => setVisible(false)}
          style={{
            background: "none",
            border: "none",
            color: "rgba(255,255,255,0.4)",
            cursor: "pointer",
            fontSize: 18,
            lineHeight: 1,
            padding: "0 0 0 8px",
            flexShrink: 0,
          }}
          aria-label="Dismiss"
        >
          ✕
        </button>
      )}
    </div>
  )
}
