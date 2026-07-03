import React, { useEffect, useState } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getAvailableModels, startModelPull, getModelPullStatus, setDefaultModel, distillFromCloud } from "../api/client"

interface ModelItem {
  name: string
  status: "available" | "downloading" | "failed" | "installed"
  progress?: number
  label?: string
}

const taskTypes = ["chat", "embed", "vision", "summary", "extraction"]

export function AdminModelsScreen() {
  const [models, setModels] = useState<ModelItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<"installed" | "available">("installed")
  const [pullingModel, setPullingModel] = useState<string | null>(null)
  const [pullProgress, setPullProgress] = useState(0)
  const [error, setError] = useState("")
  const [defaultModels, setDefaultModels] = useState<Record<string, string>>({})
  const [distilling, setDistilling] = useState(false)
  const [distillMsg, setDistillMsg] = useState("")
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  useEffect(() => {
    loadModels()
  }, [])

  const loadModels = async () => {
    try {
      setLoading(true)
      setError("")
      const res = await getAvailableModels()
      const installedList = (res?.installed || []).map((name: string) => ({
        name,
        status: "installed" as const,
        label: (res as any)?.labels?.[name] || undefined,
      }))
      const availableList = (res?.available || [])
        .filter((name: string) => !res?.installed?.includes(name))
        .map((name: string) => ({
          name,
          status: "available" as const,
          label: (res as any)?.labels?.[name] || undefined,
        }))
      const seen = new Set<string>()
      const deduped = [...installedList, ...availableList].filter((m) => {
        if (seen.has(m.name)) return false
        seen.add(m.name)
        return true
      })
      setModels(deduped)
      if ((res as any)?.default_models) {
        setDefaultModels((res as any).default_models)
      } else if (res?.default_model) {
        setDefaultModels({ default: res.default_model })
      }
    } catch (err: any) {
      setError(err.message || "Failed to load models")
    } finally {
      setLoading(false)
    }
  }

  const handlePullModel = async (modelName: string) => {
    try {
      setPullingModel(modelName)
      setPullProgress(0)
      setError("")
      await startModelPull(modelName)
      const pollInterval = setInterval(async () => {
        try {
          const status = await getModelPullStatus(modelName)
          setPullProgress(status?.percent || status?.progress || 0)
          if (status?.state === "success" || status?.installed) {
            clearInterval(pollInterval)
            setPullingModel(null)
            loadModels()
          } else if (status?.state === "failed") {
            clearInterval(pollInterval)
            setPullingModel(null)
            setError(`Failed to pull ${modelName}: ${status?.error || "Unknown error"}`)
          }
        } catch {
          clearInterval(pollInterval)
          setPullingModel(null)
        }
      }, 2000)
    } catch (err: any) {
      setError(err.message || "Failed to start model pull")
      setPullingModel(null)
    }
  }

  const handleSetDefault = async (taskType: string, modelId: string) => {
    try {
      await setDefaultModel(taskType, modelId)
      setDefaultModels((prev) => ({ ...prev, [taskType]: modelId }))
    } catch (err: any) {
      setError(err.message || "Failed to set default model")
    }
  }

  const filteredModels = models.filter((m) => {
    if (activeTab === "installed") return m.status === "installed"
    return m.status === "available"
  })

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: 12, color: c.textMuted }}>Loading models...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        AI Models
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <View style={{ flexDirection: "row", marginBottom: t.spacing.md, backgroundColor: c.bgSecondary, borderRadius: t.radii.md, padding: t.spacing.xs }}>
        {(["installed", "available"] as const).map((tab) => (
          <Pressable
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={{
              flex: 1,
              paddingVertical: 10,
              borderRadius: t.radii.sm,
              backgroundColor: activeTab === tab ? c.cardBg : "transparent",
              alignItems: "center",
            }}
          >
            <Text style={{ fontSize: 14, fontWeight: "600", color: activeTab === tab ? c.primary : c.textMuted }}>
              {tab === "installed" ? "Installed" : "Available"}
            </Text>
          </Pressable>
        ))}
      </View>

      {activeTab === "installed" && models.filter(m => m.status === "installed").length > 0 && (
        <View style={{ marginBottom: t.spacing.md }}>
          <Text style={{ fontSize: 14, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
            Default Models
          </Text>
          {taskTypes.map((task) => (
            <View key={task} style={{ marginBottom: t.spacing.sm }}>
              <Text style={{ fontSize: 13, color: c.textMuted, marginBottom: t.spacing.xs }}>
                {task.charAt(0).toUpperCase() + task.slice(1)}
              </Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {models
                  .filter((m) => m.status === "installed")
                  .map((model, i) => (
                    <Pressable
                      key={`installed-${i}`}
                      onPress={() => handleSetDefault(task, model.name)}
                      style={{
                        paddingHorizontal: t.spacing.sm,
                        paddingVertical: 6,
                        borderRadius: t.radii.xl,
                        backgroundColor: defaultModels[task] === model.name ? c.success + "18" : c.bgSecondary,
                        marginRight: t.spacing.sm,
                        borderWidth: 1,
                        borderColor: defaultModels[task] === model.name ? c.success : "transparent",
                      }}
                    >
                      <Text style={{ fontSize: 11, fontWeight: "600", color: defaultModels[task] === model.name ? c.success : c.text }}>
                        {model.name}
                      </Text>
                    </Pressable>
                  ))}
              </ScrollView>
            </View>
          ))}
        </View>
      )}

      {filteredModels.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>🤖</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
            No {activeTab} models
          </Text>
          <Text style={{ fontSize: 13, color: c.textMuted }}>
            {activeTab === "available" ? "All models are installed" : "Pull models from the Available tab"}
          </Text>
        </View>
      ) : (
        <View style={{ flexDirection: isTablet ? "row" : "column", flexWrap: isTablet ? "wrap" : "nowrap", gap: t.spacing.sm }}>
          {filteredModels.map((model, i) => (
            <View
              key={`model-${i}`}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: t.radii.md,
                padding: t.spacing.sm,
                marginBottom: isTablet ? 0 : 10,
                width: isTablet ? "48%" : "100%",
                borderWidth: 1,
                borderColor: c.border,
              }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.sm }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>
                    {model.name}
                  </Text>
                  {model.label ? (
                    <Text style={{ fontSize: 12, color: c.textMuted }}>{model.label}</Text>
                  ) : null}
                </View>
                <View
                  style={{
                    backgroundColor: model.status === "installed" ? c.success + "18" : model.status === "downloading" ? c.warning + "18" : c.accent + "18",
                    borderRadius: t.radii.sm,
                    paddingHorizontal: t.spacing.sm,
                    paddingVertical: 3,
                  }}
                >
                  <Text style={{ fontSize: 10, fontWeight: "700", color: model.status === "installed" ? c.success : c.text }}>
                    {model.status.toUpperCase()}
                  </Text>
                </View>
              </View>

              {pullingModel === model.name && (
                <View style={{ marginBottom: t.spacing.sm }}>
                  <View style={{ backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, height: 10, overflow: "hidden" }}>
                    <View
                      style={{
                        backgroundColor: c.primary,
                        height: "100%",
                        width: `${Math.min(pullProgress, 100)}%`,
                        borderRadius: t.radii.sm,
                      }}
                    />
                  </View>
                  <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 2 }}>{pullProgress}%</Text>
                </View>
              )}

              {model.status === "available" && (
                <Pressable
                  onPress={() => handlePullModel(model.name)}
                  disabled={pullingModel === model.name}
                  style={{
                    backgroundColor: pullingModel === model.name ? c.textMuted : c.primary,
                    borderRadius: t.radii.sm,
                    paddingVertical: t.spacing.sm,
                    alignItems: "center",
                  }}
                >
                  <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 13 }}>
                    {pullingModel === model.name ? "Pulling..." : "Pull Model"}
                  </Text>
                </Pressable>
              )}
            </View>
          ))}
        </View>
      )}

      <View style={{ marginTop: t.spacing.lg, backgroundColor: c.cardBg, borderRadius: t.radii.lg, padding: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
          Knowledge Distillation
        </Text>
        <Text style={{ fontSize: 13, color: c.textMuted, marginBottom: t.spacing.md }}>
          Query Gemini/DeepSeek with ZETDC topics to generate training data for local models.
        </Text>
        <Pressable
          onPress={async () => {
            setDistilling(true)
            setDistillMsg("")
            try {
              const res = await distillFromCloud({ auto_train: true })
              setDistillMsg(
                `${res.total_samples} samples (${res.gemini_samples} Gemini, ${res.deepseek_samples} DeepSeek) across ${res.topics_covered} topics${res.training_triggered ? " — training triggered" : ""}`
              )
            } catch (e: any) {
              setDistillMsg(`Failed: ${e.message ?? e}`)
            } finally {
              setDistilling(false)
            }
          }}
          disabled={distilling}
          style={{
            backgroundColor: distilling ? c.textMuted : c.primary,
            borderRadius: t.radii.md,
            paddingVertical: t.spacing.sm + 2,
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 14 }}>
            {distilling ? "Distilling..." : "Distill ZETDC Knowledge"}
          </Text>
        </Pressable>
        {distillMsg ? (
          <Text style={{ fontSize: 13, color: distillMsg.startsWith("Failed") ? c.error : c.success, marginTop: t.spacing.sm }}>
            {distillMsg}
          </Text>
        ) : null}
      </View>
    </ScrollView>
  )
}