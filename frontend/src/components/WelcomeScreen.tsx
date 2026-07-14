import React from "react"
import { ThemeTokens } from "../theme/themeTokens"
import { PromptSuggestion } from "../api/client"
import AiAvatar from "./avatars/AiAvatar"

/* ── Props ── */
interface WelcomeScreenProps {
  t: ThemeTokens
  isDark: boolean
  promptSuggestions: PromptSuggestion[]
  loadingPrompts: boolean
  onSend: (text: string) => void
}

/* ── Fallback prompts ── */
const FALLBACK_PROMPTS = [
  { label: "ZETDC outage reporting process", icon: "⚡" },
  { label: "Explain ZETDC net metering policy", icon: "📋" },
  { label: "Summarize in Shona", icon: "🇿🇼" },
  { label: "ZETDC safety procedures", icon: "🏗️" },
]

/* ── Component ── */
const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  t,
  isDark,
  promptSuggestions,
  loadingPrompts,
  onSend,
}) => {
  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      paddingBottom: 40,
    }}>
      {/* AI Avatar */}
      <div style={{ marginBottom: 20 }}>
        <AiAvatar state="idle" size={180} showLabel />
      </div>

      <div style={{ fontSize: 20, fontWeight: 700, color: t.colors.text, marginBottom: 8 }}>
        Start a conversation
      </div>
      <div style={{
        fontSize: 13.5, color: t.colors.textMuted, textAlign: "center",
        maxWidth: 440, lineHeight: 1.7, marginBottom: 24,
      }}>
        Chat with the ZETDC AI assistant. Ask about policies, procedures,
        reports, or request responses in Shona — no document upload needed.
      </div>

      {/* Prompt suggestions */}
      <div style={{
        display: "flex", gap: 10, flexWrap: "wrap",
        justifyContent: "center", maxWidth: 500,
      }}>
        {loadingPrompts ? (
          <div style={{ color: t.colors.textMuted, fontSize: 14 }}>
            Loading suggestions...
          </div>
        ) : promptSuggestions.length > 0 ? (
          promptSuggestions.map((q) => (
            <button
              key={q.id}
              onClick={() => onSend(q.prompt_text)}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                background: t.colors.cardBg,
                color: t.colors.text, border: `1px solid ${t.colors.border}`,
                borderRadius: 24, padding: "10px 18px", fontSize: 13,
                cursor: "pointer", transition: "all 0.2s ease",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                const el = e.target as HTMLElement
                el.style.background = t.colors.surfaceActive
                el.style.borderColor = t.colors.primary + "60"
              }}
              onMouseLeave={(e) => {
                const el = e.target as HTMLElement
                el.style.background = t.colors.cardBg
                el.style.borderColor = t.colors.border
              }}
            >
              <span>{q.icon}</span> {q.title}
            </button>
          ))
        ) : (
          FALLBACK_PROMPTS.map((q) => (
            <button
              key={q.label}
              onClick={() => onSend(q.label)}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                background: t.colors.cardBg,
                color: t.colors.text, border: `1px solid ${t.colors.border}`,
                borderRadius: 24, padding: "10px 18px", fontSize: 13,
                cursor: "pointer", transition: "all 0.2s ease",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                const el = e.target as HTMLElement
                el.style.background = t.colors.surfaceActive
                el.style.borderColor = t.colors.primary + "60"
              }}
              onMouseLeave={(e) => {
                const el = e.target as HTMLElement
                el.style.background = t.colors.cardBg
                el.style.borderColor = t.colors.border
              }}
            >
              <span>{q.icon}</span> {q.label}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

export default WelcomeScreen
