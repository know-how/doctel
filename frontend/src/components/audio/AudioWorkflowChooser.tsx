import React, { useState, useCallback, useEffect, useRef } from "react"
import { useTheme } from "../../context/ThemeContext"
import { getTokens, ThemeTokens } from "../../theme/themeTokens"
import { transcribeAudio } from "../../api/client"

/* ── Props ── */
interface AudioWorkflowChooserProps {
  file: File
  onClose: () => void
  /** Called when user picks a workflow action. */
  onWorkflowSelect: (action: AudioWorkflowAction) => void
  /** Called with transcribed text when "Transcribe" or "Chat" path needs it. */
  onTranscriptionResult?: (text: string) => void
}

export type AudioWorkflowAction =
  | "transcribe"      // Just transcribe and show text
  | "analyze_meeting" // Transcribe + analyze meeting structure
  | "add_to_kb"       // Full ingestion into knowledge base
  | "chat_with_audio" // Transcribe + chat about it (temp session)

/* ── Helpers ── */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatEstimatedDuration(bytes: number): string {
  // Rough estimate: ~16 KB/s for compressed audio
  const secs = Math.round(bytes / 16000)
  if (secs < 60) return `~${secs}s`
  return `~${Math.round(secs / 60)}min`
}

/* ── Workflow options ── */
const WORKFLOW_OPTIONS: {
  action: AudioWorkflowAction
  icon: string
  title: string
  description: string
  color: string
}[] = [
  {
    action: "transcribe",
    icon: "\uD83C\uDF99\uFE0F",
    title: "Transcribe Recording",
    description: "Convert speech to text. View the full transcript instantly.",
    color: "#5B88FF",
  },
  {
    action: "analyze_meeting",
    icon: "\uD83D\uDCCB",
    title: "Analyze Meeting",
    description: "Extract summary, decisions, action items, risks, and participants.",
    color: "#16a34a",
  },
  {
    action: "add_to_kb",
    icon: "\uD83E\uDDE0",
    title: "Add To Knowledge Base",
    description: "Index in the knowledge base. Make it searchable and retrievable via RAG.",
    color: "#ca8a04",
  },
  {
    action: "chat_with_audio",
    icon: "\uD83D\uDCAC",
    title: "Chat With Recording",
    description: "Ask questions about the recording without full indexing.",
    color: "#7c3aed",
  },
]

/* ── Component ── */
const AudioWorkflowChooser: React.FC<AudioWorkflowChooserProps> = ({
  file,
  onClose,
  onWorkflowSelect,
  onTranscriptionResult,
}) => {
  const { theme } = useTheme()
  const t: ThemeTokens = getTokens(theme)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [transcriptText, setTranscriptText] = useState<string | null>(null)
  const [transcriptError, setTranscriptError] = useState<string | null>(null)
  const [chosenAction, setChosenAction] = useState<AudioWorkflowAction | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // Click outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    // Delay to avoid immediate trigger
    const timer = setTimeout(() => document.addEventListener("click", handler), 100)
    return () => {
      clearTimeout(timer)
      document.removeEventListener("click", handler)
    }
  }, [onClose])

  const handleAction = useCallback(async (action: AudioWorkflowAction) => {
    setChosenAction(action)
    onWorkflowSelect(action)

    // For "add_to_kb", just pass through — the parent handles ingestion
    if (action === "add_to_kb") {
      return
    }

    // For transcribe / analyze_meeting / chat_with_audio, transcribe first
    setIsTranscribing(true)
    setTranscriptError(null)
    try {
      const result = await transcribeAudio(file)
      const text = (result as any).text || ""
      setTranscriptText(text)
      if (onTranscriptionResult) {
        onTranscriptionResult(text)
      }
    } catch (err: any) {
      const msg = err?.message || "Transcription failed. Check that Gemini API key is configured."
      setTranscriptError(msg)
    } finally {
      setIsTranscribing(false)
    }
  }, [file, onWorkflowSelect, onTranscriptionResult])

  return (
    <div
      ref={panelRef}
      style={{
        background: t.colors.cardBg,
        border: `1px solid ${t.colors.border}`,
        borderRadius: t.radii.lg,
        overflow: "hidden",
        boxShadow: t.shadows.lg,
        width: "100%",
        maxWidth: 480,
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 16px",
          borderBottom: `1px solid ${t.colors.border}`,
        }}
      >
        <span style={{ fontSize: 22 }}>\uD83C\uDFA4</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: t.colors.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            Audio recording detected
          </div>
          <div style={{ fontSize: 11, color: t.colors.textMuted, marginTop: 1 }}>
            {file.name} &middot; {formatFileSize(file.size)} &middot; {formatEstimatedDuration(file.size)}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none", border: "none", color: t.colors.textMuted,
            cursor: "pointer", fontSize: 16, padding: "2px 6px", lineHeight: 1,
          }}
        >
          \u2715
        </button>
      </div>

      {/* ── Body ── */}
      <div style={{ padding: "12px 16px" }}>
        {transcriptError ? (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 8,
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.2)",
              fontSize: 12.5,
              color: "#F87171",
              marginBottom: 8,
            }}
          >
            {transcriptError}
          </div>
        ) : isTranscribing ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "16px 0",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: 16, height: 16,
                border: "2px solid rgba(91,136,255,0.2)",
                borderTopColor: t.colors.primary,
                borderRadius: "50%",
                animation: "audio-chooser-spin 0.8s linear infinite",
              }}
            />
            <span style={{ fontSize: 13, color: t.colors.textMuted }}>
              Transcribing audio...
            </span>
          </div>
        ) : transcriptText ? (
          <div
            style={{
              fontSize: 12,
              lineHeight: 1.55,
              color: t.colors.textSecondary,
              maxHeight: 120,
              overflowY: "auto",
              padding: "8px 10px",
              background: t.colors.surfaceActive,
              borderRadius: 8,
              whiteSpace: "pre-wrap",
              marginBottom: 8,
            }}
          >
            {transcriptText.slice(0, 500)}
            {transcriptText.length > 500 && (
              <span style={{ color: t.colors.textMuted }}>...</span>
            )}
          </div>
        ) : (
          <div style={{ fontSize: 12.5, color: t.colors.textSecondary, lineHeight: 1.55, marginBottom: 10 }}>
            DocTel can transcribe, analyze and index this recording. Choose how to process it:
          </div>
        )}

        {/* ── Workflow buttons ── */}
        {!transcriptText && !isTranscribing && !transcriptError && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {WORKFLOW_OPTIONS.map((opt) => (
              <button
                key={opt.action}
                onClick={() => handleAction(opt.action)}
                disabled={isTranscribing}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  borderRadius: t.radii.md,
                  border: `1px solid ${t.colors.border}`,
                  background: t.colors.surfaceActive,
                  cursor: isTranscribing ? "not-allowed" : "pointer",
                  textAlign: "left" as const,
                  width: "100%",
                  transition: "all 0.15s ease",
                  fontFamily: "inherit",
                  opacity: isTranscribing ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isTranscribing) {
                    e.currentTarget.style.borderColor = opt.color
                    e.currentTarget.style.background = `${opt.color}10`
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = t.colors.border
                  e.currentTarget.style.background = t.colors.surfaceActive
                }}
              >
                <span style={{ fontSize: 18, flexShrink: 0 }}>{opt.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: t.colors.text }}>
                    {opt.title}
                  </div>
                  <div style={{ fontSize: 10.5, color: t.colors.textMuted, marginTop: 1 }}>
                    {opt.description}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* ── After transcription, show action-specific options ── */}
        {transcriptText && chosenAction === "transcribe" && (
          <div style={{ fontSize: 12, color: t.colors.textSecondary, lineHeight: 1.55 }}>
            Transcribed {transcriptText.split(/\s+/).length} words. You can now copy the transcript or ask questions about it.
          </div>
        )}
        {transcriptText && chosenAction === "chat_with_audio" && (
          <div style={{ fontSize: 12, color: t.colors.textSecondary, lineHeight: 1.55 }}>
            Ready to answer questions about this recording. Ask anything in the chat input above.
          </div>
        )}
      </div>

      {/* ── Inline keyframes ── */}
      <style>{`
        @keyframes audio-chooser-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}

export default AudioWorkflowChooser
