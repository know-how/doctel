import React from "react"
import { View, Text } from "react-native"
import { ModelDropdown } from "./ModelDropdown"
import type { V2Provider } from "../types/api"

const CAP_ICON: Record<string, string> = {
  reasoning: "🧠",
  vision: "👁️",
  audio: "🎤",
  code: "💻",
  fast: "⚡",
  large: "🐘",
  embedding: "📊",
}

interface ChatHeaderProps {
  model: string | null
  modelLabels: Record<string, string>
  modelCapabilities: Record<string, string[]>
  messagesLength: number
  onModelChange: (modelId: string) => void
  availableModels: string[]
  v2Providers: V2Provider[]
  loadingModels: boolean
}

export function ChatHeader({
  model,
  modelLabels,
  modelCapabilities,
  messagesLength,
  onModelChange,
  availableModels,
  v2Providers,
  loadingModels,
}: ChatHeaderProps) {
  return (
    <View style={{
      paddingHorizontal: 16,
      paddingVertical: 12,
      borderBottomWidth: 1,
      borderBottomColor: "rgba(255,255,255,0.08)",
      backgroundColor: "#0F1117",
    }}>
      <View style={{ gap: 8 }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <Text style={{ fontSize: 20, fontWeight: "700", color: "#FFFFFF", letterSpacing: -0.3 }}>
            New Chat
          </Text>
          <Text style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>{messagesLength} messages</Text>
        </View>

        {/* Model dropdown - provider grouped */}
        <ModelDropdown
          v2Providers={v2Providers}
          availableModels={availableModels}
          selectedModel={model}
          modelCapabilities={modelCapabilities}
          modelLabels={modelLabels}
          loading={loadingModels}
          onSelect={onModelChange}
        />

        {/* Capability badges */}
        {model && modelCapabilities[model] && modelCapabilities[model].length > 0 && (
          <View style={{ flexDirection: "row", gap: 4, flexWrap: "wrap" }}>
            {modelCapabilities[model].slice(0, 4).map((cap) => (
              <View key={cap} style={{
                backgroundColor: "rgba(255,255,255,0.05)",
                borderRadius: 6,
                paddingHorizontal: 6,
                paddingVertical: 2,
                borderWidth: 1,
                borderColor: "rgba(255,255,255,0.08)",
                flexDirection: "row",
                alignItems: "center",
                gap: 3,
              }}>
                <Text style={{ fontSize: 9 }}>{CAP_ICON[cap] || "📄"}</Text>
                <Text style={{ fontSize: 9, color: "rgba(255,255,255,0.6)", textTransform: "capitalize" }}>{cap}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </View>
  )
}
