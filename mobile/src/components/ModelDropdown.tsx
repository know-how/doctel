import React, { useState, useMemo } from "react"
import { View, Text, Pressable, ScrollView, Modal, TouchableOpacity, TextInput } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { V2Provider, V2ModelMetadata } from "../types/api"

// ═══════════════════════════════════════════════════════════════════
// Provider icon / label mapping (mirrors frontend CAPABILITY_CONFIG)
// ═══════════════════════════════════════════════════════════════════
const PROVIDER_ICONS: Record<string, string> = {
  openai: "🟢",
  anthropic: "🟣",
  google: "🔵",
  gemini: "🔵",
  deepseek: "🔷",
  opencode: "🟠",
  opencode_go: "🟠",
  opencode_zen: "🟠",
  huggingface: "🟡",
  azure: "🔷",
  ollama: "⚙️",
  local: "⚙️",
}

const CAP_CONFIG: Record<string, { label: string; icon: string; color: string; bgColor: string }> = {
  chat: { label: "TEXT", icon: "📄", color: "#4F7CFF", bgColor: "rgba(79,124,255,0.15)" },
  text: { label: "TEXT", icon: "📄", color: "#4F7CFF", bgColor: "rgba(79,124,255,0.15)" },
  vision: { label: "VISION", icon: "🖼", color: "#A855F7", bgColor: "rgba(168,85,247,0.15)" },
  image: { label: "VISION", icon: "🖼", color: "#A855F7", bgColor: "rgba(168,85,247,0.15)" },
  audio: { label: "AUDIO", icon: "🎤", color: "#14B8A6", bgColor: "rgba(20,184,166,0.15)" },
  code: { label: "CODE", icon: "💻", color: "#22C55E", bgColor: "rgba(34,197,94,0.15)" },
  reasoning: { label: "REASONING", icon: "🧠", color: "#EAB308", bgColor: "rgba(234,179,8,0.15)" },
  embedding: { label: "EMBEDDING", icon: "📌", color: "#6B7280", bgColor: "rgba(107,114,128,0.15)" },
  fast: { label: "FAST", icon: "⚡", color: "#F97316", bgColor: "rgba(249,115,22,0.15)" },
  large: { label: "LARGE", icon: "🐘", color: "#EC4899", bgColor: "rgba(236,72,153,0.15)" },
  tools: { label: "TOOLS", icon: "🔧", color: "#6366F1", bgColor: "rgba(99,102,241,0.15)" },
}

function getProviderIcon(vendor?: string): string {
  if (!vendor) return "🤖"
  return PROVIDER_ICONS[vendor.toLowerCase()] || "🤖"
}

function getCapDisplay(cap: string) {
  return CAP_CONFIG[cap.toLowerCase()] || { label: cap.toUpperCase(), icon: "🔧", color: "#9CA3AF", bgColor: "rgba(156,163,175,0.15)" }
}

// ═══════════════════════════════════════════════════════════════════
// Props
// ═══════════════════════════════════════════════════════════════════
interface ModelDropdownProps {
  v2Providers: V2Provider[]
  availableModels: string[]
  selectedModel: string | null
  modelCapabilities: Record<string, string[]>
  modelLabels: Record<string, string>
  loading: boolean
  onSelect: (modelId: string) => void
}

// ═══════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════
export function ModelDropdown({
  v2Providers,
  availableModels,
  selectedModel,
  modelCapabilities,
  modelLabels,
  loading,
  onSelect,
}: ModelDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set())
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  // ── Group models by provider ─────────────────────────────────
  const { groupedProviders, selectedInfo } = useMemo(() => {
    const groups: { provider: V2Provider; models: V2ModelMetadata[]; isExpanded: boolean }[] = []
    const v2ModelIdSet = new Set<string>()

    // Process V2 providers
    for (const provider of v2Providers) {
      if (provider.status === "disabled") continue

      let models = (provider.models || []).filter(m =>
        ["active", "installed", "available", "maintenance"].includes(m.state)
      )
      if (models.length === 0) continue

      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        models = models.filter(m =>
          m.id.toLowerCase().includes(q) ||
          m.name.toLowerCase().includes(q) ||
          provider.name.toLowerCase().includes(q) ||
          provider.vendor?.toLowerCase().includes(q)
        )
        if (models.length === 0) continue
      }

      for (const m of models) v2ModelIdSet.add(m.id)

      const isExpanded = searchQuery.trim() ? true : expandedProviders.has(provider.id)
      groups.push({ provider, models, isExpanded })
    }

    // Add non-V2 models (local-only). If a V2 provider with id="ollama" already
    // exists, merge into it to avoid duplicate keys; otherwise create a synthetic group.
    const nonV2Models = availableModels.filter(id => !v2ModelIdSet.has(id))
    if (nonV2Models.length > 0) {
      let filtered = nonV2Models
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        filtered = nonV2Models.filter(m => m.toLowerCase().includes(q))
      }
      if (filtered.length > 0) {
        // Check if a V2 Ollama provider already exists
        const existingOllamaGroup = groups.find(g => g.provider.id === "ollama" || g.provider.vendor === "ollama")
        if (existingOllamaGroup) {
          // Merge non-V2 models into the existing V2 Ollama group
          for (const mid of filtered) {
            if (!existingOllamaGroup.models.some(m => m.id === mid)) {
              existingOllamaGroup.models.push({
                id: mid,
                name: (modelLabels[mid] || mid).replace(/[-_:]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
                contextWindow: 4096,
                supportsChat: true,
                supportsVision: false,
                supportsTools: false,
                supportsCode: false,
                supportsEmbedding: false,
                supportsReasoning: false,
                supportsRag: false,
                supportsClassification: false,
                supportsSummary: false,
                supportsExtraction: false,
                enabled: true,
                visibleToUsers: true,
                isDefault: false,
                allowedRoles: [],
                departmentRestrictions: [],
                state: "active",
                pricingTier: "local",
                license: "Open Source",
                capabilities: modelCapabilities[mid] || ["chat"],
              })
            }
          }
        } else {
          // No V2 Ollama provider — create a synthetic group
          const localProvider: V2Provider = {
            id: "ollama",
            name: "Ollama",
            vendor: "ollama",
            base_url: "",
            api_key_value: "",
            status: "active",
            description: "Local models",
            icon: "cpu",
            order: 999,
            models: filtered.map(id => ({
              id,
              name: (modelLabels[id] || id).replace(/[-_:]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
              contextWindow: 4096,
              supportsChat: true,
              supportsVision: false,
              supportsTools: false,
              supportsCode: false,
              supportsEmbedding: false,
              supportsReasoning: false,
              supportsRag: false,
              supportsClassification: false,
              supportsSummary: false,
              supportsExtraction: false,
              enabled: true,
              visibleToUsers: true,
              isDefault: false,
              allowedRoles: [],
              departmentRestrictions: [],
              state: "active",
              pricingTier: "local",
              license: "Open Source",
              capabilities: modelCapabilities[id] || ["chat"],
            })),
          }
          const isExpanded = searchQuery.trim() ? true : expandedProviders.has("ollama")
          groups.push({ provider: localProvider, models: localProvider.models, isExpanded })
        }
      }
    }

    // Sort providers by order
    groups.sort((a, b) => (a.provider.order || 0) - (b.provider.order || 0))

    // Find selected
    let selectedInfo: { model: V2ModelMetadata; provider: V2Provider } | null = null
    for (const g of groups) {
      const m = g.models.find(m => m.id === selectedModel)
      if (m) { selectedInfo = { model: m, provider: g.provider }; break }
    }

    return { groupedProviders: groups, selectedInfo }
  }, [v2Providers, availableModels, selectedModel, modelLabels, modelCapabilities, searchQuery, expandedProviders])

  const totalModels = groupedProviders.reduce((s, g) => s + g.models.length, 0)
  const selectedName = selectedModel ? (modelLabels[selectedModel] || selectedModel) : null

  // ── Render trigger ────────────────────────────────────────────
  const renderTrigger = () => (
    <Pressable
      onPress={() => !loading && setIsOpen(true)}
      disabled={loading}
      style={{
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: "#1B2238",
        borderRadius: 10,
        borderWidth: 1,
        borderColor: isOpen ? "#4F7CFF" : "rgba(255,255,255,0.08)",
        padding: 10,
        minHeight: 44,
        opacity: loading ? 0.5 : 1,
      }}
    >
      {loading ? (
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: "#9CA3AF" }}>Loading models...</Text>
        </View>
      ) : selectedInfo ? (
        <>
          {/* Provider icon badge */}
          <View style={{
            width: 32, height: 32, borderRadius: 8,
            backgroundColor: "#131A2E",
            alignItems: "center", justifyContent: "center",
            marginRight: 10,
          }}>
            <Text style={{ fontSize: 14 }}>{getProviderIcon(selectedInfo.provider.vendor)}</Text>
          </View>
          {/* Model name + provider */}
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13, fontWeight: "600", color: "#FFFFFF" }} numberOfLines={1}>
              {selectedInfo.model.name}
            </Text>
            <Text style={{ fontSize: 11, color: "#9CA3AF", marginTop: 1 }}>
              {selectedInfo.provider.name}
              {(selectedInfo.model.capabilities || []).length > 0 && (
                ` • ${selectedInfo.model.capabilities!.slice(0, 2).join(" • ")}`
              )}
            </Text>
          </View>
          {/* State badge for non-active */}
          {!["active", "installed", "available"].includes(selectedInfo.model.state) && (
            <View style={{
              backgroundColor: "rgba(234,179,8,0.15)",
              borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, marginRight: 6,
            }}>
              <Text style={{ fontSize: 9, fontWeight: "600", color: "#EAB308" }}>
                {selectedInfo.model.state.toUpperCase()}
              </Text>
            </View>
          )}
        </>
      ) : (
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, color: "#9CA3AF" }}>Select a model...</Text>
        </View>
      )}
      {/* Chevron */}
      <Text style={{ fontSize: 10, color: "#9CA3AF", marginLeft: 6 }}>
        {isOpen ? "▲" : "▼"}
      </Text>
    </Pressable>
  )

  // ── Render: Provider section ──────────────────────────────────
  const renderProviderSection = (
    group: { provider: V2Provider; models: V2ModelMetadata[]; isExpanded: boolean }
  ) => {
    const isExpanded = group.isExpanded

    return (
      <View key={group.provider.id} style={{ marginBottom: 6 }}>
        {/* Provider header */}
        <Pressable
          onPress={() => {
            setExpandedProviders(prev => {
              const next = new Set(prev)
              if (next.has(group.provider.id)) next.delete(group.provider.id)
              else next.add(group.provider.id)
              return next
            })
          }}
          style={{
            flexDirection: "row",
            alignItems: "center",
            paddingVertical: 10,
            paddingHorizontal: 14,
            backgroundColor: "#1B2238",
          }}
        >
          <Text style={{ fontSize: 10, color: "#9CA3AF", marginRight: 8, transform: isExpanded ? [] : [{ rotate: "-90deg" }] }}>
            ▼
          </Text>
          <Text style={{ fontSize: 14, marginRight: 8 }}>{getProviderIcon(group.provider.vendor)}</Text>
          <Text style={{ fontSize: 11, fontWeight: "700", color: "#FFFFFF", textTransform: "uppercase", letterSpacing: 0.5, flex: 1 }}>
            {group.provider.name}
          </Text>
          <View style={{
            backgroundColor: "#131A2E",
            borderRadius: 12,
            paddingHorizontal: 8,
            paddingVertical: 2,
          }}>
            <Text style={{ fontSize: 10, color: "#9CA3AF" }}>{group.models.length}</Text>
          </View>
        </Pressable>

        {/* Models */}
        {isExpanded && group.models.map((model) => {
          const isSelected = selectedModel === model.id
          const isProviderOffline = group.provider.status === "disconnected" || group.provider.status === "error"
          const caps = model.capabilities || []

          return (
            <Pressable
              key={model.id}
              onPress={() => { onSelect(model.id); setIsOpen(false); setSearchQuery("") }}
              style={{
                flexDirection: "row",
                alignItems: "flex-start",
                paddingVertical: 10,
                paddingHorizontal: 14,
                backgroundColor: isSelected ? "rgba(79,124,255,0.15)" : "transparent",
                borderLeftWidth: 3,
                borderLeftColor: isSelected ? "#4F7CFF" : "transparent",
                opacity: isProviderOffline ? 0.5 : 1,
              }}
            >
              {/* Radio / check */}
              <View style={{ width: 18, flexShrink: 0, paddingTop: 2 }}>
                {isSelected && (
                  <Text style={{ fontSize: 14, color: "#4F7CFF", fontWeight: "700" }}>✓</Text>
                )}
              </View>

              {/* Model info */}
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Text style={{ fontSize: 13, fontWeight: isSelected ? "600" : "400", color: "#FFFFFF" }}>
                    {model.name}
                  </Text>
                  {/* Status badges */}
                  {isProviderOffline ? (
                    <View style={{ backgroundColor: "rgba(239,68,68,0.15)", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 1 }}>
                      <Text style={{ fontSize: 8, fontWeight: "600", color: "#EF4444" }}>OFFLINE</Text>
                    </View>
                  ) : model.state === "maintenance" ? (
                    <View style={{ backgroundColor: "rgba(234,179,8,0.15)", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 1 }}>
                      <Text style={{ fontSize: 8, fontWeight: "600", color: "#EAB308" }}>MAINT</Text>
                    </View>
                  ) : model.state === "installed" ? (
                    <View style={{ backgroundColor: "rgba(34,197,94,0.15)", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 1 }}>
                      <Text style={{ fontSize: 8, fontWeight: "600", color: "#22C55E" }}>INSTALLED</Text>
                    </View>
                  ) : model.state === "available" ? (
                    <View style={{ backgroundColor: "rgba(79,124,255,0.15)", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 1 }}>
                      <Text style={{ fontSize: 8, fontWeight: "600", color: "#4F7CFF" }}>AVAILABLE</Text>
                    </View>
                  ) : null}
                </View>

                <Text style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}>
                  {group.provider.name}
                </Text>

                {/* Capability badges */}
                {caps.length > 0 && (
                  <View style={{ flexDirection: "row", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                    {caps.slice(0, 4).map(cap => {
                      const cfg = getCapDisplay(cap)
                      return (
                        <View key={cap} style={{
                          backgroundColor: cfg.bgColor,
                          borderRadius: 3,
                          paddingHorizontal: 5,
                          paddingVertical: 1,
                        }}>
                          <Text style={{ fontSize: 8, fontWeight: "700", color: cfg.color, letterSpacing: 0.3 }}>
                            {cfg.label}
                          </Text>
                        </View>
                      )
                    })}
                  </View>
                )}
              </View>
            </Pressable>
          )
        })}
      </View>
    )
  }

  // ── Main render ───────────────────────────────────────────────
  return (
    <View>
      {renderTrigger()}

      <Modal visible={isOpen} transparent animationType="fade" onRequestClose={() => setIsOpen(false)}>
        <TouchableOpacity
          activeOpacity={1}
          onPress={() => { setIsOpen(false); setSearchQuery("") }}
          style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "center", padding: 16 }}
        >
          <TouchableOpacity activeOpacity={1} onPress={() => {}} style={{
            backgroundColor: "#131A2E",
            borderRadius: 12,
            maxHeight: "80%",
            borderWidth: 1,
            borderColor: "rgba(255,255,255,0.08)",
            overflow: "hidden",
          }}>
            {/* Search header */}
            <View style={{
              padding: 14,
              borderBottomWidth: 1,
              borderBottomColor: "rgba(255,255,255,0.08)",
              backgroundColor: "#1B2238",
            }}>
              <TextInput
                value={searchQuery}
                onChangeText={setSearchQuery}
                placeholder="Search models..."
                placeholderTextColor="#9CA3AF"
                style={{
                  width: "100%",
                  paddingVertical: 8,
                  paddingHorizontal: 12,
                  backgroundColor: "#131A2E",
                  borderRadius: 8,
                  color: "#FFFFFF",
                  fontSize: 13,
                  borderWidth: 1,
                  borderColor: "rgba(255,255,255,0.08)",
                }}
              />
              <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: 6 }}>
                <Text style={{ fontSize: 11, color: "#9CA3AF" }}>
                  {totalModels} model{totalModels !== 1 ? "s" : ""} available
                </Text>
                {groupedProviders.length > 0 && (
                  <Pressable onPress={() => setExpandedProviders(new Set(groupedProviders.map(g => g.provider.id)))}>
                    <Text style={{ fontSize: 11, color: "#4F7CFF", textDecorationLine: "underline" }}>Expand All</Text>
                  </Pressable>
                )}
              </View>
            </View>

            {/* Model list */}
            <ScrollView style={{ maxHeight: 400 }}>
              {groupedProviders.length === 0 ? (
                <View style={{ padding: 40, alignItems: "center" }}>
                  <Text style={{ fontSize: 32, marginBottom: 8, opacity: 0.5 }}>🤖</Text>
                  <Text style={{ fontSize: 13, fontWeight: "500", color: "#9CA3AF" }}>
                    {searchQuery ? "No models match your search" : "No Active Models Available"}
                  </Text>
                  <Text style={{ fontSize: 11, color: "#9CA3AF", marginTop: 4, opacity: 0.7 }}>
                    {searchQuery ? "Try a different search term" : "Add models from the Providers page"}
                  </Text>
                </View>
              ) : (
                groupedProviders.map(renderProviderSection)
              )}
            </ScrollView>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </View>
  )
}
