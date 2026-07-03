import React, { useEffect, useState } from "react"
import { getPrompts, savePrompt } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface PromptRecord {
  id: number | string
  prompt_type?: string
  content: string
  version?: number
  versions?: { id: number; content: string; created_at?: string }[]
  created_at?: string
}

const PROMPT_TYPES = ["chat", "summary", "extraction", "classification", "comparison"] as const

export const AdminPromptsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [prompts, setPrompts] = useState<PromptRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeType, setActiveType] = useState<string>("chat")
  const [editingId, setEditingId] = useState<number | string | null>(null)
  const [editContent, setEditContent] = useState("")
  const [saving, setSaving] = useState(false)
  const [showVersions, setShowVersions] = useState<number | string | null>(null)
  const [testInput, setTestInput] = useState("")
  const [testOutput, setTestOutput] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [newType, setNewType] = useState("chat")
  const [newContent, setNewContent] = useState("")

  const loadPrompts = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await getPrompts()
      setPrompts(res.prompts ?? res.items ?? res ?? [])
    } catch (e: any) {
      setError(e.message ?? "Failed to load prompts")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPrompts()
  }, [])

  const filtered = prompts.filter((p) => (p.prompt_type ?? "chat") === activeType)

  const handleSave = async (promptType: string, content: string) => {
    try {
      setSaving(true)
      setError(null)
      await savePrompt(promptType, content)
      await loadPrompts()
      setEditingId(null)
      setShowNew(false)
      setNewContent("")
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (promptType: string, content: string) => {
    try {
      setTesting(true)
      setError(null)
      setTestOutput(`[Test output for "${promptType}" prompt with input: "${testInput || '(no input provided)'}"]

Generated example response based on the current prompt template. In production, this would call the model with the actual prompt and input text.`)
    } catch (e: any) {
      setError(e.message ?? "Test failed")
    } finally {
      setTesting(false)
    }
  }

  const startEdit = (p: PromptRecord) => {
    setEditingId(p.id)
    setEditContent(p.content)
    setShowNew(false)
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>System Prompts</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Manage and edit system prompts grouped by task type.</p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Prompt type tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: t.spacing.lg, flexWrap: "wrap" }}>
        {PROMPT_TYPES.map((pt) => (
          <button
            key={pt}
            onClick={() => { setActiveType(pt); setEditingId(null); setShowVersions(null); setShowNew(false) }}
            style={{
              padding: "6px 14px",
              borderRadius: t.radii.full,
              border: `1px solid ${activeType === pt ? c.primary : c.border}`,
              backgroundColor: activeType === pt ? c.primary : c.surface,
              color: activeType === pt ? "#FFFFFF" : c.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
              textTransform: "capitalize",
            }}
          >
            {pt}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.md }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: c.text, textTransform: "capitalize" }}>
          {activeType} prompts ({filtered.length})
        </h3>
        <button
          onClick={() => { setShowNew(!showNew); setEditingId(null); setShowVersions(null) }}
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
          + New prompt
        </button>
      </div>

      {/* New prompt form */}
      {showNew && (
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.primary}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, marginRight: 8 }}>Type:</label>
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              style={{
                padding: "4px 10px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
              }}
            >
              {PROMPT_TYPES.map((pt) => (
                <option key={pt} value={pt} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{pt}</option>
              ))}
            </select>
          </div>
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="Enter prompt content..."
            rows={8}
            style={{
              width: "100%",
              borderRadius: t.radii.md,
              border: `1px solid ${c.border}`,
              padding: 12,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
              fontFamily: "monospace",
              resize: "vertical",
              boxSizing: "border-box",
            }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button
              onClick={() => handleSave(newType, newContent)}
              disabled={saving || !newContent.trim()}
              style={{
                padding: "8px 16px",
                borderRadius: t.radii.sm,
                border: "none",
                backgroundColor: c.primary,
                color: "#FFFFFF",
                cursor: saving || !newContent.trim() ? "default" : "pointer",
                fontSize: 12,
                fontWeight: 600,
                opacity: saving || !newContent.trim() ? 0.5 : 1,
              }}
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => { setShowNew(false); setNewContent("") }}
              style={{
                padding: "8px 16px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.surface,
                color: c.textSecondary,
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ display: "grid", gap: t.spacing.sm }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ borderRadius: t.radii.md, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, height: 80 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary, color: c.textSecondary }}>
          No prompts defined for {activeType}.
        </div>
      ) : (
        <div style={{ display: "grid", gap: t.spacing.md }}>
          {filtered.map((p) => (
            <div
              key={p.id}
              style={{
                borderRadius: t.radii.lg,
                border: `1px solid ${editingId === p.id ? c.primary : c.border}`,
                padding: t.spacing.lg,
                backgroundColor: c.cardBg,
              }}
            >
              {editingId === p.id ? (
                <>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={6}
                    style={{
                      width: "100%",
                      borderRadius: t.radii.md,
                      border: `1px solid ${c.border}`,
                      padding: 10,
                      backgroundColor: c.inputBg,
                      color: c.text,
                      fontSize: 13,
                      fontFamily: "monospace",
                      resize: "vertical",
                      boxSizing: "border-box",
                    }}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                    <button
                      onClick={() => handleSave(activeType, editContent)}
                      disabled={saving}
                      style={{
                        padding: "6px 14px",
                        borderRadius: t.radii.sm,
                        border: "none",
                        backgroundColor: c.success,
                        color: "#FFFFFF",
                        cursor: saving ? "default" : "pointer",
                        fontSize: 12,
                        fontWeight: 600,
                        opacity: saving ? 0.5 : 1,
                      }}
                    >
                      {saving ? "Saving..." : "Save"}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      style={{
                        padding: "6px 14px",
                        borderRadius: t.radii.sm,
                        border: `1px solid ${c.border}`,
                        backgroundColor: c.surface,
                        color: c.textSecondary,
                        cursor: "pointer",
                        fontSize: 12,
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <div style={{ fontSize: 12, color: c.textSecondary }}>
                      Version {p.version ?? 1}{p.created_at ? ` · ${new Date(p.created_at).toLocaleDateString()}` : ""}
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        onClick={() => startEdit(p)}
                        style={{
                          padding: "4px 10px",
                          borderRadius: t.radii.sm,
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
                        onClick={() => setShowVersions(showVersions === p.id ? null : p.id)}
                        style={{
                          padding: "4px 10px",
                          borderRadius: t.radii.sm,
                          border: `1px solid ${c.border}`,
                          backgroundColor: c.surface,
                          color: c.textSecondary,
                          cursor: "pointer",
                          fontSize: 11,
                          fontWeight: 600,
                        }}
                      >
                        {showVersions === p.id ? "Hide history" : "Version history"}
                      </button>
                    </div>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: 10,
                      borderRadius: t.radii.md,
                      backgroundColor: c.surface,
                      color: c.text,
                      fontSize: 12,
                      lineHeight: 1.5,
                      whiteSpace: "pre-wrap",
                      maxHeight: 150,
                      overflowY: "auto",
                    }}
                  >
                    {p.content.length > 500 ? p.content.slice(0, 500) + "..." : p.content}
                  </pre>
                </>
              )}

              {/* Version history */}
              {showVersions === p.id && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${c.border}` }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: c.textSecondary, marginBottom: 6 }}>Version history</div>
                  {p.versions && p.versions.length > 0 ? (
                    p.versions.map((v) => (
                      <div
                        key={v.id}
                        style={{
                          padding: "6px 0",
                          fontSize: 11,
                          color: c.textSecondary,
                        }}
                      >
                        v{v.id}{v.created_at ? ` · ${new Date(v.created_at).toLocaleDateString()}` : ""}
                      </div>
                    ))
                  ) : (
                    <div style={{ fontSize: 11, color: c.textMuted }}>No previous versions.</div>
                  )}
                </div>
              )}

              {/* Test prompt */}
              {editingId === p.id && (
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${c.border}` }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: c.textSecondary, marginBottom: 6 }}>Test prompt</div>
                  <input
                    type="text"
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    placeholder="Enter test input..."
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: t.radii.sm,
                      border: `1px solid ${c.border}`,
                      backgroundColor: c.inputBg,
                      color: c.text,
                      fontSize: 12,
                      boxSizing: "border-box",
                      marginBottom: 8,
                    }}
                  />
                  <button
                    onClick={() => handleTest(activeType, editContent)}
                    disabled={testing}
                    style={{
                      padding: "6px 14px",
                      borderRadius: t.radii.sm,
                      border: `1px solid ${c.border}`,
                      backgroundColor: c.surface,
                      color: c.text,
                      cursor: testing ? "default" : "pointer",
                      fontSize: 12,
                      fontWeight: 600,
                      opacity: testing ? 0.5 : 1,
                    }}
                  >
                    {testing ? "Running..." : "Run test"}
                  </button>
                  {testOutput && (
                    <pre
                      style={{
                        marginTop: 8,
                        padding: 10,
                        borderRadius: t.radii.md,
                        backgroundColor: c.surface,
                        color: c.text,
                        fontSize: 12,
                        lineHeight: 1.5,
                        whiteSpace: "pre-wrap",
                        maxHeight: 200,
                        overflowY: "auto",
                      }}
                    >
                      {testOutput}
                    </pre>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
