import React, { useEffect, useState } from "react"
import { compareDocuments, getDocumentLibrary, ApiError } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

type DocumentItem = { id: string; filename: string; status: string }
type CompareDoc = {
  label: string
  document_id: string
  filename: string
  summary: string
  sentiment: string
  topics: string[]
}

type CompareResult = {
  comparison: CompareDoc[]
  similarity?: number
  doc_a?: { name: string; content: string; entities: { name: string; type: string; category: string }[] }
  doc_b?: { name: string; content: string; entities: { name: string; type: string; category: string }[] }
  common_entities?: { name: string; type: string }[]
  unique_a?: { name: string; type: string }[]
  unique_b?: { name: string; type: string }[]
  diff_summary?: string
}

export const AnalyzeComparePage: React.FC = () => {
  const { theme: themeName, isDark } = useTheme()
  const t = getTokens(themeName)
  const c = t.colors

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [docsError, setDocsError] = useState<string | null>(null)

  const [docA, setDocA] = useState<string>("")
  const [docB, setDocB] = useState<string>("")

  const [result, setResult] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [permissionError, setPermissionError] = useState(false)

  useEffect(() => {
    const styleId = "compare-anim"
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

  const handleCompare = async () => {
    if (!docA || !docB) {
      setError("Select two documents to compare")
      return
    }
    if (docA === docB) {
      setError("Select two different documents")
      return
    }

    try {
      setLoading(true)
      setError(null)
      setResult(null)
      setPermissionError(false)

      const res = await compareDocuments(docA, docB)

      const comp = res.comparison as CompareDoc[] | undefined

      const docAFromComp = comp?.find((d) => d.label === "doc_a")
      const docBFromComp = comp?.find((d) => d.label === "doc_b")

      const allTopicsA = docAFromComp?.topics ?? []
      const allTopicsB = docBFromComp?.topics ?? []
      const commonTopics = allTopicsA.filter((t) => allTopicsB.includes(t))
      const uniqueTopicsA = allTopicsA.filter((t) => !allTopicsB.includes(t))
      const uniqueTopicsB = allTopicsB.filter((t) => !allTopicsA.includes(t))

      const topicOverlapRatio = allTopicsA.length + allTopicsB.length > 0
        ? commonTopics.length / (allTopicsA.length + allTopicsB.length - commonTopics.length || 1)
        : 0

      setResult({
        comparison: comp ?? [],
        similarity: res.similarity ?? res.similarity_score ?? res.score ?? Math.round(topicOverlapRatio * 100) / 100,
        doc_a: res.doc_a ?? res.document_a ?? (docAFromComp ? {
          name: docAFromComp.filename,
          content: docAFromComp.summary ?? "",
          entities: (docAFromComp.topics ?? []).map((t: string) => ({ name: t, type: "topic", category: "topic" })),
        } : { name: "", content: "", entities: [] }),
        doc_b: res.doc_b ?? res.document_b ?? (docBFromComp ? {
          name: docBFromComp.filename,
          content: docBFromComp.summary ?? "",
          entities: (docBFromComp.topics ?? []).map((t: string) => ({ name: t, type: "topic", category: "topic" })),
        } : { name: "", content: "", entities: [] }),
        common_entities: res.common_entities ?? res.matching_entities ?? commonTopics.map((t: string) => ({ name: t, type: "topic" })),
        unique_a: res.a_only_entities ?? res.unique_a ?? uniqueTopicsA.map((t: string) => ({ name: t, type: "topic" })),
        unique_b: res.b_only_entities ?? res.unique_b ?? uniqueTopicsB.map((t: string) => ({ name: t, type: "topic" })),
        diff_summary: res.diff_summary ?? (docAFromComp && docBFromComp
          ? `Comparison of "${docAFromComp.filename}" and "${docBFromComp.filename}". ${commonTopics.length} shared topics, ${uniqueTopicsA.length} unique to Document A, ${uniqueTopicsB.length} unique to Document B.`
          : ""),
      })
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 403) {
        setPermissionError(true)
        setError("You need admin or analyst permissions to compare documents.")
      } else {
        setError(e.message ?? "Comparison failed")
      }
    } finally {
      setLoading(false)
    }
  }

  const docName = (id: string) => documents.find((d) => d.id === id)?.filename || id

  const simPercent = result?.similarity != null ? Math.round(result.similarity * 100) : null

  const selectStyle: React.CSSProperties = {
    padding: "10px 14px",
    borderRadius: 10,
    border: `1px solid ${c.border}`,
    backgroundColor: c.inputBg,
    color: c.text,
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  }

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: "0 auto", fontFamily: t.font.sans, color: c.text }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 24px 0" }}>
        Document Comparison
      </h1>

      {/* Document selectors */}
      <div style={{ display: "flex", gap: 20, marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            Document A
          </label>
          {loadingDocs ? (
            <div className="skeleton-line" style={{ height: 42, backgroundColor: c.surface, borderRadius: 10 }} />
          ) : docsError ? (
            <div style={{ color: c.error, fontSize: 12 }}>{docsError}</div>
          ) : (
            <select
              value={docA}
              onChange={(e) => setDocA(e.target.value)}
              style={selectStyle}
            >
              <option value="" style={{ backgroundColor: c.bgSecondary, color: c.text }}>-- Select Document A --</option>
              {documents
                .filter((d) => d.id !== docB)
                .map((d) => (
<option key={d.id} value={d.id} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{d.filename}</option>
                ))}
              </select>
            )}
          </div>

          <div style={{
            alignSelf: "center",
          fontSize: 14,
          fontWeight: 700,
          color: c.textMuted,
          paddingTop: 22,
        }}>
          VS
        </div>

        <div style={{ flex: 1 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            Document B
          </label>
          {loadingDocs ? (
            <div className="skeleton-line" style={{ height: 42, backgroundColor: c.surface, borderRadius: 10 }} />
          ) : (
            <select
              value={docB}
              onChange={(e) => setDocB(e.target.value)}
              style={selectStyle}
            >
              <option value="" style={{ backgroundColor: c.bgSecondary, color: c.text }}>-- Select Document B --</option>
              {documents
                .filter((d) => d.id !== docA)
                .map((d) => (
<option key={d.id} value={d.id} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{d.filename}</option>
                ))}
              </select>
            )}
          </div>
        </div>

      {/* Compare button */}
      <button
        onClick={handleCompare}
        disabled={loading || !docA || !docB}
        style={{
          padding: "12px 32px",
          borderRadius: 12,
          border: "none",
          background: `linear-gradient(135deg, ${c.primary}, ${c.primaryHover})`,
          color: "#fff",
          fontSize: 15,
          fontWeight: 700,
          cursor: loading || !docA || !docB ? "not-allowed" : "pointer",
          opacity: loading || !docA || !docB ? 0.5 : 1,
          fontFamily: "inherit",
          marginBottom: 24,
          boxShadow: "0 4px 16px rgba(91,136,255,0.3)",
        }}
      >
        {loading ? "Comparing..." : "Compare"}
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
          {permissionError && (
            <div style={{ marginTop: 8, fontSize: 12, color: c.textMuted }}>
              Contact your administrator to request the analyst or admin role.
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!loading && !result && !error && (
        <div style={{
          textAlign: "center",
          padding: "48px 24px",
          color: c.textMuted,
          fontSize: 14,
          backgroundColor: c.cardBg,
          borderRadius: 12,
          border: `1px solid ${c.border}`,
        }}>
          Select two documents to compare
        </div>
      )}

      {/* Loading: skeleton panels */}
      {loading && (
        <div style={{ display: "flex", gap: 16 }}>
          {[1, 2].map((i) => (
            <div key={i} style={{
              flex: 1,
              backgroundColor: c.cardBg,
              borderRadius: 12,
              border: `1px solid ${c.border}`,
              padding: 20,
            }}>
              <div className="skeleton-line" style={{
                height: 16, width: "40%", backgroundColor: c.surface, marginBottom: 16,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "90%", backgroundColor: c.surface, marginBottom: 6,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "80%", backgroundColor: c.surface, marginBottom: 6,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "65%", backgroundColor: c.surface, marginBottom: 6,
              }} />
              <div className="skeleton-line" style={{
                height: 12, width: "70%", backgroundColor: c.surface,
              }} />
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {!loading && result && (() => {
        const compA = result.comparison?.find((d) => d.label === "doc_a")
        const compB = result.comparison?.find((d) => d.label === "doc_b")
        const summaryA = result.doc_a?.content || compA?.summary || "No summary available"
        const summaryB = result.doc_b?.content || compB?.summary || "No summary available"
        const sentimentA = compA?.sentiment || ""
        const sentimentB = compB?.sentiment || ""
        const topicsA = compA?.topics ?? result.doc_a?.entities?.map((e) => e.name) ?? []
        const topicsB = compB?.topics ?? result.doc_b?.entities?.map((e) => e.name) ?? []

        return (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Diff summary */}
            {result.diff_summary && (
              <div style={{
                backgroundColor: c.cardBg,
                borderRadius: 12,
                border: `1px solid ${c.border}`,
                padding: 20,
              }}>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
                  Comparison Summary
                </div>
                <p style={{ fontSize: 13, lineHeight: 1.7, color: c.textSecondary, margin: 0, whiteSpace: "pre-wrap" }}>
                  {result.diff_summary}
                </p>
              </div>
            )}

            {/* Similarity score */}
            {simPercent != null && (
              <div style={{
                backgroundColor: c.cardBg,
                borderRadius: 12,
                border: `1px solid ${c.border}`,
                padding: 20,
              }}>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
                  Topic Overlap
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    flex: 1,
                    height: 12,
                    borderRadius: 12,
                    backgroundColor: c.surface,
                    overflow: "hidden",
                  }}>
                    <div style={{
                      height: "100%",
                      width: `${simPercent}%`,
                      borderRadius: 12,
                      background: `linear-gradient(90deg, ${c.success}, ${c.primary})`,
                      transition: "width 0.6s ease",
                    }} />
                  </div>
                  <span style={{
                    fontSize: 18,
                    fontWeight: 800,
                    color: c.primary,
                    minWidth: 48,
                    textAlign: "right",
                  }}>
                    {simPercent}%
                  </span>
                </div>
              </div>
            )}

            {/* Side-by-side */}
            <div style={{ display: "flex", gap: 16 }}>
              {/* Doc A */}
              <div style={{
                flex: 1,
                backgroundColor: c.cardBg,
                borderRadius: 12,
                border: `1px solid ${c.border}`,
                padding: 20,
              }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 12px 0", color: c.primary }}>
                  {compA?.filename || result.doc_a?.name || docName(docA)}
                </h3>
                {sentimentA && (
                  <div style={{ marginBottom: 8, display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 20, backgroundColor: c.surface, fontSize: 11, color: c.textSecondary }}>
                    Sentiment: <strong>{sentimentA}</strong>
                  </div>
                )}
                <p style={{
                  fontSize: 13,
                  lineHeight: 1.7,
                  color: c.textSecondary,
                  whiteSpace: "pre-wrap",
                  margin: `${sentimentA ? 8 : 0}px 0 0 0`,
                }}>
                  {summaryA}
                </p>

                {topicsA.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: c.accent }}>
                      Topics
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {topicsA.map((t, i) => {
                        const isCommon = result.common_entities?.some((e) => e.name === t)
                        const isOnlyA = result.unique_a?.some((e) => e.name === t)
                        return (
                          <span key={i} style={{
                            padding: "3px 8px",
                            borderRadius: 6,
                            backgroundColor: isCommon ? c.surfaceActive : isOnlyA ? c.surface : c.surface,
                            fontSize: 11,
                            color: isCommon ? c.success : isOnlyA ? c.primary : c.textMuted,
                            border: isOnlyA ? `1px solid ${c.primary}` : isCommon ? `1px solid ${c.success}` : `1px solid ${c.border}`,
                          }}>
                            {t}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                )}

                {result.unique_a && result.unique_a.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: c.accent }}>
                      Unique Entities
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {result.unique_a.map((e, i) => (
                        <span key={i} style={{
                          padding: "3px 8px",
                          borderRadius: 6,
                          backgroundColor: c.surfaceActive,
                          fontSize: 11,
                          color: c.primary,
                        }}>
                          {e.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Middle diff indicator */}
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-start",
                gap: 10,
                paddingTop: 12,
                minWidth: 40,
              }}>
                <div style={{
                  width: 2,
                  flex: 1,
                  background: `linear-gradient(180deg, ${c.primary}33, ${c.primary}, ${c.secondary}33)`,
                  borderRadius: 2,
                }} />
              </div>

              {/* Doc B */}
              <div style={{
                flex: 1,
                backgroundColor: c.cardBg,
                borderRadius: 12,
                border: `1px solid ${c.border}`,
                padding: 20,
              }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 12px 0", color: c.secondary }}>
                  {compB?.filename || result.doc_b?.name || docName(docB)}
                </h3>
                {sentimentB && (
                  <div style={{ marginBottom: 8, display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 20, backgroundColor: c.surface, fontSize: 11, color: c.textSecondary }}>
                    Sentiment: <strong>{sentimentB}</strong>
                  </div>
                )}
                <p style={{
                  fontSize: 13,
                  lineHeight: 1.7,
                  color: c.textSecondary,
                  whiteSpace: "pre-wrap",
                  margin: `${sentimentB ? 8 : 0}px 0 0 0`,
                }}>
                  {summaryB}
                </p>

                {topicsB.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: c.accent }}>
                      Topics
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {topicsB.map((t, i) => {
                        const isCommon = result.common_entities?.some((e) => e.name === t)
                        const isOnlyB = result.unique_b?.some((e) => e.name === t)
                        return (
                          <span key={i} style={{
                            padding: "3px 8px",
                            borderRadius: 6,
                            backgroundColor: isCommon ? c.surfaceActive : isOnlyB ? c.surface : c.surface,
                            fontSize: 11,
                            color: isCommon ? c.success : isOnlyB ? c.secondary : c.textMuted,
                            border: isOnlyB ? `1px solid ${c.secondary}` : isCommon ? `1px solid ${c.success}` : `1px solid ${c.border}`,
                          }}>
                            {t}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                )}

                {result.unique_b && result.unique_b.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: c.accent }}>
                      Unique Entities
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {result.unique_b.map((e, i) => (
                        <span key={i} style={{
                          padding: "3px 8px",
                          borderRadius: 6,
                          backgroundColor: c.surfaceActive,
                          fontSize: 11,
                          color: c.secondary,
                        }}>
                          {e.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Entity/Topic comparison table */}
            {((result.common_entities && result.common_entities.length > 0) ||
              (result.unique_a && result.unique_a.length > 0) ||
              (result.unique_b && result.unique_b.length > 0)) && (
              <div style={{
                backgroundColor: c.cardBg,
                borderRadius: 12,
                border: `1px solid ${c.border}`,
                padding: 20,
              }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 14px 0" }}>
                  Entity Comparison
                </h3>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: `1px solid ${c.border}` }}>
                        <th style={{ textAlign: "left", padding: "8px 12px", color: c.textSecondary }}>
                          Entity
                        </th>
                        <th style={{ textAlign: "left", padding: "8px 12px", color: c.textSecondary }}>
                          Type
                        </th>
                        <th style={{ textAlign: "center", padding: "8px 12px", color: c.primary }}>
                          Document A
                        </th>
                        <th style={{ textAlign: "center", padding: "8px 12px", color: c.secondary }}>
                          Document B
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.common_entities?.map((e, i) => (
                        <tr key={`c_${i}`} style={{ borderBottom: `1px solid ${c.border}` }}>
                          <td style={{ padding: "8px 12px" }}>{e.name}</td>
                          <td style={{ padding: "8px 12px", color: c.textMuted }}>{e.type}</td>
                          <td style={{ textAlign: "center", padding: "8px 12px" }}>
                            <span style={{
                              display: "inline-block",
                              width: 10, height: 10, borderRadius: "50%",
                              backgroundColor: c.success,
                            }} />
                          </td>
                          <td style={{ textAlign: "center", padding: "8px 12px" }}>
                            <span style={{
                              display: "inline-block",
                              width: 10, height: 10, borderRadius: "50%",
                              backgroundColor: c.success,
                            }} />
                          </td>
                        </tr>
                      ))}
                      {result.unique_a?.map((e, i) => (
                        <tr key={`ua_${i}`} style={{ borderBottom: `1px solid ${c.border}` }}>
                          <td style={{ padding: "8px 12px" }}>{e.name}</td>
                          <td style={{ padding: "8px 12px", color: c.textMuted }}>{e.type}</td>
                          <td style={{ textAlign: "center", padding: "8px 12px" }}>
                            <span style={{
                              display: "inline-block",
                              width: 10, height: 10, borderRadius: "50%",
                              backgroundColor: c.success,
                            }} />
                          </td>
                          <td style={{ textAlign: "center", padding: "8px 12px", color: c.textMuted }}>
                            &mdash;
                          </td>
                        </tr>
                      ))}
                      {result.unique_b?.map((e, i) => (
                        <tr key={`ub_${i}`} style={{ borderBottom: `1px solid ${c.border}` }}>
                          <td style={{ padding: "8px 12px" }}>{e.name}</td>
                          <td style={{ padding: "8px 12px", color: c.textMuted }}>{e.type}</td>
                          <td style={{ textAlign: "center", padding: "8px 12px", color: c.textMuted }}>
                            &mdash;
                          </td>
                          <td style={{ textAlign: "center", padding: "8px 12px" }}>
                            <span style={{
                              display: "inline-block",
                              width: 10, height: 10, borderRadius: "50%",
                              backgroundColor: c.success,
                            }} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )
      })()}
    </div>
  )
}
