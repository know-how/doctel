import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { getAvailableModels, getModelCapabilities, getModelLabels, v2SelectModelForTask, v2GetCatalog } from "../api/client"
import type { OllamaModelDetail, ModelsAvailableResponse, V2Provider, V2CatalogResponse } from "../types/api"

const MODEL_KEY = "docintel_selected_model"
const BC_CHANNEL = "doctel-model-updates"

interface ModelContextValue {
  selectedModel: string
  setSelectedModel: (model: string) => void
  availableModels: string[]
  modelCapabilities: Record<string, string[]>
  modelLabels: Record<string, string>
  modelDetails: OllamaModelDetail[]
  offline: boolean
  loading: boolean
  reloadModels: () => Promise<void>
  /** Set a model based on a specific task type, using auto-routing if enabled */
  setModelForTask: (taskType: string) => Promise<void>
  /** V2 providers from the model management system (enriched) */
  v2Providers: V2Provider[]
  /** Set of model IDs managed by V2 providers (for sorting/labeling) */
  v2ModelIds: Set<string>
  /** Whether automatic routing is enabled */
  v2AutoRouting: boolean
  /** Task-to-model defaults from V2 task mapping */
  taskDefaults: Record<string, string>
}

const ModelContext = createContext<ModelContextValue | undefined>(undefined)

function getStoredModel(): string {
  try {
    return localStorage.getItem(MODEL_KEY) || ""
  } catch {
    return ""
  }
}

export function ModelProvider({ children }: { children: ReactNode }) {
  const [selectedModel, setSelectedModelState] = useState("")
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [modelCapabilities, setModelCapabilities] = useState<Record<string, string[]>>({})
  const [modelLabels, setModelLabels] = useState<Record<string, string>>({})
  const [modelDetails, setModelDetails] = useState<OllamaModelDetail[]>([])
  const [offline, setOffline] = useState(false)
  const [loading, setLoading] = useState(true)
  const [v2Providers, setV2Providers] = useState<V2Provider[]>([])
  const [v2AutoRouting, setV2AutoRouting] = useState(true)
  const [taskDefaults, setTaskDefaults] = useState<Record<string, string>>({})
  const [rawRes, setRawRes] = useState<ModelsAvailableResponse | null>(null)

  const recalcDefault = useCallback((res: ModelsAvailableResponse, all: string[], taskType?: string): string => {
    // Priority: stored user preference > task-specific default > chat default > default_model > first
    const stored = getStoredModel()
    if (stored && all.includes(stored)) return stored
    if (taskType) {
      const taskDef = res.defaults?.[taskType]
      if (taskDef && all.includes(taskDef)) return taskDef
    }
    const chatDefault = res.defaults?.["chat"]
    if (chatDefault && all.includes(chatDefault)) return chatDefault
    if (res.default_model && all.includes(res.default_model)) return res.default_model
    if (all.length > 0) return all[0]
    return ""
  }, [])

  const loadModelData = useCallback(async () => {
    setLoading(true)
    try {
      const [res, capsRes, labelsRes] = await Promise.all([
        getAvailableModels(),
        getModelCapabilities().catch(() => ({ capabilities: {} })),
        getModelLabels().catch(() => ({ labels: {} })),
      ])
      setRawRes(res)

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
        // Fallback: use v2_providers from available endpoint (same get_all_providers backend)
        catalogProviders = res.v2_providers || []
        catalogAutoRouting = res.v2_auto_routing !== false
        // Reconstruct flat task mapping from res.defaults
        for (const [taskType, modelId] of Object.entries(res.defaults || {})) {
          catalogTaskMapping[taskType] = { modelId }
        }
      }
      
      // Store providers from catalog, filtering by visible_to_users for user-facing contexts
      // Admin pages use v2GetCatalog directly so they see all
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

      let filteredModels = all
      const VISIBLE_STATES = ['active', 'installed', 'available', 'maintenance']
      if (userVisibleProviders.length > 0) {
        const v2VisibleModels = new Set<string>()
        for (const p of userVisibleProviders) {
          for (const m of p.models || []) {
            if (VISIBLE_STATES.includes(m.state)) {
              v2VisibleModels.add(m.id)
            }
          }
        }
        filteredModels = all.filter((modelId) => {
          const isV2Managed = userVisibleProviders.some((p: any) => 
            (p.models || []).some((m: any) => m.id === modelId)
          )
          if (!isV2Managed) return true
          return v2VisibleModels.has(modelId)
        })
      }
      setModelDetails(res.models || [])
      setOffline(Boolean(res.offline))

      // ── Merge capabilities ──
      const mergedCaps: Record<string, string[]> = { ...(capsRes.capabilities || {} as Record<string, string[]>) }
      for (const detail of (res.models || [])) {
        if (detail.capabilities && detail.capabilities.length > 0 && !mergedCaps[detail.name]) {
          mergedCaps[detail.name] = detail.capabilities
        }
      }
      // Augment with provider-level capabilities from catalog
      for (const p of catalogProviders) {
        for (const m of p.models || []) {
          if (m.capabilities && m.capabilities.length > 0 && !mergedCaps[m.id]) {
            mergedCaps[m.id] = m.capabilities
          }
        }
      }
      setModelCapabilities(mergedCaps)
      setModelLabels(labelsRes.labels || {})

      // ── Task defaults: derive from catalog.taskMapping (same source as Task Mapping page) ──
      // Use catalogProviders (pre-visibility-filtering) to build the lookup so
      // Task Mapping model IDs are found regardless of visibility filtering order.
      const v2ModelIdSet = new Set<string>()
      for (const p of catalogProviders) {
        for (const m of p.models || []) {
          if (VISIBLE_STATES.includes(m.state)) {
            v2ModelIdSet.add(m.id)
          }
        }
      }

      const flatTaskDefaults: Record<string, string> = {}
      for (const [taskType, mapping] of Object.entries(catalogTaskMapping)) {
        const m = mapping as any
        const mid = m.modelId || ""
        if (mid && (filteredModels.includes(mid) || v2ModelIdSet.has(mid))) {
          flatTaskDefaults[taskType] = mid
          // Ensure the model is in filteredModels too (in case it was missed by the backend filter)
          if (!filteredModels.includes(mid)) {
            filteredModels.push(mid)
          }
        }
      }
      setAvailableModels(filteredModels)
      setTaskDefaults(flatTaskDefaults)

      // ── ModelContext does NOT auto-select a model ──
      // Every page calls setModelForTask(taskType) on mount.
      // That function uses taskDefaults + auto-routing + fallback.
      // Auto-selecting here creates a race where the wrong model
      // wins before taskDefaults finishes loading.
    } catch {
    } finally {
      setLoading(false)
    }
  }, [recalcDefault])

  // ── Admin change propagation via BroadcastChannel ─────────────────────
  useEffect(() => {
    let bc: BroadcastChannel | null = null
    try {
      bc = new BroadcastChannel(BC_CHANNEL)
      bc.onmessage = (ev) => {
        if (ev.data?.type === "models-changed" || ev.data?.type === "routing-changed") {
          console.log("[ModelContext] Detected admin change, reloading model data...")
          loadModelData()
        }
      }
    } catch {
      // BroadcastChannel may not be available in all environments
    }
    return () => {
      try { bc?.close() } catch {}
    }
  }, [loadModelData])

  useEffect(() => {
    loadModelData()
  }, [loadModelData])

  const setSelectedModel = useCallback((model: string) => {
    setSelectedModelState(model)
    try { localStorage.setItem(MODEL_KEY, model) } catch {}
  }, [])

  // ── Set model for a specific task, using task mapping as primary source ──
  // Priority: 1) Task Mapping  →  2) Auto-routing  →  3) System fallback
  // Note: localStorage preference is intentionally NOT checked here.
  // Task Mapping is the single source of truth for page defaults.
  // Users can still manually change the model after page load.
  const setModelForTask = useCallback(async (taskType: string) => {
    // 1) Task Mapping default (source of truth for page defaults)
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
    // 3) Chat default → default_model → first available
    const syntheticRes: any = { ...rawRes, defaults: taskDefaults }
    const next = recalcDefault(syntheticRes || { installed: [] }, availableModels, taskType)
    if (next) setSelectedModelState(next)
  }, [availableModels, rawRes, v2AutoRouting, recalcDefault, taskDefaults])

  return (
    <ModelContext.Provider value={{
      selectedModel,
      setSelectedModel,
      availableModels,
      modelCapabilities,
      modelLabels,
      modelDetails,
      offline,
      loading,
      reloadModels: loadModelData,
      setModelForTask,
      v2Providers,
      v2ModelIds: new Set(v2Providers.flatMap(p => (p.models || []).map(m => m.id))),
      v2AutoRouting,
      taskDefaults,
    }}>
      {children}
    </ModelContext.Provider>
  )
}

export function useModel(): ModelContextValue {
  const ctx = useContext(ModelContext)
  if (!ctx) throw new Error("useModel must be used within a ModelProvider")
  return ctx
}
