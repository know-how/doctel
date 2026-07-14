import React from "react"
import { getTokens, ThemeTokens } from "../theme/themeTokens"
import SourceCitationCard from "./SourceCitationCard"
import { AiAvatar } from "./avatars/AiAvatar"
import type { AvatarState } from "./avatars/avatarStates"

/* ── Shared types (mirrored from NewChatPage.tsx) ── */
export interface Citation {
  filename?: string
  chunk_index?: number
  text?: string
  full_text_available?: boolean
  distance?: number
  can_view?: boolean
  can_download?: boolean
  open_url?: string
  download_url?: string
  preview_url?: string
  source_type?: string
  project_id?: string | number
}

export interface AttachmentMeta {
  name: string
  type: "image" | "document" | "audio"
  dataUrl?: string
}

export interface Message {
  id: number | string
  role: "user" | "assistant" | "system"
  content: string
  reasoning?: string
  uiStatus: "waiting" | "streaming" | "done" | "error"
  citations: Citation[]
  createdAt?: string
  attachment?: AttachmentMeta | null
}

/* ── Props ── */
interface ChatMessageProps {
  msg: Message
  prevMsg?: Message
  t: ThemeTokens
  isDark: boolean
  onRetry: (msg: Message) => void
  renderContent: (content: string) => React.ReactNode
  formatTime: (iso?: string) => string
  formatDate: (iso?: string) => string
}

/* ── Helpers ── */
const THIRTY_MIN_MS = 30 * 60 * 1000

const shouldShowDateSeparator = (prev: Message, curr: Message): boolean => {
  try {
    const p = new Date(prev.createdAt!).getTime()
    const c = new Date(curr.createdAt!).getTime()
    return !isNaN(p) && !isNaN(c) && c - p > THIRTY_MIN_MS
  } catch {
    return false
  }
}

/* ── Component ── */
const ChatMessage: React.FC<ChatMessageProps> = ({
  msg,
  prevMsg,
  t,
  isDark,
  onRetry,
  renderContent,
  formatTime,
  formatDate,
}) => {
  const isUser = msg.role === "user"
  const isWaiting = msg.uiStatus === "waiting"
  const isError = msg.uiStatus === "error"
  const showAvatar = !prevMsg || prevMsg.role !== msg.role

  const mapUiStatusToAvatarState = (status: Message["uiStatus"]): AvatarState => {
    switch (status) {
      case "waiting": return "thinking"
      case "streaming": return "speaking"
      case "done": return "idle"
      case "error": return "error"
      default: return "idle"
    }
  }

  return (
    <div style={{ marginBottom: showAvatar ? 28 : 8 }}>
      {/* Date separator for long gaps */}
      {prevMsg && msg.createdAt && prevMsg.createdAt && shouldShowDateSeparator(prevMsg, msg) && (
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
          <span style={{
            fontSize: 11,
            color: t.colors.textMuted,
            background: t.colors.cardBg,
            borderRadius: 12,
            padding: "4px 14px",
            border: `1px solid ${t.colors.border}`,
          }}>
            {formatDate(msg.createdAt)}
          </span>
        </div>
      )}

      <div style={{
        display: "flex",
        alignItems: "flex-start",
        flexDirection: isUser ? "row-reverse" : "row",
        gap: 14,
        animation: "msg-slide-up 0.35s ease forwards",
      }}>
        {/* Avatar */}
        {showAvatar ? (
          <div style={{
            width: 38, height: 38, flexShrink: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
            ...(isUser ? {
              borderRadius: "50%",
              background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
              border: `2px solid ${t.colors.primary}60`,
              boxShadow: `0 2px 12px ${t.colors.primary}30`,
            } : {
              marginTop: 2,
            }),
          }}>
            {isUser ? (
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            ) : (
              <AiAvatar state={mapUiStatusToAvatarState(msg.uiStatus)} size={38} />
            )}
          </div>
        ) : (
          <div style={{ width: 38, flexShrink: 0 }} />
        )}

        <div style={{ maxWidth: "72%", minWidth: 80 }}>
          {/* Message bubble */}
          <div style={{
            padding: isWaiting ? "14px 20px" : "14px 18px",
            borderRadius: isUser
              ? showAvatar ? "18px 18px 4px 18px" : "18px 4px 4px 18px"
              : showAvatar ? "18px 18px 18px 4px" : "4px 18px 18px 4px",
            background: isError
              ? t.colors.cardBg
              : isUser
                ? `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`
                : t.colors.cardBg,
            color: isUser ? "#FFFFFF" : isError ? t.colors.error : t.colors.text,
            fontSize: 14, lineHeight: 1.72,
            border: isUser ? "none" : `1px solid ${t.colors.border}`,
            boxShadow: isUser
              ? `0 2px 16px ${t.colors.primary}25`
              : "0 1px 2px rgba(0,0,0,0.06)",
          }}>
            {/* Attachment preview */}
            {msg.attachment && msg.role === "user" && (
              msg.attachment.type === "image" && msg.attachment.dataUrl ? (
                <img
                  src={msg.attachment.dataUrl}
                  alt={msg.attachment.name}
                  style={{ width: "100%", maxHeight: 180, borderRadius: 8, objectFit: "cover", marginBottom: 8 }}
                />
              ) : (
                <div style={{
                  display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
                  background: isUser ? "rgba(255,255,255,0.15)" : t.colors.surfaceActive,
                  borderRadius: 8, padding: "6px 10px",
                }}>
                  <span style={{ fontSize: 16 }}>{msg.attachment.type === "audio" ? "🎵" : "📎"}</span>
                  <span style={{
                    fontSize: 12, fontWeight: 500,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {msg.attachment.name}
                  </span>
                </div>
              )
            )}

            {/* Waiting animation */}
            {isWaiting ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0" }}>
                <div style={{
                  width: 9, height: 9, borderRadius: "50%",
                  background: t.colors.primary,
                  animation: "dot-bounce 1.4s ease-in-out infinite",
                }} />
                <div style={{
                  width: 9, height: 9, borderRadius: "50%",
                  background: t.colors.primary,
                  animation: "dot-bounce 1.4s ease-in-out infinite 0.2s",
                }} />
                <div style={{
                  width: 9, height: 9, borderRadius: "50%",
                  background: t.colors.primary,
                  animation: "dot-bounce 1.4s ease-in-out infinite 0.4s",
                }} />
                <span style={{ fontSize: 12, color: t.colors.textMuted, marginLeft: 6 }}>
                  Thinking...
                </span>
              </div>
            ) : msg.uiStatus === "streaming" ? (
              <div>
                {renderContent(msg.content)}
                <span style={{
                  display: "inline-block", width: 2, height: "1em",
                  backgroundColor: t.colors.primary, marginLeft: 2,
                  animation: "streaming-blink 1s step-end infinite",
                  verticalAlign: "text-bottom",
                }} />
              </div>
            ) : isError ? (
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                <span>⚠️</span>
                <div style={{ flex: 1 }}>
                  <div style={{ marginBottom: 8 }}>{msg.content}</div>
                  <button
                    onClick={() => onRetry(msg)}
                    style={{
                      background: t.colors.surfaceActive,
                      color: t.colors.primary, border: "none",
                      borderRadius: 6, padding: "4px 12px",
                      cursor: "pointer", fontSize: 12, fontWeight: 600,
                    }}
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : msg.content ? (
              <div>{renderContent(msg.content)}</div>
            ) : null}

            {/* Citations — premium source cards */}
            {msg.citations && msg.citations.length > 0 && (
              <div style={{
                marginTop: 14, paddingTop: 12,
                borderTop: `1px solid ${t.colors.border}`,
              }}>
                <span style={{
                  fontSize: 10.5, color: t.colors.textMuted,
                  fontWeight: 600, letterSpacing: "0.04em",
                  textTransform: "uppercase", display: "block",
                  marginBottom: 10,
                }}>
                  Sources ({msg.citations.length})
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {msg.citations.map((c, ci) => (
                    <SourceCitationCard
                      key={ci}
                      filename={c.filename}
                      chunk_index={c.chunk_index}
                      text={c.text}
                      full_text_available={c.full_text_available}
                      distance={c.distance}
                      can_view={c.can_view}
                      can_download={c.can_download}
                      open_url={c.open_url}
                      download_url={c.download_url}
                      preview_url={c.preview_url}
                      source_type={c.source_type}
                      project_id={c.project_id}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Reasoning / Thinking block */}
            {!isUser && msg.reasoning && (
              <details style={{
                marginTop: 12, paddingTop: 10,
                borderTop: `1px solid ${t.colors.border}`,
                fontSize: 12.5,
              }}>
                <summary style={{
                  cursor: "pointer",
                  color: t.colors.textMuted,
                  fontWeight: 600,
                  fontSize: 11,
                  letterSpacing: "0.3px",
                  textTransform: "uppercase" as const,
                  userSelect: "none",
                  outline: "none",
                }}>
                  💭 Show reasoning
                </summary>
                <div style={{
                  marginTop: 8,
                  padding: "10px 14px",
                  background: t.colors.surfaceActive,
                  borderRadius: 8,
                  color: t.colors.textSecondary,
                  fontSize: 12.5,
                  lineHeight: 1.65,
                  fontStyle: "italic",
                  whiteSpace: "pre-wrap",
                  borderLeft: `3px solid ${t.colors.primary}40`,
                }}>
                  {msg.reasoning}
                </div>
              </details>
            )}
          </div>

          {/* Timestamp */}
          {msg.createdAt && (
            <div style={{
              display: "flex", gap: 12, marginTop: 5,
              justifyContent: isUser ? "flex-end" : "flex-start",
              paddingRight: isUser ? 4 : 0,
              paddingLeft: isUser ? 0 : 4,
            }}>
              <span style={{ fontSize: 10.5, color: t.colors.textMuted, opacity: 0.55 }}>
                {formatTime(msg.createdAt)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ChatMessage
