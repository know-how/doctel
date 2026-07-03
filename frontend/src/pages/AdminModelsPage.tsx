import React, { useEffect, useState, useCallback, useRef } from "react"
import {
  getAvailableModels,
  setDefaultModel,
  startModelPull,
  getModelPullStatus,
  getModelLabels,
  getRegistryProviders,
  addRegistryProvider,
  updateRegistryProvider,
  deleteRegistryProvider,
  addRegistryModel,
  deleteRegistryModel,
  getRegistryFlat,
  adminSetIntegrations,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { OllamaModelDetail, RegistryProvider, RegistryModelEntry, AddRegistryProviderPayload, AddRegistryModelPayload } from "../types/api"

interface ModelInfo {
  id: string
  name?: string
  status?: string
  size?: string
  tasks?: string[]
  size_human?: string
  family?: string
  parameter_size?: string
  quantization_level?: string
  ready?: boolean
}

interface PullProgress {
  model: string
  status: string
  completed?: number
  total?: number
}

const TASK_TYPES = [
  { key: "chat", label: "Chat" },
  { key: "extraction", label: "Extraction" },
  { key: "summary", label: "Summary" },
  { key: "classification", label: "Classification" },
]

const statusColors: Record<string, string> = {
  ready: "#22C55E",
  downloading: "#5B88FF",
  failed: "#EF4444",
  pulling: "#F59E0B",
}

export const AdminModelsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [tab, setTab] = useState<"installed" | "available" | "registry">("installed")
  const [models, setModels] = useState<ModelInfo[]>([])
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [defaults, setDefaults] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pullProgress, setPullProgress] = useState<Record<string, PullProgress>>({})
  const [pullingModel, setPullingModel] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Registry state
  const [registryProviders, setRegistryProviders] = useState<RegistryProvider[]>([])
  const [registryLoading, setRegistryLoading] = useState(false)
  const [showAddProvider, setShowAddProvider] = useState(false)
  const [editingProvider, setEditingProvider] = useState<RegistryProvider | null>(null)

  // API Keys state
  const apiKeyFields = [
    { key: "gemini_api_key", label: "Gemini API Key", placeholder: "AIza...", secret: true },
    { key: "deepseek_api_key", label: "DeepSeek API Key", placeholder: "sk-...", secret: true },
    { key: "deepseek_base_url", label: "DeepSeek Base URL", placeholder: "https://opencode.ai/zen/v1", secret: false },
    { key: "deepseek_model", label: "DeepSeek Model", placeholder: "deepseek-v4-flash-free", secret: false },
    { key: "ollama_base_url", label: "Ollama Base URL", placeholder: "http://localhost:11434", secret: false },
  ]
  const [apiKeyValues, setApiKeyValues] = useState<Record<string, string>>({})
  const [apiKeyStatus, setApiKeyStatus] = useState<string | null>(null)
  const [cloudModels, setCloudModels] = useState<ModelInfo[]>([])
  const [addingModelToProvider, setAddingModelToProvider] = useState<string | null>(null)
  const [providerForm, setProviderForm] = useState<AddRegistryProviderPayload>({
    name: "", vendor: "", base_url: "", api_key_env: "",
  })
  const [modelForm, setModelForm] = useState<AddRegistryModelPayload>({
    id: "", name: "", vision: false, toolCalling: false, context_window: 4096, capabilities: [],
  })

  const loadModels = async () => {
    try {
      setLoading(true)
      setError(null)
      const [modelRes, labelRes] = await Promise.all([
        getAvailableModels(),
        getModelLabels().catch(() => ({ labels: {} })),
      ])
      const modelDetails: OllamaModelDetail[] = (modelRes as any).models ?? []
      const detailMap = new Map<string, OllamaModelDetail>()
      for (const d of modelDetails) {
        detailMap.set(d.name, d)
      }
      const installedNames: string[] = modelRes.installed ?? []
      const availableNames: string[] = modelRes.available ?? []
      const buildModelInfo = (names: string[]): ModelInfo[] =>
        names.map((id) => {
          const d = detailMap.get(id)
          return {
            id,
            name: d?.parameter_size || undefined,
            size: d?.size_human || undefined,
            size_human: d?.size_human,
            family: d?.family,
            parameter_size: d?.parameter_size,
            quantization_level: d?.quantization_level,
            ready: d?.ready ?? false,
            status: d?.ready ? "ready" : (d ? "available" : undefined),
          }
        })
      setModels(buildModelInfo(installedNames))
      setAvailableModels(buildModelInfo(availableNames))
      setDefaults(modelRes.defaults ?? {})
      setLabels(labelRes.labels ?? {})
      // Load persisted defaults from V2 task mapping
      try {
        const v2res = await fetch("/api/models/v2/task-mapping", { headers: { Authorization: "Bearer " + (localStorage.getItem("docintel_auth_token") ?? "") } })
        if (v2res.ok) {
          const v2data = await v2res.json()
          const taskMapping = v2data.taskMapping ?? {}
          const flatDefaults: Record<string, string> = {}
          for (const [taskType, mapping] of Object.entries(taskMapping)) {
            const m = mapping as any
            if (m.modelId) {
              flatDefaults[taskType] = m.modelId
            }
          }
          if (Object.keys(flatDefaults).length > 0) {
            setDefaults((prev) => ({ ...prev, ...flatDefaults }))
          }
        }
      } catch {}
      // Extract cloud/API models from available list
      const allModelNames = [...new Set([...installedNames, ...availableNames])]
      const cloudOnes = allModelNames
        .filter((name) => {
          if (name === "gemini-api" || name === "deepseek-api") return true
          if (name.startsWith("zen/") || name.startsWith("go/")) return true
          const detail = detailMap.get(name)
          return detail?.size_human === "Cloud"
        })
        .map((id) => {
          const d = detailMap.get(id)
          return {
            id,
            name: labels[id] ?? d?.parameter_size ?? undefined,
            family: d?.family,
            size_human: d?.size_human,
            ready: true,
            status: "ready",
          }
        })
      setCloudModels(cloudOnes)
    } catch (e: any) {
      setError(e.message ?? "Failed to load models")
    } finally {
      setLoading(false)
    }
  }

  const loadRegistry = async () => {
    try {
      setRegistryLoading(true)
      const data = await getRegistryProviders()
      setRegistryProviders(data.providers ?? [])
    } catch (e: any) {
      console.error("Failed to load registry:", e)
    } finally {
      setRegistryLoading(false)
    }
  }

  useEffect(() => {
    loadModels()
  }, [])

  useEffect(() => {
    if (tab === "registry") {
      loadRegistry()
    }
  }, [tab])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const handleSetDefault = async (taskType: string, modelId: string) => {
    try {
      setError(null)
      await setDefaultModel(taskType, modelId)
      setDefaults((prev) => ({ ...prev, [taskType]: modelId }))
    } catch (e: any) {
      setError(e.message ?? "Failed to set default model")
    }
  }

  const handleSaveApiKeys = async () => {
    try {
      setApiKeyStatus(null)
      const payload: Record<string, string> = {}
      for (const field of apiKeyFields) {
        const val = apiKeyValues[field.key]?.trim()
        if (val) {
          payload[field.key] = val
        }
      }
      if (Object.keys(payload).length === 0) {
        setApiKeyStatus("No values to save")
        return
      }
      const res = await adminSetIntegrations(payload)
      setApiKeyStatus("API keys saved successfully")
      setTimeout(() => setApiKeyStatus(null), 3000)
    } catch (e: any) {
      setApiKeyStatus("Error: " + (e.message ?? "Failed to save"))
    }
  }

  const handlePull = async (model: string) => {
    try {
      setError(null)
      setPullingModel(model)
      const res = await startModelPull(model, true)
      setPullProgress((prev) => ({ ...prev, [model]: { model, status: res.status ?? "downloading", completed: 0, total: 100 } }))

      // Poll for progress
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const status = await getModelPullStatus(model)
          setPullProgress((prev) => ({
            ...prev,
            [model]: {
              model,
              status: status.status ?? "downloading",
              completed: status.completed ?? prev[model]?.completed ?? 0,
              total: status.total ?? prev[model]?.total ?? 100,
            },
          }))
          if (status.status === "success" || status.status === "ready") {
            if (pollRef.current) clearInterval(pollRef.current)
            setPullingModel(null)
            loadModels()
          }
        } catch {
          // ignore polling errors
        }
      }, 2000)
    } catch (e: any) {
      setError(e.message ?? "Pull failed")
      setPullingModel(null)
    }
  }

  // ── Registry CRUD handlers ──────────────────────

  const resetProviderForm = () => setProviderForm({ name: "", vendor: "", base_url: "", api_key_env: "" })
  const resetModelForm = () => setModelForm({ id: "", name: "", vision: false, toolCalling: false, context_window: 4096, capabilities: [] })

  const handleAddProvider = async () => {
    if (!providerForm.name.trim()) return
    try {
      setError(null)
      await addRegistryProvider(providerForm)
      setShowAddProvider(false)
      resetProviderForm()
      loadRegistry()
    } catch (e: any) {
      setError(e.message ?? "Failed to add provider")
    }
  }

  const handleEditProvider = async () => {
    if (!editingProvider || !providerForm.name.trim()) return
    try {
      setError(null)
      await updateRegistryProvider(editingProvider.id, {
        name: providerForm.name,
        vendor: providerForm.vendor,
        base_url: providerForm.base_url,
        api_key_env: providerForm.api_key_env,
      })
      setEditingProvider(null)
      resetProviderForm()
      loadRegistry()
    } catch (e: any) {
      setError(e.message ?? "Failed to update provider")
    }
  }

  const handleDeleteProvider = async (providerId: string) => {
    if (!window.confirm("Delete this provider and all its models?")) return
    try {
      setError(null)
      await deleteRegistryProvider(providerId)
      loadRegistry()
    } catch (e: any) {
      setError(e.message ?? "Failed to delete provider")
    }
  }

  const handleAddModel = async (providerId: string) => {
    if (!modelForm.id.trim()) return
    try {
      setError(null)
      await addRegistryModel(providerId, modelForm)
      setAddingModelToProvider(null)
      resetModelForm()
      loadRegistry()
    } catch (e: any) {
      setError(e.message ?? "Failed to add model")
    }
  }

  const handleDeleteModel = async (providerId: string, modelId: string) => {
    if (!window.confirm(`Delete model "${modelId}"?`)) return
    try {
      setError(null)
      await deleteRegistryModel(providerId, modelId)
      loadRegistry()
    } catch (e: any) {
      setError(e.message ?? "Failed to delete model")
    }
  }

  const renderStatusBadge = (status: string) => {
    const col = statusColors[status] ?? c.textMuted
    return (
      <span
        style={{
          display: "inline-block",
          padding: "2px 10px",
          borderRadius: t.radii.full,
          fontSize: 11,
          fontWeight: 700,
          backgroundColor: col + "22",
          color: col,
          border: `1px solid ${col}44`,
          textTransform: "capitalize",
        }}
      >
        {status}
      </span>
    )
  }

  const displayedModels = tab === "installed" ? models : availableModels

  // ── Registry UI helpers ──────────────────────────

  const renderCapBadges = (m: RegistryModelEntry) => {
    const badges: { label: string; show: boolean }[] = [
      { label: "🧠 Reasoning", show: m.capabilities?.includes("reasoning") ?? false },
      { label: "👁️ Vision", show: m.vision ?? false },
      { label: "🛠️ Tool Calling", show: m.toolCalling ?? false },
      { label: "🌐 Web Search", show: m.capabilities?.includes("web_search") ?? false },
    ]
    return badges
      .filter((b) => b.show)
      .map((b) => (
        <span key={b.label} style={{
          fontSize: 10, fontWeight: 700,
          padding: "1px 6px", borderRadius: t.radii.sm,
          backgroundColor: c.primary + "18", color: c.primary,
          border: `1px solid ${c.primary}33`,
        }}>
          {b.label}
        </span>
      ))
  }

  const renderRegistry = () => {
    if (registryLoading) {
      return (
        <div style={{ display: "grid", gap: t.spacing.sm }}>
          {[1, 2].map((i) => (
            <div key={i} style={{
              borderRadius: t.radii.md, border: `1px solid ${c.border}`,
              padding: t.spacing.lg, backgroundColor: c.cardBg, height: 80,
            }} />
          ))}
        </div>
      )
    }
    if (registryProviders.length === 0) {
      return (
        <div style={{ textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary, color: c.textSecondary }}>
          No providers configured. Click "Add Provider" to register an AI provider.
        </div>
      )
    }
    return (
      <div style={{ display: "grid", gap: t.spacing.md }}>
        {registryProviders.map((p) => (
          <div key={p.id} style={{
            borderRadius: t.radii.lg, border: `1px solid ${c.border}`,
            padding: t.spacing.lg, backgroundColor: c.cardBg,
          }}>
            {/* Provider header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: t.spacing.sm }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: c.text }}>{p.name}</span>
                  {p.vendor && <span style={{ fontSize: 11, color: c.textSecondary, backgroundColor: c.surface, padding: "1px 8px", borderRadius: t.radii.sm }}>{p.vendor}</span>}
                </div>
                <div style={{ fontSize: 11, color: c.textSecondary, marginTop: 2 }}>
                  {p.base_url && <span>URL: {p.base_url}</span>}
                  {p.api_key_env && <span> · Key: {p.api_key_env}</span>}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={() => { setEditingProvider(p); setProviderForm({ name: p.name, vendor: p.vendor ?? "", base_url: p.base_url ?? "", api_key_env: p.api_key_env ?? "" }); setShowAddProvider(true) }}
                  style={{ padding: "4px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.surface, color: c.text, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                  Edit
                </button>
                <button onClick={() => handleDeleteProvider(p.id)}
                  style={{ padding: "4px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.error}44`, backgroundColor: c.error + "18", color: c.error, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                  Delete
                </button>
              </div>
            </div>

            {/* Models list */}
            {p.models && p.models.length > 0 && (
              <div style={{ marginTop: t.spacing.sm, borderTop: `1px solid ${c.border}`, paddingTop: t.spacing.sm }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 6 }}>Models ({p.models.length})</div>
                {p.models.map((m) => (
                  <div key={m.id} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "6px 10px", borderRadius: t.radii.sm, marginBottom: 4,
                    backgroundColor: c.surface,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: c.text }}>{m.id}</span>
                      {m.name && <span style={{ fontSize: 11, color: c.textSecondary }}>({m.name})</span>}
                      <span style={{ fontSize: 10, color: c.textSecondary }}>{m.context_window ?? "-"} ctx</span>
                      <div style={{ display: "flex", gap: 3 }}>{renderCapBadges(m)}</div>
                    </div>
                    <button onClick={() => handleDeleteModel(p.id, m.id)}
                      style={{ padding: "2px 8px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: "transparent", color: c.textMuted, cursor: "pointer", fontSize: 10, fontWeight: 600 }}>
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add model button */}
            {addingModelToProvider === p.id ? (
              <div style={{ marginTop: t.spacing.sm, borderTop: `1px solid ${c.border}`, paddingTop: t.spacing.sm }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 6 }}>Add Model to {p.name}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <input placeholder="Model ID *" value={modelForm.id} onChange={(e) => setModelForm((f) => ({ ...f, id: e.target.value }))}
                    style={{ flex: "1 1 140px", padding: "6px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 12 }} />
                  <input placeholder="Display name" value={modelForm.name ?? ""} onChange={(e) => setModelForm((f) => ({ ...f, name: e.target.value }))}
                    style={{ flex: "1 1 140px", padding: "6px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 12 }} />
                  <input placeholder="Context window" type="number" value={modelForm.context_window} onChange={(e) => setModelForm((f) => ({ ...f, context_window: parseInt(e.target.value) || 4096 }))}
                    style={{ flex: "0 0 100px", padding: "6px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 12 }} />
                </div>
                <div style={{ display: "flex", gap: 12, marginTop: 6, alignItems: "center" }}>
                  <label style={{ fontSize: 12, color: c.text, display: "flex", alignItems: "center", gap: 4 }}>
                    <input type="checkbox" checked={modelForm.vision} onChange={(e) => setModelForm((f) => ({ ...f, vision: e.target.checked }))} /> Vision
                  </label>
                  <label style={{ fontSize: 12, color: c.text, display: "flex", alignItems: "center", gap: 4 }}>
                    <input type="checkbox" checked={modelForm.toolCalling} onChange={(e) => setModelForm((f) => ({ ...f, toolCalling: e.target.checked }))} /> Tool Calling
                  </label>
                  <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
                    <button onClick={() => { setAddingModelToProvider(null); resetModelForm() }}
                      style={{ padding: "4px 12px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: "transparent", color: c.text, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                      Cancel
                    </button>
                    <button onClick={() => handleAddModel(p.id)}
                      style={{ padding: "4px 12px", borderRadius: t.radii.sm, border: "none", backgroundColor: c.primary, color: "#FFF", cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                      Save
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <button onClick={() => { setAddingModelToProvider(p.id); resetModelForm() }}
                style={{ marginTop: t.spacing.sm, padding: "4px 12px", borderRadius: t.radii.sm, border: `1px dashed ${c.border}`, backgroundColor: "transparent", color: c.primary, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                + Add Model
              </button>
            )}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Models</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Manage AI models and configure defaults per task type.</p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Default model assignments — only show on non-registry tabs */}
      {tab !== "registry" && (
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
          <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Default models per task</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {TASK_TYPES.map((tt) => (
              <div key={tt.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: c.text, minWidth: 100, textTransform: "capitalize" }}>
                  {tt.label}
                </span>
                <select
                  value={defaults[tt.key] ?? ""}
                  onChange={(e) => handleSetDefault(tt.key, e.target.value)}
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    borderRadius: t.radii.sm,
                    border: `1px solid ${c.border}`,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 13,
                  }}
                >
                  <option value="" style={{ backgroundColor: c.bgSecondary, color: c.text }}>— Select —</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id} style={{ backgroundColor: c.bgSecondary, color: c.text }}>
                      {labels[m.id] ?? m.name ?? m.id}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── API Keys Section ───────────────────────────────────────────── */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>
          Provider API Keys
        </h3>
        <p style={{ fontSize: 12, color: c.textSecondary, margin: `0 0 ${t.spacing.sm} 0` }}>
          Set API keys for cloud providers. Keys are stored in the database and override .env values.
        </p>
        {apiKeyFields.map((field) => (
          <div key={field.key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: c.text, minWidth: 140, flexShrink: 0 }}>{field.label}</label>
            <input
              type={field.secret ? "password" : "text"}
              placeholder={field.placeholder}
              value={apiKeyValues[field.key] ?? ""}
              onChange={(e) => setApiKeyValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
              style={{
                flex: 1,
                padding: "6px 10px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
                fontFamily: field.secret ? "monospace" : "inherit",
              }}
            />
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button onClick={handleSaveApiKeys}
            style={{ padding: "6px 16px", borderRadius: t.radii.sm, border: "none", backgroundColor: c.primary, color: "#FFF", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
            Save API Keys
          </button>
          {apiKeyStatus && (
            <span style={{ fontSize: 12, color: apiKeyStatus.includes("Error") ? c.error : "#22C55E", alignSelf: "center" }}>
              {apiKeyStatus}
            </span>
          )}
        </div>
      </div>

      {/* ── Cloud Models Section ───────────────────────────────────────── */}
      {cloudModels.length > 0 && (
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
          <h3 style={{ margin: `0 0 ${t.spacing.sm} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>
            Available Cloud Models ({cloudModels.length})
          </h3>
          <p style={{ fontSize: 12, color: c.textSecondary, margin: `0 0 ${t.spacing.sm} 0` }}>
            These models are available via configured cloud providers and can be selected in chat.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {cloudModels.map((m) => {
              const isGemini = m.id === "gemini-api"
              const isDeepseek = m.id === "deepseek-api"
              const isZen = m.id.startsWith("zen/") || m.id.startsWith("go/")
              return (
                <span key={m.id} style={{
                  display: "inline-flex", alignItems: "center", gap: 4,
                  padding: "3px 10px", borderRadius: t.radii.full,
                  fontSize: 11, fontWeight: 600,
                  border: `1px solid ${c.border}`,
                  backgroundColor: isGemini ? "#1a73e8" + "18" : isDeepseek ? "#6366f1" + "18" : isZen ? "#10b981" + "18" : c.surface,
                  color: isGemini ? "#1a73e8" : isDeepseek ? "#6366f1" : isZen ? "#10b981" : c.text,
                }}>
                  {labels[m.id] ?? m.name ?? m.id}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* Model list header with tabs */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.md }}>
        <div style={{ display: "flex", gap: 2, borderRadius: t.radii.md, border: `1px solid ${c.border}`, padding: 2, backgroundColor: c.surface }}>
          <button
            onClick={() => setTab("installed")}
            style={{
              padding: "6px 16px",
              borderRadius: t.radii.sm,
              border: "none",
              backgroundColor: tab === "installed" ? c.primary : "transparent",
              color: tab === "installed" ? "#FFFFFF" : c.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Installed ({models.length})
          </button>
          <button
            onClick={() => setTab("available")}
            style={{
              padding: "6px 16px",
              borderRadius: t.radii.sm,
              border: "none",
              backgroundColor: tab === "available" ? c.primary : "transparent",
              color: tab === "available" ? "#FFFFFF" : c.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Available ({availableModels.length})
          </button>
          <button
            onClick={() => setTab("registry")}
            style={{
              padding: "6px 16px",
              borderRadius: t.radii.sm,
              border: "none",
              backgroundColor: tab === "registry" ? c.primary : "transparent",
              color: tab === "registry" ? "#FFFFFF" : c.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Registry ({registryProviders.length})
          </button>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {tab === "registry" && (
            <button
              onClick={() => { setShowAddProvider(true); setEditingProvider(null); resetProviderForm() }}
              style={{
                padding: "6px 14px",
                borderRadius: t.radii.sm,
                border: "none",
                backgroundColor: c.primary,
                color: "#FFFFFF",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              + Add Provider
            </button>
          )}
          <button
            onClick={() => tab === "registry" ? loadRegistry() : loadModels()}
            disabled={loading || registryLoading}
            style={{
              padding: "6px 14px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.text,
              cursor: (loading || registryLoading) ? "default" : "pointer",
              fontSize: 12,
              fontWeight: 600,
              opacity: (loading || registryLoading) ? 0.5 : 1,
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      {tab === "registry" ? (
        renderRegistry()
      ) : loading ? (
        <div style={{ display: "grid", gap: t.spacing.sm }}>
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                borderRadius: t.radii.md,
                border: `1px solid ${c.border}`,
                padding: t.spacing.lg,
                backgroundColor: c.cardBg,
                height: 56,
              }}
            />
          ))}
        </div>
      ) : displayedModels.length === 0 ? (
        <div style={{ textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary, color: c.textSecondary }}>
          {tab === "installed" ? "No installed models." : "No additional models available."}
        </div>
      ) : (
        <div style={{ display: "grid", gap: t.spacing.sm }}>
          {displayedModels.map((m) => {
            const progress = pullProgress[m.id]
            const isPulling = pullingModel === m.id || (progress && progress.status !== "success" && progress.status !== "ready")
            const pct = progress ? Math.round(((progress.completed ?? 0) / (progress.total ?? 1)) * 100) : 0

            return (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 14px",
                  borderRadius: t.radii.md,
                  border: `1px solid ${c.border}`,
                  backgroundColor: c.cardBg,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontWeight: 700, color: c.text, fontSize: 14 }}>
                      {labels[m.id] ?? m.name ?? m.id}
                    </span>
                    {m.status && renderStatusBadge(m.status)}
                    {m.ready !== undefined && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                        padding: "1px 6px", borderRadius: t.radii.sm,
                        backgroundColor: m.ready ? "#22C55E22" : "#F59E0B22",
                        color: m.ready ? "#22C55E" : "#F59E0B",
                        border: `1px solid ${m.ready ? "#22C55E44" : "#F59E0B44"}`,
                      }}>
                        {m.ready ? "Downloaded" : "Not Downloaded"}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: c.textSecondary, marginTop: 4 }}>
                    {m.id}{m.size_human ? ` · ${m.size_human}` : m.size ? ` · ${m.size}` : ""}
                    {m.family ? ` · ${m.family}` : ""}
                    {m.quantization_level ? ` · ${m.quantization_level}` : ""}
                    {m.parameter_size ? ` · ${m.parameter_size}` : ""}
                  </div>

                  {isPulling && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2, fontSize: 11, color: c.textSecondary }}>
                        <span>Downloading...</span>
                        <span>{pct}%</span>
                      </div>
                      <div style={{ height: 4, borderRadius: 2, backgroundColor: c.surface, overflow: "hidden" }}>
                        <div
                          style={{
                            height: "100%",
                            width: `${pct}%`,
                            backgroundColor: c.primary,
                            borderRadius: 2,
                            transition: "width 0.5s ease",
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", gap: 6 }}>
                  {tab === "available" && (
                    <button
                      onClick={() => handlePull(m.id)}
                      disabled={isPulling}
                      style={{
                        padding: "6px 14px",
                        borderRadius: t.radii.sm,
                        border: "none",
                        backgroundColor: c.primary,
                        color: "#FFFFFF",
                        cursor: isPulling ? "default" : "pointer",
                        fontSize: 12,
                        fontWeight: 600,
                        opacity: isPulling ? 0.5 : 1,
                      }}
                    >
                      {isPulling ? "Pulling..." : "Pull"}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
      {/* Add/Edit Provider Modal */}
      {showAddProvider && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center",
          backgroundColor: "rgba(0,0,0,0.5)",
        }} onClick={() => { setShowAddProvider(false); setEditingProvider(null); resetProviderForm() }}>
          <div style={{
            width: 480, maxWidth: "90vw",
            borderRadius: t.radii.lg, border: `1px solid ${c.border}`,
            padding: t.spacing.lg, backgroundColor: c.cardBg,
          }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 15, fontWeight: 700, color: c.text }}>
              {editingProvider ? `Edit Provider: ${editingProvider.name}` : "Add Provider"}
            </h3>
            <div style={{ display: "grid", gap: 10 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 3 }}>Provider Name *</label>
                <input value={providerForm.name} onChange={(e) => setProviderForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. OpenAI, Ollama, Azure"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 13, boxSizing: "border-box" }} />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 3 }}>Vendor</label>
                <input value={providerForm.vendor ?? ""} onChange={(e) => setProviderForm((f) => ({ ...f, vendor: e.target.value }))}
                  placeholder="e.g. OpenAI, Meta, Mistral"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 13, boxSizing: "border-box" }} />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 3 }}>Base URL</label>
                <input value={providerForm.base_url ?? ""} onChange={(e) => setProviderForm((f) => ({ ...f, base_url: e.target.value }))}
                  placeholder="e.g. https://api.openai.com/v1"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 13, boxSizing: "border-box" }} />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 3 }}>API Key Environment Variable</label>
                <input value={providerForm.api_key_env ?? ""} onChange={(e) => setProviderForm((f) => ({ ...f, api_key_env: e.target.value }))}
                  placeholder="e.g. OPENAI_API_KEY"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 13, boxSizing: "border-box" }} />
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: t.spacing.md }}>
              <button onClick={() => { setShowAddProvider(false); setEditingProvider(null); resetProviderForm() }}
                style={{ padding: "8px 16px", borderRadius: t.radii.sm, border: `1px solid ${c.border}`, backgroundColor: "transparent", color: c.text, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                Cancel
              </button>
              <button onClick={editingProvider ? handleEditProvider : handleAddProvider}
                style={{ padding: "8px 16px", borderRadius: t.radii.sm, border: "none", backgroundColor: c.primary, color: "#FFF", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                {editingProvider ? "Update" : "Add"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
