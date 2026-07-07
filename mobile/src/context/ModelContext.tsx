import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { getAvailableModels, getModelCapabilities, v2GetTaskMapping, v2SelectModelForTask, v2GetVisibleChatModels } from "../api/client"
import type { V2Provider } from "../types/api"

const MODEL_KEY = "docintel_selected_model"
const TASK_DEFAULTS_KEY = "docintel_task_defaults"

interface ModelContextValue {
  selectedModel: string
  setSelectedModel: (model: string) => void
  availableModels: string[]
  loading: boolean
  modelCapabilities: Record<string, string[]>
  v2Providers: V2Provider[]
  v2AutoRouting: boolean
  taskDefaults: Record<string, string>
  setModelForTask: (taskType: string, modelId: string) => Promise<void>
}

const ModelContext = createContext<ModelContextValue | undefined>(undefined)

async function getStoredModel(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(MODEL_KEY)) || ""
  } catch {
    return ""
  }
}

async function getStoredTaskDefaults(): Promise<Record<string, string>> {
  try {
    const raw = await AsyncStorage.getItem(TASK_DEFAULTS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export function ModelProvider({ children }: { children: ReactNode }) {
  const [selectedModel, setSelectedModelState] = useState("")
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [modelCapabilities, setModelCapabilities] = useState<Record<string, string[]>>({})
  const [v2Providers, setV2Providers] = useState<V2Provider[]>([])
  const [v2AutoRouting, setV2AutoRouting] = useState(false)
  const [taskDefaults, setTaskDefaults] = useState<Record<string, string>>({})

  useEffect(() => {
    (async () => {
      try {
        const res: any = await getAvailableModels()
        const all: string[] = [...new Set([...(res.installed || []), ...(res.available || [])])]

        // Build visible V2 model set from v2GetVisibleChatModels
        let visibleV2Models: Set<string> | null = null
        let v2ManagedModels: Set<string> | null = null
        if (res.v2_providers && res.v2_providers.length > 0) {
          v2ManagedModels = new Set<string>()
          for (const p of res.v2_providers as V2Provider[]) {
            for (const m of p.models || []) {
              v2ManagedModels.add(m.id)
            }
          }
          try {
            const visRes = await v2GetVisibleChatModels()
            visibleV2Models = new Set(visRes.models.map((m) => m.id))
          } catch {
            visibleV2Models = new Set(v2ManagedModels)
          }
          // Filter: keep models not in V2 or that are visible in V2
          const filtered = all.filter((modelId) => {
            if (!v2ManagedModels!.has(modelId)) return true
            return visibleV2Models!.has(modelId)
          })
          setAvailableModels(filtered)
        } else {
          setAvailableModels(all)
        }

        const stored = await getStoredModel()
        if (res.v2_providers) {
          setV2Providers(res.v2_providers)
        }
        if (typeof res.v2_auto_routing === "boolean") {
          setV2AutoRouting(res.v2_auto_routing)
        }
        const currentModels = v2ManagedModels ? all.filter((modelId) => {
          if (!v2ManagedModels!.has(modelId)) return true
          return visibleV2Models!.has(modelId)
        }) : all
        if (stored && currentModels.includes(stored)) {
          setSelectedModelState(stored)
        } else if (currentModels.length > 0) {
          setSelectedModelState(currentModels[0])
        }
      } catch {
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  useEffect(() => {
    (async () => {
      try {
        const caps: any = await getModelCapabilities()
        setModelCapabilities(caps.capabilities || caps || {})
      } catch {}
    })()
  }, [])

  useEffect(() => {
    (async () => {
      try {
        const mapping = await v2GetTaskMapping()
        if (mapping.taskMapping) {
          const defaults: Record<string, string> = {}
          for (const [taskType, m] of Object.entries(mapping.taskMapping)) {
            const entry = m as any
            defaults[taskType] = entry.modelId || entry.model_id || ""
          }
          setTaskDefaults(defaults)
        }
      } catch {}
    })()
  }, [])

  const setSelectedModel = useCallback((model: string) => {
    setSelectedModelState(model)
    AsyncStorage.setItem(MODEL_KEY, model).catch(() => {})
  }, [])

  const setModelForTask = useCallback(async (taskType: string, modelId: string) => {
    try {
      await v2SelectModelForTask(taskType)
      setTaskDefaults((prev) => {
        const next = { ...prev, [taskType]: modelId }
        AsyncStorage.setItem(TASK_DEFAULTS_KEY, JSON.stringify(next)).catch(() => {})
        return next
      })
    } catch {}
  }, [])

  return (
    <ModelContext.Provider
      value={{
        selectedModel,
        setSelectedModel,
        availableModels,
        loading,
        modelCapabilities,
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
