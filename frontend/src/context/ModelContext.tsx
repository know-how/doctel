import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { getAvailableModels, getModelCapabilities, getModelLabels, v2SelectModelForTask } from "../api/client"
import type { OllamaModelDetail, ModelsAvailableResponse, V2Provider } from "../types/api"

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

      // Build consolidated model list: installed + available + V2-provided models
      const all: string[] = [...new Set([...(res.installed || []), ...(res.available || [])])]

      // Include V2-managed models that are selectable (active, installed, available)
      // Also include MAINTENANCE models (visible but disabled for selection)
      let filteredModels = all
      const v2provs = res.v2_providers || []
      const VISIBLE_STATES = ['active', 'installed', 'available', 'maintenance']
      if (v2provs.length > 0) {
        const v2VisibleModels = new Set<string>()
        for (const p of v2provs) {
          for (const m of p.models || []) {
            // ACTIVE, INSTALLED, AVAILABLE, and MAINTENANCE models are visible
            if (VISIBLE_STATES.includes(m.state)) {
              v2VisibleModels.add(m.id)
            }
          }
        }
        filteredModels = all.filter((modelId) => {
          // If not a V2-managed model, keep it (legacy behavior)
          const isV2Managed = v2provs.some((p: any) => 
            (p.models || []).some((m: any) => m.id === modelId)
          )
          if (!isV2Managed) return true
          // For V2-managed models, only keep if visible
          return v2VisibleModels.has(modelId)
        })
      }
      setAvailableModels(filteredModels)
      setModelDetails(res.models || [])
      setOffline(Boolean(res.offline))

      // Merge capabilities: registry first, then augment with model detail caps + V2 caps
      const mergedCaps = { ...(capsRes.capabilities || {}) }
      for (const detail of (res.models || [])) {
        if (detail.capabilities && detail.capabilities.length > 0 && !mergedCaps[detail.name]) {
          mergedCaps[detail.name] = detail.capabilities
        }
      }
      setModelCapabilities(mergedCaps)
      setModelLabels(labelsRes.labels || {})

      // Store V2 data
      const v2provsData = res.v2_providers || []
      setV2Providers(v2provsData)
      setV2AutoRouting(res.v2_auto_routing !== false)
      setTaskDefaults(res.defaults || {})

      // Select default model from filtered list
      const selected = recalcDefault(res, filteredModels)
      if (selected) setSelectedModelState(selected)
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

  // ── Set model for a specific task, using auto-routing if enabled ──────
  const setModelForTask = useCallback(async (taskType: string) => {
    const stored = getStoredModel()
    if (stored && availableModels.includes(stored)) {
      setSelectedModelState(stored)
      return
    }
    // Check task defaults from V2 mapping
    if (rawRes?.defaults?.[taskType] && availableModels.includes(rawRes.defaults[taskType])) {
      setSelectedModelState(rawRes.defaults[taskType])
      return
    }
    // Try V2 auto-routing
    if (v2AutoRouting) {
      try {
        const routeRes = await v2SelectModelForTask(taskType)
        if (routeRes.model?.id && availableModels.includes(routeRes.model.id)) {
          setSelectedModelState(routeRes.model.id)
          return
        }
      } catch {
        // fall through
      }
    }
    // Fallback to chat default or first
    const next = recalcDefault(rawRes || { installed: [] }, availableModels, taskType)
    if (next) setSelectedModelState(next)
  }, [availableModels, rawRes, v2AutoRouting, recalcDefault])

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
