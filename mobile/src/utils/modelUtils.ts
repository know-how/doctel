/**
 * Shared utilities for model capability display across mobile components.
 * Mirrors frontend/src/utils/modelUtils.ts
 */

import type { V2Provider, OllamaModelDetail } from "../types/api"

/**
 * Determine whether a model ID is a cloud/API model (vs a local Ollama model).
 * First checks V2 providers (authoritative), then falls back to model details
 * and well-known ID patterns.
 */
export function isCloudModel(
  modelId: string | undefined | null,
  modelDetails?: OllamaModelDetail[],
  v2Providers?: V2Provider[],
): boolean {
  if (!modelId) return false

  // 1) Check V2 providers (authoritative — same as Task Mapping source)
  if (v2Providers?.length) {
    for (const p of v2Providers) {
      for (const m of p.models || []) {
        if (m.id === modelId) return true
      }
    }
  }

  // 2) Namespaced model IDs (e.g. go/deepseek-v4-flash) are ALWAYS cloud.
  //    Ollama models use ":" (qwen3:4b), not "/", so this safely distinguishes.
  if (modelId.includes("/") && !modelId.includes(":")) {
    return true
  }

  // 3) Check model details from /api/models/available
  if (modelDetails?.length) {
    const entry = modelDetails.find((m) => m.name === modelId)
    if (entry) {
      return entry.size_human === "Cloud" || entry.size_human === "cloud"
    }
  }

  // 4) Fallback: check known cloud model ID patterns
  const id = modelId.toLowerCase()
  return (
    id === "gemini-api" ||
    id === "deepseek-api" ||
    id.startsWith("zen/") ||
    id.startsWith("go/") ||
    id.startsWith("huggingface/") ||
    id.startsWith("openai/") ||
    id.startsWith("anthropic/")
  )
}
