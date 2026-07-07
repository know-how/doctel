import React, { useEffect, useState, useCallback } from "react"
import {
  View, Text, Pressable, ScrollView, ActivityIndicator,
  useWindowDimensions, Alert,
} from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  v2GetTaskMapping, v2SetTaskMapping, v2RemoveTaskMapping,
  v2GetRoutingStatus, v2ToggleRouting, v2GetCatalog,
} from "../api/client"
import type { V2Provider } from "../types/api"

export function TaskMappingScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [taskMapping, setTaskMapping] = useState<Record<string, { providerId: string; modelId: string; modelName?: string; providerName?: string }>>({})
  const [taskTypes, setTaskTypes] = useState<string[]>([])
  const [routingEnabled, setRoutingEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState<string | null>(null)

  // Catalog data for selection
  const [providers, setProviders] = useState<V2Provider[]>([])
  const [expandedTask, setExpandedTask] = useState<string | null>(null)
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError("")
      const [mappingRes, routingRes, catalogRes] = await Promise.all([
        v2GetTaskMapping(),
        v2GetRoutingStatus(),
        v2GetCatalog().catch(() => null),
      ])
      setTaskMapping(mappingRes.taskMapping || {})
      setTaskTypes(mappingRes.taskTypes || [])
      setRoutingEnabled(routingRes.automaticRouting)
      if (catalogRes) {
        setProviders(catalogRes.providers || [])
        if (!mappingRes.taskTypes?.length && catalogRes.taskTypes?.length) {
          setTaskTypes(catalogRes.taskTypes)
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load task mapping")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleToggleRouting = async () => {
    const newVal = !routingEnabled
    try {
      setSaving("routing")
      setError("")
      await v2ToggleRouting(newVal)
      setRoutingEnabled(newVal)
    } catch (err: any) {
      setError(err.message || "Failed to toggle routing")
    } finally {
      setSaving(null)
    }
  }

  const handleSetMapping = async (taskType: string, providerId: string, modelId: string) => {
    try {
      setSaving(taskType)
      setError("")
      await v2SetTaskMapping(taskType, providerId, modelId)
      setTaskMapping((prev) => ({
        ...prev,
        [taskType]: { providerId, modelId },
      }))
      setExpandedTask(null)
      setSelectedProviderId(null)
    } catch (err: any) {
      setError(err.message || "Failed to set task mapping")
    } finally {
      setSaving(null)
    }
  }

  const handleRemoveMapping = (taskType: string) => {
    Alert.alert("Remove Mapping", `Clear mapping for "${taskType}"?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          try {
            setSaving(taskType)
            setError("")
            await v2RemoveTaskMapping(taskType)
            setTaskMapping((prev) => {
              const next = { ...prev }
              delete next[taskType]
              return next
            })
          } catch (err: any) {
            setError(err.message || "Failed to remove mapping")
          } finally {
            setSaving(null)
          }
        },
      },
    ])
  }

  // Get models for a provider
  const getModelsForProvider = (providerId: string) => {
    const provider = providers.find((p) => p.id === providerId)
    return provider?.models || []
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: 12, color: c.textMuted }}>Loading task mapping...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>🔀 Task Mapping</Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {/* Auto-Routing Toggle */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }}>⚡ Automatic Routing</Text>
            <Text style={{ fontSize: 12, color: c.textMuted, marginTop: 2 }}>
              {routingEnabled
                ? "Tasks are automatically routed to the best model"
                : "Manual model selection per task type"}
            </Text>
          </View>
          <Pressable
            onPress={handleToggleRouting}
            disabled={saving === "routing"}
            style={{
              width: 52,
              height: 28,
              borderRadius: 14,
              backgroundColor: routingEnabled ? c.success : c.textMuted,
              justifyContent: "center",
              paddingHorizontal: 4,
              alignItems: routingEnabled ? "flex-end" : "flex-start",
            }}
          >
            <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: "#fff" }} />
          </Pressable>
        </View>
      </View>

      {/* Routing Status Badge */}
      <View
        style={{
          backgroundColor: routingEnabled ? c.success + "14" : c.warning + "14",
          borderRadius: t.radii.md,
          padding: t.spacing.sm,
          marginBottom: t.spacing.md,
          borderWidth: 1,
          borderColor: routingEnabled ? c.success + "28" : c.warning + "28",
          flexDirection: "row",
          alignItems: "center",
          gap: t.spacing.sm,
        }}
      >
        <Text style={{ fontSize: 18 }}>{routingEnabled ? "🟢" : "🟡"}</Text>
        <Text style={{ color: routingEnabled ? c.success : c.warning, fontSize: 13, flex: 1 }}>
          {routingEnabled
            ? "Auto-routing is enabled. Models are selected automatically based on task requirements."
            : "Auto-routing is disabled. Configure individual task mappings below."}
        </Text>
      </View>

      {/* Task Mapping List */}
      <Text style={{ fontSize: 18, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>
        Task Mappings
      </Text>

      {taskTypes.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.lg, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 32, marginBottom: t.spacing.sm }}>🔀</Text>
          <Text style={{ fontSize: 14, color: c.textMuted, textAlign: "center" }}>
            No task types configured yet.
          </Text>
        </View>
      ) : (
        taskTypes.map((taskType) => {
          const mapping = taskMapping[taskType]
          const isExpanded = expandedTask === taskType
          const isSaving = saving === taskType

          return (
            <View
              key={taskType}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: t.radii.md,
                padding: t.spacing.md,
                marginBottom: t.spacing.sm,
                borderWidth: 1,
                borderColor: c.border,
              }}
            >
              {/* Task Header */}
              <Pressable
                onPress={() => setExpandedTask(isExpanded ? null : taskType)}
                style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}
              >
                <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm, flex: 1 }}>
                  <Text style={{ fontSize: 16, color: c.text, fontWeight: "600" }}>{taskType}</Text>
                  {mapping ? (
                    <View style={{ backgroundColor: c.success + "20", borderRadius: t.radii.sm, paddingHorizontal: 6, paddingVertical: 2 }}>
                      <Text style={{ color: c.success, fontSize: 11, fontWeight: "600" }}>mapped</Text>
                    </View>
                  ) : (
                    <View style={{ backgroundColor: c.warning + "20", borderRadius: t.radii.sm, paddingHorizontal: 6, paddingVertical: 2 }}>
                      <Text style={{ color: c.warning, fontSize: 11, fontWeight: "600" }}>unmapped</Text>
                    </View>
                  )}
                </View>
                <Text style={{ color: c.textMuted, fontSize: 14 }}>{isExpanded ? "▲" : "▼"}</Text>
              </Pressable>

              {/* Current Mapping */}
              {mapping ? (
                <View style={{ marginTop: t.spacing.sm, backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm }}>
                  <Text style={{ fontSize: 12, color: c.textMuted }}>Provider: {mapping.providerName || mapping.providerId}</Text>
                  <Text style={{ fontSize: 12, color: c.textMuted }}>Model: {mapping.modelName || mapping.modelId}</Text>
                </View>
              ) : null}

              {/* Expanded: Selection UI */}
              {isExpanded ? (
                <View style={{ marginTop: t.spacing.md }}>
                  {/* Provider selector */}
                  <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>Select Provider</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4, marginBottom: t.spacing.md }}>
                    {providers.map((p) => {
                      const active = selectedProviderId === p.id
                      return (
                        <Pressable
                          key={p.id}
                          onPress={() => setSelectedProviderId(active ? null : p.id)}
                          style={{
                            backgroundColor: active ? c.primary : c.bgSecondary,
                            borderRadius: t.radii.sm,
                            paddingHorizontal: 10,
                            paddingVertical: 5,
                            borderWidth: 1,
                            borderColor: active ? c.primary : c.border,
                          }}
                        >
                          <Text style={{ color: active ? "#fff" : c.text, fontSize: 12, fontWeight: "600" }}>
                            {p.name}
                          </Text>
                        </Pressable>
                      )
                    })}
                  </View>

                  {/* Model selector for selected provider */}
                  {selectedProviderId ? (
                    <>
                      <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>Select Model</Text>
                      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4, marginBottom: t.spacing.md }}>
                        {getModelsForProvider(selectedProviderId).map((m) => {
                          const isSelected = mapping?.providerId === selectedProviderId && mapping?.modelId === m.id
                          return (
                            <Pressable
                              key={m.id}
                              onPress={() => {
                                if (isSaving) return
                                handleSetMapping(taskType, selectedProviderId, m.id)
                              }}
                              disabled={isSaving}
                              style={{
                                backgroundColor: isSelected ? c.success + "30" : c.bgSecondary,
                                borderRadius: t.radii.sm,
                                paddingHorizontal: 10,
                                paddingVertical: 5,
                                borderWidth: 1,
                                borderColor: isSelected ? c.success : c.border,
                              }}
                            >
                              <Text style={{ color: isSelected ? c.success : c.text, fontSize: 12, fontWeight: "600" }}>
                                {m.name}
                              </Text>
                            </Pressable>
                          )
                        })}
                        {getModelsForProvider(selectedProviderId).length === 0 && (
                          <Text style={{ color: c.textMuted, fontSize: 12 }}>No models for this provider</Text>
                        )}
                      </View>
                    </>
                  ) : null}

                  {/* Remove mapping button */}
                  {mapping ? (
                    <Pressable
                      onPress={() => handleRemoveMapping(taskType)}
                      disabled={isSaving}
                      style={{
                        backgroundColor: c.error + "14",
                        borderRadius: t.radii.sm,
                        paddingVertical: t.spacing.sm,
                        alignItems: "center",
                        borderWidth: 1,
                        borderColor: c.error + "28",
                      }}
                    >
                      <Text style={{ color: c.error, fontWeight: "600", fontSize: 13 }}>
                        {isSaving ? "Removing..." : "Remove Mapping"}
                      </Text>
                    </Pressable>
                  ) : null}
                </View>
              ) : null}
            </View>
          )
        })
      )}
    </ScrollView>
  )
}
