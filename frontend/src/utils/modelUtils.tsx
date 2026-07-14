/**
 * Shared utilities for model capability display across frontend components.
 */

/** Map of capability key → display emoji + label */
export const CAPABILITY_META: Record<string, { emoji: string; label: string }> = {
  text:      { emoji: "💬", label: "Text" },
  vision:    { emoji: "👁️", label: "Vision" },
  audio:     { emoji: "🎤", label: "Audio" },
  code:      { emoji: "💻", label: "Code" },
  reasoning: { emoji: "🧠", label: "Reasoning" },
  embedding: { emoji: "📊", label: "Embedding" },
  fast:      { emoji: "⚡", label: "Fast" },
  large:     { emoji: "🐘", label: "Large" },
}

/** Ordered list of capability keys (for consistent rendering). */
export const CAPABILITY_ORDER = [
  "reasoning",
  "vision",
  "audio",
  "code",
  "fast",
  "large",
  "text",
  "embedding",
] as const

/** Render capability tags JSX elements. */
export function renderCapabilityTags(
  caps: string[] | undefined,
  colors: { text: string; border: string; bg: string; primary: string; textMuted: string },
): React.ReactNode[] {
  if (!caps || caps.length === 0) return []
  const items: React.ReactNode[] = []
  for (const key of CAPABILITY_ORDER) {
    if (caps.includes(key)) {
      const meta = CAPABILITY_META[key]
      if (meta) {
        items.push(
          <span
            key={key}
            title={meta.label}
            style={{
              fontSize: 10,
              padding: "1px 5px",
              borderRadius: 4,
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.bg,
              color: colors.textMuted,
              lineHeight: "1.4",
              whiteSpace: "nowrap",
            }}
          >
            {meta.emoji} {meta.label}
          </span>,
        )
      }
    }
  }
  return items
}

/** Build a display string for a capability set (e.g. "🧠 Vision · ⚡ Fast"). */
export function formatCapabilities(caps: string[] | undefined): string {
  if (!caps || caps.length === 0) return ""
  return CAPABILITY_ORDER
    .filter((k) => caps.includes(k))
    .map((k) => {
      const meta = CAPABILITY_META[k]
      return meta ? `${meta.emoji} ${meta.label}` : k
    })
    .join(" · ")
}

/** Map of icon-like symbol per capability for compact mobile use. */
export const CAPABILITY_ICONS: Record<string, string> = {
  reasoning: "🧠",
  vision: "👁️",
  audio: "🎤",
  code: "💻",
  fast: "⚡",
  large: "🐘",
  text: "💬",
  embedding: "📊",
}

// ── Cloud model detection ──────────────────────────────────────────────────

/**
 * Determine whether a model ID is a cloud/API model (vs a local Ollama model).
 * First checks V2 providers (authoritative), then falls back to model details
 * and well-known ID patterns.
 */
import type { OllamaModelDetail, V2Provider } from "../types/api"

export function isCloudModel(
  modelId: string | undefined | null,
  modelDetails: OllamaModelDetail[],
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
  const entry = modelDetails.find((m) => m.name === modelId)
  if (entry) {
    return entry.size_human === "Cloud" || entry.size_human === "cloud"
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
