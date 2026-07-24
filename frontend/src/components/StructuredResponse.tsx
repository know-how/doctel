import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"

/* ── Types ───────────────────────────────────────────────────────────── */

export interface StructuredData {
  action_items?: ActionItem[]
  decisions?: Decision[]
  risks?: Risk[]
  participants?: string[]
  follow_ups?: string[]
  comparisons?: Comparison[]
  differences?: string[]
  similarities?: string[]
  key_findings?: string[]
  systems?: string[]
  entities?: string[]
  obligations?: string[]
  controls?: string[]
  mermaid_code?: string
  steps?: WorkflowStep[]
  insights?: string[]
  trends?: string[]
  anomalies?: string[]
  chart_data?: ChartDataPoint[]
  kpis?: KpiMetric[]
  relationships?: string[]
  topics?: string[]
  speakers?: string[]
  duration?: string
  [key: string]: unknown
}

export interface ActionItem {
  action?: string
  owner?: string
  due_date?: string
  priority?: string
  status?: string
}

export interface Decision {
  decision?: string
  made_by?: string
  rationale?: string
  date?: string
}

export interface Risk {
  risk?: string
  likelihood?: string
  impact?: string
  severity?: string
  mitigation?: string
  owner?: string
}

export interface Comparison {
  aspect?: string
  item_a?: string
  item_b?: string
  notes?: string
}

export interface WorkflowStep {
  step?: string
  description?: string
  actor?: string
  system?: string
  decision?: string
  duration?: string
}

export interface ChartDataPoint {
  label?: string
  value?: number
  series?: string
}

export interface KpiMetric {
  name?: string
  value?: string
  trend?: string
  status?: string
}

export interface ResponseMetadata {
  render_hint?: string
  citation_mode?: string
  structured_data?: StructuredData
  knowledge_type?: string
  evidence_count?: number
  source_count?: number
}

/* ── Renderers ───────────────────────────────────────────────────────── */

function ExecutiveSummaryCard({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${t.colors.primary}08, ${t.colors.secondary}06)`,
      border: `1px solid ${t.colors.primary}20`,
      borderRadius: 12,
      padding: "16px 20px",
      marginBottom: 12,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: t.colors.primary, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 10 }}>
        Executive Summary
      </div>
      {data.key_findings?.map((f, i) => (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6, fontSize: 13, lineHeight: 1.6, color: t.colors.text }}>
          <span style={{ color: t.colors.primary, flexShrink: 0 }}>•</span>
          <span>{f}</span>
        </div>
      ))}
      {/* Entity chips */}
      {data.entities && data.entities.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 10 }}>
          {data.entities.map((e, i) => (
            <span key={i} style={{ fontSize: 10.5, fontWeight: 600, color: t.colors.secondary, background: `${t.colors.secondary}12`, borderRadius: 6, padding: "2px 8px" }}>
              {e}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function ActionRegister({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  const items = data.action_items || []
  if (items.length === 0) return null

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#F59E0B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>
        Action Items
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, lineHeight: 1.5 }}>
          <thead>
            <tr>
              {["Action", "Owner", "Due Date", "Priority", "Status"].map(h => (
                <th key={h} style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px", background: t.colors.surfaceActive, fontWeight: 600, textAlign: "left", fontSize: 11 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => (
              <tr key={i}>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{item.action || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{item.owner || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{item.due_date || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>
                  <span style={{
                    fontSize: 10.5, fontWeight: 600, padding: "1px 6px", borderRadius: 4,
                    background: item.priority === "High" ? "rgba(239,68,68,0.15)" : item.priority === "Medium" ? "rgba(245,158,11,0.15)" : "rgba(34,197,94,0.15)",
                    color: item.priority === "High" ? "#EF4444" : item.priority === "Medium" ? "#F59E0B" : "#22C55E",
                  }}>
                    {item.priority || "-"}
                  </span>
                </td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{item.status || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RiskRegister({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  const risks = data.risks || []
  if (risks.length === 0) return null

  const severityColor = (s?: string) => {
    if (!s) return t.colors.textMuted
    const l = s.toLowerCase()
    if (l.includes("high") || l.includes("critical")) return "#EF4444"
    if (l.includes("medium") || l.includes("moderate")) return "#F59E0B"
    return "#22C55E"
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#EF4444", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>
        Risk Register
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, lineHeight: 1.5 }}>
          <thead>
            <tr>
              {["Risk", "Likelihood", "Impact", "Severity", "Mitigation", "Owner"].map(h => (
                <th key={h} style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px", background: t.colors.surfaceActive, fontWeight: 600, textAlign: "left", fontSize: 11 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {risks.map((risk, i) => (
              <tr key={i}>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{risk.risk || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{risk.likelihood || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{risk.impact || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>
                  <span style={{ fontSize: 10.5, fontWeight: 600, color: severityColor(risk.severity), padding: "1px 6px", borderRadius: 4, background: `${severityColor(risk.severity)}15` }}>
                    {risk.severity || "-"}
                  </span>
                </td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{risk.mitigation || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{risk.owner || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ComparisonMatrix({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  const comparisons = data.comparisons || []
  if (comparisons.length === 0) return null

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: t.colors.primary, textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>
        Comparison
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, lineHeight: 1.5 }}>
          <thead>
            <tr>
              {["Aspect", "Item A", "Item B", "Notes"].map(h => (
                <th key={h} style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px", background: t.colors.surfaceActive, fontWeight: 600, textAlign: "left", fontSize: 11 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparisons.map((c, i) => (
              <tr key={i}>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px", fontWeight: 600 }}>{c.aspect || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{c.item_a || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{c.item_b || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{c.notes || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MeetingReportCard({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#8B5CF6", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 10 }}>
        Meeting Report
      </div>
      {data.participants && data.participants.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: t.colors.textMuted }}>Participants: </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
            {data.participants.map((p, i) => (
              <span key={i} style={{ fontSize: 11, fontWeight: 600, color: t.colors.primary, background: `${t.colors.primary}12`, borderRadius: 6, padding: "2px 8px" }}>{p}</span>
            ))}
          </div>
        </div>
      )}
      <ActionRegister data={data} t={t} />
      <RiskRegister data={data} t={t} />
      {data.follow_ups && data.follow_ups.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.colors.textMuted, textTransform: "uppercase", marginBottom: 6 }}>Follow-Ups</div>
          {data.follow_ups.map((f, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 12, color: t.colors.textSecondary }}>
              <span>•</span>
              <span>{f}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function WorkflowTable({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  const steps = data.steps || []
  if (steps.length === 0) return null

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#06B6D4", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>
        Process Workflow
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, lineHeight: 1.5 }}>
          <thead>
            <tr>
              {["Step", "Description", "Actor", "System", "Decision"].map(h => (
                <th key={h} style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px", background: t.colors.surfaceActive, fontWeight: 600, textAlign: "left", fontSize: 11 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {steps.map((s, i) => (
              <tr key={i}>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px", fontWeight: 600, fontSize: 11 }}>{s.step || i + 1}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{s.description || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{s.actor || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{s.system || "-"}</td>
                <td style={{ border: `1px solid ${t.colors.border}`, padding: "6px 8px" }}>{s.decision || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function KnowledgeCard({ data, t }: { data: StructuredData; t: ThemeTokens }) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${t.colors.secondary}06, ${t.colors.primary}04)`,
      border: `1px solid ${t.colors.border}`,
      borderRadius: 12,
      padding: "16px 20px",
      marginBottom: 12,
    }}>
      {data.topics && data.topics.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.colors.textMuted, textTransform: "uppercase", marginBottom: 6 }}>Topics</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.topics.map((tpc, i) => (
              <span key={i} style={{ fontSize: 11, fontWeight: 600, color: t.colors.primary, background: `${t.colors.primary}12`, borderRadius: 6, padding: "2px 8px" }}>{tpc}</span>
            ))}
          </div>
        </div>
      )}
      {data.systems && data.systems.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.colors.textMuted, textTransform: "uppercase", marginBottom: 6 }}>Systems</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.systems.map((sys, i) => (
              <span key={i} style={{ fontSize: 11, fontWeight: 600, color: "#06B6D4", background: "rgba(6,182,212,0.12)", borderRadius: 6, padding: "2px 8px" }}>{sys}</span>
            ))}
          </div>
        </div>
      )}
      {data.relationships && data.relationships.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.colors.textMuted, textTransform: "uppercase", marginBottom: 6 }}>Relationships</div>
          {data.relationships.map((rel, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 12, color: t.colors.textSecondary }}>
              <span>→</span>
              <span>{rel}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Citation Mode Badge ──────────────────────────────────────────────── */

function CitationBadge({ mode, count, t }: { mode?: string; count?: number; t: ThemeTokens }) {
  if (mode === "none") return null
  return (
    <div style={{ fontSize: 10, color: t.colors.textMuted, marginTop: 8, display: "flex", gap: 8 }}>
      {count !== undefined && count > 0 && (
        <span style={{ background: t.colors.surfaceActive, borderRadius: 4, padding: "2px 6px" }}>
          {count} evidence chunk{count !== 1 ? "s" : ""}
        </span>
      )}
      <span style={{ background: t.colors.surfaceActive, borderRadius: 4, padding: "2px 6px", textTransform: "capitalize" }}>
        {mode} citations
      </span>
    </div>
  )
}

/* ── Main Component ───────────────────────────────────────────────────── */

interface StructuredResponseProps {
  metadata?: ResponseMetadata
  renderContent: (content: string) => React.ReactNode
}

const StructuredResponse: React.FC<StructuredResponseProps> = ({ metadata, renderContent }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const data = metadata?.structured_data
  const hint = metadata?.render_hint

  if (!metadata || !data) return null

  return (
    <div style={{ marginTop: 4 }}>
      {/* Rendered structured cards based on hint */}
      {hint === "executive_summary" && <ExecutiveSummaryCard data={data} t={t} />}
      {hint === "action_register" && <ActionRegister data={data} t={t} />}
      {hint === "risk_register" && <RiskRegister data={data} t={t} />}
      {hint === "comparison_matrix" && <ComparisonMatrix data={data} t={t} />}
      {hint === "meeting_report" && <MeetingReportCard data={data} t={t} />}
      {hint === "workflow_table" && <WorkflowTable data={data} t={t} />}
      {hint === "knowledge_card" && <KnowledgeCard data={data} t={t} />}
      {hint === "policy_review" && (
        <>
          {data.obligations && data.obligations.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#EF4444", marginBottom: 6 }}>Obligations</div>
              {data.obligations.map((o, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 12, color: t.colors.textSecondary }}><span>•</span><span>{o}</span></div>
              ))}
            </div>
          )}
          {data.controls && data.controls.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#06B6D4", marginBottom: 6 }}>Controls</div>
              {data.controls.map((c, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 12, color: t.colors.textSecondary }}><span>•</span><span>{c}</span></div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Knowledge type badge + citation mode */}
      <CitationBadge mode={metadata.citation_mode} count={metadata.evidence_count} t={t} />
    </div>
  )
}

export default StructuredResponse
