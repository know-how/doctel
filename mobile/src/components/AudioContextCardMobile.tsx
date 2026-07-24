/**
 * AudioContextCardMobile — Persistent recording context banner for mobile
 *
 * Shows when a recording is attached to the active session.
 * Mirrors the web frontend AudioContextCard.tsx.
 */
import React, { useState } from "react"
import { View, Text, Pressable, ScrollView } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { AudioContextData } from "../types/api"

interface AudioContextCardMobileProps {
  audioContext: AudioContextData
  onRemove?: () => void
  onAnalyzeMeeting?: () => void
  onAddToKnowledgeBase?: () => void
}

function formatDuration(sec?: number | null): string {
  if (sec == null) return "Unknown duration"
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  if (m === 0) return `${s}s`
  return `${m}m ${s}s`
}

export function AudioContextCardMobile({
  audioContext,
  onRemove,
  onAnalyzeMeeting,
  onAddToKnowledgeBase,
}: AudioContextCardMobileProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const [expanded, setExpanded] = useState(false)
  const { filename, transcript, summary, durationSec, entities } = audioContext

  return (
    <View
      style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: c.primary + "40",
        marginHorizontal: 12,
        marginBottom: 8,
        overflow: "hidden",
      }}
    >
      {/* ── Header ── */}
      <Pressable
        onPress={() => setExpanded(!expanded)}
        style={{
          flexDirection: "row",
          alignItems: "center",
          paddingHorizontal: 12,
          paddingVertical: 10,
          backgroundColor: c.primary + "10",
        }}
      >
        <Text style={{ fontSize: 18, marginRight: 8 }}>🎙</Text>
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
            Active Recording Context
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
            {filename}
          </Text>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 2 }}>
            <Text style={{ fontSize: 10, color: c.textMuted }}>
              {formatDuration(durationSec)}
            </Text>
            <Text style={{ fontSize: 10, color: c.primary }}>
              Transcript Loaded
            </Text>
          </View>
        </View>
        <Text style={{ fontSize: 10, color: c.textMuted }}>
          {expanded ? "▲" : "▼"}
        </Text>
      </Pressable>

      {/* ── Expanded content ── */}
      {expanded && (
        <View style={{ padding: 12 }}>
          {/* Summary */}
          {summary && (
            <View style={{ marginBottom: 8 }}>
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
                numberOfLines={4}
              >
                {summary}
              </Text>
            </View>
          )}

          {/* Transcript preview */}
          {transcript && (
            <View style={{ marginBottom: 8 }}>
              <Text
                style={{
                  fontSize: 10,
                  fontWeight: "600",
                  color: c.textMuted,
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}
              >
                Transcript
              </Text>
              <Text
                style={{
                  fontSize: 11,
                  color: c.textSecondary,
                  lineHeight: 16,
                }}
                numberOfLines={6}
              >
                {transcript}
              </Text>
            </View>
          )}

          {/* Entity chips */}
          {entities && entities.length > 0 && (
            <View style={{ marginBottom: 8 }}>
              <Text
                style={{
                  fontSize: 10,
                  fontWeight: "600",
                  color: c.textMuted,
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}
              >
                Entities
              </Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                style={{ flexDirection: "row" }}
              >
                <View style={{ flexDirection: "row", gap: 4 }}>
                  {entities.map((entity, i) => (
                    <View
                      key={i}
                      style={{
                        backgroundColor: c.primary + "18",
                        borderRadius: 4,
                        paddingHorizontal: 8,
                        paddingVertical: 3,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 10,
                          fontWeight: "500",
                          color: c.primary,
                        }}
                      >
                        {entity}
                      </Text>
                    </View>
                  ))}
                </View>
              </ScrollView>
            </View>
          )}

          {/* Action buttons */}
          <View style={{ flexDirection: "row", gap: 6, marginTop: 4 }}>
            {onRemove && (
              <Pressable
                onPress={onRemove}
                style={{
                  backgroundColor: c.error + "14",
                  borderRadius: 6,
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderWidth: 1,
                  borderColor: c.error + "28",
                }}
              >
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: "600",
                    color: c.error,
                  }}
                >
                  ✕ Remove
                </Text>
              </Pressable>
            )}
            {onAnalyzeMeeting && (
              <Pressable
                onPress={onAnalyzeMeeting}
                style={{
                  backgroundColor: c.warning + "14",
                  borderRadius: 6,
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderWidth: 1,
                  borderColor: c.warning + "28",
                }}
              >
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: "600",
                    color: c.warning,
                  }}
                >
                  📊 Analyze Meeting
                </Text>
              </Pressable>
            )}
            {onAddToKnowledgeBase && (
              <Pressable
                onPress={onAddToKnowledgeBase}
                style={{
                  backgroundColor: c.success + "14",
                  borderRadius: 6,
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderWidth: 1,
                  borderColor: c.success + "28",
                }}
              >
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: "600",
                    color: c.success,
                  }}
                >
                  📚 Add to KB
                </Text>
              </Pressable>
            )}
          </View>
        </View>
      )}
    </View>
  )
}
