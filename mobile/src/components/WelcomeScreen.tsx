import React from "react"
import { View, Text, Pressable } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"
import { AnimatedRobot } from "./AnimatedRobot"

interface PromptSuggestion {
  id: number
  title: string
  prompt_text: string
  icon: string
  category: string
}

interface WelcomeScreenProps {
  promptSuggestions: PromptSuggestion[]
  loadingPrompts: boolean
  onSend: (text: string) => void
}

const FALLBACK_PROMPTS = [
  { label: "⚡ ZETDC outage process", text: "Explain the ZETDC outage reporting and restoration process" },
  { label: "📋 Net metering policy", text: "What is ZETDC's net metering policy for solar installations?" },
  { label: "🇿🇼 Summarize in Shona", text: "Please summarize this in Shona: ZETDC power supply guidelines" },
  { label: "🏗️ Safety procedures", text: "What are the ZETDC electrical safety procedures for field workers?" },
]

export function WelcomeScreen({ promptSuggestions, loadingPrompts, onSend }: WelcomeScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  return (
    <View style={{
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 24,
      paddingBottom: 40,
    }}>
      {/* AI Avatar with animation */}
      <View style={{ marginBottom: 20 }}>
        <AnimatedRobot size={140} state="idle" showLabel />
      </View>

      <Text style={{ fontSize: 18, fontWeight: "700", color: c.text, marginBottom: 8 }}>
        Start a conversation
      </Text>
      <Text style={{
        fontSize: 13,
        color: c.textMuted,
        textAlign: "center",
        lineHeight: 20,
        marginBottom: 24,
        paddingHorizontal: 20,
      }}>
        Chat with the ZETDC AI assistant. Ask about policies, procedures, reports, or request responses in Shona — no document upload needed.
      </Text>

      {/* Prompt suggestions */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8 }}>
        {loadingPrompts ? (
          <Text style={{ fontSize: 13, color: c.textMuted }}>Loading suggestions...</Text>
        ) : promptSuggestions.length > 0 ? (
          promptSuggestions.map((q) => (
            <Pressable
              key={q.id}
              onPress={() => onSend(q.prompt_text)}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: 20,
                paddingHorizontal: 14,
                paddingVertical: 8,
                borderWidth: 1,
                borderColor: c.border,
              }}
            >
              <Text style={{ fontSize: 12, color: c.text, fontWeight: "500" }}>
                {q.icon} {q.title}
              </Text>
            </Pressable>
          ))
        ) : (
          FALLBACK_PROMPTS.map((q) => (
            <Pressable
              key={q.label}
              onPress={() => onSend(q.text)}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: 20,
                paddingHorizontal: 14,
                paddingVertical: 8,
                borderWidth: 1,
                borderColor: c.border,
              }}
            >
              <Text style={{ fontSize: 12, color: c.text, fontWeight: "500" }}>{q.label}</Text>
            </Pressable>
          ))
        )}
      </View>
    </View>
  )
}
