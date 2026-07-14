import React, { useEffect, useState, useCallback } from "react"
import {
  v2ListProviders,
  v2GetProvider,
  v2AddProvider,
  v2UpdateProvider,
  v2DeleteProvider,
  v2AddModel,
  v2DeleteModel,
  v2GetHealth,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { V2Provider, V2ModelMetadata, V2HealthSummary } from "../types/api"

/* ─────────────────────────────────────────────────────────────
   Styles
   ───────────────────────────────────────────────────────────── */

const statusColors: Record<string, string> = {
  connected: "#22C55E",
  disconnected: "#9CA3AF",
  error: "#EF4444",
  connecting: "#F59E0B",
}

const stateColors: Record<string, string> = {
  active: "#22C55E",
  inactive: "#9CA3AF",
  installed: "#5B88FF",
  downloading: "#F59E0B",
  error: "#EF4444",
  maintenance: "#F97316",
  retired: "#6B7280",
  available: "#8B5CF6",
}

const PROVIDER_TEMPLATES: Record<string, {
  name: string; vendor: string; provider_type: string; base_url: string;
  models_endpoint: string; chat_endpoint: string; messages_endpoint: string;
  embeddings_endpoint: string; health_endpoint: string; icon: string; description: string;
}> = {
  opencode_go: {
    name: "OpenCode Go",
    vendor: "OpenCode",
    provider_type: "openai",
    base_url: "https://opencode.ai/zen/go/v1",
    models_endpoint: "https://opencode.ai/zen/go/v1/models",
    chat_endpoint: "https://opencode.ai/zen/go/v1/chat/completions",
    messages_endpoint: "https://opencode.ai/zen/go/v1/messages",
    embeddings_endpoint: "",
    health_endpoint: "",
    icon: "opencode",
    description: "OpenCode Go \u2014 subscription-based AI gateway",
  },
  opencode_zen: {
    name: "OpenCode Zen",
    vendor: "OpenCode",
    provider_type: "openai",
    base_url: "https://opencode.ai/zen/v1",
    models_endpoint: "https://opencode.ai/zen/v1/models",
    chat_endpoint: "https://opencode.ai/zen/v1/chat/completions",
    messages_endpoint: "https://opencode.ai/zen/v1/messages",
    embeddings_endpoint: "",
    health_endpoint: "",
    icon: "opencode",
    description: "OpenCode Zen \u2014 pay-per-use AI gateway",
  },
  openai: {
    name: "OpenAI",
    vendor: "OpenAI",
    provider_type: "openai",
    base_url: "https://api.openai.com/v1",
    models_endpoint: "https://api.openai.com/v1/models",
    chat_endpoint: "https://api.openai.com/v1/chat/completions",
    messages_endpoint: "",
    embeddings_endpoint: "https://api.openai.com/v1/embeddings",
    health_endpoint: "",
    icon: "openai",
    description: "OpenAI provider (GPT-4, GPT-4o, GPT-3.5)",
  },
  anthropic: {
    name: "Anthropic",
    vendor: "Anthropic",
    provider_type: "anthropic",
    base_url: "https://api.anthropic.com/v1",
    models_endpoint: "",
    chat_endpoint: "",
    messages_endpoint: "https://api.anthropic.com/v1/messages",
    embeddings_endpoint: "",
    health_endpoint: "",
    icon: "anthropic",
    description: "Anthropic provider (Claude models)",
  },
  gemini: {
    name: "Google Gemini",
    vendor: "Google",
    provider_type: "gemini",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    models_endpoint: "",
    chat_endpoint: "",
    messages_endpoint: "",
    embeddings_endpoint: "",
    health_endpoint: "",
    icon: "gemini",
    description: "Google Gemini provider",
  },
  ollama: {
    name: "Ollama",
    vendor: "Ollama",
    provider_type: "openai",
    base_url: "http://localhost:11434/v1",
    models_endpoint: "http://localhost:11434/v1/models",
    chat_endpoint: "http://localhost:11434/v1/chat/completions",
    messages_endpoint: "",
    embeddings_endpoint: "http://localhost:11434/v1/embeddings",
    health_endpoint: "http://localhost:11434/api/tags",
    icon: "ollama",
    description: "Local Ollama provider",
  },
}

export const AdminProvidersPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [providers, setProviders] = useState<V2Provider[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal state
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: "",
    vendor: "",
    base_url: "",
    api_key_value: "",
    description: "",
    icon: "generic",
    provider_type: "openai",
    models_endpoint: "",
    chat_endpoint: "",
    messages_endpoint: "",
    embeddings_endpoint: "",
    health_endpoint: "",
    visible_to_users: true,
    sort_order: 0,
  })
  const [selectedTemplate, setSelectedTemplate] = useState("")
  const derivedProviderId = form.name.toLowerCase().replace(/\s+/g, '-').replace(/_/g, '-')

  // Add model to provider
  const [addingModelTo, setAddingModelTo] = useState<string | null>(null)
  const [modelForm, setModelForm] = useState({
    id: "",
    name: "",
    contextWindow: 4096,
    supportsChat: true,
    supportsVision: false,
    supportsTools: false,
    supportsCode: false,
    supportsEmbedding: false,
    supportsReasoning: false,
  })

  // Expanded providers
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const loadProviders = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await v2ListProviders()
      setProviders(data.providers || [])
    } catch (e: any) {
      setError(e.message || "Failed to load providers")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  // ── Form handlers ─────────────────────────

  const resetForm = () => {
    setSelectedTemplate("")
    setForm({
      name: "", vendor: "", base_url: "", api_key_value: "",
      description: "", icon: "generic", provider_type: "openai",
      models_endpoint: "", chat_endpoint: "", messages_endpoint: "",
      embeddings_endpoint: "", health_endpoint: "",
      visible_to_users: true, sort_order: 0,
    })
  }
  const resetModelForm = () => setModelForm({
    id: "", name: "", contextWindow: 4096,
    supportsChat: true, supportsVision: false, supportsTools: false,
    supportsCode: false, supportsEmbedding: false, supportsReasoning: false,
  })

  const applyTemplate = (templateKey: string) => {
    if (!templateKey) return
    const tmpl = PROVIDER_TEMPLATES[templateKey]
    if (!tmpl) return
    setForm({
      name: tmpl.name,
      vendor: tmpl.vendor,
      base_url: tmpl.base_url,
      api_key_value: "",
      description: tmpl.description,
      icon: tmpl.icon,
      provider_type: tmpl.provider_type,
      models_endpoint: tmpl.models_endpoint,
      chat_endpoint: tmpl.chat_endpoint,
      messages_endpoint: tmpl.messages_endpoint,
      embeddings_endpoint: tmpl.embeddings_endpoint,
      health_endpoint: tmpl.health_endpoint,
      visible_to_users: true,
      sort_order: 0,
    })
    setSelectedTemplate(templateKey)
  }

  const handleAddProvider = async () => {
    if (!form.name.trim()) return
    try {
      if (editingId) {
        await v2UpdateProvider(editingId, form)
      } else {
        await v2AddProvider(form)
      }
      setShowForm(false)
      setEditingId(null)
      resetForm()
      loadProviders()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleEditProvider = (p: V2Provider) => {
    setSelectedTemplate("")
    setForm({
      name: p.name,
      vendor: p.vendor || "",
      base_url: p.base_url || "",
      api_key_value: p.api_key_value || "",
      description: p.description || "",
      icon: p.icon || "generic",
      provider_type: p.providerType || "openai",
      models_endpoint: p.modelsEndpoint || "",
      chat_endpoint: p.chatEndpoint || "",
      messages_endpoint: p.messagesEndpoint || "",
      embeddings_endpoint: p.embeddingsEndpoint || "",
      health_endpoint: p.healthEndpoint || "",
      visible_to_users: p.visibleToUsers ?? true,
      sort_order: p.order ?? 0,
    })
    setEditingId(p.id)
    setShowForm(true)
  }

  const handleDeleteProvider = async (id: string, name: string) => {
    if (!window.confirm(`Delete provider "${name}" and all its models?`)) return
    try {
      await v2DeleteProvider(id)
      loadProviders()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleAddModel = async (providerId: string) => {
    if (!modelForm.id.trim()) return
    try {
      await v2AddModel(providerId, modelForm)
      setAddingModelTo(null)
      resetModelForm()
      loadProviders()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDeleteModel = async (providerId: string, modelId: string) => {
    if (!window.confirm(`Delete model "${modelId}"?`)) return
    try {
      await v2DeleteModel(providerId, modelId)
      loadProviders()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ── Render ────────────────────────────────

  const renderStatusBadge = (status: string) => {
    const color = statusColors[status] || c.textMuted
    return (
      <span style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 10px",
        borderRadius: 9999,
        fontSize: 11,
        fontWeight: 700,
        backgroundColor: color + "18",
        color,
        border: `1px solid ${color}33`,
        textTransform: "capitalize",
      }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: color }} />
        {status}
      </span>
    )
  }

  const renderIcon = (icon: string) => {
    const icons: Record<string, string> = {
      ollama: "🦙", gemini: "🔮", opencode: "🔓", deepseek: "🧊",
      openai: "⚡", anthropic: "🎩", mistral: "🌬️", huggingface: "🤗",
      lmstudio: "💻", generic: "🏢",
    }
    return icons[icon] || "🏢"
  }

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: c.text, display: "flex", alignItems: "center", gap: 10 }}>
            <span>🏢</span> AI Providers
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
            Manage AI model providers — similar to VS Code's extension manager.
          </p>
        </div>
        <button
          onClick={() => { setShowForm(true); setEditingId(null); resetForm() }}
          style={{
            padding: "8px 18px",
            borderRadius: 8,
            border: "none",
            backgroundColor: c.primary,
            color: "#FFF",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          + Add Provider
        </button>
      </div>

      {error && (
        <div style={{
          padding: "8px 12px", marginBottom: 12, borderRadius: 8,
          backgroundColor: c.error + "18", color: c.error, fontSize: 12, fontWeight: 600,
        }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 12, background: "none", border: "none", color: c.error, cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Provider Cards */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 48, color: c.textSecondary }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          Loading providers...
        </div>
      ) : providers.length === 0 ? (
        <div style={{
          textAlign: "center", padding: "48px 24px", borderRadius: 16,
          border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🏢</div>
          <h3 style={{ margin: "0 0 8px", color: c.text }}>No Providers</h3>
          <p style={{ margin: 0, fontSize: 13, color: c.textSecondary }}>
            Register your first AI provider to get started. Providers connect your AI platform to model APIs.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {providers.map((provider) => (
            <div key={provider.id} style={{
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              backgroundColor: c.cardBg,
              overflow: "hidden",
            }}>
              {/* Provider Card Header — GitHub Copilot style */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "14px 16px",
              }}>
                <span style={{ fontSize: 24 }}>{renderIcon(provider.icon || "generic")}</span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color: c.text }}>{provider.name}</span>
                    {provider.vendor && provider.vendor !== provider.name && (
                      <span style={{ fontSize: 11, color: c.textSecondary, backgroundColor: c.surface, padding: "1px 8px", borderRadius: 6 }}>
                        {provider.vendor}
                      </span>
                    )}
                    {renderStatusBadge(provider.status || "disconnected")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 2, fontSize: 11, color: c.textSecondary }}>
                    <span>{provider.models?.length || 0} models</span>
                    {provider.base_url && <span>· {provider.base_url}</span>}
                    {provider.description && <span>· {provider.description}</span>}
                  </div>
                </div>

                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    onClick={() => toggleExpand(provider.id)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border: `1px solid ${c.border}`,
                      backgroundColor: "transparent",
                      color: c.text,
                      cursor: "pointer",
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    {expandedRows.has(provider.id) ? "▲ Hide" : "▼ Models"}
                  </button>
                  <button
                    onClick={() => handleEditProvider(provider)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border: `1px solid ${c.border}`,
                      backgroundColor: c.surface,
                      color: c.text,
                      cursor: "pointer",
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDeleteProvider(provider.id, provider.name)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border: `1px solid ${c.error}44`,
                      backgroundColor: c.error + "18",
                      color: c.error,
                      cursor: "pointer",
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Expanded Models */}
              {expandedRows.has(provider.id) && (
                <div style={{ borderTop: `1px solid ${c.border}`, padding: "12px 16px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary }}>
                      Models ({provider.models?.length || 0})
                    </span>
                    <button
                      onClick={() => setAddingModelTo(provider.id)}
                      style={{
                        padding: "3px 10px",
                        borderRadius: 6,
                        border: `1px dashed ${c.border}`,
                        backgroundColor: "transparent",
                        color: c.primary,
                        cursor: "pointer",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      + Add Model
                    </button>
                  </div>

                  {provider.models?.length === 0 && !addingModelTo ? (
                    <div style={{ fontSize: 12, color: c.textMuted, padding: "12px 0", textAlign: "center" }}>
                      No models yet. Click "Add Model" to register one.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      {provider.models?.map((model) => (
                        <div key={model.id} style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "6px 10px",
                          borderRadius: 8,
                          backgroundColor: c.surface,
                        }}>
                          <span style={{ fontWeight: 600, fontSize: 13, color: c.text, flex: 1 }}>
                            {model.name || model.id}
                          </span>
                          {model.name && model.name !== model.id && (
                            <span style={{ fontSize: 10, color: c.textMuted }}>{model.id}</span>
                          )}
                          <span style={{
                            padding: "1px 6px",
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 600,
                            backgroundColor: (stateColors[model.state] || c.textMuted) + "18",
                            color: stateColors[model.state] || c.textMuted,
                          }}>
                            {model.state}
                          </span>
                          <span style={{ fontSize: 10, color: c.textSecondary }}>
                            {(model.contextWindow / 1000).toFixed(0)}K ctx
                          </span>
                          <button
                            onClick={() => handleDeleteModel(provider.id, model.id)}
                            style={{
                              padding: "2px 8px",
                              borderRadius: 4,
                              border: `1px solid ${c.border}`,
                              backgroundColor: "transparent",
                              color: c.textMuted,
                              cursor: "pointer",
                              fontSize: 10,
                              fontWeight: 600,
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add model form */}
                  {addingModelTo === provider.id && (
                    <div style={{ borderTop: `1px solid ${c.border}`, marginTop: 8, paddingTop: 10 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, marginBottom: 8, display: "block" }}>
                        Add Model to {provider.name}
                      </span>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                        <input placeholder="Model ID *" value={modelForm.id}
                          onChange={(e) => setModelForm((f) => ({ ...f, id: e.target.value }))}
                          style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 12 }} />
                        <input placeholder="Display name" value={modelForm.name}
                          onChange={(e) => setModelForm((f) => ({ ...f, name: e.target.value }))}
                          style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 12 }} />
                        <input placeholder="Context window" type="number" value={modelForm.contextWindow}
                          onChange={(e) => setModelForm((f) => ({ ...f, contextWindow: parseInt(e.target.value) || 4096 }))}
                          style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${c.border}`, backgroundColor: c.inputBg, color: c.text, fontSize: 12 }} />
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                        {(["supportsChat", "supportsVision", "supportsTools", "supportsCode", "supportsEmbedding", "supportsReasoning"] as const).map((key) => (
                          <label key={key} style={{ fontSize: 11, color: c.text, display: "flex", alignItems: "center", gap: 4 }}>
                            <input type="checkbox" checked={modelForm[key]}
                              onChange={(e) => setModelForm((f) => ({ ...f, [key]: e.target.checked }))} />
                            {key.replace("supports", "")}
                          </label>
                        ))}
                      </div>
                      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", marginTop: 8 }}>
                        <button onClick={() => { setAddingModelTo(null); resetModelForm() }}
                          style={{ padding: "4px 12px", borderRadius: 6, border: `1px solid ${c.border}`, backgroundColor: "transparent", color: c.text, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                          Cancel
                        </button>
                        <button onClick={() => handleAddModel(provider.id)}
                          style={{ padding: "4px 12px", borderRadius: 6, border: "none", backgroundColor: c.primary, color: "#FFF", cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                          Save Model
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Provider Modal — Full Field Support */}
      {showForm && (
        <div style={{
          position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.7)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          backdropFilter: "blur(4px)",
        }} onClick={() => setShowForm(false)}>
          <div style={{
            backgroundColor: c.bgSecondary, borderRadius: 16, padding: 24,
            maxWidth: 560, width: "90%", border: `1px solid ${c.border}`,
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)", maxHeight: "90vh", overflowY: "auto",
          }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: c.text }}>
              {editingId ? "Edit Provider" : "Add New Provider"}
            </h3>

            {/* ── Section 1: Basic Information ── */}
            <SectionLabel text="Basic Information" c={c} />
            <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
              <Field label="Provider Template" c={c}>
                <select value={selectedTemplate} onChange={(e) => applyTemplate(e.target.value)}
                  style={{ ...inputStyle(c), appearance: "auto" }}>
                  <option value="">Custom (manual)</option>
                  <option value="opencode_go">OpenCode Go</option>
                  <option value="opencode_zen">OpenCode Zen</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="gemini">Google Gemini</option>
                  <option value="ollama">Ollama</option>
                </select>
              </Field>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <Field label="Provider Name *" c={c}>
                  <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="e.g., MyProvider" style={inputStyle(c)} />
                </Field>
                <Field label="Vendor" c={c}>
                  <input value={form.vendor} onChange={(e) => setForm((f) => ({ ...f, vendor: e.target.value }))}
                    placeholder="e.g., MyCompany" style={inputStyle(c)} />
                </Field>
              </div>
              <Field label="Provider Type" c={c}>
                <select value={form.provider_type} onChange={(e) => setForm((f) => ({ ...f, provider_type: e.target.value }))}
                  style={{ ...inputStyle(c), appearance: "auto" }}>
                  <option value="openai">openai</option>
                  <option value="anthropic">anthropic</option>
                  <option value="gemini">gemini</option>
                  <option value="custom">custom</option>
                </select>
              </Field>
              <Field label="Description" c={c}>
                <input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Brief description of this provider" style={inputStyle(c)} />
              </Field>
              <Field label="Provider ID (auto)" c={c}>
                <input value={editingId || derivedProviderId} disabled
                  style={{ ...inputStyle(c), opacity: 0.6, cursor: "not-allowed" }} />
              </Field>
            </div>

            {/* ── Section 2: Connection ── */}
            <SectionLabel text="Connection" c={c} />
            <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
              <Field label="Base URL" c={c}>
                <input value={form.base_url} onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                  placeholder="https://api.example.com/v1" style={inputStyle(c)} />
              </Field>
              <ApiKeyField form={form} setForm={setForm} c={c} />
            </div>

            {/* ── Section 3: Endpoints ── */}
            <SectionLabel text="Endpoints" c={c} />
            <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
              <Field label="Models Endpoint" c={c}>
                <input value={form.models_endpoint} onChange={(e) => setForm((f) => ({ ...f, models_endpoint: e.target.value }))}
                  placeholder="/v1/models" style={inputStyle(c)} />
              </Field>
              <Field label="Chat Endpoint" c={c}>
                <input value={form.chat_endpoint} onChange={(e) => setForm((f) => ({ ...f, chat_endpoint: e.target.value }))}
                  placeholder="/v1/chat/completions" style={inputStyle(c)} />
              </Field>
              <Field label="Messages Endpoint" c={c}>
                <input value={form.messages_endpoint} onChange={(e) => setForm((f) => ({ ...f, messages_endpoint: e.target.value }))}
                  placeholder="/v1/messages" style={inputStyle(c)} />
              </Field>
              <Field label="Embeddings Endpoint" c={c}>
                <input value={form.embeddings_endpoint} onChange={(e) => setForm((f) => ({ ...f, embeddings_endpoint: e.target.value }))}
                  placeholder="/v1/embeddings" style={inputStyle(c)} />
              </Field>
              <Field label="Health Endpoint" c={c}>
                <input value={form.health_endpoint} onChange={(e) => setForm((f) => ({ ...f, health_endpoint: e.target.value }))}
                  placeholder="/health" style={inputStyle(c)} />
              </Field>
            </div>

            {/* ── Section 4: Display ── */}
            <SectionLabel text="Display" c={c} />
            <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
              <Field label="Icon" c={c}>
                <input value={form.icon} onChange={(e) => setForm((f) => ({ ...f, icon: e.target.value }))}
                  placeholder="generic" style={inputStyle(c)} />
              </Field>
              <Field label="Sort Order" c={c}>
                <input type="number" value={form.sort_order} onChange={(e) => setForm((f) => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))}
                  style={inputStyle(c)} />
              </Field>
              <Field label="Visible to Users" c={c}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: c.text }}>
                  <input type="checkbox" checked={form.visible_to_users}
                    onChange={(e) => setForm((f) => ({ ...f, visible_to_users: e.target.checked }))}
                    style={{ width: 16, height: 16, cursor: "pointer" }} />
                  {form.visible_to_users ? "Visible" : "Hidden"}
                </label>
              </Field>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 20, borderTop: `1px solid ${c.border}`, paddingTop: 16 }}>
              <button onClick={() => { setShowForm(false); setEditingId(null); resetForm() }}
                style={{ padding: "8px 16px", borderRadius: 8, border: `1px solid ${c.border}`, backgroundColor: "transparent", color: c.text, cursor: "pointer", fontWeight: 600, fontSize: 12 }}>
                Cancel
              </button>
              <button onClick={handleAddProvider}
                style={{ padding: "8px 16px", borderRadius: 8, border: "none", backgroundColor: c.primary, color: "#FFF", cursor: "pointer", fontWeight: 600, fontSize: 12 }}>
                {editingId ? "Save Changes" : "Add Provider"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Modal Helper Components ─────────────────────────── */

const sectionLabelStyle = (c: any): React.CSSProperties => ({
  fontSize: 13,
  fontWeight: 700,
  color: c.primary,
  margin: "0 0 8px",
  paddingBottom: 6,
  borderBottom: `1px solid ${c.border}`,
  textTransform: "uppercase",
  letterSpacing: "0.5px",
})

const SectionLabel: React.FC<{ text: string; c: any }> = ({ text, c }) => (
  <h4 style={sectionLabelStyle(c)}>{text}</h4>
)

const inputStyle = (c: any): React.CSSProperties => ({
  width: "100%",
  padding: "8px 10px",
  borderRadius: 8,
  border: `1px solid ${c.border}`,
  backgroundColor: c.inputBg,
  color: c.text,
  fontSize: 13,
  boxSizing: "border-box" as const,
})

const Field: React.FC<{ label: string; c: any; children: React.ReactNode }> = ({ label, c, children }) => (
  <div>
    <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
      {label}
    </label>
    {children}
  </div>
)

const ApiKeyField: React.FC<{ form: any; setForm: any; c: any }> = ({ form, setForm, c }) => {
  const [showKey, setShowKey] = useState(false)
  return (
    <div>
      <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
        API Key Value
      </label>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <input
          type={showKey ? "text" : "password"}
          value={form.api_key_value}
          onChange={(e) => setForm((f: any) => ({ ...f, api_key_value: e.target.value }))}
          placeholder="sk-..." style={{ ...inputStyle(c), flex: 1 }} />
        <button
          type="button"
          onClick={() => setShowKey((v) => !v)}
          title={showKey ? "Hide" : "Show"}
          style={{
            padding: "6px 10px",
            borderRadius: 8,
            border: `1px solid ${c.border}`,
            backgroundColor: "transparent",
            color: c.textSecondary,
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 600,
            lineHeight: 1,
          }}
        >
          {showKey ? "🙈" : "👁️"}
        </button>
      </div>
    </div>
  )
}
