/**
 * MeetingSummaryCardMobile — Meeting analysis results card for mobile
 *
 * Mirrors the web frontend MeetingSummaryCard.tsx.
 * Displays decisions, actions, risks, participants, and follow-ups
 * extracted from meeting recordings/transcripts.
 */
import React, { useState } from "react"
import { View, Text, Pressable, ScrollView } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { MeetingAnalysis } from "../types/api"

interface MeetingSummaryCardMobileProps {
  analysis: MeetingAnalysis
  filename?: string
}

export function MeetingSummaryCardMobile({
  analysis,
  filename,
}: MeetingSummaryCardMobileProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const [activeTab, setActiveTab] = useState<string>("summary")

  const tabs = [
    { key: "summary", label: "Summary", icon: "📋" },
    { key: "decisions", label: "Decisions", icon: "✅", count: analysis.decisions?.length },
    { key: "actions", label: "Actions", icon: "🎯", count: analysis.action_items?.length },
    { key: "risks", label: "Risks", icon: "⚠️", count: analysis.risks?.length },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case "summary":
        return (
          <View style={{ gap: 10 }}>
            {/* Summary text */}
            <View
              style={{
                backgroundColor: "rgba(255,255,255,0.05)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <Text
                style={{
                  fontSize: 13,
                  color: c.text,
                  lineHeight: 20,
                }}
              >
                {analysis.summary}
              </Text>
            </View>

            {/* Participants */}
            {analysis.participants?.length > 0 && (
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
                  Participants
                </Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
                  {analysis.participants.map((p, i) => (
                    <View
                      key={i}
                      style={{
                        backgroundColor: c.primary + "14",
                        borderRadius: 4,
                        paddingHorizontal: 8,
                        paddingVertical: 3,
                      }}
                    >
                      <Text
                        style={{ fontSize: 11, color: c.primary, fontWeight: "500" }}
                      >
                        👤 {p}
                      </Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {/* Topics */}
            {analysis.topics?.length > 0 && (
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
                  Topics Discussed
                </Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
                  {analysis.topics.map((topic, i) => (
                    <View
                      key={i}
                      style={{
                        backgroundColor: c.warning + "14",
                        borderRadius: 4,
                        paddingHorizontal: 8,
                        paddingVertical: 3,
                      }}
                    >
                      <Text
                        style={{ fontSize: 11, color: c.warning, fontWeight: "500" }}
                      >
                        {topic}
                      </Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {/* Systems mentioned */}
            {analysis.systems_mentioned?.length > 0 && (
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
                  Systems Mentioned
                </Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
                  {analysis.systems_mentioned.map((sys, i) => (
                    <View
                      key={i}
                      style={{
                        backgroundColor: c.success + "14",
                        borderRadius: 4,
                        paddingHorizontal: 8,
                        paddingVertical: 3,
                      }}
                    >
                      <Text
                        style={{ fontSize: 11, color: c.success, fontWeight: "500" }}
                      >
                        💻 {sys}
                      </Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
          </View>
        )

      case "decisions":
        return (
          <View style={{ gap: 6 }}>
            {analysis.decisions?.length === 0 ? (
              <Text style={{ color: c.textMuted, fontSize: 12, fontStyle: "italic" }}>
                No decisions recorded.
              </Text>
            ) : (
              analysis.decisions?.map((d, i) => (
                <View
                  key={i}
                  style={{
                    backgroundColor: "rgba(255,255,255,0.05)",
                    borderRadius: 8,
                    padding: 10,
                    borderLeftWidth: 3,
                    borderLeftColor: c.success,
                  }}
                >
                  <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                    {d.decision}
                  </Text>
                  {d.made_by && (
                    <Text
                      style={{
                        fontSize: 10,
                        color: c.textMuted,
                        marginTop: 4,
                      }}
                    >
                      Made by: {d.made_by}
                    </Text>
                  )}
                </View>
              ))
            )}
          </View>
        )

      case "actions":
        return (
          <View style={{ gap: 6 }}>
            {analysis.action_items?.length === 0 ? (
              <Text style={{ color: c.textMuted, fontSize: 12, fontStyle: "italic" }}>
                No action items identified.
              </Text>
            ) : (
              analysis.action_items?.map((a, i) => (
                <View
                  key={i}
                  style={{
                    backgroundColor: "rgba(255,255,255,0.05)",
                    borderRadius: 8,
                    padding: 10,
                    borderLeftWidth: 3,
                    borderLeftColor: c.warning,
                  }}
                >
                  <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                    {a.action}
                  </Text>
                  <View
                    style={{
                      flexDirection: "row",
                      flexWrap: "wrap",
                      gap: 6,
                      marginTop: 4,
                    }}
                  >
                    {a.owner && (
                      <Text style={{ fontSize: 10, color: c.primary }}>
                        👤 Owner: {a.owner}
                      </Text>
                    )}
                    {a.priority && (
                      <Text style={{ fontSize: 10, color: c.warning }}>
                        🔥 {a.priority}
                      </Text>
                    )}
                    {a.due_date && (
                      <Text style={{ fontSize: 10, color: c.textMuted }}>
                        📅 {a.due_date}
                      </Text>
                    )}
                  </View>
                </View>
              ))
            )}
          </View>
        )

      case "risks":
        return (
          <View style={{ gap: 6 }}>
            {analysis.risks?.length === 0 ? (
              <Text style={{ color: c.textMuted, fontSize: 12, fontStyle: "italic" }}>
                No risks identified.
              </Text>
            ) : (
              analysis.risks?.map((r, i) => (
                <View
                  key={i}
                  style={{
                    backgroundColor: "rgba(255,255,255,0.05)",
                    borderRadius: 8,
                    padding: 10,
                    borderLeftWidth: 3,
                    borderLeftColor: c.error,
                  }}
                >
                  <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                    {r.risk}
                  </Text>
                  {r.severity && (
                    <View
                      style={{
                        marginTop: 4,
                        alignSelf: "flex-start",
                        backgroundColor:
                          r.severity === "high" || r.severity === "critical"
                            ? c.error + "18"
                            : r.severity === "medium"
                            ? c.warning + "18"
                            : c.success + "18",
                        borderRadius: 4,
                        paddingHorizontal: 6,
                        paddingVertical: 2,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 9,
                          fontWeight: "600",
                          color:
                            r.severity === "high" || r.severity === "critical"
                              ? c.error
                              : r.severity === "medium"
                              ? c.warning
                              : c.success,
                        }}
                      >
                        {r.severity.toUpperCase()}
                      </Text>
                    </View>
                  )}
                </View>
              ))
            )}
          </View>
        )

      default:
        return null
    }
  }

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
      <View
        style={{
          paddingHorizontal: 12,
          paddingVertical: 10,
          backgroundColor: c.success + "10",
          borderBottomWidth: 1,
          borderBottomColor: c.border,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Text style={{ fontSize: 16 }}>📊</Text>
          <View style={{ flex: 1 }}>
            <Text
              style={{
                fontSize: 12,
                fontWeight: "700",
                color: c.success,
                textTransform: "uppercase",
              }}
            >
              Meeting Analysis
            </Text>
            {filename && (
              <Text
                style={{
                  fontSize: 12,
                  color: c.textSecondary,
                  marginTop: 2,
                }}
                numberOfLines={1}
              >
                {filename}
              </Text>
            )}
          </View>
        </View>
      </View>

      {/* Tab bar */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={{ borderBottomWidth: 1, borderBottomColor: c.border }}
      >
        <View style={{ flexDirection: "row", paddingHorizontal: 8 }}>
          {tabs.map((tab) => (
            <Pressable
              key={tab.key}
              onPress={() => setActiveTab(tab.key)}
              style={{
                paddingHorizontal: 12,
                paddingVertical: 8,
                borderBottomWidth: 2,
                borderBottomColor:
                  activeTab === tab.key ? c.primary : "transparent",
                flexDirection: "row",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Text style={{ fontSize: 11 }}>{tab.icon}</Text>
              <Text
                style={{
                  fontSize: 11,
                  fontWeight: activeTab === tab.key ? "600" : "400",
                  color: activeTab === tab.key ? c.primary : c.textMuted,
                }}
              >
                {tab.label}
              </Text>
              {tab.count != null && tab.count > 0 && (
                <View
                  style={{
                    backgroundColor: c.primary + "18",
                    borderRadius: 8,
                    paddingHorizontal: 5,
                    paddingVertical: 1,
                  }}
                >
                  <Text style={{ fontSize: 9, color: c.primary, fontWeight: "600" }}>
                    {tab.count}
                  </Text>
                </View>
              )}
            </Pressable>
          ))}
        </View>
      </ScrollView>

      {/* Tab content */}
      <ScrollView
        style={{ maxHeight: 300, padding: 12 }}
        showsVerticalScrollIndicator={true}
      >
        {renderTabContent()}
      </ScrollView>
    </View>
  )
}
