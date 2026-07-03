import React, { useEffect, useState } from "react"
import { classifyDocuments, getDocumentLibrary, getAvailableModels } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

type DocumentItem = { id: string; filename: string; status: string }
type ClassResult = {
  document_id: string
  document_name: string
  tags: string[]
  categories: string[]
  confidence: number
  reasoning?: string
}

const DEFAULT_RULES = `# Classification Rules
# Define one rule per line. Format: TAG/CATEGORY: condition

URGENT: contains words like "immediate", "emergency", "urgent", "critical"
FINANCE: related to budget, expenditure, revenue, financial statements
LEGAL: contains legal terms, contracts, legislation, compliance
HR: related to personnel, staff, human resources, recruitment
TECHNICAL: contains technical specifications, engineering, IT systems
ROUTINE: contains "status update", "regular report", "routine"
EXTERNAL: sent from outside parties, vendors, stakeholders`

export const AnalyzeClassificationPage: React.FC = () => {
  const { theme: themeName, isDark } = useTheme()
  const t = getTokens(themeName)
  const c = t.colors

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [docsError, setDocsError] = useState<string | null>(null)

  const [rules, setRules] = useState(DEFAULT_RULES)
  const [rulesError, setRulesError] = useState<string | null>(null)

  const [results, setResults] = useState<ClassResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState("")

  const [removedTags, setRemovedTags] = useState<Record<string, string[]>>({})

  useEffect(() => {
    const styleId = "classify-anim"
    if (document.getElementById(styleId)) return
    const style = document.createElement("style")
    style.id = styleId
    style.textContent = [
      "@keyframes skeleton-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.7; } }",
      ".skeleton-line { border-radius: 4px; animation: skeleton-pulse 1.5s infinite ease-in-out; }",
    ].join("\n")
    document.head.appendChild(style)
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoadingDocs(true)
    setDocsError(null)
    Promise.all([
      getDocumentLibrary().catch((e: any) => { setDocsError(e?.message || "Failed to load documents"); return { documents: [] } }),
      getAvailableModels().catch(() => ({ installed: [], available: [] })),
    ]).then(([docsRes, modelsRes]) => {
      if (cancelled) return
      setDocuments(docsRes?.documents || docsRes?.items || [])
      const all = [...new Set([...(modelsRes.installed || []), ...(modelsRes.available || [])])]
      setAvailableModels(all)
      if (all.length > 0) setSelectedModel(all[0])
    }).finally(() => {
      if (!cancelled) setLoadingDocs(false)
    })
    return () => { cancelled = true }
  }, [])

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    )
    setResults(null)
    setError(null)
  }

  const handleRun = async () => {
    if (selectedDocIds.length === 0) {
      setError("Select at least one document to classify")
      return
    }
    if (!rules.trim()) {
      setRulesError("Rules cannot be empty")
      return
    }
    setRulesError(null)

    try {
      setLoading(true)
      setError(null)
      setResults(null)
      setRemovedTags({})

      const payload = {
        rules: rules.trim(),
        document_ids: selectedDocIds,
        model: selectedModel || undefined,
      }
      const res = await classifyDocuments(payload as any)

      const classified: ClassResult[] = (res.results || res.classifications || res.data || []).map((item: any) => ({
        document_id: item.document_id || item.id,
        document_name: item.document_name || item.filename || "Unknown",
        tags: item.tags || item.labels || item.categories || [],
        categories: item.categories || [],
        confidence: item.confidence ?? item.score ?? 0,
        reasoning: item.reasoning,
      }))

      setResults(classified)
    } catch (e: any) {
      const status = e.status ? ` (HTTP ${e.status})` : ""
      setError((e.message || "Classification failed") + status)
    } finally {
      setLoading(false)
    }
  }

  const removeTag = (docId: string, tag: string) => {
    setRemovedTags((prev) => ({
      ...prev,
      [docId]: [...(prev[docId] || []), tag],
    }))
  }

  const getVisibleTags = (docId: string, tags: string[]) => {
    const removed = removedTags[docId] || []
    return tags.filter((t) => !removed.includes(t))
  }

  const confidenceBar = (pct: number) => {
    const clamped = Math.min(100, Math.max(0, Math.round(pct * 100)))
    const barColor = clamped >= 70 ? c.success : clamped >= 40 ? c.warning : c.error
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          flex: 1,
          height: 5,
          borderRadius: 5,
          backgroundColor: c.surface,
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            width: `${clamped}%`,
            borderRadius: 5,
            background: `linear-gradient(90deg, ${barColor}, ${barColor})`,
            transition: "width 0.5s ease",
          }} />
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: c.textSecondary, minWidth: 34 }}>
          {clamped}%
        </span>
      </div>
    )
  }

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: "0 auto", fontFamily: t.font.sans, color: c.text }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 24px 0" }}>
        Auto Classification
      </h1>

      {/* Document selector */}
      <div style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        border: `1px solid ${c.border}`,
        padding: 16,
        marginBottom: 16,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>
            Documents ({selectedDocIds.length} selected)
          </span>
          <button
            onClick={() => setSelectedDocIds([])}
            style={{
              padding: "4px 12px", borderRadius: 6, border: `1px solid ${c.border}`,
              backgroundColor: c.surface, color: c.textSecondary, fontSize: 12,
              cursor: "pointer", fontFamily: "inherit",
            }}
          >
            Clear
          </button>
        </div>

        {loadingDocs && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-line" style={{
                height: 28, width: `${50 + i * 15}%`, backgroundColor: c.surface,
              }} />
            ))}
          </div>
        )}

        {docsError && (
          <div style={{ color: c.error, fontSize: 13, padding: "8px 0" }}>{docsError}</div>
        )}

        {!loadingDocs && !docsError && documents.length === 0 && (
          <div style={{ color: c.textMuted, fontSize: 13, padding: "8px 0" }}>
            No documents available
          </div>
        )}

        {!loadingDocs && !docsError && documents.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, maxHeight: 140, overflowY: "auto" }}>
            {documents.map((doc) => {
              const checked = selectedDocIds.includes(doc.id)
              return (
                <label
                  key={doc.id}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "6px 12px", borderRadius: 8,
                    backgroundColor: checked ? c.surfaceActive : c.surface,
                    border: `1px solid ${checked ? c.borderFocus : c.border}`,
                    cursor: "pointer", fontSize: 13, userSelect: "none",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleDoc(doc.id)}
                    style={{ accentColor: c.primary }}
                  />
                  {doc.filename}
                </label>
              )
            })}
          </div>
        )}
      </div>

      {/* Model selector */}
      <div style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        border: `1px solid ${c.border}`,
        padding: "12px 16px",
        marginBottom: 16,
        display: "flex", alignItems: "center", gap: 12,
      }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Model</span>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          style={{
            padding: "6px 12px", borderRadius: 8,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg, color: c.text,
            fontSize: 13, fontFamily: "inherit", outline: "none",
          }}
        >
          {availableModels.map((m, i) => (
            <option key={i} value={m} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{m}</option>
          ))}
        </select>
      </div>

      {/* Rules textarea */}
      <div style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        border: `1px solid ${c.border}`,
        padding: 16,
        marginBottom: 16,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Classification Rules</span>
          {rulesError && (
            <span style={{ fontSize: 12, color: c.error }}>{rulesError}</span>
          )}
        </div>
        <textarea
          value={rules}
          onChange={(e) => { setRules(e.target.value); setRulesError(null) }}
          rows={12}
          spellCheck={false}
          style={{
            width: "100%",
            padding: 14,
            borderRadius: 10,
            border: `1px solid ${rulesError ? c.error : c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
            lineHeight: 1.6,
            fontFamily: "'Fira Code', 'IBM Plex Mono', monospace",
            resize: "vertical",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={loading || selectedDocIds.length === 0}
        style={{
          padding: "12px 32px",
          borderRadius: 12,
          border: "none",
          background: `linear-gradient(135deg, ${c.primary}, ${c.primaryHover})`,
          color: "#fff",
          fontSize: 15,
          fontWeight: 700,
          cursor: loading || selectedDocIds.length === 0 ? "not-allowed" : "pointer",
          opacity: loading || selectedDocIds.length === 0 ? 0.5 : 1,
          fontFamily: "inherit",
          marginBottom: 24,
          boxShadow: "0 4px 16px rgba(91,136,255,0.3)",
        }}
      >
        {loading ? "Running Classification..." : "Run Classification"}
      </button>

      {/* Error */}
      {error && (
        <div style={{
          padding: "12px 16px",
          borderRadius: 10,
          backgroundColor: isDark ? "rgba(239,68,68,0.15)" : "rgba(220,38,38,0.1)",
          color: c.error,
          fontSize: 13,
          marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {/* Loading: skeleton table */}
      {loading && (
        <div style={{
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
          padding: 20,
        }}>
          <div className="skeleton-line" style={{
            height: 14, width: "30%", backgroundColor: c.surface, marginBottom: 16,
          }} />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ display: "flex", gap: 20, marginBottom: 12 }}>
              <div className="skeleton-line" style={{
                height: 12, width: "25%", backgroundColor: c.surface,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "40%", backgroundColor: c.surface,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "20%", backgroundColor: c.surface,
              }} />
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && !results && !error && selectedDocIds.length === 0 && (
        <div style={{
          textAlign: "center",
          padding: "48px 24px",
          color: c.textMuted,
          fontSize: 14,
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
        }}>
          Select documents and define rules to classify
        </div>
      )}

      {!loading && !results && !error && selectedDocIds.length > 0 && (
        <div style={{
          textAlign: "center",
          padding: "48px 24px",
          color: c.textMuted,
          fontSize: 14,
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
        }}>
          {selectedDocIds.length} document(s) selected. Click "Run Classification" to proceed.
        </div>
      )}

      {/* Results */}
      {!loading && results && results.length === 0 && (
        <div style={{ color: c.textMuted, fontSize: 13, textAlign: "center", padding: 32 }}>
          No classification results returned
        </div>
      )}

      {!loading && results && results.length > 0 && (
        <div style={{
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
          overflow: "hidden",
        }}>
          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "2fr 3fr 1fr",
            padding: "12px 20px",
            borderBottom: `1px solid ${c.border}`,
            backgroundColor: c.surface,
            fontSize: 12,
            fontWeight: 700,
            color: c.textSecondary,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}>
            <span>Document</span>
            <span>Tags / Categories</span>
            <span>Confidence</span>
          </div>

          {/* Table rows */}
          {results.map((r, idx) => (
            <div key={r.document_id} style={{
              display: "grid",
              gridTemplateColumns: "2fr 3fr 1fr",
              padding: "14px 20px",
              borderBottom: idx < results.length - 1 ? `1px solid ${c.border}` : "none",
              alignItems: "start",
            }}>
              {/* Document name */}
              <div style={{ fontSize: 13, fontWeight: 600, paddingRight: 12 }}>
                {r.document_name}
              </div>

              {/* Tags */}
              <div>
                {r.tags.length === 0 && r.categories.length === 0 ? (
                  <span style={{ fontSize: 12, color: c.textMuted }}>No tags assigned</span>
                ) : (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {r.categories.map((cat) => {
                      const visibleTags = getVisibleTags(r.document_id, r.tags)
                      return (
                        <span
                          key={cat}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "4px 10px",
                            borderRadius: 14,
                            backgroundColor: `${c.primary}22`,
                            color: c.primary,
                            fontSize: 12,
                            fontWeight: 500,
                          }}
                        >
                          {cat}
                        </span>
                      )
                    })}
                    {getVisibleTags(r.document_id, r.tags).map((tag) => (
                      <span
                        key={tag}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "4px 10px",
                          borderRadius: 14,
                          backgroundColor: c.surfaceActive,
                          color: c.textSecondary,
                          fontSize: 12,
                          fontWeight: 500,
                        }}
                      >
                        {tag}
                        <span
                          onClick={() => removeTag(r.document_id, tag)}
                          style={{
                            cursor: "pointer",
                            fontSize: 14,
                            lineHeight: 1,
                            marginLeft: 2,
                            opacity: 0.6,
                          }}
                          title="Remove tag"
                        >
                          &times;
                        </span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Confidence */}
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {confidenceBar(r.confidence)}
                {r.reasoning && (
                  <div style={{ fontSize: 11, color: c.textMuted, fontStyle: "italic" }}>
                    {r.reasoning}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Save button (shown when results exist) */}
      {!loading && results && results.length > 0 && (
        <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
          <button
            onClick={() => {
              const visible = results.map((r) => ({
                ...r,
                tags: getVisibleTags(r.document_id, r.tags),
              }))
              const json = JSON.stringify(visible, null, 2)
              const blob = new Blob([json], { type: "application/json" })
              const url = window.URL.createObjectURL(blob)
              const a = document.createElement("a")
              a.href = url
              a.download = `classification_${new Date().toISOString().slice(0, 10)}.json`
              a.click()
              window.URL.revokeObjectURL(url)
            }}
            style={{
              padding: "10px 24px",
              borderRadius: 10,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.text,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Save Classification
          </button>
        </div>
      )}
    </div>
  )
}
