/**
 * AgentExecutionCardMobile — Agent execution results card for mobile
 *
 * Mirrors the web frontend AgentExecutionCard.tsx.
 * Shows agent plan, execution status, duration, findings,
 * and collapsed agent results.
 */
import React, { useState } from "react"
import { View, Text, Pressable, ScrollView } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { AgentResult } from "../types/api"

interface AgentExecutionCardMobileProps {
  agentsExecuted: number
  agentResults?: AgentResult[]
  executionSummary?: string
  mergedEntities?: string[]
  mergedActions?: any[]
  mergedDecisions?: any[]
  mergedRisks?: any[]
  totalDurationMs?: number
}

/** Agent icon mapping */
const AGENT_ICONS: Record<string, string> = {
  retrieval_agent: "🔍",
  graph_agent: "🕸️",
  asset_agent: "📚",
  media_agent: "🎬",
  meeting_agent: "📋",
  workflow_agent: "⚙️",
  risk_agent: "⚠️",
  reporting_agent: "📊",
  policy_agent: "📜",
  entity_agent: "🏷️",
}

function getAgentIcon(type: string): string {
  return AGENT_ICONS[type.toLowerCase()] || "🤖"
}

export function AgentExecutionCardMobile({
  agentsExecuted,
  agentResults,
  executionSummary,
  mergedEntities,
  mergedActions,
  mergedDecisions,
  mergedRisks,
  totalDurationMs,
}: AgentExecutionCardMobileProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const [expanded, setExpanded] = useState(false)
  const [expandedResults, setExpandedResults] = useState<Set<number>>(new Set())

  const toggleResult = (idx: number) => {
    setExpandedResults((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const hasFindings =
    (mergedEntities && mergedEntities.length > 0) ||
    (mergedActions && mergedActions.length > 0) ||
    (mergedDecisions && mergedDecisions.length > 0) ||
    (mergedRisks && mergedRisks.length > 0)

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
        <Text style={{ fontSize: 16, marginRight: 8 }}>🤖</Text>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontSize: 11,
              fontWeight: "700",
              color: c.primary,
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            Agent Execution
          </Text>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 2 }}>
            <Text style={{ fontSize: 11, color: c.textSecondary }}>
              {agentsExecuted} agent{agentsExecuted !== 1 ? "s" : ""}
            </Text>
            {totalDurationMs != null && (
              <Text style={{ fontSize: 11, color: c.textMuted }}>
                {(totalDurationMs / 1000).toFixed(1)}s
              </Text>
            )}
            {hasFindings && (
              <Text style={{ fontSize: 11, color: c.success }}>
                ✓ Findings
              </Text>
            )}
          </View>
        </View>
        <Text style={{ fontSize: 10, color: c.textMuted }}>
          {expanded ? "▲" : "▼"}
        </Text>
      </Pressable>

      {/* Expanded content */}
      {expanded && (
        <ScrollView style={{ maxHeight: 400 }} showsVerticalScrollIndicator>
          <View style={{ padding: 12, gap: 8 }}>
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

            {/* Agent results */}
            {agentResults && agentResults.length > 0 && (
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
                  Agent Results
                </Text>
                {agentResults.map((ar, idx) => (
                  <Pressable
                    key={idx}
                    onPress={() => toggleResult(idx)}
                    style={{
                      backgroundColor: "rgba(255,255,255,0.03)",
                      borderRadius: 8,
                      padding: 10,
                      marginBottom: 4,
                      borderWidth: 1,
                      borderColor:
                        ar.status === "failed"
                          ? c.error + "28"
                          : c.border,
                    }}
                  >
                    <View
                      style={{
                        flexDirection: "row",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Text style={{ fontSize: 14 }}>
                        {getAgentIcon(ar.agent_type)}
                      </Text>
                      <View style={{ flex: 1 }}>
                        <Text
                          style={{
                            fontSize: 12,
                            fontWeight: "600",
                            color: c.text,
                          }}
                        >
                          {ar.agent_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </Text>
                        <View
                          style={{
                            flexDirection: "row",
                            gap: 8,
                            marginTop: 2,
                          }}
                        >
                          <Text style={{ fontSize: 10, color: c.textMuted }}>
                            {ar.duration_ms != null
                              ? `${(ar.duration_ms / 1000).toFixed(1)}s`
                              : ""}
                          </Text>
                          {ar.status === "completed" && (
                            <Text style={{ fontSize: 10, color: c.success }}>
                              ✓ Completed
                            </Text>
                          )}
                          {ar.status === "failed" && (
                            <Text style={{ fontSize: 10, color: c.error }}>
                              ✕ Failed
                            </Text>
                          )}
                        </View>
                      </View>
                      <Text style={{ fontSize: 10, color: c.textMuted }}>
                        {expandedResults.has(idx) ? "▲" : "▼"}
                      </Text>
                    </View>

                    {expandedResults.has(idx) && (
                      <View style={{ marginTop: 8, gap: 4 }}>
                        {ar.summary && (
                          <Text
                            style={{
                              fontSize: 11,
                              color: c.textSecondary,
                              lineHeight: 16,
                            }}
                          >
                            {ar.summary}
                          </Text>
                        )}
                        {ar.key_findings &&
                          ar.key_findings.length > 0 && (
                            <View style={{ gap: 2 }}>
                              <Text
                                style={{
                                  fontSize: 10,
                                  fontWeight: "600",
                                  color: c.textMuted,
                                }}
                              >
                                Key Findings:
                              </Text>
                              {ar.key_findings.map((kf, j) => (
                                <Text
                                  key={j}
                                  style={{
                                    fontSize: 10,
                                    color: c.textSecondary,
                                    paddingLeft: 8,
                                  }}
                                >
                                  • {kf}
                                </Text>
                              ))}
                            </View>
                          )}
                        {ar.error && (
                          <Text
                            style={{
                              fontSize: 10,
                              color: c.error,
                            }}
                          >
                            Error: {ar.error}
                          </Text>
                        )}
                      </View>
                    )}
                  </Pressable>
                ))}
              </View>
            )}

            {/* Findings summary */}
            {hasFindings && (
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
                  {mergedEntities &&
                    mergedEntities.map((e, i) => (
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
                          style={{ fontSize: 10, color: c.primary, fontWeight: "500" }}
                        >
                          🏷️ {e}
                        </Text>
                      </View>
                    ))}
                  {mergedActions &&
                    mergedActions.length > 0 && (
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
                          🎯 {mergedActions.length} action
                          {mergedActions.length !== 1 ? "s" : ""}
                        </Text>
                      </View>
                    )}
                  {mergedDecisions &&
                    mergedDecisions.length > 0 && (
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
                          ✅ {mergedDecisions.length} decision
                          {mergedDecisions.length !== 1 ? "s" : ""}
                        </Text>
                      </View>
                    )}
                  {mergedRisks &&
                    mergedRisks.length > 0 && (
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
                          ⚠️ {mergedRisks.length} risk
                          {mergedRisks.length !== 1 ? "s" : ""}
                        </Text>
                      </View>
                    )}
                </View>
              </View>
            )}
          </View>
        </ScrollView>
      )}
    </View>
  )
}
