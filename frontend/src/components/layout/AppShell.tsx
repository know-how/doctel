import React, { ReactNode, useState } from "react"
import { theme } from "../../theme/theme"
import zetdcLogo from "../../assets/zetdc-logo.png"

interface AppShellProps {
  children: ReactNode
  page: "copilot" | "mywork" | "admin" | "training"
  onNavigate: (page: "copilot" | "mywork" | "admin" | "training") => void
  onLogout: () => void
  userRole: string
  displayName: string
  isAuthenticated: boolean
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  page,
  onNavigate,
  onLogout,
  userRole,
  displayName,
  isAuthenticated,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const sidebarWidth = sidebarOpen ? 260 : 64

  const navItems = [
    { id: "copilot" as const, label: "Copilot", icon: "✦" },
    { id: "mywork" as const, label: "My Work", icon: "📂" },
    ...(userRole === "admin"
      ? [
          { id: "admin" as const, label: "Admin", icon: "⚙️" },
          { id: "training" as const, label: "Training", icon: "🧠" },
        ]
      : []),
  ]

  const avatarLetter = displayName
    ? displayName.charAt(0).toUpperCase()
    : "U"

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "row",
        background: theme.gradients.darkBg,
        color: theme.colors.gray["100"],
        fontFamily: theme.typography.fontFamily.sans,
      }}
    >
      {/* ── Sidebar ── */}
      <aside
        style={{
          width: sidebarWidth,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          background:
            "linear-gradient(180deg, rgba(15,17,23,0.98) 0%, rgba(20,24,40,0.98) 100%)",
          backdropFilter: "blur(20px)",
          borderRight: "1px solid rgba(91,136,255,0.12)",
          boxShadow: "4px 0 24px rgba(0,0,0,0.3)",
          transition: `width ${theme.transitions.duration.slow} ${theme.transitions.timing.easeInOut}`,
          overflow: "hidden",
          flexShrink: 0,
          position: "relative",
          zIndex: 10,
        }}
      >
        {/* Ambient glow */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "200px",
            background:
              "radial-gradient(ellipse at 50% -20%, rgba(91,136,255,0.15) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        {/* Logo row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: sidebarOpen ? "20px 20px 16px" : "20px 14px 16px",
            borderBottom: "1px solid rgba(255,255,255,0.05)",
            minHeight: 72,
            flexShrink: 0,
            cursor: "pointer",
            transition: "padding 0.3s ease",
          }}
          onClick={() => setSidebarOpen((v) => !v)}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background:
                "linear-gradient(135deg, rgba(91,136,255,0.25) 0%, rgba(31,231,255,0.12) 100%)",
              border: "1px solid rgba(91,136,255,0.35)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 12px rgba(91,136,255,0.25)",
              flexShrink: 0,
              transition: "transform 0.2s ease",
            }}
          >
            <img
              src={zetdcLogo}
              alt="ZETDC logo"
              style={{ width: "auto", height: "auto", maxHeight: 22, objectFit: "contain" }}
            />
          </div>

          {sidebarOpen && (
            <div style={{ overflow: "hidden" }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 800,
                  letterSpacing: "0.03em",
                  background: "linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  whiteSpace: "nowrap",
                }}
              >
                DOCTEL LARGE LANGUAGE MODEL
              </div>
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 600,
                  color: "rgba(255,255,255,0.35)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                  marginTop: 1,
                }}
              >
                Zimbabwe Electricity Transmission and Distribution Company
              </div>
            </div>
          )}

          {/* Toggle arrow */}
          {sidebarOpen && (
            <div
              style={{
                marginLeft: "auto",
                color: "rgba(255,255,255,0.3)",
                fontSize: 12,
                flexShrink: 0,
              }}
            >
              ◀
            </div>
          )}
          {!sidebarOpen && (
            <div
              style={{
                position: "absolute",
                right: 8,
                color: "rgba(255,255,255,0.25)",
                fontSize: 10,
              }}
            >
              ▶
            </div>
          )}
        </div>

        {/* Nav items */}
        <nav
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 4,
            padding: "12px 10px",
            overflowY: "auto",
            overflowX: "hidden",
          }}
        >
          {isAuthenticated &&
            navItems.map((item) => {
              const isActive = page === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onNavigate(item.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: sidebarOpen ? "10px 14px" : "10px 14px",
                    borderRadius: 12,
                    border: "none",
                    background: isActive
                      ? "linear-gradient(135deg, rgba(91,136,255,0.2) 0%, rgba(31,231,255,0.08) 100%)"
                      : "transparent",
                    color: isActive ? "#FFFFFF" : "rgba(255,255,255,0.5)",
                    fontSize: 14,
                    fontWeight: isActive ? 700 : 500,
                    cursor: "pointer",
                    textAlign: "left",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    transition: "all 0.2s ease",
                    boxShadow: isActive
                      ? "inset 0 0 0 1px rgba(91,136,255,0.3)"
                      : "none",
                    position: "relative",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      ;(e.currentTarget as HTMLElement).style.background =
                        "rgba(255,255,255,0.05)"
                      ;(e.currentTarget as HTMLElement).style.color =
                        "rgba(255,255,255,0.8)"
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      ;(e.currentTarget as HTMLElement).style.background =
                        "transparent"
                      ;(e.currentTarget as HTMLElement).style.color =
                        "rgba(255,255,255,0.5)"
                    }
                  }}
                >
                  {/* Active indicator bar */}
                  {isActive && (
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: "50%",
                        transform: "translateY(-50%)",
                        width: 3,
                        height: "60%",
                        borderRadius: "0 3px 3px 0",
                        background:
                          "linear-gradient(180deg, #5B88FF, #1FE7FF)",
                      }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: 18,
                      flexShrink: 0,
                      width: 22,
                      textAlign: "center",
                    }}
                  >
                    {item.icon}
                  </span>
                  {sidebarOpen && (
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                      {item.label}
                    </span>
                  )}
                </button>
              )
            })}
        </nav>

        {/* Bottom: user + logout */}
        {isAuthenticated && (
          <div
            style={{
              borderTop: "1px solid rgba(255,255,255,0.06)",
              padding: sidebarOpen ? "14px 14px" : "14px 10px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              flexShrink: 0,
            }}
          >
            {/* User info row */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: "linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#FFFFFF",
                  fontWeight: 700,
                  fontSize: 13,
                  flexShrink: 0,
                  boxShadow: "0 0 10px rgba(91,136,255,0.3)",
                }}
              >
                {avatarLetter}
              </div>
              {sidebarOpen && (
                <div style={{ overflow: "hidden" }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: "#E5E7EB",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {displayName || "User"}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "rgba(255,255,255,0.35)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {userRole || "member"}
                  </div>
                </div>
              )}
            </div>

            {/* Logout button */}
            <button
              type="button"
              onClick={onLogout}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: sidebarOpen ? "8px 12px" : "8px 14px",
                borderRadius: 10,
                border: "1px solid rgba(239,68,68,0.2)",
                background: "rgba(239,68,68,0.06)",
                color: "rgba(248,113,113,0.8)",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                textAlign: "left",
                whiteSpace: "nowrap",
                overflow: "hidden",
                transition: "all 0.2s ease",
                width: "100%",
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLElement).style.background =
                  "rgba(239,68,68,0.12)"
                ;(e.currentTarget as HTMLElement).style.color = "#F87171"
                ;(e.currentTarget as HTMLElement).style.borderColor =
                  "rgba(239,68,68,0.4)"
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLElement).style.background =
                  "rgba(239,68,68,0.06)"
                ;(e.currentTarget as HTMLElement).style.color =
                  "rgba(248,113,113,0.8)"
                ;(e.currentTarget as HTMLElement).style.borderColor =
                  "rgba(239,68,68,0.2)"
              }}
            >
              <span style={{ fontSize: 16, flexShrink: 0, width: 22, textAlign: "center" }}>
                ⏻
              </span>
              {sidebarOpen && <span>Logout</span>}
            </button>
          </div>
        )}
      </aside>

      {/* ── Main area ── */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          transition: `all ${theme.transitions.duration.slow} ${theme.transitions.timing.easeInOut}`,
        }}
      >
        {/* Top bar */}
        <header
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            padding: "0 28px",
            background:
              "linear-gradient(135deg, rgba(15,17,23,0.85) 0%, rgba(26,31,53,0.85) 100%)",
            backdropFilter: "blur(20px)",
            borderBottom: "1px solid rgba(91,136,255,0.08)",
            boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
            justifyContent: "space-between",
            position: "sticky",
            top: 0,
            zIndex: 5,
            flexShrink: 0,
          }}
        >
          {/* Title breadcrumb */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                fontSize: 13,
                color: "rgba(255,255,255,0.4)",
                fontWeight: 500,
              }}
            >
              DOCTEL LARGE LANGUAGE MODEL
            </div>
            <div style={{ color: "rgba(255,255,255,0.2)", fontSize: 12 }}>›</div>
            <div
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: "#E5E7EB",
                textTransform: "capitalize",
              }}
            >
              {page === "copilot" ? "AI Copilot" : page === "mywork" ? "My Work" : page === "admin" ? "Admin" : "Training"}
            </div>
          </div>

          {/* Right section */}
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {/* Status badge */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 10px",
                borderRadius: 999,
                background:
                  "linear-gradient(135deg, rgba(34,197,94,0.15) 0%, rgba(16,185,129,0.08) 100%)",
                border: "1px solid rgba(34,197,94,0.25)",
                fontSize: 11,
                fontWeight: 700,
                color: "#4ADE80",
                letterSpacing: "0.05em",
              }}
            >
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#22C55E",
                  animation: "pulse 2s infinite",
                }}
              />
              ACTIVE
            </div>

            {/* User display */}
            {isAuthenticated && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "6px 12px",
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  cursor: "default",
                }}
              >
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 500,
                    color: "rgba(255,255,255,0.7)",
                    maxWidth: 180,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {displayName || "User"}
                </div>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 10,
                    background:
                      "linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#FFFFFF",
                    fontWeight: 700,
                    fontSize: 13,
                    boxShadow: "0 0 12px rgba(91,136,255,0.3)",
                  }}
                >
                  {avatarLetter}
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <main
          style={{
            flex: 1,
            padding: "24px",
            overflow: "auto",
            background: `linear-gradient(180deg, transparent 0%, rgba(91,136,255,0.02) 100%)`,
            position: "relative",
          }}
        >
          {children}
        </main>
      </div>

      {/* Decorative ambient orbs */}
      <div
        style={{
          position: "fixed",
          top: "10%",
          right: "5%",
          width: "350px",
          height: "350px",
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(91,136,255,0.08) 0%, transparent 70%)`,
          filter: "blur(60px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: "fixed",
          bottom: "-10%",
          left: "20%",
          width: "400px",
          height: "400px",
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(31,231,255,0.06) 0%, transparent 70%)`,
          filter: "blur(80px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
    </div>
  )
}
