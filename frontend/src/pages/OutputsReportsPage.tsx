import React, { useEffect, useState } from "react"
import { getMyDocuments, generateSummary, runExtraction, classifyDocuments, compareDocuments } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface DocItem {
  id: string
  filename?: string
  name?: string
}

interface SectionOption {
  key: string
  label: string
  description: string
}

const SECTIONS: SectionOption[] = [
  { key: "summary", label: "Summary", description: "Executive summary of document content" },
  { key: "entities", label: "Entities", description: "Named entities and key terms" },
  { key: "topics", label: "Topics", description: "Identified topics and themes" },
  { key: "actions", label: "Action Items", description: "Extracted action items and decisions" },
]

const OUTPUT_TYPES = ["summary", "extraction", "classification", "comparison"] as const

export const OutputsReportsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [documents, setDocuments] = useState<DocItem[]>([])
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [outputType, setOutputType] = useState("summary")
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set(["summary", "entities"]))
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [docSearch, setDocSearch] = useState("")
  const [previewText, setPreviewText] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadDocs = async () => {
      try {
        setLoadingDocs(true)
        const res = await getMyDocuments(1, 200)
        setDocuments(res.documents ?? res.items ?? [])
      } catch (e: any) {
        setError(e.message ?? "Failed to load documents")
      } finally {
        setLoadingDocs(false)
      }
    }
    loadDocs()
  }, [])

  const toggleDoc = (id: string) => {
    setSelectedDocs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSection = (key: string) => {
    setSelectedSections((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const generateReportData = async (): Promise<any> => {
    const docIds = Array.from(selectedDocs)
    if (docIds.length === 0) throw new Error("No documents selected")
    switch (outputType) {
      case "summary":
        return await generateSummary(docIds)
      case "extraction":
        return await runExtraction("", docIds)
      case "classification":
        return await classifyDocuments({ rules: "Classify each document", document_ids: docIds })
      case "comparison":
        return docIds.length >= 2
          ? await compareDocuments(docIds[0], docIds[1])
          : { error: "Select at least 2 documents for comparison" }
      default:
        return await generateSummary(docIds)
    }
  }

  const formatReportText = (data: any): string => {
    const lines: string[] = [`# Report - ${new Date().toISOString().slice(0, 10)}`, `Output Type: ${outputType}`, `Documents: ${selectedDocs.size}`, ""]
    if (selectedSections.has("summary")) {
      lines.push("## Summary", data?.executive_summary || data?.summary || JSON.stringify(data, null, 2), "")
    }
    if (selectedSections.has("entities") && data?.entities?.length) {
      lines.push("## Entities", data.entities.map((e: any) => `- ${typeof e === "string" ? e : JSON.stringify(e)}`).join("\n"), "")
    }
    if (selectedSections.has("topics") && data?.topics?.length) {
      lines.push("## Topics", data.topics.map((t: any) => `- ${typeof t === "string" ? t : JSON.stringify(t)}`).join("\n"), "")
    }
    if (selectedSections.has("actions")) {
      const items = data?.action_items || data?.actions || []
      if (items.length) {
        lines.push("## Action Items", items.map((a: any) => `- ${typeof a === "string" ? a : JSON.stringify(a)}`).join("\n"), "")
      }
    }
    return lines.join("\n")
  }

  const handleGeneratePreview = async () => {
    if (selectedDocs.size === 0) return
    try {
      setGenerating(true)
      setError(null)
      const data = await generateReportData()
      setPreviewText(formatReportText(data))
    } catch (e: any) {
      setError(e.message ?? "Report generation failed")
    } finally {
      setGenerating(false)
    }
  }

  const handleExport = async () => {
    try {
      setGenerating(true)
      setError(null)
      const data = await generateReportData()
      const text = formatReportText(data)
      const blob = new Blob([text], { type: "text/plain" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `report_${Date.now()}.txt`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e.message ?? "Export failed")
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Report Builder</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
          Build custom reports by selecting documents, output type, and sections.
        </p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Config panel */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: t.spacing.lg,
          marginBottom: t.spacing.lg,
        }}
      >
        {/* Document selection */}
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg }}>
          <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Select documents</h3>
          {loadingDocs ? (
            <div style={{ color: c.textSecondary, fontSize: 13 }}>Loading documents...</div>
          ) : documents.length === 0 ? (
            <div style={{ color: c.textSecondary, fontSize: 13 }}>No documents available.</div>
          ) : (
            <>
              <input
                type="text"
                placeholder="Search documents..."
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: t.radii.sm,
                  border: `1px solid ${c.border}`,
                  backgroundColor: c.inputBg,
                  color: c.text,
                  fontSize: 13,
                  marginBottom: 8,
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ maxHeight: 200, overflowY: "auto", display: "grid", gap: 6 }}>
                {documents
                  .filter((d) => !(docSearch.trim()) || (d.filename ?? d.name ?? d.id).toLowerCase().includes(docSearch.toLowerCase()))
                  .map((d) => (
                <label
                  key={d.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "6px 8px",
                    borderRadius: t.radii.sm,
                    cursor: "pointer",
                    fontSize: 13,
                    color: c.text,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedDocs.has(d.id)}
                    onChange={() => toggleDoc(d.id)}
                    style={{ accentColor: c.primary }}
                  />
                  {d.filename ?? d.name ?? d.id}
                </label>
              ))}
            </div>
          </>
          )}
          <div style={{ marginTop: t.spacing.sm, fontSize: 12, color: c.textSecondary }}>
            {selectedDocs.size} document(s) selected
          </div>
        </div>

        {/* Output type */}
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg }}>
          <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Output type</h3>
          <div style={{ display: "grid", gap: 6 }}>
            {OUTPUT_TYPES.map((ot) => (
              <label
                key={ot}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 10px",
                  borderRadius: t.radii.sm,
                  border: `1px solid ${outputType === ot ? c.primary : c.border}`,
                  backgroundColor: outputType === ot ? c.surfaceActive : "transparent",
                  cursor: "pointer",
                  fontSize: 13,
                  color: c.text,
                  textTransform: "capitalize",
                }}
              >
                <input
                  type="radio"
                  name="outputType"
                  value={ot}
                  checked={outputType === ot}
                  onChange={() => setOutputType(ot)}
                  style={{ accentColor: c.primary }}
                />
                {ot}
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Sections */}
      <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, padding: t.spacing.lg, backgroundColor: c.cardBg, marginBottom: t.spacing.lg }}>
        <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Report sections</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {SECTIONS.map((s) => (
            <label
              key={s.key}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: "10px 12px",
                borderRadius: t.radii.md,
                border: `1px solid ${selectedSections.has(s.key) ? c.primary : c.border}`,
                backgroundColor: selectedSections.has(s.key) ? c.surfaceActive : "transparent",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={selectedSections.has(s.key)}
                onChange={() => toggleSection(s.key)}
                style={{ accentColor: c.primary, marginTop: 2 }}
              />
              <div>
                <div style={{ fontWeight: 600, color: c.text, fontSize: 13 }}>{s.label}</div>
                <div style={{ fontSize: 11, color: c.textSecondary }}>{s.description}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Preview */}
      {previewText && (
        <div
          style={{
            borderRadius: t.radii.lg,
            border: `1px solid ${c.border}`,
            padding: t.spacing.lg,
            backgroundColor: c.cardBg,
            marginBottom: t.spacing.lg,
          }}
        >
          <h3 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 14, fontWeight: 700, color: c.text }}>Preview</h3>
          <pre
            style={{
              margin: 0,
              padding: 12,
              borderRadius: t.radii.md,
              backgroundColor: c.surface,
              color: c.text,
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              maxHeight: 400,
              overflowY: "auto",
            }}
          >
            {previewText}
          </pre>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 10 }}>
        <button
          onClick={handleGeneratePreview}
          disabled={generating || selectedDocs.size === 0}
          style={{
            padding: "10px 20px",
            borderRadius: t.radii.md,
            border: `1px solid ${c.border}`,
            backgroundColor: c.surface,
            color: c.text,
            cursor: generating || selectedDocs.size === 0 ? "default" : "pointer",
            fontWeight: 600,
            fontSize: 14,
            opacity: generating || selectedDocs.size === 0 ? 0.5 : 1,
          }}
        >
          {generating ? "Generating..." : "Generate preview"}
        </button>
        <button
          onClick={handleExport}
          disabled={!previewText}
          style={{
            padding: "10px 20px",
            borderRadius: t.radii.md,
            border: "none",
            backgroundColor: c.primary,
            color: "#FFFFFF",
            cursor: previewText ? "pointer" : "default",
            fontWeight: 600,
            fontSize: 14,
            opacity: previewText ? 1 : 0.5,
          }}
        >
          Export report
        </button>
      </div>
    </div>
  )
}
