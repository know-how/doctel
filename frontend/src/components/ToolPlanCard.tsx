import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"

export interface ToolPlan {
  intent: string
  tools: ToolPlanTool[]
  estimated_steps: number
  render_hint: string
  citation_mode: string
  strategy_summary: string
  execution_metadata?: {
    tools_executed?: string[]
    completed?: number
    failed?: number
    total_time_sec?: number
    results?: Record<string, {
      elapsed_sec: number
      status: string
      error?: string
    }>
    errors?: Record<string, string>
  }
}

export interface ToolPlanTool {
  tool: string
  purpose: string
  optional: boolean
}

const INTENT_LABELS: Record<string, string> = {
  question_answering: "Question Answering",
  executive_summary: "Executive Summary",
  document_analysis: "Document Analysis",
  policy_review: "Policy Review",
  frs_analysis: "FRS Analysis",
  meeting_analysis: "Meeting Analysis",
  risk_assessment: "Risk Assessment",
  action_extraction: "Action Extraction",
  workflow_extraction: "Workflow Extraction",
  process_diagram: "Process Diagram",
  comparison: "Comparison",
  root_cause_analysis: "Root Cause Analysis",
  data_analysis: "Data Analysis",
  csv_analysis: "CSV Analysis",
  database_analysis: "Database Analysis",
  report_generation: "Report Generation",
  dashboard_generation: "Dashboard Generation",
  knowledge_discovery: "Knowledge Discovery",
  image_analysis: "Image Analysis",
  audio_analysis: "Audio Analysis",
  chat: "Conversational",
}

const INTENT_COLORS: Record<string, string> = {
  question_answering: "#3B82F6",
  executive_summary: "#8B5CF6",
  document_analysis: "#06B6D4",
  policy_review: "#EF4444",
  frs_analysis: "#F59E0B",
  meeting_analysis: "#8B5CF6",
  risk_assessment: "#EF4444",
  action_extraction: "#F59E0B",
  workflow_extraction: "#06B6D4",
  process_diagram: "#10B981",
  comparison: "#3B82F6",
  root_cause_analysis: "#EF4444",
  data_analysis: "#10B981",
  csv_analysis: "#10B981",
  database_analysis: "#06B6D4",
  report_generation: "#8B5CF6",
  dashboard_generation: "#F59E0B",
  knowledge_discovery: "#3B82F6",
  image_analysis: "#EC4899",
  audio_analysis: "#8B5CF6",
  chat: "#6B7280",
}

const TOOL_ICONS: Record<string, string> = {
  rag_search: "🔍",
  document_compare: "📊",
  document_summary: "📋",
  policy_analysis: "📜",
  frs_analysis: "📐",
  risk_analysis: "⚠️",
  action_extraction: "✅",
  decision_extraction: "🎯",
  workflow_extraction: "🔄",
  diagram_generation: "📈",
  meeting_analysis: "📝",
  audio_analysis: "🎙",
  csv_analysis: "📊",
  database_query: "🗄",
  report_generation: "📄",
  knowledge_graph_query: "🔗",
  timeline_generation: "📅",
  entity_extraction: "🏷",
  query_rewrite: "✏️",
  chat: "💬",
}

interface ToolPlanCardProps {
  plan?: ToolPlan
  /** If true, the card starts collapsed */
  defaultCollapsed?: boolean
}

const ToolPlanCard: React.FC<ToolPlanCardProps> = ({ plan, defaultCollapsed = true }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const [isOpen, setIsOpen] = useState(!defaultCollapsed)

  if (!plan) return null

  const intentLabel = INTENT_LABELS[plan.intent] || plan.intent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  const intentColor = INTENT_COLORS[plan.intent] || t.colors.textMuted
  const toolCount = plan.tools.length
  const completedCount = plan.execution_metadata?.completed ?? 0
  const metadata = plan.execution_metadata

  return (
    <details
      open={isOpen}
      onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
      style={{
        margin: "8px 0 12px",
        borderRadius: 10,
        border: `1px solid ${t.colors.border}40`,
        background: t.colors.surfaceActive + "80",
        fontSize: 12,
      }}
    >
      <summary
        style={{
          padding: "8px 12px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 8,
          userSelect: "none",
          outline: "none",
          fontWeight: 600,
          fontSize: 11,
          color: t.colors.textSecondary,
          letterSpacing: "0.02em",
        }}
      >
        {/* Intent badge */}
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "2px 8px",
          borderRadius: 6,
          background: `${intentColor}15`,
          color: intentColor,
          fontWeight: 700,
          fontSize: 10.5,
          textTransform: "uppercase",
        }}>
          {intentLabel}
        </span>

        <span style={{ color: t.colors.textMuted, fontWeight: 400 }}>
          {plan.estimated_steps} step{plan.estimated_steps !== 1 ? "s" : ""} · {toolCount} tool{toolCount !== 1 ? "s" : ""}
        </span>

        {metadata && metadata.completed !== undefined && (
          <span style={{
            marginLeft: "auto",
            fontSize: 10,
            color: metadata.failed ? "#EF4444" : "#22C55E",
          }}>
            {metadata.total_time_sec !== undefined
              ? `${metadata.completed}/${plan.estimated_steps} in ${metadata.total_time_sec.toFixed(1)}s`
              : `${metadata.completed}/${plan.estimated_steps} completed`
            }
          </span>
        )}
      </summary>

      <div style={{
        padding: "0 12px 10px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}>
        {/* Strategy summary */}
        {plan.strategy_summary && (
          <div style={{
            fontSize: 10.5,
            color: t.colors.textMuted,
            lineHeight: 1.5,
            marginBottom: 4,
            fontStyle: "italic",
          }}>
            {plan.strategy_summary}
          </div>
        )}

        {/* Tool list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {plan.tools.map((tool, i) => {
            const icon = TOOL_ICONS[tool.tool] || "🛠"
            const toolLabel = tool.tool.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
            const result = metadata?.results?.[tool.tool]
            const isCompleted = result?.status === "completed"
            const isFailed = result?.status === "failed"

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "4px 8px",
                  borderRadius: 6,
                  background: isCompleted
                    ? "rgba(34,197,94,0.08)"
                    : isFailed
                      ? "rgba(239,68,68,0.08)"
                      : "transparent",
                  fontSize: 11,
                }}
              >
                <span style={{ flexShrink: 0, fontSize: 13 }}>{icon}</span>
                <span style={{ flex: 1, color: t.colors.text }}>{toolLabel}</span>
                {tool.optional && (
                  <span style={{
                    fontSize: 9,
                    fontWeight: 600,
                    color: t.colors.textMuted,
                    background: t.colors.border + "60",
                    borderRadius: 4,
                    padding: "1px 5px",
                  }}>
                    optional
                  </span>
                )}
                <span style={{
                  fontSize: 10,
                  color: t.colors.textMuted,
                  maxWidth: 200,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>
                  {tool.purpose}
                </span>
                {result && (
                  <span style={{
                    fontSize: 10,
                    color: isFailed ? "#EF4444" : "#22C55E",
                    flexShrink: 0,
                  }}>
                    {isCompleted ? `${result.elapsed_sec?.toFixed(1)}s` : isFailed ? "failed" : ""}
                  </span>
                )}
              </div>
            )
          })}
        </div>

        {/* Render hint + citation mode */}
        <div style={{
          display: "flex",
          gap: 8,
          marginTop: 4,
          fontSize: 10,
          color: t.colors.textMuted,
        }}>
          <span style={{
            background: t.colors.border + "40",
            borderRadius: 4,
            padding: "1px 6px",
          }}>
            render: {plan.render_hint}
          </span>
          <span style={{
            background: t.colors.border + "40",
            borderRadius: 4,
            padding: "1px 6px",
          }}>
            citations: {plan.citation_mode}
          </span>
        </div>

        {/* Error details */}
        {metadata?.errors && Object.keys(metadata.errors).length > 0 && (
          <div style={{
            marginTop: 4,
            padding: "6px 8px",
            background: "rgba(239,68,68,0.08)",
            borderRadius: 6,
            fontSize: 10,
            color: "#EF4444",
          }}>
            {Object.entries(metadata.errors).map(([tool, err]) => (
              <div key={tool}>
                <strong>{tool}:</strong> {err}
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  )
}

export default ToolPlanCard
