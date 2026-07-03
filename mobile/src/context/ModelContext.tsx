import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { getAvailableModels, getModelCapabilities } from "../api/client"

const MODEL_KEY = "docintel_selected_model"

interface ModelContextValue {
  selectedModel: string
  setSelectedModel: (model: string) => void
  availableModels: string[]
  loading: boolean
  modelCapabilities: Record<string, string[]>
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

  useEffect(() => {
    (async () => {
      try {
        const res: any = await getAvailableModels()
        const all: string[] = [...new Set([...(res.installed || []), ...(res.available || [])])]
        setAvailableModels(all)
        const stored = await getStoredModel()
        if (stored && all.includes(stored)) {
          setSelectedModelState(stored)
        } else if (all.length > 0) {
          setSelectedModelState(all[0])
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

  const setSelectedModel = useCallback((model: string) => {
    setSelectedModelState(model)
    AsyncStorage.setItem(MODEL_KEY, model).catch(() => {})
  }, [])

  return (
    <ModelContext.Provider value={{ selectedModel, setSelectedModel, availableModels, loading, modelCapabilities }}>
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
