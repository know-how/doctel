import React, { useState, useCallback, useEffect } from "react"
import { useTheme } from "../../context/ThemeContext"
import { getTokens } from "../../theme/themeTokens"
import { sidebarConfig, type NavItem } from "../../navigation/sidebarConfig"
import zetdcLogo from "../../assets/zetdc-logo.png"

interface SidebarProps {
  currentPath: string
  onNavigate: (path: string) => void
  onLogout: () => void
  userRole: string
  displayName: string
  isAuthenticated: boolean
  collapsed: boolean
  onToggleCollapse: () => void
}

const COLLAPSED_KEY = "docintel_sidebar_collapsed"
const EXPANDED_KEY = "docintel_sidebar_expanded"
const EXPANDED_WIDTH = 340
const COLLAPSED_WIDTH = 64
const TRANSITION = "0.25s cubic-bezier(0.4, 0, 0.2, 1)"

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function saveJson(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value))
}

function filterByRole(items: NavItem[], role: string): NavItem[] {
  return items.filter((item) => {
    if (item.roles && item.roles.length > 0 && !item.roles.includes(role)) {
      return false
    }
    return true
  })
}

function isItemActive(item: NavItem, current: string): boolean {
  if (current === item.path) return true
  if (item.children) {
    return item.children.some((c) => current === c.path)
  }
  return false
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath,
  onNavigate,
  onLogout,
  userRole,
  displayName,
  isAuthenticated,
  collapsed,
  onToggleCollapse,
}) => {
  const { theme: themeName, toggleTheme, isDark } = useTheme()
  const t = getTokens(themeName)

  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => {
    const arr = loadJson<string[]>(EXPANDED_KEY, [])
    return new Set(arr)
  })

  useEffect(() => {
    saveJson(EXPANDED_KEY, Array.from(expandedSections))
  }, [expandedSections])

  const filteredItems = filterByRole(
    sidebarConfig,
    isAuthenticated ? userRole : "",
  )

  const sidebarWidth = collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH

  const toggleSection = useCallback(
    (id: string) => {
      setExpandedSections((prev) => {
        const next = new Set(prev)
        if (next.has(id)) {
          next.delete(id)
        } else {
          next.add(id)
        }
        return next
      })
    },
    [],
  )

  useEffect(() => {
    let changed = false
    const next = new Set(expandedSections)
    for (const item of filteredItems) {
      if (item.children && item.children.some((c) => currentPath === c.path)) {
        if (!next.has(item.id)) {
          next.add(item.id)
          changed = true
        }
      }
    }
    if (changed) {
      setExpandedSections(next)
    }
  }, [currentPath]) // eslint-disable-line react-hooks/exhaustive-deps

  const avatarLetter = displayName
    ? displayName.charAt(0).toUpperCase()
    : "U"

  const chevronIcon = (id: string) =>
    expandedSections.has(id) ? "▼" : "▶"

  return (
    <aside
      style={{
        width: sidebarWidth,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        background: t.gradients.sidebar,
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        borderRight: `1px solid ${t.colors.sidebarBorder}`,
        zIndex: 100,
        transition: `width ${TRANSITION}`,
        overflow: "hidden",
      }}
    >
      {/* ── Ambient top glow ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 160,
          background: `radial-gradient(ellipse at 50% 0%, ${t.colors.primary}18 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      {/* ── Logo ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: collapsed ? "18px 16px" : "18px 18px",
          borderBottom: `1px solid ${t.colors.border}`,
          minHeight: 64,
          flexShrink: 0,
          cursor: "pointer",
          transition: `padding ${TRANSITION}`,
          position: "relative",
        }}
        onClick={() => onToggleCollapse()}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <img
            src={zetdcLogo}
            alt="ZETDC DOCTEL LARGE LANGUAGE MODEL"
            style={{
              width: "auto",
              height: "auto",
              maxHeight: 48,
              objectFit: "contain",
              flexShrink: 0,
            }}
          />

        {!collapsed && (
          <>
            <div style={{ overflow: "hidden", flex: 1 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.04em",
                  background: `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.secondary})`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  whiteSpace: "nowrap",
                  lineHeight: 1.2,
                }}
              >
                DOCTEL LARGE LANGUAGE MODEL
              </div>
              <div
                style={{
                  fontSize: 6,
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  color: t.colors.primary,
                  whiteSpace: "nowrap",
                  opacity: 0.7,
                }}
              >
                Zimbabwe Electricity Transmission and Distribution Company
              </div>
            </div>
            <div
              style={{
                fontSize: 10,
                color: t.colors.textMuted,
                flexShrink: 0,
                transition: `transform ${TRANSITION}`,
              }}
            >
              ◀
            </div>
          </>
        )}

        {collapsed && (
          <div
            style={{
              position: "absolute",
              right: 6,
              top: "50%",
              transform: "translateY(-50%)",
              fontSize: 9,
              color: t.colors.textMuted,
            }}
          >
            ▶
          </div>
        )}
      </div>

      {/* ── Navigation ── */}
      <nav
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 2,
          padding: collapsed ? "10px 8px" : "10px 10px",
          overflowY: "auto",
          overflowX: "hidden",
        }}
      >
        {isAuthenticated &&
          filteredItems.map((item) => {
            const active = isItemActive(item, currentPath)
            const isExpanded = expandedSections.has(item.id)
            const hasChildren = item.children && item.children.length > 0

            return (
              <div key={item.id} style={{ position: "relative" }}>
                {/* ── Section header ── */}
                <button
                  type="button"
                  onClick={() => {
                    if (collapsed) {
                      onToggleCollapse()
                      if (hasChildren) {
                        setExpandedSections((prev) => {
                          const next = new Set(prev)
                          next.add(item.id)
                          return next
                        })
                      }
                    } else if (hasChildren) {
                      toggleSection(item.id)
                    } else {
                      onNavigate(item.path)
                    }
                  }}
                  title={collapsed ? item.label : undefined}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    width: "100%",
                    padding: collapsed
                      ? "10px 0"
                      : "10px 12px",
                    justifyContent: collapsed ? "center" : "flex-start",
                    borderRadius: t.radii.md,
                    border: "none",
                    background: active
                      ? t.colors.surfaceActive
                      : "transparent",
                    color: active
                      ? t.colors.text
                      : collapsed
                        ? t.colors.textSecondary
                        : t.colors.textMuted,
                    fontSize: 11,
                    fontWeight: active ? 700 : 600,
                    cursor: "pointer",
                    textAlign: "left",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    transition: `all ${TRANSITION}`,
                    position: "relative",
                    letterSpacing: collapsed ? undefined : "0.04em",
                    textTransform: collapsed ? undefined : "uppercase",
                    lineHeight: collapsed ? undefined : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      ;(
                        e.currentTarget as HTMLElement
                      ).style.background = t.colors.surfaceHover
                      ;(
                        e.currentTarget as HTMLElement
                      ).style.color = t.colors.textSecondary
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      ;(
                        e.currentTarget as HTMLElement
                      ).style.background = "transparent"
                      ;(
                        e.currentTarget as HTMLElement
                      ).style.color = collapsed
                        ? t.colors.textSecondary
                        : t.colors.textMuted
                    }
                  }}
                >
                  {/* Active left border */}
                  {active && (
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: "50%",
                        transform: "translateY(-50%)",
                        width: 3,
                        height: "50%",
                        borderRadius: "0 3px 3px 0",
                        background: `linear-gradient(180deg, ${t.colors.primary}, ${t.colors.secondary})`,
                      }}
                    />
                  )}

                  <span
                    style={{
                      fontSize: collapsed ? 18 : 13,
                      flexShrink: 0,
                      width: collapsed ? 50 : 20,
                      textAlign: "center",
                      color: active ? "inherit" : undefined,
                      lineHeight: 1,
                    }}
                  >
                    {item.icon}
                  </span>

                  {!collapsed && (
                    <>
                      <span
                        style={{
                          flex: 1,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {item.label}
                      </span>
                      {hasChildren && (
                        <span
                          style={{
                            fontSize: 8,
                            flexShrink: 0,
                            transition: `transform ${TRANSITION}`,
                          }}
                        >
                          {chevronIcon(item.id)}
                        </span>
                      )}
                    </>
                  )}
                </button>

                {/* ── Children ── */}
                {!collapsed && hasChildren && isExpanded && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 1,
                      paddingLeft: 20,
                      marginTop: 2,
                      marginBottom: 4,
                    }}
                  >
                    {item.children!.map((child) => {
                      const childActive = currentPath === child.path
                      return (
                        <button
                          key={child.id}
                          type="button"
                          onClick={() => onNavigate(child.path)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            width: "100%",
                            padding: "8px 12px",
                            borderRadius: t.radii.sm,
                            border: "none",
                            background: childActive
                              ? t.colors.surfaceActive
                              : "transparent",
                            color: childActive
                              ? t.colors.text
                              : t.colors.textSecondary,
                            fontSize: 12,
                            fontWeight: childActive ? 600 : 400,
                            cursor: "pointer",
                            textAlign: "left",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            transition: `all ${TRANSITION}`,
                            position: "relative",
                          }}
                          onMouseEnter={(e) => {
                            if (!childActive) {
                              ;(
                                e.currentTarget as HTMLElement
                              ).style.background = t.colors.surfaceHover
                              ;(
                                e.currentTarget as HTMLElement
                              ).style.color = t.colors.text
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!childActive) {
                              ;(
                                e.currentTarget as HTMLElement
                              ).style.background = "transparent"
                              ;(
                                e.currentTarget as HTMLElement
                              ).style.color = t.colors.textSecondary
                            }
                          }}
                        >
                          {childActive && (
                            <div
                              style={{
                                position: "absolute",
                                left: 0,
                                top: "50%",
                                transform: "translateY(-50%)",
                                width: 3,
                                height: "60%",
                                borderRadius: "0 3px 3px 0",
                                background: `linear-gradient(180deg, ${t.colors.primary}, ${t.colors.secondary})`,
                              }}
                            />
                          )}
                          <span
                            style={{
                              fontSize: 13,
                              flexShrink: 0,
                              width: 18,
                              textAlign: "center",
                              opacity: childActive ? 1 : 0.6,
                            }}
                          >
                            {child.icon}
                          </span>
                          <span
                            style={{
                              flex: 1,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {child.label}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
      </nav>

      {/* ── Footer ── */}
      {isAuthenticated && (
        <div
          style={{
            borderTop: `1px solid ${t.colors.border}`,
            padding: collapsed ? "12px 8px" : "14px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            flexShrink: 0,
          }}
        >
          {/* Theme toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: collapsed ? "center" : "flex-start",
              gap: collapsed ? 0 : 10,
              padding: collapsed ? "8px 0" : "8px 12px",
              borderRadius: t.radii.sm,
              border: "none",
              background: "transparent",
              color: t.colors.textSecondary,
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              width: "100%",
              transition: `all ${TRANSITION}`,
            }}
            onMouseEnter={(e) => {
              ;(e.currentTarget as HTMLElement).style.background =
                t.colors.surfaceHover
              ;(e.currentTarget as HTMLElement).style.color = t.colors.text
            }}
            onMouseLeave={(e) => {
              ;(e.currentTarget as HTMLElement).style.background = "transparent"
              ;(e.currentTarget as HTMLElement).style.color =
                t.colors.textSecondary
            }}
          >
            <span
              style={{
                fontSize: collapsed ? 18 : 16,
                flexShrink: 0,
                width: collapsed ? 50 : 22,
                textAlign: "center",
              }}
            >
              {isDark ? "☀️" : "🌙"}
            </span>
            {!collapsed && (
              <span style={{ fontSize: 12 }}>
                {isDark ? "Light mode" : "Dark mode"}
              </span>
            )}
          </button>

          {/* User info */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: collapsed ? "center" : "flex-start",
              gap: 10,
              padding: collapsed ? "4px 0" : "6px 10px",
              borderRadius: t.radii.md,
              background: t.colors.surface,
              overflow: "hidden",
              transition: `all ${TRANSITION}`,
            }}
          >
            {/* Avatar circle */}
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: t.radii.full,
                background: `linear-gradient(135deg, ${t.colors.primary} 0%, ${t.colors.secondary} 100%)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#FFFFFF",
                fontWeight: 700,
                fontSize: 12,
                flexShrink: 0,
              }}
              title={displayName || "User"}
            >
              {avatarLetter}
            </div>

            {!collapsed && (
              <div style={{ overflow: "hidden", flex: 1 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: t.colors.text,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {displayName || "User"}
                </div>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: t.colors.textMuted,
                    textTransform: "capitalize",
                    letterSpacing: "0.03em",
                    marginTop: 1,
                  }}
                >
                  {userRole}
                </div>
              </div>
            )}
          </div>

          {/* Logout */}
          <button
            type="button"
            onClick={onLogout}
            title="Logout"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: collapsed ? "center" : "flex-start",
              gap: collapsed ? 0 : 10,
              padding: collapsed ? "8px 0" : "8px 12px",
              borderRadius: t.radii.sm,
              border: `1px solid ${t.colors.error}30`,
              background: `${t.colors.error}0D`,
              color: `${t.colors.error}CC`,
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              width: "100%",
              transition: `all ${TRANSITION}`,
            }}
            onMouseEnter={(e) => {
              ;(e.currentTarget as HTMLElement).style.background =
                `${t.colors.error}1F`
              ;(e.currentTarget as HTMLElement).style.color = t.colors.error
              ;(e.currentTarget as HTMLElement).style.borderColor =
                `${t.colors.error}60`
            }}
            onMouseLeave={(e) => {
              ;(e.currentTarget as HTMLElement).style.background =
                `${t.colors.error}0D`
              ;(e.currentTarget as HTMLElement).style.color =
                `${t.colors.error}CC`
              ;(e.currentTarget as HTMLElement).style.borderColor =
                `${t.colors.error}30`
            }}
          >
            <span
              style={{
                fontSize: collapsed ? 18 : 15,
                flexShrink: 0,
                width: collapsed ? 50 : 22,
                textAlign: "center",
              }}
            >
              ⏻
            </span>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      )}
    </aside>
  )
}
