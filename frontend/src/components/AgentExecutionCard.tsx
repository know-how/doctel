import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

/* ── Types ── */

export interface AgentResult {
  agent_type: string
  status: string
  duration_ms: number
  summary?: string
  key_findings?: string[]
  entities_count?: number
  actions_count?: number
  decisions_count?: number
  risks_count?: number
  has_evidence?: boolean
  error?: string
}

export interface AgentExecution {
  agents_executed: number
  agent_results: AgentResult[]
  execution_summary?: string
  total_duration_ms?: number
}

/* ── Agent metadata ── */

const AGENT_META: Record<string, { label: string; icon: string; color: string }> = {
  retrieval_agent: { label: "Retrieval Agent", icon: "🔍", color: "#3B82F6" },
  graph_agent: { label: "Graph Agent", icon: "🔗", color: "#8B5CF6" },
  asset_agent: { label: "Asset Agent", icon: "📦", color: "#06B6D4" },
  media_agent: { label: "Media Agent", icon: "🎬", color: "#EC4899" },
  workflow_agent: { label: "Workflow Agent", icon: "🔄", color: "#10B981" },
  meeting_agent: { label: "Meeting Agent", icon: "📝", color: "#8B5CF6" },
  risk_agent: { label: "Risk Agent", icon: "⚠️", color: "#EF4444" },
  reporting_agent: { label: "Reporting Agent", icon: "📄", color: "#F59E0B" },
  policy_agent: { label: "Policy Agent", icon: "📜", color: "#EF4444" },
  comparison_agent: { label: "Comparison Agent", icon: "📊", color: "#3B82F6" },
  entity_agent: { label: "Entity Agent", icon: "🏷", color: "#06B6D4" },
  summary_agent: { label: "Summary Agent", icon: "📋", color: "#8B5CF6" },
}

function getAgentMeta(agentType: string) {
  return AGENT_META[agentType] || {
    label: agentType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    icon: "🤖",
    color: "#6B7280",
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/* ── Props ── */

interface AgentExecutionCardProps {
  execution?: AgentExecution
  defaultCollapsed?: boolean
}

/* ── Component ── */

const AgentExecutionCard: React.FC<AgentExecutionCardProps> = ({
  execution,
  defaultCollapsed = true,
}) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const [isOpen, setIsOpen] = useState(!defaultCollapsed)

  if (!execution || !execution.agent_results || execution.agent_results.length === 0) {
    return null
  }

  const totalDuration = execution.total_duration_ms ?? 0
  const completedAgents = execution.agent_results.filter((a) => a.status === "completed").length
  const failedAgents = execution.agent_results.filter((a) => a.status === "failed").length
  const hasFindings = execution.agent_results.some(
    (a) => (a.key_findings?.length ?? 0) > 0 || a.summary
  )

  return (
    <details
      open={isOpen}
      onToggle={(e) => setIsOpen((e.target as HTMLDetailsElement).open)}
      style={{
        margin: "8px 0 12px",
        borderRadius: 10,
        border: `1px solid ${t.colors.border}40`,
        background: `linear-gradient(135deg, ${t.colors.surfaceActive}80, ${t.colors.cardBg}40)`,
        fontSize: 12,
        overflow: "hidden",
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
        {/* Icon */}
        <span style={{ fontSize: 14, flexShrink: 0 }}>🧠</span>

        {/* Title */}
        <span style={{ fontWeight: 700, color: t.colors.text }}>
          Agent Execution
        </span>

        {/* Agent count */}
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 3,
          padding: "1px 7px",
          borderRadius: 6,
          background: `${t.colors.primary}15`,
          color: t.colors.primary,
          fontWeight: 600,
          fontSize: 10,
        }}>
          {execution.agents_executed} agent{execution.agents_executed !== 1 ? "s" : ""}
        </span>

        {/* Status badges */}
        {completedAgents > 0 && (
          <span style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 3,
            padding: "1px 7px",
            borderRadius: 6,
            background: "rgba(34,197,94,0.12)",
            color: "#22C55E",
            fontWeight: 600,
            fontSize: 10,
          }}>
            ✓ {completedAgents} done
          </span>
        )}
        {failedAgents > 0 && (
          <span style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 3,
            padding: "1px 7px",
            borderRadius: 6,
            background: "rgba(239,68,68,0.12)",
            color: "#EF4444",
            fontWeight: 600,
            fontSize: 10,
          }}>
            ✗ {failedAgents} failed
          </span>
        )}

        {/* Duration */}
        {totalDuration > 0 && (
          <span style={{
            marginLeft: "auto",
            fontSize: 10,
            color: t.colors.textMuted,
            whiteSpace: "nowrap",
          }}>
            {formatDuration(totalDuration)}
          </span>
        )}
      </summary>

      <div style={{
        padding: "0 12px 10px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}>
        {/* Execution summary */}
        {execution.execution_summary && (
          <div style={{
            fontSize: 10.5,
            color: t.colors.textMuted,
            lineHeight: 1.5,
            marginBottom: 2,
            padding: "6px 8px",
            background: `${t.colors.border}30`,
            borderRadius: 6,
            whiteSpace: "pre-wrap",
            maxHeight: 120,
            overflow: "hidden",
          }}>
            {execution.execution_summary.length > 400
              ? execution.execution_summary.slice(0, 400) + "…"
              : execution.execution_summary}
          </div>
        )}

        {/* Agent result list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {execution.agent_results.map((agent, i) => {
            const meta = getAgentMeta(agent.agent_type)
            const isCompleted = agent.status === "completed"
            const isFailed = agent.status === "failed"

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  padding: "6px 8px",
                  borderRadius: 6,
                  background: isCompleted
                    ? "rgba(34,197,94,0.04)"
                    : isFailed
                      ? "rgba(239,68,68,0.06)"
                      : "transparent",
                  border: `1px solid ${isCompleted ? "rgba(34,197,94,0.12)" : isFailed ? "rgba(239,68,68,0.15)" : "transparent"}`,
                }}
              >
                {/* Agent row */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}>
                  <span style={{ fontSize: 13, flexShrink: 0 }}>{meta.icon}</span>
                  <span style={{
                    flex: 1,
                    fontSize: 11.5,
                    fontWeight: 600,
                    color: t.colors.text,
                  }}>
                    {meta.label}
                  </span>

                  {/* Status indicator */}
                  <span style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: isCompleted ? "#22C55E" : isFailed ? "#EF4444" : "#F59E0B",
                  }}>
                    {agent.status}
                  </span>

                  {/* Duration */}
                  {agent.duration_ms > 0 && (
                    <span style={{
                      fontSize: 10,
                      color: t.colors.textMuted,
                      whiteSpace: "nowrap",
                    }}>
                      {formatDuration(agent.duration_ms)}
                    </span>
                  )}
                </div>

                {/* Key findings */}
                {(agent.key_findings?.length ?? 0) > 0 && (
                  <div style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 3,
                    marginTop: 2,
                  }}>
                    {agent.key_findings!.slice(0, 3).map((f, fi) => (
                      <span
                        key={fi}
                        style={{
                          fontSize: 9.5,
                          color: t.colors.textMuted,
                          background: `${t.colors.border}40`,
                          borderRadius: 4,
                          padding: "1px 6px",
                          lineHeight: "18px",
                        }}
                      >
                        {f}
                      </span>
                    ))}
                    {(agent.key_findings!.length) > 3 && (
                      <span style={{
                        fontSize: 9.5,
                        color: t.colors.textMuted,
                      }}>
                        +{agent.key_findings!.length - 3} more
                      </span>
                    )}
                  </div>
                )}

                {/* Entity/action/decision/risk counts */}
                {(agent.entities_count || agent.actions_count || agent.decisions_count || agent.risks_count) && (
                  <div style={{
                    display: "flex",
                    gap: 6,
                    marginTop: 2,
                    fontSize: 9.5,
                    color: t.colors.textMuted,
                  }}>
                    {agent.entities_count ? (
                      <span>🏷 {agent.entities_count} entities</span>
                    ) : null}
                    {agent.actions_count ? (
                      <span>✅ {agent.actions_count} actions</span>
                    ) : null}
                    {agent.decisions_count ? (
                      <span>🎯 {agent.decisions_count} decisions</span>
                    ) : null}
                    {agent.risks_count ? (
                      <span>⚠️ {agent.risks_count} risks</span>
                    ) : null}
                  </div>
                )}

                {/* Error */}
                {agent.error && (
                  <div style={{
                    fontSize: 10,
                    color: "#EF4444",
                    marginTop: 2,
                  }}>
                    Error: {agent.error}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Legend */}
        {hasFindings && (
          <div style={{
            display: "flex",
            gap: 12,
            marginTop: 4,
            fontSize: 9,
            color: t.colors.textMuted,
            justifyContent: "center",
            borderTop: `1px solid ${t.colors.border}30`,
            paddingTop: 6,
          }}>
            <span>🏷 Entities</span>
            <span>✅ Action items</span>
            <span>🎯 Decisions</span>
            <span>⚠️ Risks</span>
          </div>
        )}
      </div>
    </details>
  )
}

export default AgentExecutionCard
export type { AgentExecutionCardProps }
