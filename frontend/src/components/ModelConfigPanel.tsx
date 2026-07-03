/**
 * ModelConfigPanel — GitHub Copilot‑inspired model configuration UI
 *
 * Replaces the native <select> dropdown with a rich floating panel
 * that shows model names, capability badges, and a selection indicator.
 */

import React, { useState, useEffect, useRef } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

/* ── capability icon / label map ── */
const CAP_MAP: Record<string, { icon: string; label: string; color: string }> = {
  reasoning: { icon: "🧠", label: "Reasoning", color: "#A78BFA" },
  vision:    { icon: "👁️", label: "Vision",    color: "#60A5FA" },
  audio:     { icon: "🎤", label: "Audio",     color: "#34D399" },
  code:      { icon: "💻", label: "Code",      color: "#F472B6" },
  fast:      { icon: "⚡", label: "Fast",      color: "#FBBF24" },
  large:     { icon: "🐘", label: "Large",     color: "#FB923C" },
}

function getCapInfo(cap: string) {
  return CAP_MAP[cap] ?? { icon: "🔧", label: cap, color: "#9CA3AF" }
}

/* ── Props ── */
interface Props {
  selectedModel: string
  availableModels: string[]
  modelCapabilities: Record<string, string[]>
  modelLabels: Record<string, string>
  onSelect: (model: string) => void
  loading?: boolean
}

export const ModelConfigPanel: React.FC<Props> = ({
  selectedModel,
  availableModels,
  modelCapabilities,
  modelLabels,
  onSelect,
  loading,
}) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  /* close on outside click */
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  /* close on Escape */
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open])

  const handleSelect = (m: string) => {
    onSelect(m)
    setOpen(false)
  }

  /* ── trigger button ── */
  const trigger = (
    <button
      type="button"
      onClick={() => setOpen((o) => !o)}
      disabled={loading}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        background: open
          ? `${t.colors.primary}15`
          : t.colors.cardBg,
        borderRadius: t.radii.md,
        padding: "7px 14px",
        border: open
          ? `1px solid ${t.colors.primary}50`
          : `1px solid ${t.colors.border}`,
        cursor: loading ? "default" : "pointer",
        transition: "all 0.2s ease",
        opacity: loading ? 0.6 : 1,
        backdropFilter: "blur(4px)",
        boxShadow: open ? `0 0 20px ${t.colors.primary}15` : "none",
      }}
      onMouseEnter={(e) => {
        if (!open) {
          e.currentTarget.style.borderColor = `${t.colors.primary}40`
          e.currentTarget.style.boxShadow = `0 0 15px ${t.colors.primary}10`
        }
      }}
      onMouseLeave={(e) => {
        if (!open) {
          e.currentTarget.style.borderColor = t.colors.border
          e.currentTarget.style.boxShadow = "none"
        }
      }}
    >
      {/* green dot */}
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          flexShrink: 0,
          background: "#22C55E",
          boxShadow: "0 0 8px rgba(34,197,94,0.5)",
        }}
      />
      {/* current model name */}
      <span
        style={{
          fontSize: 12.5,
          fontWeight: 600,
          color: t.colors.text,
          whiteSpace: "nowrap",
          maxWidth: 180,
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {modelLabels[selectedModel] || selectedModel || "Select model"}
      </span>
      {/* chevron */}
      <svg
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        style={{
          transition: "transform 0.25s ease",
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          flexShrink: 0,
        }}
      >
        <path
          d="M2 3.5L5 6.5L8 3.5"
          stroke={t.colors.textSecondary}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  )

  /* ── dropdown panel ── */
  const dropdown = open && (
    <div
      style={{
        position: "absolute",
        top: "calc(100% + 8px)",
        right: 0,
        width: 320,
        maxHeight: 400,
        overflowY: "auto",
        background: `${t.colors.bgSecondary}E6`,
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRadius: t.radii.lg,
        border: `1px solid ${t.colors.border}80`,
        boxShadow: `0 25px 60px rgba(0,0,0,0.5), 0 0 0 1px ${t.colors.border}20`,
        padding: t.spacing.sm,
        zIndex: 9999,
      }}
    >
      {/* header */}
      <div
        style={{
          padding: `${t.spacing.xs}px ${t.spacing.sm}px ${t.spacing.sm}px`,
          borderBottom: `1px solid ${t.colors.border}40`,
          marginBottom: t.spacing.xs,
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: t.colors.textMuted,
            textTransform: "uppercase",
            letterSpacing: "0.8px",
          }}
        >
          AI Model
        </div>
        <div
          style={{
            fontSize: 10,
            color: t.colors.textMuted,
            marginTop: 2,
          }}
        >
          {availableModels.length} model{availableModels.length !== 1 ? "s" : ""} available
        </div>
      </div>

      {/* model list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {availableModels.map((m) => {
          const isSelected = m === selectedModel
          const caps = modelCapabilities[m] ?? []
          return (
            <button
              key={m}
              type="button"
              onClick={() => handleSelect(m)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "10px 12px",
                borderRadius: t.radii.md,
                border: isSelected
                  ? `1px solid ${t.colors.primary}50`
                  : "1px solid transparent",
                background: isSelected
                  ? `linear-gradient(135deg, ${t.colors.primary}18, ${t.colors.primary}05)`
                  : "transparent",
                cursor: "pointer",
                transition: "all 0.15s ease",
                display: "flex",
                alignItems: "center",
                gap: 10,
                position: "relative",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.background = `${t.colors.surface}80`
                  e.currentTarget.style.borderColor = `${t.colors.border}60`
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.background = "transparent"
                  e.currentTarget.style.borderColor = "transparent"
                }
              }}
            >
              {/* model icon */}
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: isSelected
                    ? `linear-gradient(135deg, ${t.colors.primary}30, ${t.colors.secondary}20)`
                    : `${t.colors.surface}80`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  fontSize: 16,
                  border: isSelected
                    ? `1px solid ${t.colors.primary}30`
                    : `1px solid ${t.colors.border}40`,
                }}
              >
                {caps.includes("reasoning") ? "🧠" : caps.includes("vision") ? "👁️" : caps.includes("code") ? "💻" : "🤖"}
              </div>

              {/* name + capabilities */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: isSelected ? 700 : 500,
                    color: isSelected ? t.colors.text : t.colors.textSecondary,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {modelLabels[m] || m}
                </div>
                {modelLabels[m] && modelLabels[m] !== m && (
                  <div
                    style={{
                      fontSize: 10,
                      color: t.colors.textMuted,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {m}
                  </div>
                )}
                {caps.length > 0 && (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 3,
                      marginTop: 3,
                    }}
                  >
                    {caps.map((cap) => {
                      const info = getCapInfo(cap)
                      return (
                        <span
                          key={cap}
                          style={{
                            fontSize: 9,
                            padding: "1px 5px",
                            borderRadius: 4,
                            border: `1px solid ${info.color}40`,
                            backgroundColor: `${info.color}15`,
                            color: info.color,
                            lineHeight: "16px",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 2,
                          }}
                        >
                          {info.icon} {info.label}
                        </span>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* checkmark when selected */}
              {isSelected && (
                <span
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.secondary})`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    fontSize: 11,
                    color: "#fff",
                    fontWeight: 700,
                    boxShadow: `0 0 12px ${t.colors.primary}40`,
                  }}
                >
                  ✓
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )

  return (
    <div ref={panelRef} style={{ position: "relative" }}>
      {trigger}
      {dropdown}
    </div>
  )
}
