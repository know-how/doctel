import React, { useEffect, useMemo, useState } from "react"
import { theme } from "../theme/theme"
import { utilityStyles } from "../theme/utilityStyles"
import zetdcLogo from "../assets/zetdc-logo.png"

function timeGreeting(now: Date): string {
  const h = now.getHours()
  if (h >= 5 && h < 12) return "Good morning ⚡ Welcome back to DocTel"
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
        background: `linear-gradient(135deg, rgba(15, 17, 23, 0.98) 0%, rgba(26, 31, 53, 0.95) 100%)`,
        backdropFilter: "blur(10px)",
        overflow: "hidden",
        animation: `fadeIn 300ms ${theme.transitions.timing.easeOut}`,
      }}
    >
      <style>{`
        @keyframes introGlow {
          0% {
            transform: translateY(30px) scale(0.7);
            filter: drop-shadow(0 0 0 rgba(91, 136, 255, 0));
            opacity: 0;
          }
          40% {
            opacity: 1;
          }
          70% {
            filter: drop-shadow(0 0 40px rgba(91, 136, 255, 0.8));
          }
          100% {
            transform: translateY(0) scale(1);
            filter: drop-shadow(0 0 25px rgba(91, 136, 255, 0.5));
            opacity: 1;
          }
        }

        @keyframes introPulse {
          0% {
            opacity: 0.15;
            transform: scale(0.9);
          }
          100% {
            opacity: 0;
            transform: scale(1.4);
          }
        }

        @keyframes introRing {
          0% {
            opacity: 1;
            transform: scale(0.8);
          }
          100% {
            opacity: 0;
            transform: scale(1.6);
          }
        }

        @keyframes introFloat {
          0%, 100% {
            transform: translateY(0px);
          }
          50% {
            transform: translateY(-15px);
          }
        }
      `}</style>

      {/* Background animated orbs */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {/* Primary glow orb */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "45%",
            width: 600,
            height: 600,
            transform: "translate(-50%, -50%)",
            borderRadius: "50%",
            background: `radial-gradient(circle, rgba(91, 136, 255, 0.25) 0%, rgba(91, 136, 255, 0) 70%)`,
            animation: `introPulse 2s ease-out infinite`,
            filter: "blur(40px)",
          }}
        />

        {/* Secondary cyan glow */}
        <div
          style={{
            position: "absolute",
            right: "-15%",
            bottom: "-15%",
            width: 500,
            height: 500,
            borderRadius: "50%",
            background: `radial-gradient(circle, rgba(31, 231, 255, 0.15) 0%, rgba(31, 231, 255, 0) 70%)`,
            animation: `introRing 3s ease-in-out infinite`,
            filter: "blur(50px)",
          }}
        />

        {/* Tertiary accent glow */}
        <div
          style={{
            position: "absolute",
            left: "-10%",
            top: "-20%",
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: `radial-gradient(circle, rgba(255, 131, 73, 0.1) 0%, rgba(255, 131, 73, 0) 70%)`,
            animation: `introFloat 4s ease-in-out infinite`,
            filter: "blur(40px)",
          }}
        />
      </div>

      {/* Main content card */}
      <div
        style={{
          width: "min(520px, 90vw)",
          textAlign: "center",
          color: theme.colors.gray[100],
          padding: theme.spacing[8],
          borderRadius: theme.borderRadius["2xl"],
          border: `1px solid rgba(91, 136, 255, 0.2)`,
          background: `linear-gradient(135deg, rgba(15, 17, 23, 0.7) 0%, rgba(26, 31, 53, 0.7) 100%)`,
          backdropFilter: "blur(20px)",
          boxShadow: `0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(91, 136, 255, 0.1)`,
          animation: `introGlow 900ms cubic-bezier(0.34, 1.56, 0.64, 1) both`,
          position: "relative",
          zIndex: 10,
        }}
      >
        {/* Decorative top border gradient */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "1px",
            background: `linear-gradient(90deg, transparent 0%, rgba(91, 136, 255, 0.4) 50%, transparent 100%)`,
            borderRadius: "16px 16px 0 0",
          }}
        />

        {/* Logo container with glow */}
        <div
          style={{
            marginBottom: theme.spacing[6],
            display: "flex",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              width: 100,
              height: 100,
              borderRadius: theme.borderRadius.lg,
              background: `linear-gradient(135deg, rgba(91, 136, 255, 0.15) 0%, rgba(31, 231, 255, 0.08) 100%)`,
              border: `1px solid rgba(91, 136, 255, 0.25)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `0 0 30px rgba(91, 136, 255, 0.3)`,
              animation: `introFloat 3s ease-in-out infinite`,
            }}
          >
            <img
              src={zetdcLogo}
              alt="ZETDC logo"
              style={{
                width: 64,
                height: 64,
                objectFit: "contain",
              }}
            />
          </div>
        </div>

        {/* Greeting content */}
        {showGreeting && (
          <>
            {/* Time-based greeting */}
            <div
              style={{
                ...utilityStyles.bodySmall,
                color: theme.colors.secondary[300],
                marginBottom: theme.spacing[3],
                fontWeight: theme.typography.fontWeight.medium,
                animation: `slideInUp 600ms ${theme.transitions.timing.easeOut} 200ms both`,
              }}
            >
              {greet}
            </div>

            {/* Display name */}
            {displayName && (
              <div
                style={{
                  fontSize: theme.typography.fontSize["3xl"],
                  fontWeight: theme.typography.fontWeight.bold,
                  color: "#FFFFFF",
                  marginBottom: theme.spacing[4],
                  background: `linear-gradient(135deg, #FFFFFF 0%, #E5E7EB 100%)`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  animation: `slideInUp 600ms ${theme.transitions.timing.easeOut} 300ms both`,
                }}
              >
                {displayName}
              </div>
            )}

            {/* Rotating message */}
            {unique && (
              <div
                style={{
                  ...utilityStyles.bodySmall,
                  color: theme.colors.gray[300],
                  marginTop: theme.spacing[4],
                  fontStyle: "italic",
                  opacity: 0.9,
                  animation: `slideInUp 600ms ${theme.transitions.timing.easeOut} 400ms both`,
                }}
              >
                "{unique}"
              </div>
            )}

            {/* Loading indicator */}
            <div
              style={{
                marginTop: theme.spacing[8],
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: theme.spacing[2],
                animation: `slideInUp 600ms ${theme.transitions.timing.easeOut} 500ms both`,
              }}
            >
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: `linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)`,
                    animation: `pulse 1.5s ease-in-out infinite`,
                    animationDelay: `${i * 200}ms`,
                  }}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

