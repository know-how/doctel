/**
 * WorkflowExecutionCardMobile — Workflow execution results card for mobile
 *
 * Mirrors the web frontend WorkflowExecutionCard.tsx.
 * Shows workflow type, steps, status, progress, deliverables,
 * and agent findings.
 */
import React, { useState } from "react"
import { View, Text, Pressable, ScrollView } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { WorkflowStep } from "../types/api"

interface WorkflowExecutionCardMobileProps {
  workflowType: string
  objective: string
  status: string
  steps?: WorkflowStep[]
  deliverables?: Record<string, any>
  mergedEntities?: string[]
  mergedActionsCount?: number
  mergedDecisionsCount?: number
  mergedRisksCount?: number
  executionSummary?: string
  error?: string
  totalDurationMs?: number
  startedAt?: string
  completedAt?: string
}

const WORKFLOW_ICONS: Record<string, string> = {
  policy_review: "📜",
  meeting_review: "📋",
  meeting_analysis: "📋",
  frs_review: "📄",
  risk_assessment: "⚠️",
  compliance_review: "✅",
  knowledge_discovery: "🔍",
  executive_briefing: "📊",
  project_health_check: "🏥",
}

const STATUS_COLORS: Record<string, string> = {
  pending: "#9CA3AF",
  running: "#4F7CFF",
  completed: "#22C55E",
  failed: "#EF4444",
}

function getWorkflowIcon(type: string): string {
  return WORKFLOW_ICONS[type.toLowerCase()] || "⚙️"
}

export function WorkflowExecutionCardMobile({
  workflowType,
  objective,
  status,
  steps,
  deliverables,
  mergedEntities,
  mergedActionsCount,
  mergedDecisionsCount,
  mergedRisksCount,
  executionSummary,
  error,
  totalDurationMs,
  startedAt,
  completedAt,
}: WorkflowExecutionCardMobileProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const [expanded, setExpanded] = useState(false)
  const [showDeliverables, setShowDeliverables] = useState(false)
  const statusColor = STATUS_COLORS[status] || "#9CA3AF"

  const completedSteps = steps?.filter((s) => s.status === "completed").length || 0
  const totalSteps = steps?.length || 0
  const progress = totalSteps > 0 ? completedSteps / totalSteps : 0

  return (
    <View
      style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: c.border,
        marginHorizontal: 12,
        marginBottom: 8,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Pressable
        onPress={() => setExpanded(!expanded)}
        style={{
          flexDirection: "row",
          alignItems: "center",
          paddingHorizontal: 12,
          paddingVertical: 10,
          backgroundColor: c.primary + "12",
        }}
      >
        <Text style={{ fontSize: 16, marginRight: 8 }}>
          {getWorkflowIcon(workflowType)}
        </Text>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontSize: 11,
              fontWeight: "700",
              color: statusColor,
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            {workflowType.replace(/_/g, " ")}
          </Text>
          <Text
            style={{
              fontSize: 13,
              fontWeight: "600",
              color: c.text,
              marginTop: 2,
            }}
            numberOfLines={1}
          >
            {objective}
          </Text>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 2 }}>
            <Text style={{ fontSize: 10, color: c.textMuted }}>
              {totalSteps > 0
                ? `${completedSteps}/${totalSteps} steps`
                : status}
            </Text>
            {totalDurationMs != null && (
              <Text style={{ fontSize: 10, color: c.textMuted }}>
                {(totalDurationMs / 1000).toFixed(1)}s
              </Text>
            )}
          </View>
        </View>
        <Text style={{ fontSize: 10, color: c.textMuted }}>
          {expanded ? "▲" : "▼"}
        </Text>
      </Pressable>

      {/* Progress bar */}
      {totalSteps > 0 && (
        <View
          style={{
            height: 3,
            backgroundColor: c.border,
          }}
        >
          <View
            style={{
              height: "100%",
              width: `${Math.round(progress * 100)}%`,
              backgroundColor:
                status === "failed"
                  ? c.error
                  : status === "completed"
                  ? c.success
                  : c.primary,
              borderRadius: 2,
            }}
          />
        </View>
      )}

      {/* Expanded content */}
      {expanded && (
        <ScrollView style={{ maxHeight: 400 }} showsVerticalScrollIndicator>
          <View style={{ padding: 12, gap: 8 }}>
            {/* Status badge */}
            <View
              style={{
                alignSelf: "flex-start",
                backgroundColor: statusColor + "18",
                borderRadius: 6,
                paddingHorizontal: 8,
                paddingVertical: 3,
              }}
            >
              <Text
                style={{
                  fontSize: 10,
                  fontWeight: "600",
                  color: statusColor,
                }}
              >
                {status.toUpperCase()}
              </Text>
            </View>

            {/* Execution summary */}
            {executionSummary && (
              <View
                style={{
                  backgroundColor: "rgba(255,255,255,0.05)",
                  borderRadius: 8,
                  padding: 10,
                }}
              >
                <Text
                  style={{
                    fontSize: 10,
                    fontWeight: "600",
                    color: c.textMuted,
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Summary
                </Text>
                <Text
                  style={{
                    fontSize: 12,
                    color: c.textSecondary,
                    lineHeight: 18,
                  }}
                >
                  {executionSummary}
                </Text>
              </View>
            )}

            {/* Steps */}
            {steps && steps.length > 0 && (
              <View>
                <Text
                  style={{
                    fontSize: 10,
                    fontWeight: "600",
                    color: c.textMuted,
                    textTransform: "uppercase",
                    marginBottom: 6,
                  }}
                >
                  Steps
                </Text>
                {steps.map((step, idx) => (
                  <View
                    key={idx}
                    style={{
                      flexDirection: "row",
                      alignItems: "flex-start",
                      gap: 8,
                      paddingVertical: 6,
                      borderBottomWidth: idx < steps.length - 1 ? 1 : 0,
                      borderBottomColor: c.border,
                    }}
                  >
                    {/* Step number circle */}
                    <View
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: 11,
                        backgroundColor:
                          step.status === "completed"
                            ? c.success + "18"
                            : step.status === "failed"
                            ? c.error + "18"
                            : "rgba(255,255,255,0.08)",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 10,
                          fontWeight: "600",
                          color:
                            step.status === "completed"
                              ? c.success
                              : step.status === "failed"
                              ? c.error
                              : c.textMuted,
                        }}
                      >
                        {step.status === "completed"
                          ? "✓"
                          : step.status === "failed"
                          ? "✕"
                          : idx + 1}
                      </Text>
                    </View>

                    <View style={{ flex: 1 }}>
                      <Text
                        style={{
                          fontSize: 12,
                          fontWeight: "500",
                          color: c.text,
                        }}
                      >
                        {step.agent_type
                          ? step.agent_type
                              .replace(/_/g, " ")
                              .replace(/\b\w/g, (c) => c.toUpperCase())
                          : step.purpose || `Step ${idx + 1}`}
                      </Text>
                      {step.purpose && (
                        <Text
                          style={{
                            fontSize: 10,
                            color: c.textMuted,
                            marginTop: 2,
                          }}
                          numberOfLines={2}
                        >
                          {step.purpose}
                        </Text>
                      )}
                      {step.duration_ms != null && (
                        <Text style={{ fontSize: 9, color: c.textMuted, marginTop: 1 }}>
                          {(step.duration_ms / 1000).toFixed(1)}s
                        </Text>
                      )}
                      {step.error && (
                        <Text
                          style={{
                            fontSize: 10,
                            color: c.error,
                            marginTop: 2,
                          }}
                        >
                          Error: {step.error}
                        </Text>
                      )}
                    </View>
                  </View>
                ))}
              </View>
            )}

            {/* Findings chips */}
            {(mergedEntities?.length ||
              mergedActionsCount ||
              mergedDecisionsCount ||
              mergedRisksCount) && (
              <View>
                <Text
                  style={{
                    fontSize: 10,
                    fontWeight: "600",
                    color: c.textMuted,
                    textTransform: "uppercase",
                    marginBottom: 6,
                  }}
                >
                  Findings
                </Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
                  {mergedEntities?.map((e, i) => (
                    <View
                      key={`e-${i}`}
                      style={{
                        backgroundColor: c.primary + "14",
                        borderRadius: 4,
                        paddingHorizontal: 6,
                        paddingVertical: 2,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 10,
                          color: c.primary,
                          fontWeight: "500",
                        }}
                      >
                        🏷️ {e}
                      </Text>
                    </View>
                  ))}
                  {mergedActionsCount != null && mergedActionsCount > 0 && (
                    <View
                      style={{
                        backgroundColor: c.warning + "14",
                        borderRadius: 4,
                        paddingHorizontal: 6,
                        paddingVertical: 2,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 10,
                          color: c.warning,
                          fontWeight: "500",
                        }}
                      >
                        🎯 {mergedActionsCount} action
                        {mergedActionsCount !== 1 ? "s" : ""}
                      </Text>
                    </View>
                  )}
                  {mergedDecisionsCount != null && mergedDecisionsCount > 0 && (
                    <View
                      style={{
                        backgroundColor: c.success + "14",
                        borderRadius: 4,
                        paddingHorizontal: 6,
                        paddingVertical: 2,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 10,
                          color: c.success,
                          fontWeight: "500",
                        }}
                      >
                        ✅ {mergedDecisionsCount} decision
                        {mergedDecisionsCount !== 1 ? "s" : ""}
                      </Text>
                    </View>
                  )}
                  {mergedRisksCount != null && mergedRisksCount > 0 && (
                    <View
                      style={{
                        backgroundColor: c.error + "14",
                        borderRadius: 4,
                        paddingHorizontal: 6,
                        paddingVertical: 2,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 10,
                          color: c.error,
                          fontWeight: "500",
                        }}
                      >
                        ⚠️ {mergedRisksCount} risk
                        {mergedRisksCount !== 1 ? "s" : ""}
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            )}

            {/* Deliverables toggle */}
            {deliverables && Object.keys(deliverables).length > 0 && (
              <View>
                <Pressable
                  onPress={() => setShowDeliverables(!showDeliverables)}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <Text style={{ fontSize: 12 }}>📄</Text>
                  <Text
                    style={{
                      fontSize: 11,
                      fontWeight: "600",
                      color: c.primary,
                    }}
                  >
                    {showDeliverables ? "Hide" : "Show"} Deliverables (
                    {Object.keys(deliverables).length})
                  </Text>
                </Pressable>
                {showDeliverables && (
                  <View style={{ marginTop: 6, gap: 4 }}>
                    {Object.entries(deliverables).map(([key, value], idx) => (
                      <View
                        key={idx}
                        style={{
                          backgroundColor: "rgba(255,255,255,0.05)",
                          borderRadius: 6,
                          padding: 8,
                        }}
                      >
                        <Text
                          style={{
                            fontSize: 11,
                            fontWeight: "600",
                            color: c.text,
                          }}
                        >
                          {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </Text>
                        <Text
                          style={{
                            fontSize: 10,
                            color: c.textSecondary,
                            marginTop: 2,
                          }}
                          numberOfLines={3}
                        >
                          {typeof value === "string"
                            ? value
                            : JSON.stringify(value).slice(0, 200)}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            )}

            {/* Error */}
            {error && (
              <Text style={{ fontSize: 11, color: c.error }}>
                Error: {error}
              </Text>
            )}

            {/* Timestamps */}
            {startedAt && (
              <Text style={{ fontSize: 9, color: c.textMuted }}>
                Started: {startedAt}
              </Text>
            )}
            {completedAt && (
              <Text style={{ fontSize: 9, color: c.textMuted }}>
                Completed: {completedAt}
              </Text>
            )}
          </View>
        </ScrollView>
      )}
    </View>
  )
}
