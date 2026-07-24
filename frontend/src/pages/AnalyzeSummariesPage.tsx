import React, { useEffect, useState } from "react"
import { generateSummary, getEnterpriseSummary, getDocumentLibrary, exportOutput } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import type { EnterpriseSummary } from "../types/api"

type DocumentItem = { id: string; filename: string; status: string }
type SummaryResult = { document_id: string; document_name: string; summary: string; executive_summary?: string; topics?: string[]; enterprise?: EnterpriseSummary | null }

export const AnalyzeSummariesPage: React.FC = () => {
  const { theme: themeName, isDark } = useTheme()
  const t = getTokens(themeName)
  const c = t.colors

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [docsError, setDocsError] = useState<string | null>(null)

  const [summaries, setSummaries] = useState<SummaryResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const styleId = "summary-anim"
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
    const load = async () => {
      try {
        setLoadingDocs(true)
        setDocsError(null)
        const res = await getDocumentLibrary()
        setDocuments(res.documents || res.items || [])
      } catch (e: any) {
        setDocsError(e.message ?? "Failed to load documents")
      } finally {
        setLoadingDocs(false)
      }
    }
    load()
  }, [])

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    )
    setSummaries(null)
    setError(null)
  }

  const selectAll = () => setSelectedDocIds(documents.map((d) => d.id))
  const clearSelection = () => {
    setSelectedDocIds([])
    setSummaries(null)
  }

  const handleGenerate = async () => {
    if (selectedDocIds.length === 0) {
      setError("Select at least one document to summarize")
      return
    }

    try {
      setLoading(true)
      setError(null)
      setSummaries(null)

      // Try to get enterprise summaries for each selected document in parallel
      const docMap = new Map(documents.map(d => [d.id, d]))
      const results = await Promise.allSettled(
        selectedDocIds.map(docId =>
          getEnterpriseSummary(docId).then(esRes => ({
            document_id: docId,
            document_name: docMap.get(docId)?.filename || esRes.filename || "Unknown",
            summary: esRes.summary?.executive_summary || "",
            executive_summary: esRes.summary?.executive_summary,
            topics: [],
            enterprise: esRes.summary as EnterpriseSummary | null,
          }))
        )
      )

      const enterpriseResults: SummaryResult[] = []
      for (const r of results) {
        if (r.status === "fulfilled") {
          enterpriseResults.push(r.value)
        } else {
          enterpriseResults.push({
            document_id: "",
            document_name: "Failed to load",
            summary: "",
            topics: [],
            enterprise: null,
          })
        }
      }

      // If enterprise summaries failed entirely, fall back to batch
      if (enterpriseResults.every(r => !r.enterprise)) {
        const res = await generateSummary(selectedDocIds)
        const fallbackResults: SummaryResult[] = (res.summaries || res.results || res.data || []).map((item: any) => ({
          document_id: item.document_id || item.id,
          document_name: item.document_name || item.filename || "Unknown",
          summary: item.summary || item.text || item.content || "",
          executive_summary: item.executive_summary,
          topics: item.topics,
          enterprise: null,
        }))
        setSummaries(fallbackResults)
      } else {
        setSummaries(enterpriseResults)
      }
    } catch (e: any) {
      setError(e.message ?? "Failed to generate summaries")
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (!summaries || summaries.length === 0) return
    const text = summaries
      .map(
        (s) =>
          `---\nDocument: ${s.document_name}\n\n${s.summary}\n${s.topics ? `\nTopics: ${s.topics.join(", ")}\n` : ""}`,
      )
      .join("\n\n")
    const blob = new Blob([text], { type: "text/plain" })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `summaries_${new Date().toISOString().slice(0, 10)}.txt`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: "0 auto", fontFamily: t.font.sans, color: c.text }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, margin: 0 }}>
          Batch Summaries
        </h1>
        {summaries && summaries.length > 0 && (
          <button
            onClick={handleDownload}
            style={{
              padding: "9px 20px",
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
            Download as Text
          </button>
        )}
      </div>

      {/* Document selector */}
      <div style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        border: `1px solid ${c.border}`,
        padding: 16,
        marginBottom: 20,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>
            Documents ({selectedDocIds.length} selected)
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={selectAll} style={btnSmStyle(c)}>Select All</button>
            <button onClick={clearSelection} style={btnSmStyle(c)}>Clear</button>
          </div>
        </div>

        {loadingDocs && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-line" style={{
                height: 28, width: `${55 + i * 12}%`, backgroundColor: c.surface,
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

      {/* Generate button */}
      <button
        onClick={handleGenerate}
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
        {loading ? "Generating..." : "Generate Summaries"}
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

      {/* Empty / prompt */}
      {!loading && !summaries && !error && (
        <div style={{
          textAlign: "center",
          padding: "48px 24px",
          color: c.textMuted,
          fontSize: 14,
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
        }}>
          Select documents to summarize
        </div>
      )}

      {/* Loading: skeleton cards */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              padding: 20,
            }}>
              <div className="skeleton-line" style={{
                height: 16, width: "35%", backgroundColor: c.surface, marginBottom: 12,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "90%", backgroundColor: c.surface, marginBottom: 6,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "75%", backgroundColor: c.surface, marginBottom: 6,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "60%", backgroundColor: c.surface,
              }} />
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {!loading && summaries && summaries.length === 0 && (
        <div style={{ color: c.textMuted, fontSize: 13, textAlign: "center", padding: 32 }}>
          No summaries returned
        </div>
      )}

      {!loading && summaries && summaries.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {summaries.map((s) => (
            <div key={s.document_id} style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              padding: 20,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: `linear-gradient(135deg, ${c.primary}, ${c.secondary})`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  D
                </div>
                <div style={{ fontWeight: 700, fontSize: 14 }}>
                  {s.document_name}
                </div>
              </div>
              <p style={{
                fontSize: 14,
                lineHeight: 1.7,
                color: c.textSecondary,
                margin: "0 0 12px 0",
                whiteSpace: "pre-wrap",
              }}>
                {s.summary}
              </p>
              {s.topics && s.topics.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {s.topics.map((topic) => (
                    <span key={topic} style={{
                      padding: "3px 10px",
                      borderRadius: 10,
                      backgroundColor: c.surfaceActive,
                      fontSize: 11,
                      fontWeight: 500,
                      color: c.primary,
                    }}>
                      {topic}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function btnSmStyle(c: ReturnType<typeof getTokens>["colors"]): React.CSSProperties {
  return {
    padding: "4px 12px",
    borderRadius: 6,
    border: `1px solid ${c.border}`,
    backgroundColor: c.surface,
    color: c.textSecondary,
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  }
}
