import React from "react"
import { ThemeTokens } from "../theme/themeTokens"
import { ModelSelector } from "./ModelSelector"

/* ── Props ── */
interface ChatHeaderProps {
  t: ThemeTokens
  model: string | null
  modelLabels: Record<string, string>
  modelCapabilities: Record<string, string[]>
  messagesLength: number
  onModelChange: (modelId: string) => void
  models: any[]
  v2Providers: any[]
  disabled: boolean
}

/* ── Capability icon mapping ── */
const CAP_ICON: Record<string, string> = {
  reasoning: "🧠",
  vision: "🖼",
  audio: "🎤",
  code: "💻",
  fast: "⚡",
  large: "🐘",
  embedding: "📌",
  video: "🎥",
  tools: "🔧",
}

/* ── Component ── */
const ChatHeader: React.FC<ChatHeaderProps> = ({
  t,
  model,
  modelLabels,
  modelCapabilities,
  messagesLength,
  onModelChange,
  models,
  v2Providers,
  disabled,
}) => {
  const c = t.colors

  return (
    <div style={{
      flexShrink: 0, position: "relative", zIndex: 10,
      padding: "20px 32px",
      borderBottom: `1px solid ${c.border}`,
      backgroundColor: c.bg,
    }}>
      <div style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "24px",
      }}>
        {/* Left: Title and Session Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{
            fontSize: "24px",
            fontWeight: 700,
            color: c.text,
            margin: 0,
            letterSpacing: "-0.5px",
            lineHeight: 1.2,
          }}>
            New Chat
          </h1>

          <p style={{
            fontSize: "13px",
            color: c.textSecondary,
            margin: "6px 0 0 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <span>Chatting with</span>
            <span style={{
              fontWeight: 600,
              color: c.primary,
              backgroundColor: c.primary + "15",
              padding: "2px 10px",
              borderRadius: "6px",
              fontSize: "12px",
            }}>
              {modelLabels[model || ""] || model || "AI"}
            </span>
            <span style={{ color: c.border }}>•</span>
            <span>{messagesLength} messages</span>
          </p>

          {/* Capability Icons */}
          {model && modelCapabilities[model] && modelCapabilities[model].length > 0 && (
            <div style={{
              display: "flex",
              gap: "6px",
              marginTop: "10px",
              alignItems: "center",
              flexWrap: "wrap",
            }}>
              {modelCapabilities[model].map(cap => (
                <span key={cap} style={{
                  fontSize: "11px",
                  padding: "4px 10px",
                  borderRadius: "8px",
                  backgroundColor: c.surface,
                  color: c.textSecondary,
                  border: `1px solid ${c.border}`,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  fontWeight: 500,
                }}>
                  {CAP_ICON[cap] || "📄"}
                  <span style={{ textTransform: "capitalize" }}>{cap}</span>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Right: Compact Model Selector */}
        <div style={{ flexShrink: 0, width: "380px", maxWidth: "100%" }}>
          <ModelSelector
            providers={v2Providers}
            value={model || ""}
            onChange={(modelId: string) => onModelChange(modelId)}
            placeholder={models.length > 0 ? "Select model" : "No models available"}
            selectableOnly={true}
            includeLocalModels={true}
            localModels={models}
            disabled={disabled || models.length === 0}
          />
        </div>
      </div>
    </div>
  )
}

export default ChatHeader
