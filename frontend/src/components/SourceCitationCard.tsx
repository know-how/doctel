import React from "react"
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

// ── helper: truncate text ────────────────────────────────────────────────────
function truncate(text: string, max = 180): string {
  if (!text) return ""
  return text.length > max ? text.slice(0, max) + "…" : text
}

// ── helper: format chunk / page label ────────────────────────────────────────
function chunkLabel(idx?: number): string {
  if (idx === undefined || idx === null) return ""
  return `p.${idx + 1}`
}

// ── helper: derive file icon letter from extension ───────────────────────────
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

  // ── styles (computed from tokens) ──────────────────────────────────────────
  const cardStyle: React.CSSProperties = {
    background: t.colors.cardBg,
    border: `1px solid ${t.colors.border}`,
    borderRadius: t.radii.md,
    padding: 0,
    display: "flex",
    flexDirection: "column",
    gap: 0,
    overflow: "hidden",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    transition: "all 0.2s ease",
    minWidth: 0,
    maxWidth: "100%",
    boxShadow: t.shadows.sm,
  }

  const headerStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: t.spacing.sm,
    padding: `${t.spacing.sm} ${t.spacing.md}`,
    borderBottom: `1px solid ${t.colors.border}`,
  }

  const iconBoxStyle: React.CSSProperties = {
    width: 28,
    height: 28,
    borderRadius: t.radii.sm,
    background: `linear-gradient(135deg, ${t.colors.primary}22, ${t.colors.secondary}11)`,
    color: t.colors.primary,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 700,
    fontSize: 11,
    flexShrink: 0,
    fontFamily: t.font.sans,
  }

  const fileNameStyle: React.CSSProperties = {
    fontSize: 12.5,
    fontWeight: 600,
    color: t.colors.text,
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontFamily: t.font.sans,
  }

  const chunkBadgeStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 600,
    color: t.colors.textMuted,
    background: t.colors.surface,
    borderRadius: t.radii.sm,
    padding: "2px 7px",
    flexShrink: 0,
    fontFamily: t.font.sans,
  }

  const bodyStyle: React.CSSProperties = {
    padding: `${t.spacing.sm} ${t.spacing.md}`,
  }

  const previewStyle: React.CSSProperties = {
    fontSize: 12,
    lineHeight: "1.55",
    color: t.colors.textSecondary,
    fontFamily: t.font.sans,
    display: "-webkit-box",
    WebkitLineClamp: 3,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
    margin: 0,
    wordBreak: "break-word",
  }

  const footerStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: t.spacing.xs,
    padding: `${t.spacing.xs} ${t.spacing.md}`,
    borderTop: `1px solid ${t.colors.border}`,
    flexWrap: "wrap",
  }

  const actionBtnBase: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 10.5,
    fontWeight: 600,
    fontFamily: t.font.sans,
    padding: "4px 10px",
    borderRadius: t.radii.sm,
    border: "none",
    cursor: "pointer",
    transition: "all 0.15s ease",
    textDecoration: "none",
    lineHeight: 1,
  }

  const primaryBtn: React.CSSProperties = {
    ...actionBtnBase,
    background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.secondary})`,
    color: "#FFFFFF",
  }

  const ghostBtn: React.CSSProperties = {
    ...actionBtnBase,
    background: t.colors.surface,
    color: t.colors.textSecondary,
    border: `1px solid ${t.colors.border}`,
  }

  // round distance to 3 decimal places for display
  const distLabel = distance !== undefined ? `rel: ${distance.toFixed(3)}` : null

  // ── build action buttons ──────────────────────────────────────────────────
  const actions: React.ReactNode[] = []

  //   View / Preview
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

  //   Download
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

  //   Full-text available indicator
  if (full_text_available && can_view) {
    actions.push(
      <span key="fulltext" style={{
        ...ghostBtn, cursor: "default", opacity: 0.7, fontSize: 10, gap: 3,
      }}>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        Full text
      </span>,
    )
  }

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div style={cardStyle}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = t.colors.borderFocus
        e.currentTarget.style.boxShadow = t.shadows.md
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = t.colors.border
        e.currentTarget.style.boxShadow = t.shadows.sm
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={headerStyle}>
        <div style={iconBoxStyle}>{fileIconLetter(filename)}</div>
        <span style={fileNameStyle} title={filename}>
          {filename || "Source document"}
        </span>
        {chunk_index !== undefined && (
          <span style={chunkBadgeStyle}>{chunkLabel(chunk_index)}</span>
        )}
      </div>

      {/* ── Text preview ───────────────────────────────────────────── */}
      {text && (
        <div style={bodyStyle}>
          <p style={previewStyle}>
            {truncate(text)}
          </p>
        </div>
      )}

      {/* ── Footer: distance + action buttons ──────────────────────── */}
      {(actions.length > 0 || distLabel) && (
        <div style={footerStyle}>
          {distLabel && (
            <span style={{
              fontSize: 9.5,
              color: t.colors.textMuted,
              fontFamily: t.font.sans,
              marginRight: "auto",
              fontWeight: 500,
            }}>
              {distLabel}
            </span>
          )}
          {actions}
        </div>
      )}
    </div>
  )
}

export default SourceCitationCard
