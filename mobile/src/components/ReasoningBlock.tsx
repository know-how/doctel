import React, { useState } from "react"
import { View, Text, Pressable } from "react-native"

interface ReasoningColors {
  textMuted: string
  border: string
  surfaceActive: string
  primary: string
  textSecondary: string
}

interface ReasoningBlockProps {
  reasoning: string
  colors: ReasoningColors
}

/**
 * Collapsible reasoning/thinking block that mimics the web frontend's
 * <details>/<summary> pattern. Hidden by default — tap "💭 Show reasoning"
 * to expand with a styled container (border-left accent, italic text).
 */
export function ReasoningBlock({ reasoning, colors }: ReasoningBlockProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <View style={{ marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
      <Pressable
        onPress={() => setExpanded((p) => !p)}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 6,
        }}
      >
        <Text style={{ fontSize: 11, fontWeight: "600", color: colors.textMuted, letterSpacing: 0.3 }}>
          💭 Show reasoning
        </Text>
        <Text style={{ fontSize: 9, color: colors.textMuted, transform: [{ rotate: expanded ? "90deg" : "0deg" }] }}>
          ▶
        </Text>
      </Pressable>
      {expanded && (
        <View style={{
          marginTop: 8,
          padding: 12,
          backgroundColor: colors.surfaceActive,
          borderRadius: 8,
          borderLeftWidth: 3,
          borderLeftColor: colors.primary + "40",
        }}>
          <Text style={{
            fontSize: 12,
            color: colors.textSecondary,
            fontStyle: "italic",
            lineHeight: 18,
          }}>
            {reasoning}
          </Text>
        </View>
      )}
    </View>
  )
}
