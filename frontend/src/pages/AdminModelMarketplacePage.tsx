import React, { useEffect, useState, useCallback } from "react"
import { v2GetMarketplace, v2GetCatalog } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { V2MarketplaceItem } from "../types/api"

/* ─────────────────────────────────────────────────────────────
   Styles
   ───────────────────────────────────────────────────────────── */

const capBadgeStyle = (c: any, cap: string) => {
  const colorMap: Record<string, string> = {
    chat: "#5B88FF", vision: "#8B5CF6", tools: "#F59E0B",
    code: "#22C55E", reasoning: "#EC4899", embedding: "#06B6D4",
    rag: "#F97316", classification: "#14B8A6", summary: "#6366F1",
    extraction: "#EF4444",
  }
  const color = colorMap[cap] || c.primary
  return {
    display: "inline-flex" as const,
    alignItems: "center",
    padding: "2px 8px",
    borderRadius: 6,
    fontSize: 10,
    fontWeight: 600,
    backgroundColor: color + "15",
    color: color,
    border: `1px solid ${color}25`,
  }
}

export const AdminModelMarketplacePage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [catalog, setCatalog] = useState<V2MarketplaceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [selectedProvider, setSelectedProvider] = useState<string>("all")
  const [selectedCap, setSelectedCap] = useState<string>("all")

  const loadMarketplace = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // First try marketplace endpoint
      try {
        const data = await v2GetMarketplace()
        setCatalog(data.catalog || [])
      } catch {
        // Fallback: extract from catalog
        const cat = await v2GetCatalog()
        const items: V2MarketplaceItem[] = []
        for (const p of cat.providers || []) {
          for (const m of p.models) {
            if (m.state === "installed" || m.state === "active") continue
            items.push({
              modelId: m.id,
              modelName: m.name || m.id,
              providerId: p.id,
              providerName: p.name,
              contextWindow: m.contextWindow,
              capabilities: m.capabilities || [],
              pricingTier: m.pricingTier || "free",
              license: m.license || "Proprietary",
              state: m.state,
            })
          }
        }
        setCatalog(items)
      }
    } catch (e: any) {
      setError(e.message || "Failed to load marketplace")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMarketplace()
  }, [loadMarketplace])

  // Filtering
  const filteredCatalog = catalog.filter((item) => {
    if (search && !item.modelName.toLowerCase().includes(search.toLowerCase()) && !item.modelId.toLowerCase().includes(search.toLowerCase())) return false
    if (selectedProvider !== "all" && item.providerId !== selectedProvider) return false
    if (selectedCap !== "all" && !item.capabilities.includes(selectedCap)) return false
    return true
  })

  const uniqueProviders = Array.from(new Set(catalog.map((item) => item.providerId)))
  const uniqueCaps = Array.from(new Set(catalog.flatMap((item) => item.capabilities)))

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: c.text, display: "flex", alignItems: "center", gap: 10 }}>
          <span>🛒</span> Model Marketplace
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
          Browse and install models from your configured providers. Inspired by GitHub Copilot's "Add Models" experience.
        </p>
      </div>

      {error && (
        <div style={{ padding: "8px 12px", marginBottom: 12, borderRadius: 8, backgroundColor: c.error + "18", color: c.error, fontSize: 12, fontWeight: 600 }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 12, background: "none", border: "none", color: c.error, cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Search & Filters */}
      <div style={{
        display: "flex", gap: 10, marginBottom: 16,
        padding: "10px 14px", borderRadius: 12,
        border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
        flexWrap: "wrap", alignItems: "center",
      }}>
        <input
          type="text"
          placeholder="Search models..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: 1,
            minWidth: 200,
            padding: "8px 12px",
            borderRadius: 8,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
          }}
        />
        <select
          value={selectedProvider}
          onChange={(e) => setSelectedProvider(e.target.value)}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 12,
          }}
        >
          <option value="all">All Providers</option>
          {uniqueProviders.map((pid) => (
            <option key={pid} value={pid}>{pid}</option>
          ))}
        </select>
        <select
          value={selectedCap}
          onChange={(e) => setSelectedCap(e.target.value)}
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 12,
          }}
        >
          <option value="all">All Capabilities</option>
          {uniqueCaps.map((cap) => (
            <option key={cap} value={cap}>{cap.charAt(0).toUpperCase() + cap.slice(1)}</option>
          ))}
        </select>
        <span style={{ fontSize: 11, color: c.textSecondary }}>
          {filteredCatalog.length} models
        </span>
      </div>

      {/* Marketplace Grid */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 48, color: c.textSecondary }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          Loading marketplace...
        </div>
      ) : filteredCatalog.length === 0 ? (
        <div style={{
          textAlign: "center", padding: "48px 24px", borderRadius: 16,
          border: `1px solid ${c.border}`, backgroundColor: c.cardBg,
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📦</div>
          <h3 style={{ margin: "0 0 8px", color: c.text }}>All Models Installed</h3>
          <p style={{ margin: 0, fontSize: 13, color: c.textSecondary }}>
            All available models from your providers are already installed. Add more providers to discover new models.
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {filteredCatalog.map((item) => (
            <div key={`${item.providerId}/${item.modelId}`} style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 16px",
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              backgroundColor: c.cardBg,
              transition: "box-shadow 0.15s",
            }}>
              {/* Provider icon */}
              <span style={{ fontSize: 20, flexShrink: 0 }}>
                {item.providerId === "ollama" ? "🦙" :
                 item.providerId === "google-gemini" ? "🔮" :
                 item.providerId === "opencode-go" ? "🔓" :
                 item.providerId === "deepseek" ? "🧊" :
                 item.providerId === "openai" ? "⚡" : "🤖"}
              </span>

              {/* Model Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: 14, color: c.text }}>{item.modelName}</span>
                  <span style={{ fontSize: 10, color: c.textMuted }}>{item.modelId}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                  <span style={{ fontSize: 11, color: c.primary, fontWeight: 600 }}>{item.providerName}</span>
                  <span style={{ fontSize: 10, color: c.textMuted }}>·</span>
                  <span style={{ fontSize: 10, color: c.textSecondary }}>{(item.contextWindow / 1000).toFixed(0)}K context</span>
                  <span style={{ fontSize: 10, color: c.textMuted }}>·</span>
                  <span style={{ fontSize: 10, color: c.textSecondary }}>{item.pricingTier}</span>
                  <span style={{ fontSize: 10, color: c.textMuted }}>·</span>
                  <span style={{ fontSize: 10, color: c.textSecondary }}>{item.license}</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 4 }}>
                  {item.capabilities.map((cap) => (
                    <span key={cap} style={capBadgeStyle(c, cap)}>{cap}</span>
                  ))}
                </div>
              </div>

              {/* Install button */}
              <button
                style={{
                  padding: "6px 16px",
                  borderRadius: 8,
                  border: "none",
                  backgroundColor: c.primary,
                  color: "#FFF",
                  fontWeight: 700,
                  fontSize: 12,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  whiteSpace: "nowrap",
                }}
                title="Add this model to your provider configuration"
                onClick={() => {
                  // Navigate to providers page - simplified by showing a message
                  alert(`To install "${item.modelName}":\n1. Go to Providers\n2. Select "${item.providerName}"\n3. Click "Add Model"\n4. Enter ID: ${item.modelId}\n5. Configure capabilities`);
                }}
              >
                + Install
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
