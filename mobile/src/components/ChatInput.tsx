import React from "react"
import { View, Text, TextInput, Pressable, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"

interface ChatInputProps {
  loading: boolean
  input: string
  onInputChange: (val: string) => void
  onSend: () => void
  isRecording: boolean
  isTranscribing: boolean
  onToggleRecording: () => void
  onAttachFile: () => void
  model: string | null
}

export function ChatInput({
  loading,
  input,
  onInputChange,
  onSend,
  isRecording,
  isTranscribing,
  onToggleRecording,
  onAttachFile,
  model,
}: ChatInputProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  return (
    <View style={{
      flexDirection: "row",
      gap: 8,
      alignItems: "center",
      backgroundColor: c.cardBg,
      borderRadius: t.radii.lg,
      borderWidth: 1.5,
      borderColor: loading ? c.primary + "50" : c.border,
      padding: 4,
    }}>
      <TextInput
        value={input}
        onChangeText={onInputChange}
        placeholder={isTranscribing ? "Transcribing voice..." : `Message ${model || "AI"}...`}
        placeholderTextColor={c.textMuted}
        multiline
        editable={!loading && !isTranscribing}
        style={{
          flex: 1,
          paddingHorizontal: 10,
          paddingVertical: 8,
          fontSize: 14,
          color: c.text,
          maxHeight: 100,
          minHeight: 24,
        }}
      />
      <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
        {isTranscribing && (
          <Text style={{ fontSize: 10, color: c.primary }}>Transcribing...</Text>
        )}
        <Pressable
          onPress={onAttachFile}
          disabled={loading}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            alignItems: "center",
            justifyContent: "center",
            borderWidth: 1,
            borderColor: c.border,
          }}
        >
          <Text style={{ fontSize: 14, color: c.textMuted }}>📎</Text>
        </Pressable>
        <Pressable
          onPress={onToggleRecording}
          disabled={isTranscribing}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: isRecording ? "#EF4444" : c.primary,
            opacity: isTranscribing ? 0.5 : 1,
          }}
        >
          <Text style={{ color: "#FFFFFF", fontSize: 14 }}>
            {isRecording ? "⏹" : "🎙"}
          </Text>
        </Pressable>
        <Pressable
          onPress={onSend}
          disabled={loading || !input.trim()}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: loading || !input.trim() ? "transparent" : c.primary,
            opacity: loading || !input.trim() ? 0.3 : 1,
          }}
        >
          <Text style={{
            fontSize: 16,
            fontWeight: "700",
            color: loading || !input.trim() ? c.textMuted : "#FFFFFF",
          }}>
            ↑
          </Text>
        </Pressable>
      </View>
    </View>
  )
}
