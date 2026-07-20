import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { getAvailableModels, getModelCapabilities, getModelLabels, v2GetCatalog, v2SelectModelForTask } from "../api/client"
import type { V2Provider, V2CatalogResponse } from "../types/api"

const MODEL_KEY = "docintel_selected_model"

interface ModelContextValue {
  selectedModel: string
  setSelectedModel: (model: string) => void
  availableModels: string[]
  loading: boolean
  modelCapabilities: Record<string, string[]>
  modelLabels: Record<string, string>
  v2Providers: V2Provider[]
  v2AutoRouting: boolean
  taskDefaults: Record<string, string>
  setModelForTask: (taskType: string) => Promise<void>
}

const ModelContext = createContext<ModelContextValue | undefined>(undefined)

async function getStoredModel(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(MODEL_KEY)) || ""
  } catch {
    return ""
  }
}

export function ModelProvider({ children }: { children: ReactNode }) {
  const [selectedModel, setSelectedModelState] = useState("")
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [modelCapabilities, setModelCapabilities] = useState<Record<string, string[]>>({})
  const [modelLabels, setModelLabelsState] = useState<Record<string, string>>({})
  const [v2Providers, setV2Providers] = useState<V2Provider[]>([])
  const [v2AutoRouting, setV2AutoRouting] = useState(false)
  const [taskDefaults, setTaskDefaults] = useState<Record<string, string>>({})

  const VISIBLE_STATES = ["active", "installed", "available", "maintenance"]

  // ── Load model data: same approach as web frontend ──────────────
  useEffect(() => {
    (async () => {
      try {
        const [res, capsRes, labelsRes] = await Promise.all([
          getAvailableModels(),
          getModelCapabilities().catch(() => ({ capabilities: {} })),
          getModelLabels().catch(() => ({ labels: {} })),
        ])

        // ── Provider source: prefer v2GetCatalog (same as Task Mapping) ──
        let catalogProviders: V2Provider[] = []
        let catalogTaskMapping: Record<string, any> = {}
        let catalogAutoRouting = true

        let catalog: V2CatalogResponse | null = null
        try {
          catalog = await v2GetCatalog()
          catalogProviders = catalog.providers || []
          catalogTaskMapping = catalog.taskMapping || {}
          catalogAutoRouting = catalog.automaticRouting !== false
        } catch {
          // Fallback: use v2_providers from available endpoint
          catalogProviders = res.v2_providers || []
          catalogAutoRouting = res.v2_auto_routing !== false
        }

        // ── Filter by visibleToUsers (web frontend matching logic) ──
        const userVisibleProviders = catalogProviders
          .filter((p: any) => p.visibleToUsers !== false)
          .map((p: any) => ({
            ...p,
            models: (p.models || []).filter((m: any) => m.visibleToUsers !== false),
          }))
        setV2Providers(userVisibleProviders)
        setV2AutoRouting(catalogAutoRouting)

        // ── Build flat model list ──
        const all: string[] = [...new Set([...(res.installed || []), ...(res.available || [])])]
        const v2ModelIdSet = new Set<string>()
        for (const p of userVisibleProviders) {
          for (const m of p.models || []) {
            if (VISIBLE_STATES.includes(m.state)) {
              v2ModelIdSet.add(m.id)
            }
          }
        }

        const filteredModels = all.filter((modelId) => {
          const isV2Managed = userVisibleProviders.some((p: any) =>
            (p.models || []).some((m: any) => m.id === modelId)
          )
          if (!isV2Managed) return true
          return v2ModelIdSet.has(modelId)
        })
        setAvailableModels(filteredModels)

        // ── Merge capabilities from all sources ──
        const mergedCaps: Record<string, string[]> = { ...(capsRes.capabilities || {} as Record<string, string[]>) }
        for (const detail of (res.models || [])) {
          if (detail.capabilities && detail.capabilities.length > 0 && !mergedCaps[detail.name]) {
            mergedCaps[detail.name] = detail.capabilities
          }
        }
        for (const p of catalogProviders) {
          for (const m of p.models || []) {
            if (m.capabilities && m.capabilities.length > 0 && !mergedCaps[m.id]) {
              mergedCaps[m.id] = m.capabilities
            }
          }
        }
        setModelCapabilities(mergedCaps)

        // ── Labels ──
        setModelLabelsState(labelsRes.labels || {})

        // ── Task defaults from catalog task mapping ──
        const v2ModelIdSetAll = new Set<string>()
        for (const p of catalogProviders) {
          for (const m of p.models || []) {
            if (VISIBLE_STATES.includes(m.state)) {
              v2ModelIdSetAll.add(m.id)
            }
          }
        }
        const flatTaskDefaults: Record<string, string> = {}
        for (const [taskType, mapping] of Object.entries(catalogTaskMapping)) {
          const m = mapping as any
          const mid = m.modelId || ""
          if (mid && (filteredModels.includes(mid) || v2ModelIdSetAll.has(mid))) {
            flatTaskDefaults[taskType] = mid
            if (!filteredModels.includes(mid)) {
              filteredModels.push(mid)
            }
          }
        }
        setTaskDefaults(flatTaskDefaults)

        // ── Select initial model ──
        const stored = await getStoredModel()
        if (stored && filteredModels.includes(stored)) {
          setSelectedModelState(stored)
        } else if (filteredModels.length > 0) {
          setSelectedModelState(filteredModels[0])
        }
      } catch {
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const setSelectedModel = useCallback((model: string) => {
    setSelectedModelState(model)
    AsyncStorage.setItem(MODEL_KEY, model).catch(() => {})
  }, [])

  // ── Set model for a specific task, using task mapping as primary source ──
  // Priority: 1) Task Mapping  →  2) Auto-routing  →  3) First available
  const setModelForTask = useCallback(async (taskType: string) => {
    // 1) Task Mapping default
    if (taskDefaults[taskType] && availableModels.includes(taskDefaults[taskType])) {
      setSelectedModelState(taskDefaults[taskType])
      return
    }
    // 2) Auto-routing
    if (v2AutoRouting) {
      try {
        const routeRes = await v2SelectModelForTask(taskType)
        if (routeRes.model?.id && availableModels.includes(routeRes.model.id)) {
          setSelectedModelState(routeRes.model.id)
          return
        }
      } catch { /* fall through */ }
    }
    // 3) First available
    if (availableModels.length > 0) {
      setSelectedModelState(availableModels[0])
    }
  }, [availableModels, v2AutoRouting, taskDefaults])

  return (
    <ModelContext.Provider
      value={{
        selectedModel,
        setSelectedModel,
        availableModels,
        loading,
        modelCapabilities,
        modelLabels,
        v2Providers,
        v2AutoRouting,
        taskDefaults,
        setModelForTask,
      }}
    >
      {children}
    </ModelContext.Provider>
  )
}

export function useModel(): ModelContextValue {
  const ctx = useContext(ModelContext)
  if (!ctx) {
    throw new Error("useModel must be used within a ModelProvider")
  }
  return ctx
}
