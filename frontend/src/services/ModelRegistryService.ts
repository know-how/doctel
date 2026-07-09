/**
 * ModelRegistryService.ts
 * 
 * Centralized service for model registry access.
 * Single source of truth for all model selection across the application.
 * 
 * All pages must use this service to ensure consistent:
 * - Model inventory
 * - Provider grouping
 * - Filtering logic
 * - Default model selection
 */

import { getAvailableModels, getModelCapabilities, getModelLabels, v2GetCatalog } from "../api/client"
import type { V2Provider, V2ModelMetadata, ModelsAvailableResponse, V2CatalogResponse } from "../types/api"

// Capability display configuration
export const CAPABILITY_CONFIG: Record<string, { 
  label: string 
  icon: string
  color: string 
  bgColor: string 
}> = {
  chat: { label: "Text", icon: "📄", color: "#4F7CFF", bgColor: "rgba(79,124,255,0.15)" },
  text: { label: "Text", icon: "📄", color: "#4F7CFF", bgColor: "rgba(79,124,255,0.15)" },
  vision: { label: "Vision", icon: "🖼", color: "#A855F7", bgColor: "rgba(168,85,247,0.15)" },
  image: { label: "Image", icon: "🖼", color: "#A855F7", bgColor: "rgba(168,85,247,0.15)" },
  audio: { label: "Audio", icon: "🎤", color: "#14B8A6", bgColor: "rgba(20,184,166,0.15)" },
  video: { label: "Video", icon: "🎥", color: "#EC4899", bgColor: "rgba(236,72,153,0.15)" },
  code: { label: "Code", icon: "💻", color: "#22C55E", bgColor: "rgba(34,197,94,0.15)" },
  reasoning: { label: "Reasoning", icon: "🧠", color: "#EAB308", bgColor: "rgba(234,179,8,0.15)" },
  embedding: { label: "Embedding", icon: "📌", color: "#6B7280", bgColor: "rgba(107,114,128,0.15)" },
  fast: { label: "Fast", icon: "⚡", color: "#F97316", bgColor: "rgba(249,115,22,0.15)" },
  large: { label: "Large", icon: "🐘", color: "#EC4899", bgColor: "rgba(236,72,153,0.15)" },
  tools: { label: "Tools", icon: "🔧", color: "#6366F1", bgColor: "rgba(99,102,241,0.15)" },
}

// Provider icon mapping
export const PROVIDER_ICONS: Record<string, string> = {
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

export interface ModelRegistry {
  // Providers with their models
  providers: V2Provider[]
  
  // Flat list of all model IDs (for backwards compatibility)
  allModelIds: string[]
  
  // Models that can be selected (active, installed, available)
  selectableModelIds: string[]
  
  // Map of model ID to full metadata
  modelMetadata: Map<string, V2ModelMetadata & { provider: V2Provider }>
  
  // Task defaults from Task Mapping
  taskDefaults: Record<string, string>
  
  // Capabilities per model
  capabilities: Record<string, string[]>
  
  // Labels/names per model
  labels: Record<string, string>
  
  // Loading state
  loading: boolean
  
  // Error if any
  error: string | null
  
  // Raw response for advanced use
  rawResponse: ModelsAvailableResponse | null
}

let cachedRegistry: ModelRegistry | null = null
let lastFetchTime = 0
const CACHE_TTL_MS = 30000 // 30 seconds

/**
 * Get the full model registry.
 * Uses caching to avoid redundant API calls.
 */
export async function getModelRegistry(forceRefresh = false): Promise<ModelRegistry> {
  const now = Date.now()
  
  if (!forceRefresh && cachedRegistry && (now - lastFetchTime) < CACHE_TTL_MS) {
    return cachedRegistry
  }
  
  try {
    const [modelsRes, capsRes, labelsRes] = await Promise.all([
      getAvailableModels(),
      getModelCapabilities().catch(() => ({ capabilities: {} })),
      getModelLabels().catch(() => ({ labels: {} })),
    ])
    
    const v2Providers = modelsRes.v2_providers || []
    const allModels = modelsRes.models || []
    
    // Build provider-grouped structure
    const providers: V2Provider[] = [...v2Providers]
    
    // Add Ollama as a provider if there are local models not in v2
    const v2ModelIds = new Set(v2Providers.flatMap(p => (p.models || []).map(m => m.id)))
    const localOnlyModels = modelsRes.installed?.filter(id => !v2ModelIds.has(id)) || []
    
    if (localOnlyModels.length > 0) {
      providers.push({
        id: "ollama",
        name: "Ollama",
        vendor: "ollama",
        base_url: "http://localhost:11434",
        api_key_env: "",
        status: "active",
        description: "Local models",
        icon: "cpu",
        order: 999,
        models: localOnlyModels.map(id => {
          const detail = allModels.find(m => m.name === id)
          return {
            id,
            name: formatModelName(id),
            state: "active",
            contextWindow: detail?.max_input_tokens || 4096,
            pricingTier: "local",
            license: "Open Source",
            capabilities: detail?.capabilities || ["chat"],
          }
        }),
      })
    }
    
    // Build metadata map
    const modelMetadata = new Map<string, V2ModelMetadata & { provider: V2Provider }>()
    for (const provider of providers) {
      for (const model of provider.models || []) {
        modelMetadata.set(model.id, { ...model, provider })
      }
    }
    
    // Get all model IDs
    const allModelIds = Array.from(modelMetadata.keys())
    
    // Get selectable models (active, installed, available - NOT maintenance)
    const selectableModelIds = allModelIds.filter(id => {
      const meta = modelMetadata.get(id)
      if (!meta) return false
      return ["active", "installed", "available"].includes(meta.state)
    })
    
    // Merge capabilities
    const capabilities: Record<string, string[]> = { ...(capsRes.capabilities || {}) }
    for (const [id, meta] of modelMetadata) {
      if (meta.capabilities?.length && !capabilities[id]) {
        capabilities[id] = meta.capabilities
      }
    }
    
    cachedRegistry = {
      providers,
      allModelIds,
      selectableModelIds,
      modelMetadata,
      taskDefaults: modelsRes.defaults || {},
      capabilities,
      labels: labelsRes.labels || {},
      loading: false,
      error: null,
      rawResponse: modelsRes,
    }
    
    lastFetchTime = now
    return cachedRegistry
    
  } catch (error: any) {
    return {
      providers: [],
      allModelIds: [],
      selectableModelIds: [],
      modelMetadata: new Map(),
      taskDefaults: {},
      capabilities: {},
      labels: {},
      loading: false,
      error: error.message || "Failed to load model registry",
      rawResponse: null,
    }
  }
}

/**
 * Get the default model for a specific task type.
 * Priority: Task Mapping > Auto Routing > First selectable
 */
export function getDefaultModelForTask(
  registry: ModelRegistry,
  taskType: string,
  options?: {
    storedPreference?: string
    capabilityFilter?: string
  }
): string | null {
  const { storedPreference, capabilityFilter } = options || {}
  
  // 1. Check stored user preference
  if (storedPreference && registry.selectableModelIds.includes(storedPreference)) {
    return storedPreference
  }
  
  // 2. Check Task Mapping default
  const taskDefault = registry.taskDefaults[taskType]
  if (taskDefault && registry.selectableModelIds.includes(taskDefault)) {
    return taskDefault
  }
  
  // 3. Filter by capability if specified
  let candidates = registry.selectableModelIds
  if (capabilityFilter) {
    candidates = candidates.filter(id => {
      const caps = registry.capabilities[id] || []
      return caps.includes(capabilityFilter)
    })
  }
  
  // 4. Return first selectable
  if (candidates.length > 0) {
    return candidates[0]
  }
  
  return null
}

/**
 * Format model ID to display name
 */
export function formatModelName(id: string): string {
  return id
    .split(/[-_:]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ")
}

/**
 * Get provider icon emoji
 */
export function getProviderIcon(vendor?: string): string {
  if (!vendor) return "🤖"
  return PROVIDER_ICONS[vendor.toLowerCase()] || "🤖"
}

/**
 * Get capability display info
 */
export function getCapabilityDisplay(capability: string) {
  return CAPABILITY_CONFIG[capability.toLowerCase()] || {
    label: capability,
    icon: "🔧",
    color: "#9CA3AF",
    bgColor: "rgba(156,163,175,0.15)",
  }
}

/**
 * Get capability icons for a model
 */
export function getCapabilityIcons(capabilities: string[] = []): string {
  return capabilities
    .slice(0, 4)
    .map(cap => getCapabilityDisplay(cap).icon)
    .join(" ")
}

/**
 * Invalidate the cache (call after model management changes)
 */
export function invalidateModelCache() {
  cachedRegistry = null
  lastFetchTime = 0
}

/**
 * Get catalog for admin pages (Task Mapping, etc.)
 * This is the enriched catalog with health data
 */
export async function getAdminCatalog(): Promise<V2CatalogResponse> {
  return await v2GetCatalog()
}
