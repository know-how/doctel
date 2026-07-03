import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface TokenUsageItem {
  label: string
  used: number
  max: number
}

const mockTokenUsage: TokenUsageItem[] = [
  { label: "Chat", used: 3200, max: 8192 },
  { label: "Summary", used: 1800, max: 4096 },
  { label: "Extraction", used: 2400, max: 4096 },
  { label: "Embedding", used: 512, max: 1024 },
]

export const AdminContextTokensPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [chunkSize, setChunkSize] = useState(1024)
  const [chunkOverlap, setChunkOverlap] = useState(128)
  const [maxContextTokens, setMaxContextTokens] = useState(8192)
  const [embedModel, setEmbedModel] = useState("nomic-embed-text")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      setSuccessMsg(null)
      // Simulate save
      await new Promise((r) => setTimeout(r, 600))
      setSuccessMsg("Settings saved successfully.")
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const usageBarColor = (used: number, max: number) => {
    const ratio = used / max
    if (ratio > 0.8) return c.error
    if (ratio > 0.6) return c.warning
    return c.success
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Context & Tokens</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
          Configure chunking, context window size, and embedding settings.
        </p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}
      {successMsg && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.success + "18", color: c.success, fontSize: 13 }}>
          {successMsg}
        </div>
      )}

      {/* Chunk size */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Chunk size configuration</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: t.spacing.lg }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: c.text }}>Chunk size</label>
              <span style={{ fontSize: 13, fontWeight: 700, color: c.primary }}>{chunkSize} tokens</span>
            </div>
            <input
              type="range"
              min={256}
              max={4096}
              step={128}
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
              style={{ width: "100%", accentColor: c.primary }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: c.textMuted }}>
              <span>256</span><span>4096</span>
            </div>
          </div>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: c.text }}>Chunk overlap</label>
              <span style={{ fontSize: 13, fontWeight: 700, color: c.primary }}>{chunkOverlap} tokens</span>
            </div>
            <input
              type="range"
              min={0}
              max={512}
              step={16}
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
              style={{ width: "100%", accentColor: c.primary }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: c.textMuted }}>
              <span>0</span><span>512</span>
            </div>
          </div>
        </div>

        <div style={{ marginTop: t.spacing.lg }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: c.text, display: "block", marginBottom: 6 }}>
            Max context tokens
          </label>
          <input
            type="number"
            value={maxContextTokens}
            onChange={(e) => setMaxContextTokens(Number(e.target.value))}
            min={512}
            max={32768}
            step={512}
            style={{
              width: "100%",
              padding: "8px 10px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
              boxSizing: "border-box",
            }}
          />
          <div style={{ fontSize: 11, color: c.textMuted, marginTop: 4 }}>Maximum number of tokens to pass as context to the model. Higher values use more memory.</div>
        </div>
      </div>

      {/* Token usage visualization */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Token usage (estimated)</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {mockTokenUsage.map((item) => {
            const pct = Math.round((item.used / item.max) * 100)
            const barColor = usageBarColor(item.used, item.max)
            return (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: c.text }}>{item.label}</span>
                  <span style={{ fontSize: 12, color: c.textSecondary }}>
                    {item.used.toLocaleString()} / {item.max.toLocaleString()} tokens
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 4, backgroundColor: c.surface, overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${pct}%`,
                      backgroundColor: barColor,
                      borderRadius: 4,
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Embedding model */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Embedding model</h3>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select
            value={embedModel}
            onChange={(e) => setEmbedModel(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
              minWidth: 250,
            }}
          >
            <option value="nomic-embed-text" style={{ backgroundColor: c.bgSecondary, color: c.text }}>nomic-embed-text</option>
            <option value="all-minilm" style={{ backgroundColor: c.bgSecondary, color: c.text }}>all-minilm</option>
            <option value="bge-m3" style={{ backgroundColor: c.bgSecondary, color: c.text }}>bge-m3</option>
            <option value="mxbai-embed-large" style={{ backgroundColor: c.bgSecondary, color: c.text }}>mxbai-embed-large</option>
          </select>
          <span style={{ fontSize: 12, color: c.textSecondary }}>Model used for generating document embeddings for RAG.</span>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        style={{
          padding: "10px 20px",
          borderRadius: t.radii.md,
          border: "none",
          backgroundColor: c.primary,
          color: "#FFFFFF",
          cursor: saving ? "default" : "pointer",
          fontWeight: 600,
          fontSize: 14,
          opacity: saving ? 0.5 : 1,
        }}
      >
        {saving ? "Saving..." : "Save settings"}
      </button>
    </div>
  )
}
