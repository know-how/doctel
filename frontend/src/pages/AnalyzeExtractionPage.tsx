import React, { useEffect, useState } from "react"
import { runExtraction, getDocumentLibrary, getOutputs } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

type DocumentItem = { id: string; filename: string; status: string }
type ExtractionResult = { document_id: string; document_name: string; data: any }
type HistoryItem = { id: string; type: string; name: string; created_at: string; result?: any }

export const AnalyzeExtractionPage: React.FC = () => {
  const { theme: themeName, isDark } = useTheme()
  const t = getTokens(themeName)
  const c = t.colors

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [docsError, setDocsError] = useState<string | null>(null)

  const [schema, setSchema] = useState(`{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "title": { "type": "string" },
    "date": { "type": "string" },
    "parties": { "type": "array", "items": { "type": "string" } },
    "obligations": { "type": "array", "items": { "type": "string" } },
    "value": { "type": "number" },
    "summary": { "type": "string" }
  },
  "required": ["title", "date"]
}`)
  const [schemaError, setSchemaError] = useState<string | null>(null)

  const [results, setResults] = useState<ExtractionResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const styleId = "extraction-anim"
    if (document.getElementById(styleId)) return
    const style = document.createElement("style")
    style.id = styleId
    style.textContent = [
      "@keyframes skeleton-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.7; } }",
      ".skeleton-line { border-radius: 4px; animation: skeleton-pulse 1.5s infinite ease-in-out; }",
      "@keyframes progressPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }",
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

  useEffect(() => {
    const load = async () => {
      try {
        setLoadingHistory(true)
        const res = await getOutputs({ type: "extraction", page: 1 })
        setHistory((res.outputs || res.items || []).slice(0, 10))
      } catch {
        setHistory([])
      } finally {
        setLoadingHistory(false)
      }
    }
    load()
  }, [results])

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    )
    setResults(null)
    setError(null)
  }

  const validateSchema = (text: string): boolean => {
    if (!text.trim()) {
      setSchemaError("Schema cannot be empty")
      return false
    }
    try {
      JSON.parse(text)
      setSchemaError(null)
      return true
    } catch (e: any) {
      setSchemaError(`Invalid JSON: ${e.message}`)
      return false
    }
  }

  const handleSchemaChange = (val: string) => {
    setSchema(val)
    if (val.trim()) {
      try {
        JSON.parse(val)
        setSchemaError(null)
      } catch {
        setSchemaError("JSON is not valid yet")
      }
    } else {
      setSchemaError(null)
    }
  }

  const handleRun = async () => {
    if (selectedDocIds.length === 0) {
      setError("Select at least one document")
      return
    }
    if (!validateSchema(schema)) return

    try {
      setLoading(true)
      setError(null)
      setResults(null)
      setProgress(0)

      const interval = window.setInterval(() => {
        setProgress((p) => Math.min(p + Math.random() * 20, 90))
      }, 600)

      const res = await runExtraction(schema, selectedDocIds)

      window.clearInterval(interval)
      setProgress(100)

      const extracted: ExtractionResult[] = (res.results || res.data || []).map((item: any) => ({
        document_id: item.document_id || item.id,
        document_name: item.document_name || item.filename || "Unknown",
        data: item.extracted || item.data || item,
      }))
      setResults(extracted)
    } catch (e: any) {
      setError(e.message ?? "Extraction failed")
    } finally {
      setLoading(false)
    }
  }

  const highlightJson = (obj: any): React.ReactNode => {
    const json = JSON.stringify(obj, null, 2)
    const tokens = json.split(/(\".*?\"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\],:]|\s+)/g)

    return (
      <pre style={{
        margin: 0,
        padding: 16,
        borderRadius: 10,
        fontSize: 13,
        lineHeight: 1.7,
        overflowX: "auto",
        backgroundColor: isDark ? "#0F172A" : "#1e293b",
        color: "#E2E8F0",
        fontFamily: "'Fira Code', 'IBM Plex Mono', 'Courier New', monospace",
      }}>
        {tokens.filter(Boolean).map((token, i) => {
          let style: React.CSSProperties = { color: "#E2E8F0" }
          if (/^\".*\"$/.test(token)) {
            if (token.includes(":")) style = { color: "#94A3B8" }
            else style = { color: "#A5D6A7" }
          } else if (/true|false/.test(token)) style = { color: "#CE93D8" }
          else if (/null/.test(token)) style = { color: "#EF9A9A" }
          else if (/^-?\d/.test(token)) style = { color: "#FFCC80" }
          else if (/[{}\[\],:]/.test(token)) style = { color: "#78909C" }
          return <span key={i} style={style}>{token}</span>
        })}
      </pre>
    )
  }

  return (
    <div style={{ display: "flex", padding: 32, maxWidth: 1200, margin: "0 auto", fontFamily: t.font.sans, color: c.text, gap: 28 }}>
      {/* Main area */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 24px 0" }}>
          Structured Extraction
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

        {/* Schema input */}
        <div style={{
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
          padding: 16,
          marginBottom: 16,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>JSON Schema</span>
            {schemaError && (
              <span style={{ fontSize: 12, color: c.error }}>{schemaError}</span>
            )}
          </div>
          <textarea
            value={schema}
            onChange={(e) => handleSchemaChange(e.target.value)}
            rows={14}
            spellCheck={false}
            style={{
              width: "100%",
              padding: 14,
              borderRadius: 10,
              border: `1px solid ${schemaError ? c.error : c.border}`,
              backgroundColor: isDark ? "#0F172A" : "#1e293b",
              color: "#E2E8F0",
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
          {loading ? "Running Extraction..." : "Run Extraction"}
        </button>

        {/* Progress */}
        {loading && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: c.textSecondary, marginBottom: 6 }}>
              <span>Extracting data...</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div style={{
              height: 6,
              borderRadius: 6,
              backgroundColor: c.surface,
              overflow: "hidden",
            }}>
              <div style={{
                height: "100%",
                width: `${progress}%`,
                borderRadius: 6,
                background: `linear-gradient(90deg, ${c.primary}, ${c.secondary})`,
                transition: "width 0.3s ease",
                animation: "progressPulse 1.2s infinite ease-in-out",
              }} />
            </div>
          </div>
        )}

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

        {/* Results */}
        {results && results.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Results</h2>
            {results.map((r) => (
              <div key={r.document_id} style={{
                backgroundColor: c.cardBg,
                borderRadius: 12,
                border: `1px solid ${c.border}`,
                padding: 16,
              }}>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>
                  {r.document_name}
                </div>
                {highlightJson(r.data)}
              </div>
            ))}
          </div>
        )}

        {results && results.length === 0 && (
          <div style={{ color: c.textMuted, fontSize: 13, textAlign: "center", padding: 32 }}>
            No results returned
          </div>
        )}
      </div>

      {/* Sidebar: Extraction history */}
      <div style={{
        width: 260,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}>
        <div style={{
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
          padding: 16,
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 12px 0" }}>Previous Extractions</h3>

          {loadingHistory ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton-line" style={{
                  height: 36, backgroundColor: c.surface,
                }} />
              ))}
            </div>
          ) : history.length === 0 ? (
            <div style={{ fontSize: 12, color: c.textMuted }}>
              No extraction history yet
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {history.map((h) => (
                <div
                  key={h.id}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 8,
                    backgroundColor: c.surface,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontWeight: 600, color: c.text }}>{h.name || h.type}</div>
                  <div style={{ color: c.textMuted, fontSize: 11 }}>
                    {h.created_at ? new Date(h.created_at).toLocaleString() : ""}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
