import React, { useEffect, useState, useCallback } from "react"
import { getOutputs, exportOutput } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { Pagination } from "../components/Pagination"

interface OutputItem {
  id: string
  title?: string
  type?: string
  document_name?: string
  created_at?: string
}

interface DownloadRecord {
  filename: string
  format: string
  date: string
  status: "done" | "failed" | "pending"
}

const FORMATS = ["JSON", "CSV", "PDF", "DOCX"] as const
const PAGE_SIZE = 20

const mockDownloads: DownloadRecord[] = [
  { filename: "summary_report_2025-04-15.pdf", format: "PDF", date: "2025-04-15 14:32", status: "done" },
  { filename: "extraction_data_2025-04-14.json", format: "JSON", date: "2025-04-14 09:15", status: "done" },
  { filename: "classifications_2025-04-13.csv", format: "CSV", date: "2025-04-13 16:48", status: "done" },
  { filename: "compare_output_2025-04-12.docx", format: "DOCX", date: "2025-04-12 11:22", status: "failed" },
]

export const OutputsExportsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [outputs, setOutputs] = useState<OutputItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchFormat, setBatchFormat] = useState("JSON")
  const [exporting, setExporting] = useState<string | null>(null)
  const [downloads] = useState<DownloadRecord[]>(mockDownloads)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await getOutputs({ page, page_size: PAGE_SIZE })
      setOutputs(res.outputs ?? res.items ?? [])
      setTotal(res.total ?? (res.outputs ?? res.items ?? []).length)
    } catch (e: any) {
      setError(e.message ?? "Failed to load outputs")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [page])

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (selected.size === outputs.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(outputs.map((o) => o.id)))
    }
  }

  const handleExport = async (outputId: string, format: string) => {
    try {
      setExporting(outputId)
      setError(null)
      const blob = await exportOutput(outputId, format.toLowerCase())
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `output_${outputId}.${format.toLowerCase()}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e.message ?? "Export failed")
    } finally {
      setExporting(null)
    }
  }

  const handleBatchExport = async () => {
    for (const id of selected) {
      await handleExport(id, batchFormat)
    }
  }

  const statusDot = (status: string) => {
    const col = status === "done" ? c.success : status === "pending" ? c.warning : c.error
    return (
      <span
        style={{
          display: "inline-block",
          width: 8,
          height: 8,
          borderRadius: "50%",
          backgroundColor: col,
          marginRight: 6,
        }}
      />
    )
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Exports</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Download outputs in different formats or batch export multiple items.</p>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Batch export bar */}
      {selected.size > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: 12,
            borderRadius: t.radii.md,
            border: `1px solid ${c.primary}`,
            backgroundColor: c.surfaceActive,
            marginBottom: t.spacing.lg,
          }}
        >
          <span style={{ fontWeight: 700, fontSize: 13, color: c.text }}>
            {selected.size} selected
          </span>
          <select
            value={batchFormat}
            onChange={(e) => setBatchFormat(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.inputBg,
              color: c.text,
              fontSize: 13,
            }}
          >
            {FORMATS.map((f) => (
              <option key={f} value={f} style={{ backgroundColor: c.bgSecondary, color: c.text }}>{f}</option>
            ))}
          </select>
          <button
            onClick={handleBatchExport}
            style={{
              padding: "6px 14px",
              borderRadius: t.radii.sm,
              border: "none",
              backgroundColor: c.primary,
              color: "#FFFFFF",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            Download all ({selected.size})
          </button>
          <button
            onClick={() => setSelected(new Set())}
            style={{
              padding: "6px 14px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.textSecondary,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            Clear
          </button>
        </div>
      )}

      <div style={{ marginBottom: t.spacing.xl }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: t.spacing.md }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: c.text }}>Exportable outputs</h2>
          <button
            onClick={toggleAll}
            style={{
              padding: "4px 12px",
              borderRadius: t.radii.sm,
              border: `1px solid ${c.border}`,
              backgroundColor: c.surface,
              color: c.textSecondary,
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            {selected.size === outputs.length && outputs.length > 0 ? "Deselect all" : "Select all"}
          </button>
        </div>

        {loading ? (
          <div style={{ display: "grid", gap: t.spacing.sm }}>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                style={{
                  borderRadius: t.radii.md,
                  border: `1px solid ${c.border}`,
                  padding: t.spacing.md,
                  backgroundColor: c.cardBg,
                  height: 56,
                }}
              />
            ))}
          </div>
        ) : outputs.length === 0 ? (
          <div style={{ textAlign: "center", padding: t.spacing.xxl, borderRadius: t.radii.lg, border: `1px solid ${c.border}`, backgroundColor: c.bgSecondary, color: c.textSecondary }}>
            No exportable outputs found.
          </div>
        ) : (
          <div style={{ display: "grid", gap: t.spacing.sm }}>
            {outputs.map((o) => (
              <div
                key={o.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  borderRadius: t.radii.md,
                  border: `1px solid ${selected.has(o.id) ? c.primary : c.border}`,
                  backgroundColor: selected.has(o.id) ? c.surfaceActive : c.cardBg,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
                  <input
                    type="checkbox"
                    checked={selected.has(o.id)}
                    onChange={() => toggleSelect(o.id)}
                    style={{ accentColor: c.primary }}
                  />
                  <div>
                    <div style={{ fontWeight: 600, color: c.text, fontSize: 14 }}>{o.title ?? o.id}</div>
                    <div style={{ fontSize: 11, color: c.textSecondary }}>
                      {o.document_name ?? ""}{o.created_at ? ` · ${new Date(o.created_at).toLocaleDateString()}` : ""}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {FORMATS.map((fmt) => (
                    <button
                      key={fmt}
                      onClick={() => handleExport(o.id, fmt.toLowerCase())}
                      disabled={exporting === o.id}
                      style={{
                        padding: "4px 10px",
                        borderRadius: t.radii.sm,
                        border: `1px solid ${c.border}`,
                        backgroundColor: c.surface,
                        color: c.text,
                        cursor: exporting === o.id ? "default" : "pointer",
                        fontSize: 11,
                        fontWeight: 600,
                        opacity: exporting === o.id ? 0.5 : 1,
                      }}
                    >
                      {exporting === o.id ? "..." : fmt}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Pagination page={page} totalPages={totalPages} total={total} onPageChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }) }} />

      {/* Download history */}
      <div>
        <h2 style={{ margin: `0 0 ${t.spacing.md} 0`, fontSize: 16, fontWeight: 700, color: c.text }}>Download history</h2>
        <div style={{ borderRadius: t.radii.lg, border: `1px solid ${c.border}`, overflow: "hidden" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 80px 1fr 80px",
              gap: 12,
              padding: "10px 16px",
              backgroundColor: c.surface,
              borderBottom: `1px solid ${c.border}`,
              fontWeight: 700,
              fontSize: 12,
              color: c.textSecondary,
            }}
          >
            <div>Filename</div>
            <div>Format</div>
            <div>Date</div>
            <div>Status</div>
          </div>
          {downloads.map((d, i) => (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 80px 1fr 80px",
                gap: 12,
                padding: "10px 16px",
                fontSize: 13,
                color: c.text,
                borderBottom: i < downloads.length - 1 ? `1px solid ${c.border}` : "none",
              }}
            >
              <div>{d.filename}</div>
              <div style={{ fontWeight: 600 }}>{d.format}</div>
              <div style={{ color: c.textSecondary }}>{d.date}</div>
              <div style={{ display: "flex", alignItems: "center", textTransform: "capitalize" }}>
                {statusDot(d.status)}{d.status}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
