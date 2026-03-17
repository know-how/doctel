import React, { useEffect, useMemo, useState } from "react"
import zetdcLogo from "../assets/zetdc-logo.png"

function timeGreeting(now: Date): string {
  const h = now.getHours()
  if (h >= 5 && h < 12) return "Good morning ⚡ Welcome back to DocTel."
  if (h >= 12 && h < 17) return "Good afternoon ⚡ Ready to assist?"
  if (h >= 17 && h < 22) return "Good evening ⚡ Need anything before you wrap up?"
  return "Hello ⚡ How may I help you?"
}

function pickRotatingMessage(messages: string[]): string {
  const list = messages.filter((m) => (m || "").trim())
  if (list.length === 0) return ""
  try {
    const key = "docintel_greeting_idx"
    const prev = Number(window.localStorage.getItem(key) || "0")
    const next = Number.isFinite(prev) ? (prev + 1) % list.length : 0
    window.localStorage.setItem(key, String(next))
    return list[next]
  } catch {
    return list[Math.floor(Math.random() * list.length)]
  }
}

export const IntroOverlay: React.FC<{
  visible: boolean
  durationMs: number
  showGreeting: boolean
  greetingMessages: string[]
  displayName?: string
  onDone: () => void
}> = ({ visible, durationMs, showGreeting, greetingMessages, displayName, onDone }) => {
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!visible) return
    setDone(false)
    const t = window.setTimeout(() => {
      setDone(true)
      onDone()
    }, Math.max(800, durationMs || 2400))
    return () => window.clearTimeout(t)
  }, [visible, durationMs, onDone])

  const greet = useMemo(() => timeGreeting(new Date()), [visible])
  const unique = useMemo(() => pickRotatingMessage(greetingMessages || []), [visible, greetingMessages])

  if (!visible || done) return null

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 2000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(circle at 50% 40%, rgba(59,130,246,0.26), rgba(2,6,23,0.92) 60%, rgba(0,0,0,0.96))",
        overflow: "hidden",
      }}
    >
      <style>{`
        @keyframes docintelGlow {
          0% { transform: translateY(14px) scale(0.78); filter: drop-shadow(0 0 0 rgba(59,130,246,0)); opacity: 0; }
          40% { opacity: 1; }
          70% { filter: drop-shadow(0 0 28px rgba(59,130,246,0.75)); }
          100% { transform: translateY(0px) scale(1); filter: drop-shadow(0 0 18px rgba(59,130,246,0.55)); opacity: 1; }
        }
        @keyframes docintelPulse {
          0% { opacity: 0.20; transform: scale(0.92); }
          100% { opacity: 0.00; transform: scale(1.35); }
        }
      `}</style>

      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "48%",
            width: 520,
            height: 520,
            transform: "translate(-50%, -50%)",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(59,130,246,0.22), rgba(59,130,246,0.0) 70%)",
            animation: "docintelPulse 1200ms ease-out infinite",
          }}
        />
      </div>

      <div
        style={{
          width: "min(520px, 92vw)",
          textAlign: "center",
          color: "#E2E8F0",
          padding: 24,
          borderRadius: 16,
          border: "1px solid rgba(148,163,184,0.22)",
          backgroundColor: "rgba(2,6,23,0.35)",
          backdropFilter: "blur(10px)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.55)",
          animation: "docintelGlow 850ms cubic-bezier(.2,.7,.2,1) both",
        }}
      >
        <img
          src={zetdcLogo}
          alt="ZETDC logo"
          style={{ width: 78, height: 78, objectFit: "contain", marginBottom: 12 }}
        />
        {showGreeting && (
          <>
            <div style={{ fontSize: 14, opacity: 0.9, marginBottom: 6 }}>
              {greet}
            </div>
            {displayName && (
              <div style={{ fontSize: 22, fontWeight: 800, color: "#FFFFFF" }}>
                {displayName}
              </div>
            )}
            {unique && (
              <div style={{ fontSize: 13, opacity: 0.85, marginTop: 10 }}>
                {unique}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

