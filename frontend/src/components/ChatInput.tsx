import React from "react"
import { ThemeTokens } from "../theme/themeTokens"

/* ── Props ── */
interface ChatInputProps {
  t: ThemeTokens
  loading: boolean
  input: string
  onInputChange: (val: string) => void
  onSend: () => void
  isRecording: boolean
  isTranscribing: boolean
  onToggleRecording: () => void
  onAttachFile: () => void
  model: string | null
}

/* ── Component ── */
const ChatInput: React.FC<ChatInputProps> = ({
  t,
  loading,
  input,
  onInputChange,
  onSend,
  isRecording,
  isTranscribing,
  onToggleRecording,
  onAttachFile,
  model,
}) => {
  const inputRef = React.useRef<HTMLTextAreaElement>(null)

  return (
    <>
      {/* Input area */}
      <div style={{
        flexShrink: 0, position: "relative", zIndex: 2,
        padding: `${t.spacing.md}px 40px ${t.spacing.lg}px`,
      }}>
        <div style={{ maxWidth: 860, margin: "0 auto" }}>
          <div style={{
            display: "flex", gap: 12, alignItems: "flex-end",
            background: t.colors.cardBg,
            border: `1.5px solid ${loading ? t.colors.primary + "50" : t.colors.border}`,
            borderRadius: t.radii.lg,
            padding: "6px 8px",
            boxShadow: loading
              ? `0 0 0 4px ${t.colors.primary}12, 0 4px 20px rgba(0,0,0,0.05)`
              : "0 2px 8px rgba(0,0,0,0.04)",
            transition: "border-color 0.2s, box-shadow 0.2s",
          }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
              placeholder={`Message ${model || "AI"}...`}
              disabled={loading}
              rows={1}
              style={{
                flex: 1, background: "transparent", color: t.colors.text,
                border: "none", padding: "10px 8px", fontSize: 14.5,
                outline: "none", resize: "none", fontFamily: "inherit",
                lineHeight: 1.55, maxHeight: 150,
                caretColor: t.colors.primary,
                minHeight: 24,
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = "auto"
                target.style.height = Math.min(target.scrollHeight, 150) + "px"
              }}
            />
            <div style={{
              display: "flex", alignItems: "center", gap: 4,
              flexShrink: 0, alignSelf: "flex-end", paddingBottom: 1,
            }}>
              {isTranscribing && (
                <div style={{
                  fontSize: 11, color: t.colors.primary, whiteSpace: "nowrap",
                  animation: "pulse 1.5s ease-in-out infinite",
                }}>
                  Transcribing...
                </div>
              )}
              <button
                onClick={onAttachFile}
                disabled={loading}
                title="Attach file or image"
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: "transparent",
                  color: t.colors.textMuted,
                  border: `1px solid ${t.colors.border}`,
                  cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 14,
                  transition: "all 0.2s ease",
                }}
              >
                📎
              </button>
              <button
                onClick={onToggleRecording}
                disabled={isTranscribing}
                title={isRecording ? "Stop recording" : "Record voice message"}
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: isRecording ? "#EF4444" : t.colors.primary,
                  color: "#FFFFFF",
                  border: "none",
                  cursor: isTranscribing ? "not-allowed" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 14,
                  transition: "all 0.2s ease",
                  animation: isRecording ? "pulse 1.5s ease-in-out infinite" : "none",
                  boxShadow: isRecording ? "none" : `0 2px 8px ${t.colors.primary}30`,
                }}
              >
                {isRecording ? "⏹" : "🎙"}
              </button>
              <span style={{
                fontSize: 9.5, color: t.colors.textMuted, opacity: 0.4,
                display: input.trim().length > 0 || isRecording || isTranscribing ? "none" : "block",
                whiteSpace: "nowrap", paddingRight: 4,
              }}>
                Voice
              </span>
              <span style={{
                fontSize: 9.5, color: t.colors.textMuted, opacity: 0.4,
                display: input.trim().length > 0 ? "none" : "block",
                whiteSpace: "nowrap", paddingRight: 4,
              }}>
                Shift+↵ new line
              </span>
              <button
                onClick={onSend}
                disabled={loading || !input.trim()}
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: loading || !input.trim()
                    ? "transparent"
                    : `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
                  color: loading || !input.trim() ? t.colors.textMuted : "#FFFFFF",
                  border: "none",
                  cursor: loading || !input.trim() ? "default" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 16, fontWeight: 700,
                  transition: "all 0.2s ease",
                  opacity: loading || !input.trim() ? 0.3 : 1,
                }}
              >
                ↑
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default ChatInput
