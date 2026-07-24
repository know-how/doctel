import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

/* ── Types ── */

export interface WorkflowStepData {
  step_id: number
  agent_type: string
  purpose: string
  status: string            // pending | running | completed | failed | skipped
  result?: Record<string, any>
  duration_ms?: number
  error?: string
}

export interface WorkflowExecutionData {
  execution_id: string
  workflow_type: string
  objective: string
  status: string            // pending | running | completed | failed
  steps: WorkflowStepData[]
  deliverables?: Record<string, any>
  merged_entities?: string[]
  merged_actions_count?: number
  merged_decisions_count?: number
  merged_risks_count?: number
  execution_summary?: string
  error?: string
  started_at?: string
  completed_at?: string
  total_duration_ms?: number
}

/* ── Agent metadata ── */

const AGENT_META: Record<string, { label: string; icon: string; color: string }> = {
  retrieval_agent: { label: "Retrieval Agent", icon: "\ud83d\udd0d", color: "#3B82F6" },
  graph_agent: { label: "Graph Agent", icon: "\ud83d\udd17", color: "#8B5CF6" },
  asset_agent: { label: "Asset Agent", icon: "\ud83d\udce6", color: "#06B6D4" },
  media_agent: { label: "Media Agent", icon: "\ud83c\udfac", color: "#EC4899" },
  workflow_agent: { label: "Workflow Agent", icon: "\ud83d\udd04", color: "#10B981" },
  meeting_agent: { label: "Meeting Agent", icon: "\ud83d\udcdd", color: "#8B5CF6" },
  risk_agent: { label: "Risk Agent", icon: "\u26a0\ufe0f", color: "#EF4444" },
  reporting_agent: { label: "Reporting Agent", icon: "\ud83d\udcc4", color: "#F59E0B" },
  policy_agent: { label: "Policy Agent", icon: "\ud83d\udcdc", color: "#EF4444" },
  comparison_agent: { label: "Comparison Agent", icon: "\ud83d\udcca", color: "#3B82F6" },
  entity_agent: { label: "Entity Agent", icon: "\ud83c\udff7\ufe0f", color: "#06B6D4" },
  summary_agent: { label: "Summary Agent", icon: "\ud83d\udccb", color: "#8B5CF6" },
}

function getAgentMeta(agentType: string) {
  return AGENT_META[agentType] || {
    label: agentType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    icon: "\ud83e\udd16",
    color: "#6B7280",
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/* ── Workflow type labels ── */

const WORKFLOW_LABELS: Record<string, string> = {
  policy_review: "Policy Review",
  meeting_review: "Meeting Review",
  frs_review: "FRS Review",
  project_health_check: "Project Health Check",
  risk_assessment: "Risk Assessment",
  compliance_review: "Compliance Review",
  knowledge_discovery: "Knowledge Discovery",
  executive_briefing: "Executive Briefing",
  custom: "Custom Workflow",
}

const WORKFLOW_ICONS: Record<string, string> = {
  policy_review: "\ud83d\udcdc",
  meeting_review: "\ud83d\udcdd",
  frs_review: "\ud83d\udcd0",
  project_health_check: "\ud83c\udfe5",
  risk_assessment: "\u26a0\ufe0f",
  compliance_review: "\u2696\ufe0f",
  knowledge_discovery: "\ud83d\udd0d",
  executive_briefing: "\ud83d\udcca",
  custom: "\ud83d\udcbb",
}

/* ── Props ── */

interface WorkflowExecutionCardProps {
  execution?: WorkflowExecutionData
  defaultCollapsed?: boolean
  showDeliverables?: boolean
}

/* ── Component ── */

const WorkflowExecutionCard: React.FC<WorkflowExecutionCardProps> = ({
  execution,
  defaultCollapsed = false,
  showDeliverables = true,
}) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const [isOpen, setIsOpen] = useState(!defaultCollapsed)
  const [activeDeliverable, setActiveDeliverable] = useState<string | null>(null)

  if (!execution) return null

  const wfType = execution.workflow_type
  const wfLabel = WORKFLOW_LABELS[wfType] || wfType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  const wfIcon = WORKFLOW_ICONS[wfType] || "\ud83d\udccb"
  const isCompleted = execution.status === "completed"
  const isFailed = execution.status === "failed"
  const isRunning = execution.status === "running"
  const completedSteps = execution.steps.filter((s) => s.status === "completed").length
  const failedSteps = execution.steps.filter((s) => s.status === "failed").length

  // Compute deliverables
  const deliverables = execution.deliverables || {}
  const deliverableKeys = Object.keys(deliverables)
  const hasDeliverables = deliverableKeys.length > 0

  return (
    <div
      style={{
        borderRadius: 12,
        border: `1px solid ${t.colors.border}50`,
        background: t.colors.surfaceActive + "90",
        fontSize: 12,
        overflow: "hidden",
        margin: "8px 0 12px",
      }}
    >
      {/* Header */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          padding: "10px 14px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 10,
          userSelect: "none",
        }}
      >
        {/* Workflow icon */}
        <span style={{ fontSize: 18, flexShrink: 0 }}>{wfIcon}</span>

        {/* Workflow type badge */}
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "3px 10px",
            borderRadius: 6,
            background: isCompleted
              ? "rgba(34,197,94,0.12)"
              : isFailed
                ? "rgba(239,68,68,0.12)"
                : `${t.colors.primary}15`,
            color: isCompleted ? "#22C55E" : isFailed ? "#EF4444" : t.colors.primary,
            fontWeight: 700,
            fontSize: 11,
          }}
        >
          {wfLabel}
        </span>

        {/* Status */}
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 3,
            padding: "2px 8px",
            borderRadius: 6,
            background: isRunning ? "rgba(250,204,21,0.12)" : "transparent",
            color: isRunning ? "#FACC15" : t.colors.textMuted,
            fontWeight: 600,
            fontSize: 10.5,
          }}
        >
          {isRunning ? "\u23f3" : isCompleted ? "\u2705" : isFailed ? "\u274c" : "\u23f3"}
          {" "}{execution.status}
        </span>

        {/* Step progress */}
        <span
          style={{
            fontSize: 10,
            color: t.colors.textMuted,
            padding: "2px 8px",
            background: `${t.colors.border}40`,
            borderRadius: 6,
          }}
        >
          {completedSteps}/{execution.steps.length} steps
        </span>

        {/* Duration */}
        {execution.total_duration_ms != null && execution.total_duration_ms > 0 && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              color: t.colors.textMuted,
              whiteSpace: "nowrap",
            }}
          >
            {formatDuration(execution.total_duration_ms)}
          </span>
        )}

        {/* Toggle indicator */}
        <span
          style={{
            fontSize: 10,
            color: t.colors.textMuted,
            transform: isOpen ? "rotate(180deg)" : "none",
            transition: "transform 0.2s",
          }}
        >
          \u25bc
        </span>
      </div>

      {/* Body - collapsible */}
      {isOpen && (
        <div
          style={{
            padding: "0 14px 14px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          {/* Objective */}
          <div
            style={{
              fontSize: 12,
              color: t.colors.text,
              fontWeight: 600,
              lineHeight: 1.4,
            }}
          >
            {execution.objective}
          </div>

          {/* Error */}
          {execution.error && (
            <div
              style={{
                padding: "6px 10px",
                borderRadius: 6,
                background: "rgba(239,68,68,0.08)",
                color: "#EF4444",
                fontSize: 10.5,
              }}
            >
              \u274c {execution.error}
            </div>
          )}

          {/* Execution summary */}
          {execution.execution_summary && (
            <details
              style={{
                border: `1px solid ${t.colors.border}30`,
                borderRadius: 8,
                background: `${t.colors.border}15`,
              }}
            >
              <summary
                style={{
                  padding: "6px 10px",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: 10.5,
                  color: t.colors.textSecondary,
                  userSelect: "none",
                  outline: "none",
                }}
              >
                \ud83d\udcca Execution Summary
              </summary>
              <div
                style={{
                  padding: "6px 10px 10px",
                  fontSize: 10.5,
                  color: t.colors.textMuted,
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                  maxHeight: 200,
                  overflow: "auto",
                }}
              >
                {execution.execution_summary}
              </div>
            </details>
          )}

          {/* Step-by-step progress */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                color: t.colors.textSecondary,
                marginBottom: 2,
              }}
            >
              Execution Steps ({completedSteps}/{execution.steps.length})
            </div>

            {/* Progress bar */}
            {execution.steps.length > 0 && (
              <div
                style={{
                  height: 4,
                  borderRadius: 2,
                  background: `${t.colors.border}40`,
                  overflow: "hidden",
                  marginBottom: 4,
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${(completedSteps / execution.steps.length) * 100}%`,
                    borderRadius: 2,
                    background: isFailed
                      ? "linear-gradient(90deg, #EF4444, #FCA5A5)"
                      : "linear-gradient(90deg, #22C55E, #4ADE80)",
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
            )}

            {execution.steps.map((step) => {
              const meta = getAgentMeta(step.agent_type)
              const stepCompleted = step.status === "completed"
              const stepFailed = step.status === "failed"
              const stepRunning = step.status === "running"
              const stepPending = step.status === "pending"

              return (
                <div
                  key={step.step_id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "6px 10px",
                    borderRadius: 8,
                    background: stepCompleted
                      ? "rgba(34,197,94,0.06)"
                      : stepFailed
                        ? "rgba(239,68,68,0.06)"
                        : "transparent",
                    border: `1px solid ${
                      stepCompleted
                        ? "rgba(34,197,94,0.15)"
                        : stepFailed
                          ? "rgba(239,68,68,0.15)"
                          : "transparent"
                    }`,
                    opacity: stepPending ? 0.5 : 1,
                  }}
                >
                  {/* Step number */}
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: stepCompleted
                        ? "rgba(34,197,94,0.15)"
                        : stepFailed
                          ? "rgba(239,68,68,0.15)"
                          : `${t.colors.border}40`,
                      color: stepCompleted
                        ? "#22C55E"
                        : stepFailed
                          ? "#EF4444"
                          : t.colors.textMuted,
                      fontWeight: 700,
                      fontSize: 10,
                      flexShrink: 0,
                    }}
                  >
                    {stepCompleted ? "\u2713" : stepFailed ? "\u2717" : step.step_id}
                  </span>

                  {/* Agent icon */}
                  <span style={{ fontSize: 14, flexShrink: 0 }}>{meta.icon}</span>

                  {/* Purpose + agent type */}
                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      gap: 1,
                      minWidth: 0,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: t.colors.text,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {step.purpose}
                    </span>
                    <span
                      style={{
                        fontSize: 9.5,
                        color: meta.color,
                        fontWeight: 500,
                      }}
                    >
                      {meta.label}
                    </span>
                  </div>

                  {/* Duration */}
                  {step.duration_ms != null && step.duration_ms > 0 && (
                    <span
                      style={{
                        fontSize: 10,
                        color: t.colors.textMuted,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatDuration(step.duration_ms)}
                    </span>
                  )}

                  {/* Status badge */}
                  <span
                    style={{
                      fontSize: 9.5,
                      fontWeight: 600,
                      color: stepCompleted
                        ? "#22C55E"
                        : stepFailed
                          ? "#EF4444"
                          : stepRunning
                            ? "#FACC15"
                            : t.colors.textMuted,
                      padding: "1px 6px",
                      borderRadius: 4,
                      background: stepCompleted
                        ? "rgba(34,197,94,0.1)"
                        : stepFailed
                          ? "rgba(239,68,68,0.1)"
                          : "transparent",
                    }}
                  >
                    {step.status}
                  </span>

                  {/* Error */}
                  {step.error && (
                    <span
                      style={{
                        fontSize: 9.5,
                        color: "#EF4444",
                        maxWidth: 150,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={step.error}
                    >
                      Error: {step.error}
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Finding chips */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
            }}
          >
            {(execution.merged_entities?.length ?? 0) > 0 && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "rgba(6,182,212,0.1)",
                  border: "1px solid rgba(6,182,212,0.2)",
                  color: "#22D3EE",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                \ud83c\udff7\ufe0f {execution.merged_entities!.length} entities
              </span>
            )}
            {(execution.merged_actions_count ?? 0) > 0 && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "rgba(245,158,11,0.1)",
                  border: "1px solid rgba(245,158,11,0.2)",
                  color: "#FCD34D",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                \u2705 {execution.merged_actions_count} actions
              </span>
            )}
            {(execution.merged_decisions_count ?? 0) > 0 && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "rgba(139,92,246,0.1)",
                  border: "1px solid rgba(139,92,246,0.2)",
                  color: "#A78BFA",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                \ud83c\udfaf {execution.merged_decisions_count} decisions
              </span>
            )}
            {(execution.merged_risks_count ?? 0) > 0 && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "rgba(239,68,68,0.1)",
                  border: "1px solid rgba(239,68,68,0.2)",
                  color: "#F87171",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              >
                \u26a0\ufe0f {execution.merged_risks_count} risks
              </span>
            )}
          </div>

          {/* Deliverables section */}
          {showDeliverables && hasDeliverables && (
            <div
              style={{
                border: `1px solid ${t.colors.border}30`,
                borderRadius: 8,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  padding: "6px 10px",
                  fontWeight: 600,
                  fontSize: 10.5,
                  color: t.colors.textSecondary,
                  background: `${t.colors.border}15`,
                  borderBottom: `1px solid ${t.colors.border}30`,
                }}
              >
                \ud83d\udcca Deliverables ({deliverableKeys.length})
              </div>

              {/* Deliverable tabs */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 4,
                  padding: "6px 10px",
                  borderBottom: hasDeliverables ? `1px solid ${t.colors.border}20` : "none",
                }}
              >
                {deliverableKeys.map((key) => {
                  const isActive = activeDeliverable === key
                  const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
                  return (
                    <button
                      key={key}
                      onClick={() =>
                        setActiveDeliverable(activeDeliverable === key ? null : key)
                      }
                      style={{
                        padding: "2px 8px",
                        borderRadius: 6,
                        border: `1px solid ${
                          isActive ? t.colors.primary : `${t.colors.border}40`
                        }`,
                        background: isActive ? `${t.colors.primary}15` : "transparent",
                        color: isActive ? t.colors.primary : t.colors.textMuted,
                        fontSize: 9.5,
                        fontWeight: 600,
                        cursor: "pointer",
                        outline: "none",
                      }}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>

              {/* Active deliverable content */}
              {activeDeliverable && deliverables[activeDeliverable] && (
                <div
                  style={{
                    padding: "8px 10px",
                    fontSize: 10.5,
                    color: t.colors.text,
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                    maxHeight: 300,
                    overflow: "auto",
                    fontFamily: "monospace",
                  }}
                >
                  {typeof deliverables[activeDeliverable] === "string"
                    ? deliverables[activeDeliverable]
                    : JSON.stringify(deliverables[activeDeliverable], null, 2)}
                </div>
              )}
            </div>
          )}

          {/* Timestamps */}
          <div
            style={{
              display: "flex",
              gap: 12,
              fontSize: 9.5,
              color: t.colors.textMuted,
              borderTop: `1px solid ${t.colors.border}30`,
              paddingTop: 8,
            }}
          >
            {execution.started_at && (
              <span>Started: {new Date(execution.started_at).toLocaleTimeString()}</span>
            )}
            {execution.completed_at && (
              <span>Completed: {new Date(execution.completed_at).toLocaleTimeString()}</span>
            )}
            <span>ID: {execution.execution_id.slice(0, 20)}...</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default WorkflowExecutionCard
export type { WorkflowExecutionCardProps }
