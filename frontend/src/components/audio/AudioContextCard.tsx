import React, { useState } from "react"
import { ThemeTokens } from "../../theme/themeTokens"
import { attachAudioToSession, removeAudioFromSession } from "../../api/client"

/* ── Props ── */

export interface AudioContextData {
  filename: string
  transcript: string
  summary?: string
  durationSec?: number | null
  entities?: string[]
  topics?: string[]
  speakerCount?: number | null
}

interface AudioContextCardProps {
  t: ThemeTokens
  sessionId: string | null
  audioCtx: AudioContextData
  onRemove: () => void
  onAddToKnowledgeBase?: () => void
  onAnalyzeMeeting?: () => void
}

/* ── Helpers ── */

function formatDuration(sec?: number | null): string {
  if (sec == null) return ""
  const mins = Math.floor(sec / 60)
  const remaining = Math.round(sec % 60)
  if (mins === 0) return `${remaining}s`
  return `${mins}m ${remaining}s`
}

function formatTranscriptPreview(text: string, maxLen = 400): string {
  if (!text) return ""
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (cleaned.length <= maxLen) return cleaned
  return cleaned.slice(0, maxLen) + "…"
}

/* ── Component ── */

const AudioContextCard: React.FC<AudioContextCardProps> = ({
  t,
  sessionId,
  audioCtx,
  onRemove,
  onAddToKnowledgeBase,
  onAnalyzeMeeting,
}) => {
  const [expanded, setExpanded] = useState(false)
  const [removing, setRemoving] = useState(false)

  const handleRemove = async () => {
    if (!sessionId) {
      onRemove()
      return
    }
    setRemoving(true)
    try {
      await removeAudioFromSession(sessionId)
    } catch (e) {
      console.warn("[AudioContextCard] remove failed:", e)
    }
    onRemove()
  }

  const durationStr = formatDuration(audioCtx.durationSec)
  const entityChips = (audioCtx.entities || []).slice(0, 6)
  const preview = formatTranscriptPreview(audioCtx.transcript)

  return (
    <div
      style={{
        maxWidth: 480,
        margin: "0 auto",
        background: t.colors.cardBg,
        borderRadius: t.radii.md,
        border: `1px solid ${t.colors.border}`,
        overflow: "hidden",
        transition: "box-shadow 0.2s",
      }}
    >
      {/* ── Header bar ────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: `${t.colors.primary}0D`,
          borderBottom: `1px solid ${t.colors.border}`,
        }}
      >
        <span style={{ fontSize: 18, flexShrink: 0 }}>🎙</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 12.5,
              fontWeight: 600,
              color: t.colors.text,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            Active Recording Context
          </div>
          <div
            style={{
              fontSize: 11,
              color: t.colors.textMuted,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {audioCtx.filename}
            {durationStr ? `  ·  ${durationStr}` : ""}
          </div>
        </div>
        <button
          onClick={handleRemove}
          disabled={removing}
          title="Remove recording context"
          style={{
            background: "none",
            border: "none",
            color: t.colors.error,
            cursor: removing ? "default" : "pointer",
            fontSize: 13,
            padding: "2px 6px",
            opacity: removing ? 0.4 : 1,
            flexShrink: 0,
          }}
        >
          ✕ Remove
        </button>
      </div>

      {/* ── Entity chips ──────────────────────────────── */}
      {entityChips.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 4,
            padding: "8px 14px 0",
          }}
        >
          {entityChips.map((e) => (
            <span
              key={e}
              style={{
                fontSize: 10.5,
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: 999,
                background: `${t.colors.primary}12`,
                border: `1px solid ${t.colors.primary}20`,
                color: t.colors.primary,
              }}
            >
              {e}
            </span>
          ))}
          {(audioCtx.entities || []).length > 6 && (
            <span
              style={{
                fontSize: 10.5,
                color: t.colors.textMuted,
                padding: "2px 4px",
              }}
            >
              +{(audioCtx.entities || []).length - 6}
            </span>
          )}
        </div>
      )}

      {/* ── Transcript preview ────────────────────────── */}
      {preview && (
        <div
          style={{
            padding: "8px 14px",
            cursor: "pointer",
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <div
            style={{
              fontSize: 11.5,
              lineHeight: 1.55,
              color: t.colors.textMuted,
              maxHeight: expanded ? "none" : 54,
              overflow: "hidden",
              position: "relative",
              whiteSpace: "pre-wrap",
            }}
          >
            {preview}
            {!expanded && preview.length > 100 && (
              <span
                style={{
                  position: "absolute",
                  bottom: 0,
                  right: 0,
                  paddingLeft: 12,
                  background: `linear-gradient(to right, transparent, ${t.colors.cardBg})`,
                  fontSize: 11,
                  color: t.colors.primary,
                  fontWeight: 500,
                }}
              >
                more
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Action buttons ────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 6,
          padding: "0 14px 10px",
        }}
      >
        {onAnalyzeMeeting && (
          <button
            onClick={onAnalyzeMeeting}
            style={{
              flex: 1,
              padding: "6px 10px",
              fontSize: 11,
              fontWeight: 500,
              borderRadius: t.radii.sm,
              background: t.colors.cardBg,
              border: `1px solid ${t.colors.border}`,
              color: t.colors.text,
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = t.colors.border
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = t.colors.cardBg
            }}
          >
            📋 Analyze Meeting
          </button>
        )}
        {onAddToKnowledgeBase && (
          <button
            onClick={onAddToKnowledgeBase}
            style={{
              flex: 1,
              padding: "6px 10px",
              fontSize: 11,
              fontWeight: 500,
              borderRadius: t.radii.sm,
              background: t.colors.cardBg,
              border: `1px solid ${t.colors.border}`,
              color: t.colors.text,
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = t.colors.border
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = t.colors.cardBg
            }}
          >
            🧠 Add to KB
          </button>
        )}
      </div>
    </div>
  )
}

export default AudioContextCard
export type { AudioContextCardProps }
