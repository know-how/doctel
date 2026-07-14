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
  attachedFile: File | null
  attachedPreview: string | null
  onClearAttachment: () => void
  capabilityWarning: string | null
  onDismissWarning: () => void
  uploadProgress: number | null
  uploadStatusMsg: string | null
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
  attachedFile,
  attachedPreview,
  onClearAttachment,
  capabilityWarning,
  onDismissWarning,
  uploadProgress,
  uploadStatusMsg,
  model,
}) => {
  const inputRef = React.useRef<HTMLTextAreaElement>(null)

  return (
    <>
      {/* Hidden file input */}
      <input
        ref={React.useRef<HTMLInputElement>(null)}
        type="file"
        accept="image/*,application/pdf,text/plain,.docx,.doc"
        onChange={() => {}} // handled by onAttachFile callback
        style={{ display: "none" }}
      />

      {/* Attachment preview */}
      {attachedFile && (
        <div style={{
          flexShrink: 0, position: "relative", zIndex: 2,
          padding: "0 40px 6px",
        }}>
          <div style={{
            maxWidth: 860, margin: "0 auto",
            display: "flex", alignItems: "center", gap: 10,
            background: t.colors.cardBg,
            borderRadius: t.radii.md,
            padding: "8px 14px",
            border: `1px solid ${t.colors.border}`,
          }}>
            {attachedPreview ? (
              <img src={attachedPreview} alt="preview" style={{ width: 36, height: 36, borderRadius: 6, objectFit: "cover" }} />
            ) : (
              <span style={{ fontSize: 18 }}>📎</span>
            )}
            <span style={{
              flex: 1, fontSize: 13, color: t.colors.text,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>
              {attachedFile.name}
            </span>
            <button
              onClick={onClearAttachment}
              style={{
                background: "none", border: "none", color: t.colors.error,
                cursor: "pointer", fontSize: 16, padding: "2px 6px",
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Capability warning */}
      {capabilityWarning && (
        <div style={{
          flexShrink: 0, position: "relative", zIndex: 2,
          padding: "0 40px 6px",
        }}>
          <div style={{
            maxWidth: 860, margin: "0 auto",
            background: "#FEF3C7", borderRadius: t.radii.md,
            padding: "8px 14px",
            border: "1px solid #F59E0B",
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <span style={{ fontSize: 14 }}>⚠️</span>
            <span style={{ flex: 1, fontSize: 12, color: "#92400E", lineHeight: 1.4 }}>
              {capabilityWarning}
            </span>
            <button
              onClick={onDismissWarning}
              style={{
                background: "none", border: "none", color: "#92400E",
                cursor: "pointer", fontSize: 14, padding: "2px 4px", opacity: 0.6,
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Upload progress bar */}
      {(uploadProgress !== null || uploadStatusMsg) && (
        <div style={{
          flexShrink: 0, position: "relative", zIndex: 2,
          padding: "0 40px 6px",
        }}>
          <div style={{
            maxWidth: 860, margin: "0 auto",
            background: t.colors.cardBg,
            borderRadius: t.radii.md,
            padding: "10px 14px",
            border: `1px solid ${t.colors.border}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: uploadProgress !== null ? 6 : 0 }}>
              <span style={{ fontSize: 14 }}>📄</span>
              <span style={{
                flex: 1, fontSize: 13, color: t.colors.text,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {uploadStatusMsg || "Uploading..."}
              </span>
              {uploadProgress !== null && (
                <span style={{ fontSize: 12, color: t.colors.textMuted, fontVariantNumeric: "tabular-nums" }}>
                  {uploadProgress}%
                </span>
              )}
            </div>
            {uploadProgress !== null && (
              <div style={{
                width: "100%", height: 6,
                background: t.colors.border,
                borderRadius: 3, overflow: "hidden",
              }}>
                <div style={{
                  width: `${uploadProgress}%`,
                  height: "100%",
                  background: `linear-gradient(90deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
                  borderRadius: 3,
                  transition: "width 0.3s ease",
                }} />
              </div>
            )}
          </div>
        </div>
      )}

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
                  background: attachedFile ? t.colors.primary + "20" : "transparent",
                  color: attachedFile ? t.colors.primary : t.colors.textMuted,
                  border: attachedFile ? `1px solid ${t.colors.primary}60` : `1px solid ${t.colors.border}`,
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
                disabled={loading || (!input.trim() && !attachedFile)}
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: loading || (!input.trim() && !attachedFile)
                    ? "transparent"
                    : `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
                  color: loading || (!input.trim() && !attachedFile) ? t.colors.textMuted : "#FFFFFF",
                  border: "none",
                  cursor: loading || (!input.trim() && !attachedFile) ? "default" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 16, fontWeight: 700,
                  transition: "all 0.2s ease",
                  opacity: loading || (!input.trim() && !attachedFile) ? 0.3 : 1,
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
