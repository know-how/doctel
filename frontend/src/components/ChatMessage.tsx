import React from "react"
import { getTokens, ThemeTokens } from "../theme/themeTokens"
import { AiAvatar } from "./avatars/AiAvatar"
import type { AvatarState } from "./avatars/avatarStates"
import StructuredResponse from "./StructuredResponse"
import type { StructuredData } from "./StructuredResponse"
import ToolPlanCard from "./ToolPlanCard"
import type { ToolPlan } from "./ToolPlanCard"

/* ── Shared types (mirrored from NewChatPage.tsx) ── */
export interface Citation {
  document_id?: string
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
  /** Audio/video-specific metadata from ChromaDB. */
  start_sec?: number
  end_sec?: number
  speaker?: string
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
  /** Knowledge orchestration fields */
  render_hint?: string
  citation_mode?: string
  structured_data?: StructuredData
  knowledge_type?: string
  evidence_count?: number
  source_count?: number
  /** Tool execution plan */
  execution_plan?: ToolPlan
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

/** Format seconds to HH:MM:SS for audio timestamp display. */
function formatTimestamp(seconds?: number): string {
  if (seconds === undefined || seconds === null || isNaN(seconds)) return ""
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  }
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
}

/** Convert raw filename into a human-readable title. */
function humanReadableTitle(filename?: string): string {
  if (!filename) return ""
  const noExt = filename.replace(/\.[^.]+$/, "")
  // Strip leading numbers/prefixes like "2_" or "01-" that differ across project copies
  const noLeadingNum = noExt.replace(/^\d+[._-]+/, "")
  const unprefixed = noLeadingNum.replace(/^(ZETDC_|DocTel_|draft_|v\d+_)/i, "")
  const spaced = unprefixed.replace(/[_-]/g, " ")
  return spaced.replace(/\s+/g, " ").trim()
}

/** Normalized group key from a citation — uses human-readable title so
 *  the same document always produces the same key even when raw filenames
 *  differ slightly (whitespace, trailing chars across project copies). */
function citationGroupKey(c: Citation): string {
  const title = humanReadableTitle(c.filename)
  if (title) return title.toLowerCase().replace(/\s+/g, " ")
  return c.document_id || c.filename || "unknown"
}

/** Extract significant terms from a query — words ≥3 chars, excluding common stop words. */
const STOP_WORDS = new Set([
  "the","and","for","are","not","but","you","can","its","has","had","was",
  "that","this","with","what","will","from","have","been","which","would",
  "their","about","there","your","does","how","why","when","where","who",
  "all","each","some","any","just","also","very","than","then","into",
  "could","should","after","such","only","other","over","still","more"
])
function extractQueryTerms(query: string): string[] {
  const words = query.toLowerCase().match(/\b[a-z]{3,}\b/g) || []
  return [...new Set(words.filter(w => !STOP_WORDS.has(w) && !/^\d+$/.test(w)))]
}

/** Highlight matched query terms in text, returning JSX elements with highlighted spans. */
function highlightText(text: string, terms: string[]): React.ReactNode {
  if (!terms.length || !text) return text
  const escaped = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi")
  const parts = text.split(pattern)
  return parts.map((part, i) =>
    terms.some(t => part.toLowerCase() === t.toLowerCase())
      ? <span key={i} style={{
          background: "#FFE066",
          color: "#1A1A1A",
          borderRadius: 2,
          padding: "0 1px",
          fontWeight: 600,
        }}>{part}</span>
      : part
  )
}

/** Render evidence content with table formatting and query-term highlighting.
 *  Detects pipe-delimited tables and renders them as HTML tables, with
 *  query term highlighting applied within each cell.
 *  @param t ThemeTokens — required to style table borders/backgrounds.
 */
function renderEvidenceContent(text: string, terms: string[], t: ThemeTokens): React.ReactNode {
  if (!text) return text

  const lines = text.split("\n")

  // Detect contiguous pipe-table blocks (at least 3 pipe-containing or dash-sep lines)
  let tableStart = -1, tableEnd = -1
  let pipeCount = 0
  for (let i = 0; i < lines.length; i++) {
    const hasPipe = lines[i].includes("|")
    const hasDashSep = /^[\s\-:|+]+\s*$/.test(lines[i])
    if (hasPipe || hasDashSep) {
      pipeCount++
      if (tableStart === -1) tableStart = i
      tableEnd = i
    } else {
      if (tableStart !== -1 && pipeCount >= 3) break
      tableStart = -1; tableEnd = -1; pipeCount = 0
    }
  }

  // No table found — just highlight the whole text
  if (tableStart === -1 || pipeCount < 3) {
    const highlighted = highlightText(text, terms)
    return highlighted
  }

  // Build result: text-before + table + text-after, with highlighting in non-table parts
  const result: React.ReactNode[] = []

  if (tableStart > 0) {
    result.push(<span key="pre">{highlightText(lines.slice(0, tableStart).join("\n"), terms)}</span>)
  }

  const tableLines = lines.slice(tableStart, tableEnd + 1)
  const dataRows = tableLines.filter(l => !/^[\s\-:|+]+\s*$/.test(l) && l.includes("|"))
  if (dataRows.length > 0) {
    const headers = dataRows[0].split("|").map(h => h.trim()).filter(Boolean)
    result.push(
      <div key="table" style={{
        overflowX: "auto" as const,
        margin: "6px 0",
        fontSize: 10.5,
        lineHeight: 1.4,
      }}>
        <table style={{
          borderCollapse: "collapse",
          width: "100%",
        }}>
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i} style={{
                  border: `1px solid ${t.colors.border}`,
                  padding: "3px 6px",
                  background: t.colors.surfaceActive,
                  fontWeight: 600,
                  textAlign: "left" as const,
                  fontSize: 10.5,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.slice(1).map((row, ri) => {
              const cells = row.split("|").map(c => c.trim()).filter((_, ci, arr) =>
                // skip empty leading/trailing cells from leading/trailing pipes
                !(ci === 0 && arr[0] === "") && !(ci === arr.length - 1 && arr[arr.length - 1] === "")
              )
              return (
                <tr key={ri}>
                  {cells.map((cell, ci) => (
                    <td key={ci} style={{
                      border: `1px solid ${t.colors.border}`,
                      padding: "2px 6px",
                      fontSize: 10.5,
                    }}>{highlightText(cell, terms)}</td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  } else {
    result.push(<span key="table-fallback">{highlightText(tableLines.join("\n"), terms)}</span>)
  }

  if (tableEnd < lines.length - 1) {
    result.push(<span key="post">{highlightText(lines.slice(tableEnd + 1).join("\n"), terms)}</span>)
  }

  return <>{result}</>
}

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

            {/* ── Tool Execution Plan (debug mode) ── */}
            {!isUser && msg.execution_plan && (
              <ToolPlanCard plan={msg.execution_plan} />
            )}

            {/* ── Structured Response Cards (knowledge orchestration) ── */}
            {!isUser && msg.render_hint && msg.render_hint !== "narrative" && (
              <StructuredResponse
                metadata={{
                  render_hint: msg.render_hint,
                  citation_mode: msg.citation_mode || "full",
                  structured_data: msg.structured_data,
                  knowledge_type: msg.knowledge_type,
                  evidence_count: msg.evidence_count,
                  source_count: msg.source_count,
                }}
                renderContent={renderContent}
              />
            )}

            {/* ── Citations — grouped by normalized title, sections deduplicated, evidence preview ── */}
            {msg.citations && msg.citations.length > 0 && (() => {
              // Step 1: Group by NORMALIZED human-readable title, not raw filename.
              // This handles cases where the same document appears across projects
              // with slightly different filenames (whitespace, trailing chars).
              const groups = new Map<string, {
                title: string; sections: Citation[]; seenChunks: Set<number | undefined>; distance: number
              }>()
              let totalUniqueSections = 0
              for (const c of msg.citations) {
                const key = citationGroupKey(c)
                const displayTitle = humanReadableTitle(c.filename) || "Source"
                
                // Before creating a new group, check if any EXISTING group has
                // the SAME display title (fuzzy merge for edge cases where
                // normalization still produces different keys for same doc).
                let group = groups.get(key)
                if (!group) {
                  // Check if another key with the same display title exists
                  for (const [existingKey, existingGroup] of groups) {
                    if (existingGroup.title === displayTitle) {
                      group = existingGroup
                      // Re-map this citation to the existing key
                      break
                    }
                  }
                }
                if (!group) {
                  group = { title: displayTitle, sections: [], seenChunks: new Set(), distance: c.distance ?? 1 }
                  groups.set(key, group)
                }
                // Deduplicate sections by unique chunk_index
                if (!group.seenChunks.has(c.chunk_index)) {
                  group.seenChunks.add(c.chunk_index)
                  group.sections.push(c)
                  totalUniqueSections++
                }
                group.distance = Math.min(group.distance, c.distance ?? 1)
              }
              const groupEntries = Array.from(groups.entries())
              const totalDocs = groupEntries.length

              return (
                <details style={{
                  marginTop: 14, paddingTop: 10,
                  borderTop: `1px solid ${t.colors.border}`,
                  cursor: "pointer",
                }}>
                  <summary style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 10.5,
                    fontWeight: 600,
                    color: t.colors.textMuted,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase" as const,
                    userSelect: "none",
                    outline: "none",
                    paddingBottom: 6,
                  } as React.CSSProperties}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="16" y1="13" x2="8" y2="13"/>
                      <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                    SOURCES &mdash; {totalDocs} DOCUMENT{totalDocs !== 1 ? "S" : ""} &bull; {totalUniqueSections} SECTION{totalUniqueSections !== 1 ? "S" : ""}
                  </summary>
                  <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 10 }}>
                    {groupEntries.map(([key, group]) => {
                      // Sections are rendered individually below with prev/next navigation

                      return (
                      <div key={key} style={{
                        background: t.colors.surfaceActive,
                        borderRadius: 10,
                        padding: "10px 12px",
                        border: `1px solid ${t.colors.border}`,
                      }}>
                        {/* ── Document title with section indices ── */}
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          marginBottom: 8,
                          fontSize: 12,
                          fontWeight: 600,
                          color: t.colors.text,
                        }}>
                          <span style={{ fontSize: 13 }}>&#x1F4C4;</span>
                          {group.title}
                          {group.sections.length > 0 && (
                            <span style={{
                              fontSize: 10.5,
                              fontWeight: 500,
                              color: t.colors.textMuted,
                              marginLeft: 4,
                            }}>
                              &mdash; Sections: {group.sections.map((s, si) => 
                                (s.chunk_index !== undefined ? s.chunk_index + 1 : si + 1)
                              ).join(", ")}
                            </span>
                          )}
                        </div>

                        {/* ── Relevance badge ── */}
                        {group.distance <= 0.6 && (
                          <div style={{
                            marginBottom: 8,
                            fontSize: 10,
                            color: group.distance <= 0.3 ? "#16a34a" : "#ca8a04",
                          }}>
                            {group.distance <= 0.3 ? "High relevance" : "Medium relevance"}
                          </div>
                        )}

                        {/* ── Evidence preview with section context navigation (scrollable) ── */}
                        {group.sections.length > 0 && (
                          <div style={{
                            maxHeight: 220,
                            overflowY: "auto" as const,
                            fontSize: 11.5,
                            lineHeight: 1.55,
                            color: t.colors.textSecondary,
                            background: t.colors.cardBg,
                            border: `1px solid ${t.colors.border}`,
                            borderRadius: 6,
                            padding: "4px 0",
                            marginBottom: 8,
                          }}>
                            {group.sections.map((s, si) => {
                              const sectionNum = s.chunk_index !== undefined ? s.chunk_index + 1 : si + 1
                              const prevIdx = si > 0 ? group.sections[si - 1].chunk_index ?? (si - 1) : null
                              const nextIdx = si < group.sections.length - 1 ? group.sections[si + 1].chunk_index ?? (si + 1) : null
                              const safeKey = key.replace(/[^a-z0-9-]/g, "-")
                              const sectionId = `cite-section-${safeKey}-${sectionNum}`

                              return (
                                <div
                                  key={si}
                                  id={sectionId}
                                  style={{
                                    padding: "8px 10px",
                                    borderBottom: si < group.sections.length - 1 ? `1px solid ${t.colors.border}` : "none",
                                  }}
                                >
                                  {/* ── Section heading with audio metadata ── */}
                                  <div style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    marginBottom: 4,
                                    flexWrap: "wrap" as const,
                                    gap: 4,
                                  }}>
                                    <span style={{
                                      fontSize: 10,
                                      fontWeight: 700,
                                      color: t.colors.primary,
                                      textTransform: "uppercase" as const,
                                      letterSpacing: "0.3px",
                                    }}>
                                      Section {sectionNum}
                                    </span>
                                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                      {/* Speaker label for audio/video citations */}
                                      {(s.source_type === "audio" || s.source_type === "video") && s.speaker && (
                                        <span style={{
                                          fontSize: 9,
                                          fontWeight: 600,
                                          color: t.colors.secondary,
                                          background: `${t.colors.secondary}15`,
                                          borderRadius: 4,
                                          padding: "1px 6px",
                                          letterSpacing: "0.2px",
                                        }}>
                                          {'\uD83C\uDF99\uFE0F'} {s.speaker}
                                        </span>
                                      )}
                                      {/* Timestamp for audio/video citations */}
                                      {(s.source_type === "audio" || s.source_type === "video") && (s.start_sec !== undefined) && (
                                        <span style={{
                                          fontSize: 9,
                                          fontWeight: 600,
                                          color: t.colors.textMuted,
                                          background: t.colors.surfaceActive,
                                          borderRadius: 4,
                                          padding: "1px 6px",
                                          fontFamily: "monospace",
                                        }}>
                                          {formatTimestamp(s.start_sec)}
                                          {s.end_sec !== undefined && s.end_sec !== s.start_sec
                                            ? ` - ${formatTimestamp(s.end_sec)}`
                                            : ""}
                                        </span>
                                      )}
                                    </span>
                                  </div>

                                  {/* ── Text content with query-term highlighting ── */}
                                  <div style={{
                                    whiteSpace: "pre-wrap" as const,
                                    wordBreak: "break-word" as const,
                                    fontSize: 11,
                                    lineHeight: 1.55,
                                    color: t.colors.textSecondary,
                                    marginBottom: 6,
                                  }}>
                                    {s.text
                                      ? (() => {
                                          const userQuery = prevMsg?.role === "user" ? prevMsg.content : ""
                                          const terms = extractQueryTerms(userQuery)
                                          return renderEvidenceContent(s.text, terms, t)
                                        })()
                                      : "(No preview text available)"
                                    }
                                  </div>

                                  {/* ── Navigation: Previous / Next section ── */}
                                  <div style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                    fontSize: 10,
                                  }}>
                                    {prevIdx !== null && (
                                      <span
                                        onClick={() => {
                                          const el = document.getElementById(`cite-section-${safeKey}-${prevIdx + 1}`)
                                          if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" })
                                        }}
                                        style={{
                                          color: t.colors.primary,
                                          cursor: "pointer",
                                          fontWeight: 600,
                                          display: "inline-flex",
                                          alignItems: "center",
                                          gap: 3,
                                          userSelect: "none",
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.7" }}
                                        onMouseLeave={(e) => { e.currentTarget.style.opacity = "1" }}
                                      >
                                        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                                        Section {prevIdx + 1}
                                      </span>
                                    )}
                                    {prevIdx !== null && nextIdx !== null && (
                                      <span style={{ color: t.colors.border }}>|</span>
                                    )}
                                    {nextIdx !== null && (
                                      <span
                                        onClick={() => {
                                          const el = document.getElementById(`cite-section-${safeKey}-${nextIdx + 1}`)
                                          if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" })
                                        }}
                                        style={{
                                          color: t.colors.primary,
                                          cursor: "pointer",
                                          fontWeight: 600,
                                          display: "inline-flex",
                                          alignItems: "center",
                                          gap: 3,
                                          userSelect: "none",
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.7" }}
                                        onMouseLeave={(e) => { e.currentTarget.style.opacity = "1" }}
                                      >
                                        Section {nextIdx + 1}
                                        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                                      </span>
                                    )}
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        )}

                        {/* ── Action buttons with audio play support ── */}
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          flexWrap: "wrap" as const,
                        }}>
                          {/* Play from timestamp for audio/video citations */}
                          {group.sections[0]?.start_sec !== undefined && (
                            <button
                              onClick={() => {
                                const first = group.sections[0]
                                if (first.start_sec !== undefined && first.filename) {
                                  const ts = formatTimestamp(first.start_sec)
                                  // Dispatch a custom event so an audio player overlay can pick it up
                                  window.dispatchEvent(new CustomEvent("doctel_play_audio", {
                                    detail: {
                                      filename: first.filename,
                                      startSec: first.start_sec,
                                      endSec: first.end_sec,
                                      label: `Playing from ${ts} - ${first.filename}`,
                                    },
                                  }))
                                }
                              }}
                              title={`Play from ${formatTimestamp(group.sections[0].start_sec!)}`}
                              style={{
                                fontSize: 10.5,
                                fontWeight: 600,
                                color: t.colors.primary,
                                border: "none",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                padding: "4px 8px",
                                borderRadius: 4,
                                background: `${t.colors.primary}10`,
                                cursor: "pointer",
                                fontFamily: "inherit",
                              }}
                              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = `${t.colors.primary}20` }}
                              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = `${t.colors.primary}10` }}
                            >
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                              Play from {formatTimestamp(group.sections[0].start_sec!)}
                            </button>
                          )}
                          {group.sections[0]?.preview_url && (
                            <a href={group.sections[0].preview_url!}
                              style={{
                                fontSize: 10.5,
                                fontWeight: 600,
                                color: t.colors.primary,
                                textDecoration: "none",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                padding: "4px 8px",
                                borderRadius: 4,
                                background: `${t.colors.primary}10`,
                              }}
                              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = `${t.colors.primary}20` }}
                              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = `${t.colors.primary}10` }}
                            >
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                              Preview Document
                            </a>
                          )}
                          <span style={{
                            fontSize: 10,
                            color: t.colors.textMuted,
                          }}>
                            {group.sections.length} section{group.sections.length !== 1 ? "s" : ""} matched
                          </span>
                        </div>
                      </div>
                      )
                    })}
                  </div>
                </details>
              )
            })()}

            {/* Citation mode badge for summary/light modes */}
            {!isUser && msg.citation_mode === "summary" && msg.evidence_count !== undefined && msg.evidence_count > 0 && (
              <div style={{
                marginTop: 10,
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 10.5,
                fontWeight: 600,
                color: t.colors.textMuted,
              }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                </svg>
                Sources: {msg.evidence_count} evidence chunk{msg.evidence_count !== 1 ? "s" : ""}
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
