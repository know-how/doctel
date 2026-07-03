import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { getAvailableModels, getModelCapabilities, getModelLabels } from "../api/client"
import type { OllamaModelDetail } from "../types/api"

const MODEL_KEY = "docintel_selected_model"

interface ModelContextValue {
  selectedModel: string
  setSelectedModel: (model: string) => void
  availableModels: string[]
  modelCapabilities: Record<string, string[]>
  modelLabels: Record<string, string>
  modelDetails: OllamaModelDetail[]
  offline: boolean
  loading: boolean
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

  useEffect(() => {
    (async () => {
      try {
        const [res, capsRes, labelsRes] = await Promise.all([
          getAvailableModels(),
          getModelCapabilities().catch(() => ({ capabilities: {} })),
          getModelLabels().catch(() => ({ labels: {} })),
        ])
        const all: string[] = [...new Set([...(res.installed || []), ...(res.available || [])])]
        setAvailableModels(all)
        setModelDetails(res.models || [])
        setOffline(Boolean(res.offline))
        // Merge capabilities: registry first, then augment with model detail caps
        const mergedCaps = { ...(capsRes.capabilities || {}) }
        for (const detail of (res.models || [])) {
          if (detail.capabilities && detail.capabilities.length > 0 && !mergedCaps[detail.name]) {
            mergedCaps[detail.name] = detail.capabilities
          }
        }
        setModelCapabilities(mergedCaps)
        setModelLabels(labelsRes.labels || {})
        // Priority: stored user preference > chat task default > default_model > first available
        const stored = getStoredModel()
        const chatDefault = res.defaults?.["chat"]
        if (stored && all.includes(stored)) {
          setSelectedModelState(stored)
        } else if (chatDefault && all.includes(chatDefault)) {
          setSelectedModelState(chatDefault)
        } else if (res.default_model && all.includes(res.default_model)) {
          setSelectedModelState(res.default_model)
        } else if (all.length > 0) {
          setSelectedModelState(all[0])
        }
      } catch {
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const setSelectedModel = useCallback((model: string) => {
    setSelectedModelState(model)
    try { localStorage.setItem(MODEL_KEY, model) } catch {}
  }, [])

  return (
    <ModelContext.Provider value={{ selectedModel, setSelectedModel, availableModels, modelCapabilities, modelLabels, modelDetails, offline, loading }}>
      {children}
    </ModelContext.Provider>
  )
}

export function useModel(): ModelContextValue {
  const ctx = useContext(ModelContext)
  if (!ctx) throw new Error("useModel must be used within a ModelProvider")
  return ctx
}
