import React, { useState, useCallback } from "react"
import { useTheme } from "../../context/ThemeContext"
import { getTokens, ThemeTokens } from "../../theme/themeTokens"

/* ── Types ── */
export interface MeetingParticipant {
  name: string
  role?: string | null
  speaking_percentage?: number | null
}

export interface AgendaItem {
  topic: string
  timestamp_sec?: number | null
  duration_sec?: number | null
}

export interface MeetingDecision {
  description: string
  made_by?: string | null
  timestamp_sec?: number | null
  consensus?: boolean
}

export interface ActionItem {
  action: string
  owner?: string | null
  due_date?: string | null
  priority?: string
  status?: string
}

export interface RiskItem {
  risk: string
  impact?: string | null
  mitigation?: string | null
  severity?: string
}

export interface FollowUp {
  task: string
  owner?: string | null
  next_meeting?: boolean
}

export interface MeetingSummaryData {
  title: string
  date?: string | null
  duration_minutes?: number | null
  summary: string
  participants: MeetingParticipant[]
  agenda: AgendaItem[]
  topics_discussed: string[]
  decisions: MeetingDecision[]
  action_items: ActionItem[]
  risks: RiskItem[]
  follow_ups: FollowUp[]
  key_dates: { date: string; event: string }[]
  systems_mentioned: string[]
  entities: string[]
  sentiment: string
}

/* ── Props ── */
interface MeetingSummaryCardProps {
  data: MeetingSummaryData
  /** Called when user wants to analyze a different meeting. */
  onReAnalyze?: () => void
}

/* ── Helpers ── */
function formatTimestamp(seconds?: number | null): string {
  if (seconds === undefined || seconds === null) return ""
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
}

function sentimentColor(sentiment: string): string {
  switch (sentiment) {
    case "Positive": return "#16a34a"
    case "Negative": return "#dc2626"
    case "Urgent": return "#ea580c"
    default: return "#6b7280"
  }
}

function priorityColor(priority: string): string {
  switch (priority?.toLowerCase()) {
    case "high": return "#dc2626"
    case "medium": return "#ca8a04"
    case "low": return "#6b7280"
    default: return "#6b7280"
  }
}

/* ── Sub-components ── */
function Section({
  icon,
  title,
  children,
  defaultOpen = false,
}: {
  icon: string
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const { theme } = useTheme()
  const t: ThemeTokens = getTokens(theme)
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div
      style={{
        border: `1px solid ${t.colors.border}`,
        borderRadius: t.radii.md,
        overflow: "hidden",
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "8px 12px",
          border: "none",
          background: t.colors.surfaceActive,
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
          color: t.colors.text,
          fontFamily: "inherit",
          textAlign: "left",
        }}
      >
        <span style={{ fontSize: 14, flexShrink: 0 }}>{icon}</span>
        <span style={{ flex: 1 }}>{title}</span>
        <span style={{
          fontSize: 10,
          color: t.colors.textMuted,
          transition: "transform 0.2s ease",
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
        }}>
          \u25BC
        </span>
      </button>
      {open && (
        <div style={{ padding: "8px 12px", fontSize: 12, lineHeight: 1.55, color: t.colors.textSecondary }}>
          {children}
        </div>
      )}
    </div>
  )
}

/* ── Main Component ── */
const MeetingSummaryCard: React.FC<MeetingSummaryCardProps> = ({
  data,
  onReAnalyze,
}) => {
  const { theme } = useTheme()
  const t: ThemeTokens = getTokens(theme)

  return (
    <div
      style={{
        background: t.colors.cardBg,
        border: `1px solid ${t.colors.border}`,
        borderRadius: t.radii.lg,
        overflow: "hidden",
        boxShadow: t.shadows.md,
      }}
    >
      {/* ── Header ── */}
      <div style={{
        padding: "14px 16px",
        borderBottom: `1px solid ${t.colors.border}`,
        display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12,
      }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: t.colors.text, marginBottom: 2 }}>
            \uD83D\uDCCB {data.title || "Meeting Summary"}
          </div>
          <div style={{ fontSize: 11, color: t.colors.textMuted }}>
            {data.date && `${data.date} \u00B7 `}
            {data.duration_minutes ? `${Math.round(data.duration_minutes)} min \u00B7 ` : ""}
            <span style={{
              color: sentimentColor(data.sentiment),
              fontWeight: 600,
            }}>
              {data.sentiment}
            </span>
          </div>
        </div>
        {onReAnalyze && (
          <button
            onClick={onReAnalyze}
            style={{
              padding: "4px 10px",
              borderRadius: t.radii.sm,
              border: `1px solid ${t.colors.border}`,
              background: t.colors.surfaceActive,
              cursor: "pointer",
              fontSize: 10.5,
              fontWeight: 600,
              color: t.colors.textMuted,
              fontFamily: "inherit",
              flexShrink: 0,
            }}
          >
            Re-analyze
          </button>
        )}
      </div>

      {/* ── Summary ── */}
      {data.summary && (
        <div style={{ padding: "10px 16px", borderBottom: `1px solid ${t.colors.border}` }}>
          <div style={{ fontSize: 12.5, lineHeight: 1.65, color: t.colors.textSecondary }}>
            {data.summary}
          </div>
        </div>
      )}

      {/* ── Sections ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "10px 16px" }}>

        {/* Participants */}
        {data.participants.length > 0 && (
          <Section icon="\uD83D\uDC65" title={`Participants (${data.participants.length})`}>
            {data.participants.map((p, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontWeight: 600, color: t.colors.text, fontSize: 12 }}>{p.name}</span>
                {p.role && <span style={{ color: t.colors.textMuted, fontSize: 11 }}>({p.role})</span>}
                {p.speaking_percentage !== null && p.speaking_percentage !== undefined && (
                  <div style={{
                    marginLeft: "auto",
                    fontSize: 10,
                    color: t.colors.textMuted,
                    fontVariantNumeric: "tabular-nums",
                  }}>
                    {Math.round(p.speaking_percentage)}%
                  </div>
                )}
              </div>
            ))}
          </Section>
        )}

        {/* Topics */}
        {data.topics_discussed.length > 0 && (
          <Section icon="\uD83D\uDCCA" title={`Topics Discussed (${data.topics_discussed.length})`}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {data.topics_discussed.map((topic, i) => (
                <span key={i} style={{
                  background: `${t.colors.primary}12`,
                  color: t.colors.primary,
                  borderRadius: 12,
                  padding: "2px 10px",
                  fontSize: 11,
                  fontWeight: 500,
                }}>
                  {topic}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Decisions */}
        {data.decisions.length > 0 && (
          <Section icon="\u2705" title={`Key Decisions (${data.decisions.length})`} defaultOpen>
            {data.decisions.map((d, i) => (
              <div key={i} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: i < data.decisions.length - 1 ? `1px solid ${t.colors.border}` : "none" }}>
                <div style={{ fontSize: 12, color: t.colors.text, marginBottom: 2 }}>{d.description}</div>
                <div style={{ display: "flex", gap: 10, fontSize: 10.5, color: t.colors.textMuted }}>
                  {d.made_by && <span>By: {d.made_by}</span>}
                  {d.timestamp_sec !== null && d.timestamp_sec !== undefined && (
                    <span>{formatTimestamp(d.timestamp_sec)}</span>
                  )}
                  {d.consensus && <span style={{ color: "#16a34a" }}>Consensus</span>}
                </div>
              </div>
            ))}
          </Section>
        )}

        {/* Action Items */}
        {data.action_items.length > 0 && (
          <Section icon="\uD83D\uDCCC" title={`Action Items (${data.action_items.length})`} defaultOpen>
            {data.action_items.map((a, i) => (
              <div key={i} style={{
                marginBottom: 6,
                padding: "6px 8px",
                borderRadius: 6,
                background: t.colors.surfaceActive,
                border: `1px solid ${t.colors.border}`,
              }}>
                <div style={{ fontSize: 12, color: t.colors.text, marginBottom: 2 }}>{a.action}</div>
                <div style={{ display: "flex", gap: 10, fontSize: 10.5, color: t.colors.textMuted, flexWrap: "wrap" }}>
                  {a.owner && <span>Owner: <strong>{a.owner}</strong></span>}
                  {a.due_date && <span>Due: {a.due_date}</span>}
                  {a.priority && (
                    <span style={{
                      color: priorityColor(a.priority),
                      fontWeight: 600,
                      marginLeft: "auto",
                    }}>
                      {a.priority}
                    </span>
                  )}
                  {a.status && (
                    <span style={{
                      color: a.status === "Open" ? "#ca8a04" : "#16a34a",
                      fontWeight: 600,
                    }}>
                      {a.status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </Section>
        )}

        {/* Risks */}
        {data.risks.length > 0 && (
          <Section icon="\u26A0\uFE0F" title={`Risks (${data.risks.length})`}>
            {data.risks.map((r, i) => (
              <div key={i} style={{ marginBottom: 6, padding: "6px 8px", borderRadius: 6, background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.15)" }}>
                <div style={{ fontSize: 12, color: t.colors.text, marginBottom: 2 }}>{r.risk}</div>
                <div style={{ fontSize: 10.5, color: t.colors.textMuted }}>
                  {r.impact && <div>Impact: {r.impact}</div>}
                  {r.mitigation && <div>Mitigation: {r.mitigation}</div>}
                  {r.severity && <span style={{ color: priorityColor(r.severity), fontWeight: 600 }}>{r.severity} severity</span>}
                </div>
              </div>
            ))}
          </Section>
        )}

        {/* Systems Mentioned */}
        {data.systems_mentioned.length > 0 && (
          <Section icon="\uD83D\uDEE1\uFE0F" title={`Systems Mentioned (${data.systems_mentioned.length})`}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {data.systems_mentioned.map((sys, i) => (
                <span key={i} style={{
                  background: `${t.colors.secondary}12`,
                  color: t.colors.secondary,
                  borderRadius: 12,
                  padding: "2px 10px",
                  fontSize: 11,
                  fontWeight: 500,
                }}>
                  {sys}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Key Dates */}
        {data.key_dates.length > 0 && (
          <Section icon="\uD83D\uDCC5" title={`Key Dates (${data.key_dates.length})`}>
            {data.key_dates.map((kd, i) => (
              <div key={i} style={{ display: "flex", gap: 10, marginBottom: 4, fontSize: 12 }}>
                <span style={{ fontWeight: 600, color: t.colors.text, flexShrink: 0 }}>{kd.date}</span>
                <span style={{ color: t.colors.textSecondary }}>{kd.event}</span>
              </div>
            ))}
          </Section>
        )}

        {/* Follow-Ups */}
        {data.follow_ups.length > 0 && (
          <Section icon="\uD83D\uDD04" title={`Follow-Ups (${data.follow_ups.length})`}>
            {data.follow_ups.map((f, i) => (
              <div key={i} style={{ marginBottom: 4, fontSize: 12 }}>
                <span style={{ color: t.colors.text }}>{f.task}</span>
                {f.owner && <span style={{ color: t.colors.textMuted }}> — {f.owner}</span>}
                {f.next_meeting && <span style={{ color: t.colors.primary, marginLeft: 6 }}>Next meeting</span>}
              </div>
            ))}
          </Section>
        )}
      </div>
    </div>
  )
}

export default MeetingSummaryCard
