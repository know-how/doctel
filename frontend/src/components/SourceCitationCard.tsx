import React, { useState, useCallback } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"

// ── types ────────────────────────────────────────────────────────────────────
export interface SourceCitationProps {
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

// ── helpers ──────────────────────────────────────────────────────────────────

/** Convert raw filename into a human-readable title.
 *  - Strips file extension
 *  - Removes noisy prefixes (apply BEFORE replacing separators)
 *  - Replaces underscores/hyphens with spaces
 *  - Preserves original casing so acronyms (ZETDC, LLM, FRS) stay readable
 */
function humanReadableTitle(filename?: string): string {
  if (!filename) return "Source document"
  // Strip extension
  const noExt = filename.replace(/\.[^.]+$/, "")
  // Remove common prefixes BEFORE replacing separators (regex needs underscores)
  const unprefixed = noExt.replace(/^(ZETDC_|DocTel_|draft_|v\d+_)/i, "")
  // Replace underscores/hyphens with spaces
  const spaced = unprefixed.replace(/[_-]/g, " ")
  // Trim and collapse multiple spaces
  return spaced.replace(/\s+/g, " ").trim()
}

/** Derive a relevance label and color from the distance score.
 *  Returns CSS-compatible values that work in both light and dark mode
 *  by using opaque text colors and semi-transparent backgrounds.
 */
function relevanceBadge(distance?: number): { label: string; color: string; bg: string } {
  if (distance === undefined || distance === null) {
    return { label: "Source", color: "#888", bg: "rgba(128,128,128,0.12)" }
  }
  if (distance <= 0.3) return { label: "High relevance", color: "#16a34a", bg: "rgba(22,163,74,0.10)" }
  if (distance <= 0.6) return { label: "Medium relevance", color: "#ca8a04", bg: "rgba(202,138,4,0.10)" }
  return { label: "Low relevance", color: "#dc2626", bg: "rgba(220,38,38,0.10)" }
}

/** Truncate text for preview. */
function truncate(text: string, max = 180): string {
  if (!text) return ""
  return text.length > max ? text.slice(0, max) + "…" : text
}

/** File icon letter from extension. */
function fileIconLetter(filename?: string): string {
  if (!filename) return "D"
  const ext = filename.split(".").pop()?.toLowerCase()
  if (ext === "pdf") return "P"
  if (["doc", "docx"].includes(ext ?? "")) return "W"
  if (["xls", "xlsx"].includes(ext ?? "")) return "X"
  if (["ppt", "pptx"].includes(ext ?? "")) return "S"
  if (["txt", "md"].includes(ext ?? "")) return "T"
  if (["jpg", "jpeg", "png", "gif", "svg", "webp"].includes(ext ?? "")) return "I"
  return "D"
}

// ── component ────────────────────────────────────────────────────────────────
const SourceCitationCard: React.FC<SourceCitationProps> = ({
  filename,
  chunk_index,
  text,
  full_text_available,
  distance,
  can_view,
  can_download,
  open_url,
  download_url,
  preview_url,
  source_type,
  project_id,
}) => {
  const { theme } = useTheme()
  const t: ThemeTokens = getTokens(theme)
  const [expanded, setExpanded] = useState(false)
  const toggle = useCallback(() => setExpanded((e) => !e), [])

  const title = humanReadableTitle(filename)
  const badge = relevanceBadge(distance)
  const letter = fileIconLetter(filename)

  // ── inline styles ──────────────────────────────────────────────────────────
  const card: React.CSSProperties = {
    background: t.colors.cardBg,
    border: `1px solid ${t.colors.border}`,
    borderRadius: t.radii.md,
    overflow: "hidden",
    cursor: "pointer",
    transition: "all 0.2s ease",
    boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
  }

  const header: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 14px",
    userSelect: "none",
  }

  const iconBox: React.CSSProperties = {
    width: 26,
    height: 26,
    borderRadius: t.radii.sm,
    background: `linear-gradient(135deg, ${t.colors.primary}22, ${t.colors.secondary}11)`,
    color: t.colors.primary,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 700,
    fontSize: 10,
    flexShrink: 0,
    fontFamily: t.font.sans,
  }

  const titleStyle: React.CSSProperties = {
    fontSize: 13,
    fontWeight: 600,
    color: t.colors.text,
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontFamily: t.font.sans,
  }

  const badgeStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 600,
    color: badge.color,
    background: badge.bg,
    borderRadius: 20,
    padding: "2px 10px",
    flexShrink: 0,
    lineHeight: "18px",
    fontFamily: t.font.sans,
  }

  const chevron: React.CSSProperties = {
    fontSize: 10,
    color: t.colors.textMuted,
    flexShrink: 0,
    transition: "transform 0.25s ease",
    transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
  }

  const detailPanel: React.CSSProperties = {
    maxHeight: expanded ? 500 : 0,
    opacity: expanded ? 1 : 0,
    overflow: "hidden",
    transition: "all 0.3s ease",
  }

  const bodyText: React.CSSProperties = {
    fontSize: 12.5,
    lineHeight: 1.6,
    color: t.colors.textSecondary,
    padding: "0 14px 10px",
    margin: 0,
    wordBreak: "break-word",
    fontFamily: t.font.sans,
  }

  const footer: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "0 14px 10px",
    flexWrap: "wrap",
  }

  const btnBase: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 10.5,
    fontWeight: 600,
    padding: "4px 10px",
    borderRadius: t.radii.sm,
    border: "none",
    cursor: "pointer",
    textDecoration: "none",
    lineHeight: 1,
    transition: "opacity 0.15s ease",
  }

  const primaryBtn: React.CSSProperties = {
    ...btnBase,
    background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.secondary})`,
    color: "#FFFFFF",
  }

  const ghostBtn: React.CSSProperties = {
    ...btnBase,
    background: t.colors.surface,
    color: t.colors.textSecondary,
    border: `1px solid ${t.colors.border}`,
  }

  // ── build action buttons (only shown when expanded) ───────────────────────
  const actions: React.ReactNode[] = []
  if (can_view && preview_url) {
    actions.push(
      <a key="preview" href={preview_url} style={primaryBtn}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0.85" }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1" }}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        Preview
      </a>,
    )
  } else if (can_view && open_url) {
    actions.push(
      <a key="open" href={open_url} target="_blank" rel="noopener noreferrer" style={ghostBtn}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = t.colors.surfaceHover }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = t.colors.surface }}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        Open
      </a>,
    )
  }
  if (can_download && download_url) {
    actions.push(
      <a key="download" href={download_url} style={ghostBtn}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = t.colors.surfaceHover }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = t.colors.surface }}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Download
      </a>,
    )
  }
  if (full_text_available && can_view) {
    actions.push(
      <span key="fulltext" style={{ ...ghostBtn, cursor: "default", opacity: 0.7, fontSize: 10, gap: 3 }}>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        Full text
      </span>,
    )
  }

  // ── section reference (human-readable, not "Chunk N") ────────────────────
  const sectionRef = chunk_index !== undefined
    ? `Section ${(chunk_index + 1)}`
    : null

  return (
    <div
      style={card}
      onClick={toggle}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = t.colors.borderFocus
        e.currentTarget.style.boxShadow = t.shadows.md
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = t.colors.border
        e.currentTarget.style.boxShadow = "0 1px 2px rgba(0,0,0,0.05)"
      }}
    >
      {/* ── Header (always visible) ─────────────────────────────────── */}
      <div style={header}>
        <div style={iconBox}>{letter}</div>
        <span style={titleStyle} title={title}>
          {title}
        </span>
        <span style={badgeStyle}>{badge.label}</span>
        <span style={chevron}>▼</span>
      </div>

      {/* ── Detail panel (collapsible) ───────────────────────────────── */}
      <div style={detailPanel}>
        {/* Section reference */}
        {sectionRef && (
          <div style={{ padding: "0 14px 4px" }}>
            <span style={{
              fontSize: 10.5,
              color: t.colors.textMuted,
              fontWeight: 500,
            }}>
              {sectionRef}
            </span>
          </div>
        )}

        {/* Text preview */}
        {text && (
          <p style={bodyText}>{truncate(text)}</p>
        )}

        {/* Action buttons */}
        {actions.length > 0 && (
          <div style={footer}>{actions}</div>
        )}
      </div>
    </div>
  )
}

export default SourceCitationCard
