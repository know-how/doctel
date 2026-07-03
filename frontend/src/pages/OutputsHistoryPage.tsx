import React, { useEffect, useState, useMemo } from "react"
import { getOutputs, exportOutput } from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { Pagination } from "../components/Pagination"

type OutputType = "" | "summary" | "extraction" | "classification" | "comparison"

interface OutputRecord {
  id: string
  title?: string
  type?: string
  document_name?: string
  created_at?: string
  preview?: string
  content?: string
}

const FILTERS: { label: string; value: OutputType }[] = [
  { label: "All", value: "" },
  { label: "Summaries", value: "summary" },
  { label: "Extractions", value: "extraction" },
  { label: "Classifications", value: "classification" },
  { label: "Comparisons", value: "comparison" },
]

function typeBadgeColor(t: string): string {
  if (t === "summary") return "#22C55E"
  if (t === "extraction") return "#5B88FF"
  if (t === "classification") return "#F59E0B"
  if (t === "comparison") return "#A855F7"
  return "#6B7280"
}

const PAGE_SIZE = 20

export const OutputsHistoryPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [outputs, setOutputs] = useState<OutputRecord[]>([])
  const [filter, setFilter] = useState<OutputType>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await getOutputs(filter ? { type: filter, page, page_size: PAGE_SIZE } : { page, page_size: PAGE_SIZE })
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
  }, [filter, page])

  const handleExport = async (outputId: string, fmt: string) => {
    try {
      const blob = await exportOutput(outputId, fmt)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `output_${outputId}.${fmt}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e.message ?? "Export failed")
    }
  }

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: t.spacing.lg }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Outputs History</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>Browse and manage saved AI outputs.</p>
      </div>

      <div style={{ display: "flex", gap: t.spacing.sm, marginBottom: t.spacing.lg, flexWrap: "wrap" }}>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            style={{
              padding: "6px 14px",
              borderRadius: t.radii.full,
              border: `1px solid ${filter === f.value ? c.primary : c.border}`,
              backgroundColor: filter === f.value ? c.primary : c.surface,
              color: filter === f.value ? "#FFFFFF" : c.text,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
              transition: "all 0.15s",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, borderRadius: t.radii.md, backgroundColor: c.error + "18", color: c.error, fontSize: 13 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: "grid", gap: t.spacing.md }}>
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                borderRadius: t.radii.lg,
                border: `1px solid ${c.border}`,
                padding: t.spacing.lg,
                backgroundColor: c.cardBg,
                minHeight: 120,
                animation: "pulse 1.5s ease-in-out infinite",
              }}
            >
              <div style={{ height: 16, width: "40%", backgroundColor: c.surfaceHover, borderRadius: 4, marginBottom: 8 }} />
              <div style={{ height: 12, width: "60%", backgroundColor: c.surfaceHover, borderRadius: 4, marginBottom: 6 }} />
              <div style={{ height: 12, width: "80%", backgroundColor: c.surfaceHover, borderRadius: 4 }} />
            </div>
          ))}
        </div>
      ) : outputs.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: t.spacing.xxl,
            borderRadius: t.radii.lg,
            border: `1px solid ${c.border}`,
            backgroundColor: c.cardBg,
          }}
        >
          <div style={{ fontSize: 48, marginBottom: t.spacing.md }}>📄</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: c.text, marginBottom: 4 }}>No saved outputs</div>
          <div style={{ fontSize: 13, color: c.textSecondary }}>Generate summaries, extractions, or other analyses to see them here.</div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: t.spacing.md }}>
          {outputs.map((o) => (
            <div
              key={o.id}
              style={{
                borderRadius: t.radii.lg,
                border: `1px solid ${activeId === o.id ? c.primary : c.border}`,
                padding: t.spacing.lg,
                backgroundColor: c.cardBg,
                cursor: "pointer",
                transition: "border-color 0.15s",
              }}
              onClick={() => setActiveId(activeId === o.id ? null : o.id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 700, color: c.text, fontSize: 15 }}>
                      {o.title ?? o.id}
                    </span>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: t.radii.full,
                        fontSize: 11,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        backgroundColor: typeBadgeColor(o.type ?? "") + "22",
                        color: typeBadgeColor(o.type ?? ""),
                        border: `1px solid ${typeBadgeColor(o.type ?? "")}44`,
                      }}
                    >
                      {o.type ?? "unknown"}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: c.textSecondary }}>
                    {o.document_name ? `Document: ${o.document_name}` : ""}
                    {o.created_at ? ` · ${new Date(o.created_at).toLocaleDateString()}` : ""}
                  </div>
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: 13,
                      color: c.textSecondary,
                      lineHeight: 1.5,
                      display: "-webkit-box",
                      WebkitLineClamp: expanded.has(o.id) ? undefined : 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {o.preview ?? o.content ?? "No preview available."}
                  </div>
                  {((o.preview ?? o.content ?? "").length > 200) && (
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleExpand(o.id) }}
                      style={{
                        marginTop: 4,
                        background: "none",
                        border: "none",
                        color: c.primary,
                        cursor: "pointer",
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      {expanded.has(o.id) ? "Show less" : "Show more"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} total={total} onPageChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }) }} />
    </div>
  )
}
