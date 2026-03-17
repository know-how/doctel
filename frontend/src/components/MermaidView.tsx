import React, { useEffect, useMemo, useState } from "react"

type MermaidApi = {
  initialize: (opts: any) => void
  render: (id: string, text: string) => Promise<{ svg: string }>
}

async function loadMermaid(): Promise<MermaidApi> {
  const w = window as any
  if (w.__docintel_mermaid) return w.__docintel_mermaid as MermaidApi
  const mod = await import("https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs" as any)
  const mermaid = (mod.default || mod) as MermaidApi
  try {
    mermaid.initialize({ startOnLoad: false, theme: "dark" })
  } catch {
  }
  w.__docintel_mermaid = mermaid
  return mermaid
}

export const MermaidView: React.FC<{ code: string }> = ({ code }) => {
  const [svg, setSvg] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  const normalized = useMemo(() => (code || "").trim(), [code])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      try {
        setFailed(false)
        setSvg(null)
        const mermaid = await loadMermaid()
        const id = `m_${Math.random().toString(36).slice(2)}`
        const res = await mermaid.render(id, normalized)
        if (cancelled) return
        setSvg(res.svg)
      } catch {
        if (cancelled) return
        setFailed(true)
      }
    }
    if (normalized) run()
    return () => {
      cancelled = true
    }
  }, [normalized])

  if (!normalized) return null

  if (failed || !svg) {
    return (
      <pre
        style={{
          margin: 0,
          padding: 12,
          borderRadius: 12,
          backgroundColor: "#0F172A",
          color: "#E2E8F0",
          fontSize: 12,
          overflowX: "auto",
          whiteSpace: "pre",
        }}
      >
        {normalized}
      </pre>
    )
  }

  return (
    <div
      style={{
        borderRadius: 12,
        overflow: "hidden",
        backgroundColor: "#0B1220",
        border: "1px solid rgba(148,163,184,0.18)",
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

