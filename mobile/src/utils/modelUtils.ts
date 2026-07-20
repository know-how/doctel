/**
 * Shared utilities for model capability display across mobile components.
 * Mirrors frontend/src/utils/modelUtils.ts
 */

import type { V2Provider } from "../types/api"

const CLOUD_ID_PATTERNS = [
  "gemini",
  "deepseek",
  "zen/",
  "go/",
  "huggingface/",
  "openai/",
  "anthropic/",
  "cloud",
]

/**
 * Determine whether a model ID is a cloud/API model (vs a local Ollama model).
 * First checks V2 providers (authoritative), then falls back to well-known ID patterns.
 */
export function isCloudModel(
  modelId: string | undefined | null,
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

  // 3) Fallback: check known cloud model ID patterns
  const id = modelId.toLowerCase()
  return CLOUD_ID_PATTERNS.some((pattern) => id.startsWith(pattern) || id === pattern)
}
