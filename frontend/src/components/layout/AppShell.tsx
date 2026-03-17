import React, { ReactNode } from "react"
import { colors } from "../../theme/colors"
import zetdcLogo from "../../assets/zetdc-logo.png"

interface AppShellProps {
  children: ReactNode
  nav?: ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({ children, nav }) => {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: colors.background,
      }}
    >
      <header
        style={{
          height: 64,
          display: "flex",
          alignItems: "center",
          padding: "0 24px",
          background: `linear-gradient(90deg, ${colors.primary} 0%, ${colors.accentOrange} 55%, ${colors.secondary} 100%)`,
          color: "#FFFFFF",
          justifyContent: "space-between",
          boxShadow: "0 2px 10px rgba(11,78,162,0.25)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <img
            src={zetdcLogo}
            alt="ZETDC logo"
            style={{
              width: 36,
              height: 36,
              objectFit: "contain",
            }}
          />
          <div>
            <div style={{ fontWeight: 600 }}>ZETDC DocIntel</div>
            <div style={{ fontSize: 12, opacity: 0.8 }}>Internal Document AI</div>
          </div>
        </div>

        {nav}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            fontSize: 14,
          }}
        >
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.6)",
              fontSize: 11,
            }}
          >
            INTERNAL
          </span>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              backgroundColor: "rgba(255,255,255,0.25)",
            }}
          />
        </div>
      </header>

      <main style={{ flex: 1, padding: 24 }}>{children}</main>
    </div>
  )
}
