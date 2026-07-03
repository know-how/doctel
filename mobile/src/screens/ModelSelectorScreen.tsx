import React, { useEffect, useState } from "react"
import {
  View,
  Text,
  FlatList,
  Pressable,
  ActivityIndicator,
  Alert,
  RefreshControl,
  useWindowDimensions,
} from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  getAvailableModels,
  startModelPull,
  getModelPullStatus,
  getModelLabels,
  getModelCapabilities,
} from "../api/client"

interface Model {
  name: string
  status: "available" | "downloading" | "failed" | "ready"
  progress?: number
  label?: string
  size_human?: string
  family?: string
  parameter_size?: string
  quantization_level?: string
  downloaded?: boolean
}

interface ModelSelectorScreenProps {
  onBack?: () => void
  onSelectModel?: (model: string) => void
}

export function ModelSelectorScreen({
  onBack,
  onSelectModel,
}: ModelSelectorScreenProps) {
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [pullingModels, setPullingModels] = useState<Set<string>>(new Set())
  const [capabilities, setCapabilities] = useState<Record<string, string[]>>({})
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  useEffect(() => {
    loadModels()
    loadCapabilities()
  }, [])

  const loadCapabilities = async () => {
    try {
      const caps: any = await getModelCapabilities()
      setCapabilities(caps.capabilities || caps || {})
    } catch {}
  }

  const loadModels = async () => {
    try {
      setLoading(true)
      console.log("Loading models...")
      const modelsRes = await getAvailableModels()
      console.log("Models response:", modelsRes)

      const labelsRes = await getModelLabels().catch((err) => {
        console.error("Failed to load labels:", err)
        return { labels: {} }
      })

      const availableModels = [...new Set(modelsRes?.available || [])]
      const installedModels = modelsRes?.installed || []
      const modelDetails: any[] = (modelsRes as any)?.models || []
      const detailMap = new Map<string, any>()
      for (const d of modelDetails) {
        detailMap.set(d.name, d)
      }
      const installedSet = new Set(installedModels)
      console.log("Available models array:", availableModels)

      const modelList: Model[] = availableModels.map((m: any) => {
        const id = typeof m === "string" ? m : m.name || m
        const d = detailMap.get(id)
        return {
          name: id,
          status: installedSet.has(id) ? "ready" : "available",
          label: labelsRes?.labels?.[id],
          size_human: d?.size_human,
          family: d?.family,
          parameter_size: d?.parameter_size,
          quantization_level: d?.quantization_level,
          downloaded: d?.ready ?? installedSet.has(id),
        }
      })

      console.log("Processed models:", modelList)
      setModels(modelList)
      setLabels(labelsRes?.labels || {})
    } catch (e: any) {
      console.error("Failed to load models:", e)
      Alert.alert("Error", `Could not load available models: ${e?.message || "Unknown error"}`)
      setModels([])
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.all([loadModels(), loadCapabilities()])
    setRefreshing(false)
  }

  const handlePullModel = async (modelName: string) => {
    try {
      setPullingModels((prev) => new Set(prev).add(modelName))
      setModels((prev) =>
        prev.map((m) => (m.name === modelName ? { ...m, status: "downloading" } : m)),
      )

      const res = await startModelPull(modelName, true)
      console.log("Model pull started:", res)

      let attempts = 0
      const checkStatus = async () => {
        try {
          const statusRes = await getModelPullStatus(modelName)
          if (statusRes.status === "completed") {
            setModels((prev) =>
              prev.map((m) =>
                m.name === modelName ? { ...m, status: "available", progress: 100 } : m,
              ),
            )
            setPullingModels((prev) => {
              const next = new Set(prev)
              next.delete(modelName)
              return next
            })
            Alert.alert("Success", `Model ${modelName} is now available`)
          } else if (statusRes.status === "failed") {
            setModels((prev) =>
              prev.map((m) =>
                m.name === modelName ? { ...m, status: "failed" } : m,
              ),
            )
            setPullingModels((prev) => {
              const next = new Set(prev)
              next.delete(modelName)
              return next
            })
            Alert.alert("Error", `Failed to download ${modelName}`)
          } else if (statusRes.progress) {
            setModels((prev) =>
              prev.map((m) =>
                m.name === modelName
                  ? { ...m, progress: statusRes.progress }
                  : m,
              ),
            )
            if (attempts < 60) {
              attempts++
              setTimeout(checkStatus, 1000)
            }
          }
        } catch (e) {
          console.error("Status check failed:", e)
        }
      }

      setTimeout(checkStatus, 1000)
    } catch (e: any) {
      setPullingModels((prev) => {
        const next = new Set(prev)
        next.delete(modelName)
        return next
      })
      setModels((prev) =>
        prev.map((m) => (m.name === modelName ? { ...m, status: "failed" } : m)),
      )
      Alert.alert("Error", e.message || "Failed to start model download")
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading models...</Text>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <View
        style={{
          paddingHorizontal: t.spacing.md,
          paddingVertical: t.spacing.sm,
          borderBottomWidth: 1,
          borderBottomColor: c.border,
          backgroundColor: c.cardBg,
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "700", color: c.text }}>
          🤖 Model Manager
        </Text>
        {onBack && (
          <Pressable onPress={onBack}>
            <Text style={{ fontSize: 14, color: c.primary }}>← Back</Text>
          </Pressable>
        )}
      </View>

      <FlatList
        data={models}
        keyExtractor={(item, index) => `model-${index}`}
        numColumns={isTablet ? 2 : 1}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
        ListEmptyComponent={
          <View style={{ padding: t.spacing.lg, alignItems: "center" }}>
            <Text style={{ fontSize: 14, color: c.textMuted, marginBottom: t.spacing.sm }}>
              No models available
            </Text>
            <Pressable
              onPress={handleRefresh}
              style={{
                paddingHorizontal: t.spacing.md,
                paddingVertical: t.spacing.sm,
                backgroundColor: c.primary,
                borderRadius: t.radii.sm,
              }}
            >
              <Text style={{ color: "#FFFFFF", fontWeight: "600" }}>Retry</Text>
            </Pressable>
          </View>
        }
        renderItem={({ item }) => (
          <View
            style={{
              backgroundColor: c.cardBg,
              borderBottomWidth: 1,
              borderBottomColor: c.border,
              paddingHorizontal: t.spacing.md,
              paddingVertical: t.spacing.sm,
              flex: isTablet ? 0.5 : undefined,
            }}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: "600", color: c.text }}>
                  {item.name}
                </Text>
                {item.label && (
                  <Text
                    style={{
                      fontSize: 12,
                      color: c.textMuted,
                      marginTop: t.spacing.xs,
                    }}
                  >
                    {item.label}
                  </Text>
                )}
                {(() => {
                  const caps = capabilities[item.name] || []
                  const icons = caps.slice(0, 4).map((cap: string) => ({ reasoning: "🧠", vision: "👁️", audio: "🎤", code: "💻", fast: "⚡", large: "🐘", text: "💬", embedding: "📊" })[cap] || "").filter(Boolean).join(" ")
                  return icons ? (
                    <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 3 }}>{icons}</Text>
                  ) : null
                })()}
                <View style={{ flexDirection: "row", gap: t.spacing.xs, marginTop: 6 }}>
                  <View
                    style={{
                      paddingHorizontal: t.spacing.sm,
                      paddingVertical: t.spacing.xs,
                      borderRadius: t.radii.sm,
                      backgroundColor:
                        item.status === "ready"
                          ? c.success + "18"
                          : item.status === "downloading"
                            ? c.warning + "18"
                            : item.status === "available"
                              ? c.primary + "14"
                              : c.error + "14",
                    }}
                  >
                    <Text
                      style={{
                        fontSize: 11,
                        fontWeight: "600",
                        color:
                          item.status === "ready"
                            ? c.success
                            : item.status === "downloading"
                              ? c.warning
                              : item.status === "available"
                                ? c.primary
                                : c.error,
                      }}
                    >
                      {item.status === "ready"
                        ? "✓ Downloaded"
                        : item.status === "downloading"
                          ? "⬇ Downloading"
                          : item.status === "available"
                            ? "☁ Ready to Pull"
                            : "✗ Failed"}
                    </Text>
                  </View>
                  {item.size_human && (
                    <View style={{ paddingHorizontal: t.spacing.xs, paddingVertical: 2, borderRadius: t.radii.sm, backgroundColor: c.bgSecondary + "80" }}>
                      <Text style={{ fontSize: 10, color: c.textMuted }}>{item.size_human}</Text>
                    </View>
                  )}
                  {item.family && (
                    <View style={{ paddingHorizontal: t.spacing.xs, paddingVertical: 2, borderRadius: t.radii.sm, backgroundColor: c.bgSecondary + "80" }}>
                      <Text style={{ fontSize: 10, color: c.textMuted }}>{item.family}</Text>
                    </View>
                  )}
                </View>
                {item.progress !== undefined && item.progress < 100 && (
                  <View
                    style={{
                      marginTop: t.spacing.sm,
                      backgroundColor: c.bgSecondary,
                      borderRadius: t.radii.sm,
                      height: 4,
                      overflow: "hidden",
                    }}
                  >
                    <View
                      style={{
                        height: 4,
                        backgroundColor: c.primary,
                        width: `${item.progress}%`,
                      }}
                    />
                  </View>
                )}
              </View>

              <View style={{ marginLeft: t.spacing.sm }}>
                {item.status === "available" ? (
                  <Pressable
                    onPress={() => onSelectModel?.(item.name)}
                    style={{
                      backgroundColor: c.primary,
                      borderRadius: t.radii.sm,
                      paddingHorizontal: t.spacing.sm,
                      paddingVertical: t.spacing.sm,
                    }}
                  >
                    <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 12 }}>
                      Select
                    </Text>
                  </Pressable>
                ) : item.status === "downloading" ? (
                  <ActivityIndicator size="small" color={c.primary} />
                ) : (
                  <Pressable
                    onPress={() => handlePullModel(item.name)}
                    style={{
                      backgroundColor: c.primary,
                      borderRadius: t.radii.sm,
                      paddingHorizontal: t.spacing.sm,
                      paddingVertical: t.spacing.sm,
                    }}
                  >
                    <Text
                      style={{
                        color: "#FFFFFF",
                        fontWeight: "600",
                        fontSize: 12,
                      }}
                    >
                      Retry
                    </Text>
                  </Pressable>
                )}
              </View>
            </View>
          </View>
        )}
        contentContainerStyle={{ paddingTop: t.spacing.sm }}
      />
    </View>
  )
}