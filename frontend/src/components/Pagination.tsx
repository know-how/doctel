import React, { useState } from "react"
import { getTokens } from "../theme/themeTokens"
import { useTheme } from "../context/ThemeContext"

interface PaginationProps {
  page: number
  totalPages: number
  total: number
  onPageChange: (page: number) => void
}

export const Pagination: React.FC<PaginationProps> = ({ page, totalPages, total, onPageChange }) => {
  const { theme } = useTheme()
  const t = getTokens(theme)

  if (totalPages <= 1) return null

  const btnStyle: React.CSSProperties = {
    padding: "8px 14px",
    borderRadius: 8,
    border: `1px solid ${t.colors.border}`,
    background: t.colors.cardBg,
    color: t.colors.text,
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
  }

  const disabledStyle: React.CSSProperties = {
    ...btnStyle,
    opacity: 0.4,
    cursor: "not-allowed",
  }

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, marginTop: 20 }}>
      <button type="button" style={page <= 1 ? disabledStyle : btnStyle} disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))}>
        ← Prev
      </button>
      <span style={{ fontSize: 13, color: t.colors.textSecondary }}>
        Page {page} of {totalPages} ({total} items)
      </span>
      <button type="button" style={page >= totalPages ? disabledStyle : btnStyle} disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
        Next →
      </button>
    </div>
  )
}

export function usePagination(fetchFn: (page: number, pageSize: number) => Promise<any>, pageSize: number = 20) {
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const totalPages = Math.ceil(total / pageSize) || 1

  const goToPage = (p: number) => {
    setPage(p)
    fetchFn(p, pageSize).then((res: any) => {
      setTotal(res.total || (res.documents || res.sessions || res.projects || []).length)
    }).catch(() => {})
  }

  return { page, setPage, totalPages, total, goToPage }
}