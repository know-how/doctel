import React, { useEffect, useState, useCallback, useRef } from "react"
import {
  v2GetCatalog,
  v2ToggleModel,
  v2SetModelState,
  v2SetVisibility,
  v2SetModelRoles,
  v2SetModelDepartments,
  v2UpdateModel,
  v2GetTaskMapping,
  v2SetTaskMapping,
  v2RemoveTaskMapping,
  v2GetRoutingStatus,
  v2ToggleRouting,
  v2GetHealth,
  v2GetAudit,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type {
  V2CatalogResponse,
  V2Provider,
  V2ModelMetadata,
  V2HealthSummary,
  V2AuditEntry,
} from "../types/api"

/* ─────────────────────────────────────────────────────────────
   Styles
   ───────────────────────────────────────────────────────────── */

const badgeStyle = (color: string, bgColor: string) => ({
  display: "inline-flex" as const,
  alignItems: "center",
  gap: 4,
  padding: "2px 8px",
  borderRadius: 9999,
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.3px",
  color,
  backgroundColor: bgColor,
  border: `1px solid ${color}33`,
})

const capBadgeStyle = (c: any) => ({
  display: "inline-flex" as const,
  alignItems: "center",
  gap: 3,
  padding: "2px 7px",
  borderRadius: 6,
  fontSize: 10,
  fontWeight: 600,
  backgroundColor: c.primary + "15",
  color: c.primary,
  border: `1px solid ${c.primary}25`,
})

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

const healthColors: Record<string, string> = {
  healthy: "#22C55E",
  degraded: "#F59E0B",
  unhealthy: "#EF4444",
  unknown: "#9CA3AF",
}

/* ─────────────────────────────────────────────────────────────
   Sub-components
   ───────────────────────────────────────────────────────────── */

const HealthIndicator: React.FC<{ health?: V2HealthSummary }> = ({ health }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  if (!health || health.totalRequests === 0) {
    return <span style={{ fontSize: 11, color: c.textMuted }}>No data</span>
  }
  const color = healthColors[health.status] || c.textMuted
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: c.textSecondary }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: color, flexShrink: 0 }} />
      <span>{health.status}</span>
      <span>{health.avgLatencyMs !== null ? `${health.avgLatencyMs}ms` : "-"}</span>
      <span>{health.successRate}%</span>
      <span style={{ color: c.textMuted }}>{health.totalRequests} req</span>
    </div>
  )
}

const StateBadge: React.FC<{ state: string }> = ({ state }) => {
  const color = stateColors[state] || "#9CA3AF"
  return <span style={badgeStyle(color, color + "18")}>{state}</span>
}

const CapabilityBadges: React.FC<{ model: V2ModelMetadata }> = ({ model }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const caps: { key: string; label: string; active: boolean }[] = [
    { key: "supportsChat", label: "Chat", active: model.supportsChat },
    { key: "supportsVision", label: "Vision", active: model.supportsVision },
    { key: "supportsTools", label: "Tools", active: model.supportsTools },
    { key: "supportsCode", label: "Code", active: model.supportsCode },
    { key: "supportsReasoning", label: "Reasoning", active: model.supportsReasoning },
    { key: "supportsEmbedding", label: "Embedding", active: model.supportsEmbedding },
    { key: "supportsRag", label: "RAG", active: model.supportsRag },
    { key: "supportsClassification", label: "Classification", active: model.supportsClassification },
    { key: "supportsSummary", label: "Summary", active: model.supportsSummary },
    { key: "supportsExtraction", label: "Extraction", active: model.supportsExtraction },
  ]
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
      {caps.filter((c) => c.active).map((cap) => (
        <span key={cap.key} style={capBadgeStyle(c)}>{cap.label}</span>
      ))}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────
   Main Page Component
   ───────────────────────────────────────────────────────────── */

type PageTab = "models" | "task-mapping" | "routing" | "health" | "audit"

export const AdminModelManagementPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [tab, setTab] = useState<PageTab>("models")
  const [catalog, setCatalog] = useState<V2CatalogResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Health data
  const [healthData, setHealthData] = useState<any>(null)

  // Task mapping
  const [taskMapping, setTaskMapping] = useState<Record<string, any>>({})
  const [autoRouting, setAutoRouting] = useState(true)

  // Expanded providers
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set())

  // Expanded model details
  const [expandedModelDetails, setExpandedModelDetails] = useState<Set<string>>(new Set())

  // Edit modal state
  const [editingModel, setEditingModel] = useState<{ providerId: string; model: V2ModelMetadata } | null>(null)
  const [editForm, setEditForm] = useState<Record<string, any>>({})

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const cat = await v2GetCatalog()
      setCatalog(cat)

      const tm = await v2GetTaskMapping()
      setTaskMapping(tm.taskMapping || {})

      const rs = await v2GetRoutingStatus()
      setAutoRouting(rs.automaticRouting)

      if (tab === "health") {
        const h = await v2GetHealth()
        setHealthData(h)
      }
    } catch (e: any) {
      setError(e.message || "Failed to load data")
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    loadData()
  }, [loadData])

  // ── Handlers ──────────────────────────────

  const handleToggleModel = async (providerId: string, modelId: string, enabled: boolean) => {
    try {
      await v2ToggleModel(providerId, modelId, enabled)
      loadData()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleSetState = async (providerId: string, modelId: string, state: string) => {
    try {
      await v2SetModelState(providerId, modelId, state)
      loadData()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleSetVisibility = async (providerId: string, modelId: string, visible: boolean) => {
    try {
      await v2SetVisibility(providerId, modelId, visible)
      loadData()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleSaveModelEdit = async () => {
    if (!editingModel) return
    try {
      await v2UpdateModel(editingModel.providerId, editingModel.model.id, editForm)
      setEditingModel(null)
      loadData()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleSetTaskMapping = async (taskType: string, providerId: string, modelId: string) => {
    try {
      if (!providerId || !modelId) {
        await v2RemoveTaskMapping(taskType)
      } else {
        await v2SetTaskMapping(taskType, providerId, modelId)
      }
      loadData()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleToggleRouting = async () => {
    try {
      const res = await v2ToggleRouting(!autoRouting)
      setAutoRouting(res.automaticRouting)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const toggleProvider = (id: string) => {
    setExpandedProviders((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleModelDetails = (id: string) => {
    setExpandedModelDetails((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ── Render: Model Catalog (Layers 1-8) ────

  const renderCatalog = () => {
    if (!catalog) return null
    const { providers } = catalog
    if (providers.length === 0) {
      return (
        <div style={{ textAlign: "center", padding: 48, color: c.textSecondary }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: c.text, marginBottom: 8 }}>No providers configured</div>
          <div style={{ fontSize: 13 }}>Go to <strong>Providers</strong> to add an AI provider.</div>
        </div>
      )
    }

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {providers.map((provider) => {
          const isExpanded = expandedProviders.has(provider.id)
          const enabledCount = provider.models.filter((m) => m.enabled).length
          return (
            <div key={provider.id} style={{
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              backgroundColor: c.cardBg,
              overflow: "hidden",
            }}>
              {/* Provider Header — GitHub Copilot style */}
              <div
                onClick={() => toggleProvider(provider.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 16px",
                  cursor: "pointer",
                  userSelect: "none",
                  borderBottom: isExpanded ? `1px solid ${c.border}` : "none",
                }}
              >
                <span style={{ fontSize: 18, flexShrink: 0 }}>
                  {provider.icon === "ollama" ? "🦙" :
                   provider.icon === "gemini" ? "🔮" :
                   provider.icon === "opencode" ? "🔓" :
                   provider.icon === "deepseek" ? "🧊" :
                   provider.icon === "openai" ? "⚡" :
                   provider.icon === "anthropic" ? "🎩" :
                   provider.icon === "mistral" ? "🌬️" :
                   provider.icon === "huggingface" ? "🤗" :
                   provider.icon === "lmstudio" ? "💻" : "🏢"}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 700, fontSize: 14, color: c.text }}>{provider.name}</span>
                    {provider.vendor && provider.vendor !== provider.name && (
                      <span style={{ fontSize: 11, color: c.textSecondary }}>{provider.vendor}</span>
                    )}
                    <StateBadge state={provider.status || "unknown"} />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 2 }}>
                    <span style={{ fontSize: 11, color: c.textSecondary }}>
                      {provider.models.length} models · {enabledCount} enabled
                    </span>
                    {provider.description && (
                      <span style={{ fontSize: 11, color: c.textMuted }}>{provider.description}</span>
                    )}
                  </div>
                </div>
                <HealthIndicator health={provider.health} />
                <span style={{ color: c.textMuted, fontSize: 12, transition: "transform 0.2s", transform: isExpanded ? "rotate(180deg)" : "" }}>
                  ▼
                </span>
              </div>

              {/* Models list */}
              {isExpanded && (
                <div style={{ padding: "8px 16px 12px" }}>
                  {provider.models.map((model) => {
                    const detailKey = `${provider.id}/${model.id}`
                    const isDetailExpanded = expandedModelDetails.has(detailKey)
                    return (
                      <div key={model.id} style={{
                        borderRadius: 8,
                        border: `1px solid ${c.border}`,
                        backgroundColor: c.surface,
                        marginBottom: 6,
                        overflow: "hidden",
                      }}>
                        {/* Model row */}
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: "10px 12px",
                        }}>
                          {/* Toggle */}
                          <button
                            onClick={() => handleToggleModel(provider.id, model.id, !model.enabled)}
                            style={{
                              width: 36,
                              height: 20,
                              borderRadius: 10,
                              border: "none",
                              backgroundColor: model.enabled ? "#22C55E" : c.border,
                              cursor: "pointer",
                              position: "relative",
                              transition: "background 0.2s",
                              flexShrink: 0,
                            }}
                          >
                            <span style={{
                              position: "absolute",
                              top: 2,
                              left: model.enabled ? 18 : 2,
                              width: 16,
                              height: 16,
                              borderRadius: "50%",
                              backgroundColor: "#FFF",
                              transition: "left 0.2s",
                              boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                            }} />
                          </button>

                          {/* Model info */}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <span style={{ fontWeight: 600, fontSize: 13, color: c.text }}>{model.name || model.id}</span>
                              {model.id !== model.name && (
                                <span style={{ fontSize: 10, color: c.textMuted }}>{model.id}</span>
                              )}
                              <StateBadge state={model.state} />
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
                              <span style={{ fontSize: 10, color: c.textSecondary }}>
                                {(model.contextWindow / 1000).toFixed(0)}K ctx
                              </span>
                              <span style={{ fontSize: 10, color: c.textMuted }}>·</span>
                              <span style={{ fontSize: 10, color: c.textSecondary }}>{model.pricingTier}</span>
                              <span style={{ fontSize: 10, color: c.textMuted }}>·</span>
                              <span style={{ fontSize: 10, color: c.textSecondary }}>{model.license}</span>
                            </div>
                          </div>

                          {/* Capability badges */}
                          <div style={{ display: "none", gap: 3, flexShrink: 0 }}>
                            <CapabilityBadges model={model} />
                          </div>

                          {/* Visibility toggle */}
                          <label style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            fontSize: 10,
                            color: model.visibleToUsers ? c.primary : c.textMuted,
                            cursor: "pointer",
                            flexShrink: 0,
                          }}>
                            <input
                              type="checkbox"
                              checked={model.visibleToUsers}
                              onChange={(e) => handleSetVisibility(provider.id, model.id, e.target.checked)}
                              style={{ accentColor: c.primary }}
                            />
                            Visible
                          </label>

                          {/* Actions */}
                          <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                            <select
                              value={model.state}
                              onChange={(e) => handleSetState(provider.id, model.id, e.target.value)}
                              style={{
                                padding: "3px 6px",
                                borderRadius: 6,
                                border: `1px solid ${c.border}`,
                                backgroundColor: c.inputBg,
                                color: c.text,
                                fontSize: 10,
                                fontWeight: 600,
                                cursor: "pointer",
                              }}
                            >
                              <option value="active">Active</option>
                              <option value="inactive">Inactive</option>
                              <option value="maintenance">Maintenance</option>
                              <option value="retired">Retired</option>
                            </select>
                            <button
                              onClick={() => {
                                setEditingModel({ providerId: provider.id, model })
                                setEditForm({ ...model })
                              }}
                              style={{
                                padding: "3px 8px",
                                borderRadius: 6,
                                border: `1px solid ${c.border}`,
                                backgroundColor: "transparent",
                                color: c.text,
                                cursor: "pointer",
                                fontSize: 10,
                                fontWeight: 600,
                              }}
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => toggleModelDetails(detailKey)}
                              style={{
                                padding: "3px 8px",
                                borderRadius: 6,
                                border: `1px solid ${c.border}`,
                                backgroundColor: "transparent",
                                color: c.textMuted,
                                cursor: "pointer",
                                fontSize: 10,
                              }}
                            >
                              {isDetailExpanded ? "▲" : "▼"}
                            </button>
                          </div>
                        </div>

                        {/* Expanded details */}
                        {isDetailExpanded && (
                          <div style={{
                            borderTop: `1px solid ${c.border}`,
                            padding: "10px 12px",
                            backgroundColor: c.bgSecondary,
                          }}>
                            <CapabilityBadges model={model} />
                            <div style={{
                              display: "grid",
                              gridTemplateColumns: "1fr 1fr 1fr",
                              gap: 6,
                              marginTop: 8,
                              fontSize: 11,
                              color: c.textSecondary,
                            }}>
                              <div><strong>Model ID:</strong> {model.id}</div>
                              <div><strong>Context:</strong> {(model.contextWindow / 1000).toFixed(0)}K tokens</div>
                              <div><strong>State:</strong> {model.state}</div>
                              <div><strong>Pricing:</strong> {model.pricingTier}</div>
                              <div><strong>License:</strong> {model.license}</div>
                              <div><strong>Default:</strong> {model.isDefault ? "Yes" : "No"}</div>
                              {model.allowedRoles && model.allowedRoles.length > 0 && (
                                <div><strong>Roles:</strong> {model.allowedRoles.join(", ")}</div>
                              )}
                              {model.departmentRestrictions && model.departmentRestrictions.length > 0 && (
                                <div><strong>Departments:</strong> {model.departmentRestrictions.join(", ")}</div>
                              )}
                              {model.forTasks && model.forTasks.length > 0 && (
                                <div><strong>For Tasks:</strong> {model.forTasks.join(", ")}</div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}

                  {/* Capability summary for the provider */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 8 }}>
                    {Array.from(new Set(provider.models.flatMap((m) => m.capabilities || []))).map((cap) => (
                      <span key={cap} style={capBadgeStyle(c)}>{cap}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // ── Render: Task Mapping (Layer 11) ──────

  const renderTaskMapping = () => {
    if (!catalog) return null
    const { providers, taskTypes } = catalog

    return (
      <div>
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: c.text }}>Task-to-Model Mapping</h3>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: c.textSecondary }}>
            Assign specific models to each AI task type. Leave unassigned for automatic routing.
          </p>
        </div>

        <div style={{ display: "grid", gap: 8 }}>
          {taskTypes.map((taskType) => {
            const current = taskMapping[taskType] || {}
            return (
              <div key={taskType} style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                borderRadius: 10,
                border: `1px solid ${c.border}`,
                backgroundColor: c.cardBg,
              }}>
                <span style={{
                  fontWeight: 600,
                  fontSize: 13,
                  color: c.text,
                  minWidth: 130,
                  textTransform: "capitalize",
                }}>
                  {taskType.replace(/_/g, " ")}
                </span>
                <select
                  value={current.modelId ? `${current.providerId}::${current.modelId}` : ""}
                  onChange={(e) => {
                    const val = e.target.value
                    if (!val) {
                      handleSetTaskMapping(taskType, "", "")
                    } else {
                      const [pid, mid] = val.split("::")
                      handleSetTaskMapping(taskType, pid, mid)
                    }
                  }}
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: `1px solid ${c.border}`,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 12,
                  }}
                >
                  <option value="">— Auto (recommended) —</option>
                  {providers.map((p) =>
                    p.models
                      .filter((m) => m.enabled)
                      .map((m) => (
                        <option key={`${p.id}::${m.id}`} value={`${p.id}::${m.id}`}>
                          {p.name} → {m.name || m.id}
                        </option>
                      ))
                  )}
                </select>
                {current.modelName && (
                  <span style={{ fontSize: 11, color: c.textSecondary }}>
                    {current.providerName} · {current.modelName}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // ── Render: Auto Routing (Layer 12) ──────

  const renderRouting = () => {
    if (!catalog) return null
    const { automaticRoutingRules } = catalog

    return (
      <div>
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: c.text }}>Intelligent Model Selection</h3>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: c.textSecondary }}>
              Let the system automatically choose the best model for each task.
            </p>
          </div>
          <button
            onClick={handleToggleRouting}
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              border: "none",
              backgroundColor: autoRouting ? "#22C55E" : c.border,
              color: autoRouting ? "#FFF" : c.text,
              fontWeight: 700,
              fontSize: 13,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 16 }}>{autoRouting ? "✅" : "❌"}</span>
            {autoRouting ? "Automatic Routing ON" : "Automatic Routing OFF"}
          </button>
        </div>

        <div style={{ display: "grid", gap: 6 }}>
          {Object.entries(automaticRoutingRules || {}).map(([task, rule]: [string, any]) => (
            <div key={task} style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "10px 14px",
              borderRadius: 10,
              border: `1px solid ${c.border}`,
              backgroundColor: autoRouting ? c.cardBg : c.surface,
              opacity: autoRouting ? 1 : 0.5,
            }}>
              <span style={{
                fontWeight: 600,
                fontSize: 13,
                color: c.text,
                minWidth: 130,
                textTransform: "capitalize",
              }}>
                {task.replace(/_/g, " ")}
              </span>
              <span style={{ fontSize: 12, color: c.textSecondary, flex: 1 }}>
                {rule.description}
              </span>
              {rule.preferred_family && (
                <span style={{
                  padding: "2px 8px",
                  borderRadius: 9999,
                  fontSize: 10,
                  fontWeight: 600,
                  backgroundColor: c.primary + "18",
                  color: c.primary,
                }}>
                  prefers {rule.preferred_family}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ── Render: Health (Layer 13) ────────────

  const renderHealthCard = (key: string, data: V2HealthSummary) => {
    const color = healthColors[data.status] || c.textMuted
    return (
      <div key={key} style={{
        padding: "12px 14px",
        borderRadius: 10,
        border: `1px solid ${c.border}`,
        backgroundColor: c.cardBg,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: color, flexShrink: 0 }} />
          <span style={{ fontWeight: 600, fontSize: 13, color: c.text }}>{key}</span>
          <span style={{ fontSize: 11, color, fontWeight: 600, textTransform: "capitalize" }}>{data.status}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, fontSize: 11, color: c.textSecondary }}>
          <div>Requests: {data.totalRequests}</div>
          <div>Success Rate: {data.successRate}%</div>
          <div>Avg Latency: {data.avgLatencyMs !== null ? `${data.avgLatencyMs}ms` : "-"}</div>
          <div>Total Tokens: {data.totalTokens.toLocaleString()}</div>
          <div>Errors: {data.errorCount}</div>
          {data.lastChecked && <div>Last: {new Date(data.lastChecked).toLocaleTimeString()}</div>}
        </div>
      </div>
    )
  }

  const renderHealth = () => {
    if (!healthData) {
      return <div style={{ textAlign: "center", padding: 32, color: c.textSecondary }}>Loading health data...</div>
    }

    return (
      <div>
        <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700, color: c.text }}>Health Monitoring</h3>
        {healthData.system && (
          <div style={{ marginBottom: 16 }}>{renderHealthCard("System", healthData.system)}</div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {Object.entries(healthData.providers || {}).map(([k, v]: [string, any]) => renderHealthCard(k, v))}
        </div>
        {Object.keys(healthData.models || {}).length > 0 && (
          <>
            <h4 style={{ margin: "16px 0 8px", fontSize: 14, fontWeight: 600, color: c.text }}>Per Model</h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {Object.entries(healthData.models || {}).map(([k, v]: [string, any]) => renderHealthCard(k, v))}
            </div>
          </>
        )}
      </div>
    )
  }

  // ── Render: Audit (Layer 14) ─────────────

  const [localAudit, setLocalAudit] = useState<V2AuditEntry[]>([])
  const [auditFilter, setAuditFilter] = useState<string>("")

  useEffect(() => {
    if (tab === "audit") {
      v2GetAudit(100, auditFilter || undefined).then((r) => setLocalAudit(r.audit || [])).catch(() => {})
    }
  }, [auditFilter, tab])

  const renderAudit = () => {
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: c.text }}>Audit & Governance</h3>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: c.textSecondary }}>
              Track all model and provider changes.
            </p>
          </div>
          <select
            value={auditFilter}
            onChange={(e) => setAuditFilter(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 12,
            }}
          >
            <option value="">All Actions</option>
            <option value="provider_added">Provider Added</option>
            <option value="provider_removed">Provider Removed</option>
            <option value="provider_updated">Provider Updated</option>
            <option value="model_added">Model Added</option>
            <option value="model_removed">Model Removed</option>
            <option value="model_updated">Model Updated</option>
            <option value="task_mapping_updated">Task Mapping</option>
            <option value="automatic_routing">Auto Routing</option>
          </select>
        </div>

        {localAudit.length === 0 ? (
          <div style={{ textAlign: "center", padding: 32, color: c.textSecondary, fontSize: 13 }}>
            No audit entries found.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {localAudit.map((entry) => (
              <div key={entry.id} style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${c.border}`,
                backgroundColor: c.cardBg,
                fontSize: 12,
              }}>
                <span style={{
                  padding: "2px 8px",
                  borderRadius: 6,
                  fontSize: 10,
                  fontWeight: 700,
                  backgroundColor: c.primary + "18",
                  color: c.primary,
                  whiteSpace: "nowrap",
                  marginTop: 1,
                }}>
                  {entry.action.replace(/_/g, " ")}
                </span>
                <div style={{ flex: 1, color: c.text }}>
                  <strong>{entry.userName}</strong>
                  <span style={{ color: c.textSecondary }}>
                    {" "}{entry.action.replace(/_/g, " ")}{" "}
                    <strong>{entry.entityId}</strong>
                    {entry.details?.changes && (
                      <span style={{ color: c.textMuted }}>
                        {" · "}{Object.keys(entry.details.changes).join(", ")}
                      </span>
                    )}
                  </span>
                </div>
                <span style={{ color: c.textMuted, whiteSpace: "nowrap", fontSize: 11 }}>
                  {new Date(entry.timestamp).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── Edit Modal ────────────────────────────

  const renderEditModal = () => {
    if (!editingModel) return null
    const { model } = editingModel

    const fields: { key: string; label: string; type: "text" | "number" | "checkbox" | "select" }[] = [
      { key: "name", label: "Display Name", type: "text" },
      { key: "contextWindow", label: "Context Window", type: "number" },
      { key: "pricingTier", label: "Pricing Tier", type: "text" },
      { key: "license", label: "License", type: "text" },
      { key: "supportsChat", label: "Chat", type: "checkbox" },
      { key: "supportsVision", label: "Vision", type: "checkbox" },
      { key: "supportsTools", label: "Tools", type: "checkbox" },
      { key: "supportsCode", label: "Code", type: "checkbox" },
      { key: "supportsReasoning", label: "Reasoning", type: "checkbox" },
      { key: "supportsEmbedding", label: "Embedding", type: "checkbox" },
      { key: "supportsRag", label: "RAG", type: "checkbox" },
      { key: "supportsClassification", label: "Classification", type: "checkbox" },
      { key: "supportsSummary", label: "Summary", type: "checkbox" },
      { key: "supportsExtraction", label: "Extraction", type: "checkbox" },
    ]

    return (
      <div style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }} onClick={() => setEditingModel(null)}>
        <div style={{
          backgroundColor: c.cardBg,
          borderRadius: 16,
          padding: 24,
          maxWidth: 520,
          width: "90%",
          maxHeight: "80vh",
          overflow: "auto",
          border: `1px solid ${c.border}`,
        }} onClick={(e) => e.stopPropagation()}>
          <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: c.text }}>
            Edit Model — {model.name || model.id}
          </h3>

          <div style={{ display: "grid", gap: 10 }}>
            {fields.map((field) => (
              <div key={field.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <label style={{ minWidth: 140, fontSize: 12, fontWeight: 600, color: c.textSecondary }}>
                  {field.label}
                </label>
                {field.type === "checkbox" ? (
                  <input
                    type="checkbox"
                    checked={!!editForm[field.key]}
                    onChange={(e) => setEditForm((f: any) => ({ ...f, [field.key]: e.target.checked }))}
                    style={{ accentColor: c.primary }}
                  />
                ) : field.type === "number" ? (
                  <input
                    type="number"
                    value={editForm[field.key] ?? ""}
                    onChange={(e) => setEditForm((f: any) => ({ ...f, [field.key]: parseInt(e.target.value) || 0 }))}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 8,
                      border: `1px solid ${c.border}`,
                      backgroundColor: c.inputBg,
                      color: c.text,
                      fontSize: 12,
                    }}
                  />
                ) : (
                  <input
                    type="text"
                    value={editForm[field.key] ?? ""}
                    onChange={(e) => setEditForm((f: any) => ({ ...f, [field.key]: e.target.value }))}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 8,
                      border: `1px solid ${c.border}`,
                      backgroundColor: c.inputBg,
                      color: c.text,
                      fontSize: 12,
                    }}
                  />
                )}
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 20 }}>
            <button
              onClick={() => setEditingModel(null)}
              style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: `1px solid ${c.border}`,
                backgroundColor: "transparent",
                color: c.text,
                cursor: "pointer",
                fontWeight: 600,
                fontSize: 12,
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSaveModelEdit}
              style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: "none",
                backgroundColor: c.primary,
                color: "#FFF",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: 12,
              }}
            >
              Save Changes
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Main Render ───────────────────────────

  const tabs: { id: PageTab; label: string; icon: string }[] = [
    { id: "models", label: "Model Catalog", icon: "🤖" },
    { id: "task-mapping", label: "Task Mapping", icon: "🎯" },
    { id: "routing", label: "Auto Routing", icon: "🧠" },
    { id: "health", label: "Health", icon: "❤️" },
    { id: "audit", label: "Audit", icon: "📋" },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: c.text, display: "flex", alignItems: "center", gap: 10 }}>
          <span>🤖</span> Model Management
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
          GitHub Copilot-style enterprise model management for ZETDC's AI platform.
        </p>
      </div>

      {error && (
        <div style={{
          padding: "8px 12px",
          marginBottom: 12,
          borderRadius: 8,
          backgroundColor: c.error + "18",
          color: c.error,
          fontSize: 12,
          fontWeight: 600,
        }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 12, background: "none", border: "none", color: c.error, cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
      )}

      {/* Tab bar */}
      <div style={{
        display: "flex",
        gap: 2,
        marginBottom: 20,
        padding: 3,
        borderRadius: 12,
        border: `1px solid ${c.border}`,
        backgroundColor: c.surface,
        flexWrap: "wrap",
      }}>
        {tabs.map((tItem) => (
          <button
            key={tItem.id}
            onClick={() => setTab(tItem.id)}
            style={{
              padding: "7px 16px",
              borderRadius: 8,
              border: "none",
              backgroundColor: tab === tItem.id ? c.primary : "transparent",
              color: tab === tItem.id ? "#FFF" : c.text,
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 5,
              transition: "all 0.15s",
            }}
          >
            <span>{tItem.icon}</span>
            {tItem.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 48, color: c.textSecondary }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          Loading model catalog...
        </div>
      ) : (
        <>
          {tab === "models" && renderCatalog()}
          {tab === "task-mapping" && renderTaskMapping()}
          {tab === "routing" && renderRouting()}
          {tab === "health" && renderHealth()}
          {tab === "audit" && renderAudit()}
        </>
      )}

      {/* Edit modal */}
      {renderEditModal()}
    </div>
  )
}
