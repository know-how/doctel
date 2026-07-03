import React, { useCallback, useEffect, useState } from "react"
import { ThemeProvider } from "./context/ThemeContext"
import { ModelProvider } from "./context/ModelContext"
import { AppShell } from "./components/layout/AppShell"
import { AuthenticatedLayout } from "./components/layout/AuthenticatedLayout"
import { IntroOverlay } from "./components/IntroOverlay"
import { DocumentViewPage } from "./pages/DocumentViewPage"
import { MyWorkPage } from "./pages/MyWorkPage"
import { AdminSettingsPage } from "./pages/AdminSettingsPage"
import { TrainingRoomPage } from "./pages/TrainingRoomPage"
import { useEcNumber } from "./hooks/useEcNumber"
import { useSyncEvents } from "./hooks/useSyncEvents"
import { useConnectionMonitor } from "./hooks/useConnectionMonitor"
import { ConnectionToast } from "./components/ConnectionToast"
import { colors } from "./theme/colors"
import { globalStyles } from "./theme/globalStyles"
import { login, setAuthToken, requestEmailOtp, verifyEmailOtp, logout, clearAuthToken, getMe, getUiSettings } from "./api/client"
import zetdcLogo from "./assets/zetdc-logo.png"
import { DocChatAnimation } from "./components/DocChatAnimation"

/* ─────────────────────────────────────────────────────────────
   Inject global animation styles once
────────────────────────────────────────────────────────────── */
const loginStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  @keyframes float-orb {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33%  { transform: translate(30px, -40px) scale(1.05); }
    66%  { transform: translate(-20px, 20px) scale(0.97); }
  }
  @keyframes drift {
    0%, 100% { transform: translateY(0px) rotate(0deg); opacity: 0.6; }
    50%       { transform: translateY(-18px) rotate(180deg); opacity: 1; }
  }
  @keyframes shimmer-text {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  @keyframes slide-up {
    from { opacity: 0; transform: translateY(28px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes pulse-ring {
    0%   { transform: scale(1); opacity: 0.6; }
    70%  { transform: scale(1.6); opacity: 0; }
    100% { transform: scale(1.6); opacity: 0; }
  }
  @keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(91,136,255,0.3); }
    50%       { box-shadow: 0 0 40px rgba(91,136,255,0.6), 0 0 80px rgba(31,231,255,0.2); }
  }
  @keyframes scan-line {
    0%   { transform: translateY(0); }
    100% { transform: translateY(100vh); }
  }
  @keyframes docintel-pulse {
    0%, 100% { opacity: 0.7; }
    50%       { opacity: 1; }
  }
`

/* ─────────────────────────────────────────────────────────────
   Standalone Login Page
────────────────────────────────────────────────────────────── */
interface LoginPageProps {
  onLogin: (ecNumber: string, role: string, displayName: string, token: string) => void
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [inputValue, setInputValue] = useState("")
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [emailCode, setEmailCode] = useState("")
  const [emailSent, setEmailSent] = useState(false)
  const [loginMode, setLoginMode] = useState<"ec" | "email">("email")
  const [touched, setTouched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const showError = touched && !inputValue.trim()
  const showPasswordError = touched && !password.trim()
  const showEmailError = touched && !email.trim()
  const showEmailCodeError = touched && emailSent && !emailCode.trim()
  const isValidZetdcEmail = !!email.trim() && email.trim().toLowerCase().endsWith("@zetdc.co.zw")

  const features = [
    { icon: "🧠", label: "LLM-Powered Analysis", desc: "Gemini, DeepSeek & Ollama models" },
    { icon: "📄", label: "Document Intelligence", desc: "PDF, DOCX, TXT support" },
    { icon: "💬", label: "Grounded Chat", desc: "Citation-backed answers" },
    { icon: "🔒", label: "Enterprise Security", desc: "ZETDC internal portal" },
  ]

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "linear-gradient(135deg, #070B14 0%, #0D1426 40%, #0A1020 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Animated background orbs */}
      {[
        { size: 500, x: "-15%", y: "-20%", color: "rgba(91,136,255,0.12)", delay: "0s", dur: "12s" },
        { size: 400, x: "70%", y: "60%", color: "rgba(31,231,255,0.08)", delay: "4s", dur: "15s" },
        { size: 300, x: "50%", y: "-10%", color: "rgba(91,136,255,0.07)", delay: "8s", dur: "10s" },
        { size: 250, x: "-5%", y: "65%", color: "rgba(31,231,255,0.06)", delay: "2s", dur: "18s" },
      ].map((orb, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            width: orb.size,
            height: orb.size,
            left: orb.x,
            top: orb.y,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${orb.color} 0%, transparent 70%)`,
            filter: "blur(40px)",
            animation: `float-orb ${orb.dur} ${orb.delay} ease-in-out infinite`,
            pointerEvents: "none",
          }}
        />
      ))}

      {/* Floating particles */}
      {Array.from({ length: 20 }).map((_, i) => (
        <div
          key={`p${i}`}
          style={{
            position: "absolute",
            width: 2,
            height: 2,
            borderRadius: "50%",
            background: i % 3 === 0 ? "#5B88FF" : i % 3 === 1 ? "#1FE7FF" : "rgba(255,255,255,0.4)",
            left: `${(i * 17 + 5) % 100}%`,
            top: `${(i * 23 + 10) % 100}%`,
            animation: `drift ${6 + (i % 5) * 2}s ${i * 0.4}s ease-in-out infinite`,
            pointerEvents: "none",
          }}
        />
      ))}

      {/* Grid overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(91,136,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(91,136,255,0.03) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          pointerEvents: "none",
        }}
      />

      {/* Main layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 420px",
          width: "100%",
          maxWidth: 1100,
          height: "100%",
          maxHeight: "100vh",
          alignItems: "center",
          padding: "40px",
          gap: 60,
          boxSizing: "border-box",
        }}
      >
        {/* Left — branding section */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 32,
            animation: "slide-up 0.8s ease forwards",
          }}
        >
          {/* Logo + name */}
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 18,
                background: "linear-gradient(135deg, rgba(91,136,255,0.25) 0%, rgba(31,231,255,0.12) 100%)",
                border: "1px solid rgba(91,136,255,0.4)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 30px rgba(91,136,255,0.3)",
                animation: "glow-pulse 3s ease-in-out infinite",
              }}
            >
              <img src={zetdcLogo} alt="ZETDC" style={{ width: "auto", height: "auto", maxHeight: 48, objectFit: "contain" }} />
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.15em",
                  textTransform: "uppercase",
                  color: "rgba(255,255,255,0.4)",
                }}
              >
                Zimbabwe Electricity Transmission & Distribution Company
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 800,
                  background: "linear-gradient(135deg, #5B88FF 0%, #1FE7FF 60%, #A78BFA 100%)",
                  backgroundSize: "200% 200%",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  animation: "shimmer-text 4s linear infinite",
                  letterSpacing: "0.02em",
                }}
              >
                DOCTEL LARGE LANGUAGE MODEL
              </div>
            </div>
          </div>

          {/* Headline */}
          <div>
            <h1
              style={{
                fontSize: 48,
                fontWeight: 800,
                lineHeight: 1.1,
                margin: 0,
                color: "#FFFFFF",
                letterSpacing: "-0.02em",
              }}
            >
              AI-Powered
              <br />
              <span
                style={{
                  background: "linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                Document
              </span>
              <br />
              Intelligence</h1>

            <DocChatAnimation />
            
            <p
              style={{
                marginTop: 16,
                fontSize: 16,
                color: "rgba(255,255,255,0.5)",
                lineHeight: 1.6,
                maxWidth: 460,
              }}
            >
              Instantly extract insights, generate summaries, and chat with your
              ZETDC documents using state-of-the-art large language models.
            </p>
          </div>

          {/* Feature chips */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {features.map((f) => (
              <div
                key={f.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 16px",
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  backdropFilter: "blur(10px)",
                }}
              >
                <span style={{ fontSize: 22 }}>{f.icon}</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#E5E7EB" }}>{f.label}</div>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 2 }}>{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right — login card */}
        <div
          style={{
            background: "linear-gradient(145deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.03) 100%)",
            backdropFilter: "blur(24px)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 24,
            padding: "36px 32px",
            boxShadow: "0 32px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(91,136,255,0.1)",
            animation: "slide-up 0.8s 0.15s ease both",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Card top glow */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: "20%",
              right: "20%",
              height: 1,
              background: "linear-gradient(90deg, transparent, rgba(91,136,255,0.5), transparent)",
            }}
          />

          <div style={{ marginBottom: 28 }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#FFFFFF", marginBottom: 6 }}>
              Sign in to continue
            </div>
          </div>

          {/* Mode toggle */}
          {/* <div
            style={{
              display: "flex",
              gap: 6,
              padding: 4,
              borderRadius: 12,
              background: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(255,255,255,0.06)",
              marginBottom: 24,
            }}
          >
            {(["ec", "email"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => {
                  setLoginMode(mode)
                  setAuthError(null)
                  setTouched(false)
                  setEmailSent(false)
                }}
                style={{
                  flex: 1,
                  padding: "9px 12px",
                  borderRadius: 9,
                  border: "none",
                  background:
                    loginMode === mode
                      ? "linear-gradient(135deg, rgba(91,136,255,0.3) 0%, rgba(31,231,255,0.15) 100%)"
                      : "transparent",
                  color: loginMode === mode ? "#FFFFFF" : "rgba(255,255,255,0.4)",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  boxShadow: loginMode === mode ? "0 2px 8px rgba(91,136,255,0.2)" : "none",
                }}
              >
                {mode === "ec" ? "EC + Password" : "ZETDC Email"}
              </button>
            ))}
          </div> */}

          {/* Fields */}
          <form
            onSubmit={async (e) => {
              e.preventDefault()
              setTouched(true)
              setAuthError(null)
              if (loginMode === "ec") {
                if (!inputValue.trim() || !password.trim()) return
                try {
                  setLoading(true)
                  const res = await login({ ec_number: inputValue.trim(), password })
                  setAuthToken(res.access_token)
                  onLogin(res.ec_number, (res as any).role || "", (res as any).display_name || "", res.access_token)
                  setPassword("")
                } catch (err: any) {
                  setAuthError(err.message ?? "Login failed")
                } finally {
                  setLoading(false)
                }
                return
              }
              if (!email.trim() || !isValidZetdcEmail) return
              try {
                setLoading(true)
                if (!emailSent) {
                  await requestEmailOtp({ email: email.trim() })
                  setEmailSent(true)
                } else {
                  if (!emailCode.trim()) return
                  const res = await verifyEmailOtp({ email: email.trim(), code: emailCode.trim() })
                  setAuthToken(res.access_token)
                  onLogin(res.ec_number, (res as any).role || "", (res as any).display_name || "", res.access_token)
                  setEmailCode("")
                }
              } catch (err: any) {
                setAuthError(err.message ?? "Verification failed")
              } finally {
                setLoading(false)
              }
            }}
            style={{ display: "flex", flexDirection: "column", gap: 14 }}
          >
            {loginMode === "ec" ? (
              <>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.5)", marginBottom: 8, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    EC Number
                  </label>
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onBlur={() => setTouched(true)}
                    placeholder="e.g. EC12345"
                    style={{
                      width: "100%",
                      padding: "12px 16px",
                      borderRadius: 12,
                      border: showError ? "1px solid rgba(239,68,68,0.6)" : "1px solid rgba(255,255,255,0.1)",
                      background: "rgba(0,0,0,0.3)",
                      color: "#FFFFFF",
                      fontSize: 14,
                      fontFamily: "inherit",
                      outline: "none",
                      boxSizing: "border-box",
                      transition: "border-color 0.2s",
                    }}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(91,136,255,0.6)" }}
                    onBlurCapture={(e) => { if (!showError) e.target.style.borderColor = "rgba(255,255,255,0.1)" }}
                  />
                  {showError && <div style={{ fontSize: 12, color: "#F87171", marginTop: 4 }}>EC number is required.</div>}
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.5)", marginBottom: 8, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onBlur={() => setTouched(true)}
                    placeholder="Enter your password"
                    style={{
                      width: "100%",
                      padding: "12px 16px",
                      borderRadius: 12,
                      border: showPasswordError ? "1px solid rgba(239,68,68,0.6)" : "1px solid rgba(255,255,255,0.1)",
                      background: "rgba(0,0,0,0.3)",
                      color: "#FFFFFF",
                      fontSize: 14,
                      fontFamily: "inherit",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(91,136,255,0.6)" }}
                    onBlurCapture={(e) => { if (!showPasswordError) e.target.style.borderColor = "rgba(255,255,255,0.1)" }}
                  />
                  {showPasswordError && <div style={{ fontSize: 12, color: "#F87171", marginTop: 4 }}>Password is required.</div>}
                </div>
              </>
            ) : (
              <>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.5)", marginBottom: 8, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    ZETDC Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onBlur={() => setTouched(true)}
                    placeholder="name@zetdc.co.zw"
                    style={{
                      width: "100%",
                      padding: "12px 16px",
                      borderRadius: 12,
                      border: showEmailError || (touched && !isValidZetdcEmail && email.length > 0) ? "1px solid rgba(239,68,68,0.6)" : "1px solid rgba(255,255,255,0.1)",
                      background: "rgba(0,0,0,0.3)",
                      color: "#FFFFFF",
                      fontSize: 14,
                      fontFamily: "inherit",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(91,136,255,0.6)" }}
                  />
                  {(showEmailError || (touched && !isValidZetdcEmail && email.length > 0)) && (
                    <div style={{ fontSize: 12, color: "#F87171", marginTop: 4 }}>Enter a valid ZETDC email.</div>
                  )}
                </div>
                {emailSent && (
                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.5)", marginBottom: 8, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                      Verification Code
                    </label>
                    <input
                      type="text"
                      value={emailCode}
                      onChange={(e) => setEmailCode(e.target.value)}
                      placeholder="6-digit code"
                      style={{
                        width: "100%",
                        padding: "12px 16px",
                        borderRadius: 12,
                        border: showEmailCodeError ? "1px solid rgba(239,68,68,0.6)" : "1px solid rgba(255,255,255,0.1)",
                        background: "rgba(0,0,0,0.3)",
                        color: "#FFFFFF",
                        fontSize: 14,
                        fontFamily: "inherit",
                        outline: "none",
                        boxSizing: "border-box",
                        letterSpacing: "0.15em",
                      }}
                    />
                    {showEmailCodeError && <div style={{ fontSize: 12, color: "#F87171", marginTop: 4 }}>Code is required.</div>}
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          setLoading(true)
                          await requestEmailOtp({ email: email.trim() })
                          setEmailCode("")
                        } catch (err: any) {
                          setAuthError(err.message ?? "Failed to resend")
                        } finally {
                          setLoading(false)
                        }
                      }}
                      disabled={loading}
                      style={{ marginTop: 8, padding: 0, border: "none", background: "none", color: "#5B88FF", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}
                    >
                      Resend code
                    </button>
                  </div>
                )}
              </>
            )}

            {authError && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "rgba(239,68,68,0.1)",
                  border: "1px solid rgba(239,68,68,0.2)",
                  fontSize: 13,
                  color: "#F87171",
                }}
              >
                {authError}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                padding: "14px",
                borderRadius: 14,
                border: "none",
                background: loading
                  ? "rgba(91,136,255,0.4)"
                  : "linear-gradient(135deg, #5B88FF 0%, #4A6FE8 50%, #1FE7FF 100%)",
                color: "#FFFFFF",
                fontSize: 15,
                fontWeight: 700,
                cursor: loading ? "default" : "pointer",
                transition: "all 0.2s ease",
                boxShadow: loading ? "none" : "0 4px 20px rgba(91,136,255,0.4)",
                letterSpacing: "0.02em",
                fontFamily: "inherit",
              }}
              onMouseEnter={(e) => {
                if (!loading) (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)"
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLElement).style.transform = "translateY(0)"
              }}
            >
              {loading
                ? loginMode === "email" && !emailSent
                  ? "Sending code…"
                  : "Signing in…"
                : loginMode === "email" && !emailSent
                  ? "Send Verification Code"
                  : "Sign In →"}
            </button>
          </form>

          {/* Bottom note */}
          <div style={{ marginTop: 20, textAlign: "center", fontSize: 12, color: "rgba(255,255,255,0.25)" }}>
            Internal ZETDC portal • Authorized personnel only
          </div>
        </div>
      </div>

      {/* Bottom tech strip */}
      <div
        style={{
          position: "absolute",
          bottom: 16,
          left: "50%",
          transform: "translateX(-50%)",
          fontSize: 11,
          color: "rgba(255,255,255,0.2)",
          letterSpacing: "0.08em",
          display: "flex",
          gap: 24,
          whiteSpace: "nowrap",
        }}
      >
        {["SECURE CONNECTION", "GEMINI + OLLAMA", "ENTERPRISE GRADE"].map((t) => (
          <span key={t} style={{ animation: "docintel-pulse 3s ease-in-out infinite" }}>
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────
   Main App
────────────────────────────────────────────────────────────── */
export const App: React.FC = () => {
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [page, setPage] = useState<"copilot" | "mywork" | "admin" | "training">("copilot")
  const { ecNumber, setEcNumber } = useEcNumber()
  const [loading] = useState(false)
  const [authEpoch, setAuthEpoch] = useState(0)
  const [userRole, setUserRole] = useState<string>("")
  const [displayName, setDisplayName] = useState<string>("")
  const [introVisible, setIntroVisible] = useState(false)
  const [uiCfg, setUiCfg] = useState<any>({
    show_intro_animation: true,
    show_greeting_message: true,
    intro_duration_ms: 2400,
    greeting_messages: [],
  })
  const [hasToken, setHasToken] = useState(
    typeof window !== "undefined" &&
    !!window.localStorage.getItem("docintel_auth_token"),
  )
  const [everAuthed, setEverAuthed] = useState(!!ecNumber && hasToken)

  // ── Persistent live connection monitor ─────────────────────────
  const {
    checked: connectionChecked,
    ok: connectionOk,
    initialChecking: connectionChecking,
    liveChecking,
    error: connectionError,
    backendRunning,
    ollamaRunning,
    hasExternalServices,
    startupSteps,
    recheck,
  } = useConnectionMonitor()

  const isAuthenticated = !!ecNumber && hasToken

  // Inject login page animations
  useEffect(() => {
    const id = "docintel-login-styles"
    if (!document.getElementById(id)) {
      const el = document.createElement("style")
      el.id = id
      el.textContent = loginStyles
      document.head.appendChild(el)
    }
  }, [])

  // Inject global design-system styles (links, tables, scrollbars, etc.)
  useEffect(() => {
    const id = "docintel-global-styles"
    if (!document.getElementById(id)) {
      const el = document.createElement("style")
      el.id = id
      el.textContent = globalStyles
      document.head.appendChild(el)
    }
  }, [])

  useEffect(() => {
    const onAuthChanged = () => {
      if (typeof window === "undefined") return
      const next = !!window.localStorage.getItem("docintel_auth_token")
      setHasToken(next)
      if (!next) setUserRole("")
    }
    window.addEventListener("docintel_auth_changed", onAuthChanged as any)
    return () => window.removeEventListener("docintel_auth_changed", onAuthChanged as any)
  }, [])

  useEffect(() => {
    const onLogout = () => {
      setAuthEpoch((v) => v + 1)
      setHasToken(false)
      setUserRole("")
      setDocumentId(null)
      setPage("copilot")
    }
    window.addEventListener("docintel_logout", onLogout as any)
    return () => window.removeEventListener("docintel_logout", onLogout as any)
  }, [])

  useEffect(() => {
    if (isAuthenticated) setEverAuthed(true)
  }, [isAuthenticated])

  useEffect(() => {
    const loadMe = async () => {
      if (!hasToken) return
      try {
        const me = await getMe()
        setUserRole(me.role || "")
        setDisplayName(me.display_name || "")
      } catch {}
    }
    loadMe()
  }, [hasToken, authEpoch])

  useEffect(() => {
    const loadUi = async () => {
      if (!hasToken) return
      try {
        const ui = await getUiSettings()
        setUiCfg(ui || {})
      } catch {}
    }
    loadUi()
  }, [hasToken, authEpoch])

  const handleLogout = useCallback(async () => {
    try {
      await logout()
    } catch {} finally {
      clearAuthToken()
      setEcNumber("")
      setDocumentId(null)
      setDisplayName("")
      setAuthEpoch((v) => v + 1)
      setHasToken(false)
      setUserRole("")
      window.dispatchEvent(new CustomEvent("docintel_logout"))
      try {
        const bc = new BroadcastChannel("doctel_sync")
        bc.postMessage({ event: "session.logout" })
        bc.close()
      } catch {}
    }
  }, [setEcNumber])

  useEffect(() => {
    let bc: BroadcastChannel | null = null
    try {
      bc = new BroadcastChannel("doctel_sync")
      bc.onmessage = (e) => {
        if (e.data?.event === "session.logout") handleLogout()
      }
    } catch {}
    return () => { bc?.close() }
  }, [handleLogout])

  // Custom scrollbar styles
  useEffect(() => {
    const style = document.createElement("style")
    style.textContent = `
      ::-webkit-scrollbar { width: 6px; height: 6px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
      ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.3); }
      * { scrollbar-color: rgba(255,255,255,0.15) transparent; scrollbar-width: thin; }
      @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.5} }
    `
    document.head.appendChild(style)
    return () => document.head.removeChild(style)
  }, [])

  useSyncEvents({
    enabled: isAuthenticated,
    onLogout: () => handleLogout(),
  })

  const handleLoginSuccess = useCallback(
    async (ec: string, role: string, name: string, token: string) => {
      const effectiveEc = ec.trim() || (name.includes("@") ? name.split("@")[0] : name) || "user"
      setEcNumber(effectiveEc)
      setAuthToken(token)
      setHasToken(true)
      setDocumentId(null)
      setPage("mywork")
      if (role) setUserRole(role)
      if (name) setDisplayName(name)
      try {
        const ui = await getUiSettings()
        setUiCfg(ui || {})
        const showIntro = Boolean(ui?.show_intro_animation) || Boolean(ui?.show_greeting_message)
        if (showIntro) setIntroVisible(true)
      } catch {}
      window.dispatchEvent(new CustomEvent("docintel_auth_restored"))
    },
    [setEcNumber]
  )

  return (
    <ThemeProvider>
      <ModelProvider>
        {/* ── Connection check gate ─────────────────────────────── */}
        {/* Inline keyframes for the spinner (avoids dependency on injected styles) */}
        <style>{`@keyframes conn-spin { to { transform: rotate(360deg); } }`}</style>
        {connectionChecking ? (
          <div style={{
            position: "fixed", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            background: "#070B14", color: "#fff",
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            gap: 24,
          }}>
            {/* ZETDC Logo */}
            <div style={{ fontSize: 14, fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: 1, marginBottom: 8 }}>
              DocIntel
            </div>
            {/* Progress Steps */}
            <div style={{
              display: "flex", flexDirection: "column", gap: 10,
              minWidth: 280, maxWidth: 360,
            }}>
              {(startupSteps || []).map((step) => (
                <div key={step.id} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  opacity: step.status === "pending" ? 0.35 : 1,
                  transition: "opacity 0.3s ease",
                }}>
                  {/* Status icon */}
                  <div style={{
                    width: 20, height: 20, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 700, flexShrink: 0,
                    backgroundColor:
                      step.status === "done" ? "#22C55E" :
                      step.status === "error" ? "#EF4444" :
                      step.status === "in-progress" ? "#5B88FF" :
                      step.status === "skipped" ? "#6B7280" : "rgba(255,255,255,0.1)",
                    color: "#FFF",
                  }}>
                    {step.status === "done" ? "✓" :
                     step.status === "error" ? "✕" :
                     step.status === "in-progress" ? "⟳" :
                     step.status === "skipped" ? "–" : "·"}
                  </div>
                  {/* Label */}
                  <span style={{
                    fontSize: 13, fontWeight: 500,
                    color: step.status === "done" ? "#22C55E" :
                           step.status === "error" ? "#EF4444" :
                           step.status === "in-progress" ? "#5B88FF" : "rgba(255,255,255,0.6)",
                  }}>
                    {step.label}
                  </span>
                  {/* Message */}
                  {step.message && step.status === "in-progress" && (
                    <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginLeft: "auto", whiteSpace: "nowrap" }}>
                      {step.message}
                    </span>
                  )}
                </div>
              ))}
            </div>
            {/* Spinner */}
            <div style={{
              width: 24, height: 24,
              border: "2px solid rgba(91,136,255,0.2)",
              borderTopColor: "#5B88FF",
              borderRadius: "50%",
              animation: "conn-spin 0.8s linear infinite",
              marginTop: 8,
            }} />
          </div>
        ) : !connectionOk ? (
          <div style={{
            position: "fixed", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            background: "#070B14", color: "#fff",
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            gap: 16, padding: 32,
          }}>
            <div style={{ fontSize: 48, lineHeight: 1 }}>
              {!backendRunning ? "🔌" : !ollamaRunning ? "🤖" : "⚠️"}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>
              {!backendRunning
                ? "Backend Server Offline"
                : !ollamaRunning
                  ? "Local AI Models Offline"
                  : "Unable to Connect"}
            </div>
            <div style={{
              fontSize: 13, color: "rgba(255,255,255,0.55)",
              textAlign: "center", maxWidth: 420, lineHeight: 1.6,
            }}>
              {connectionError || "The backend server is not reachable. Please ensure the server is running and try again."}
            </div>
            {/* Service status indicators */}
            <div style={{
              display: "flex", flexDirection: "column", gap: 8,
              marginTop: 8, padding: "12px 16px",
              background: "rgba(255,255,255,0.04)",
              borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)",
              minWidth: 280,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <span style={{ fontSize: 14 }}>{backendRunning ? "✅" : "❌"}</span>
                <span style={{ color: backendRunning ? "#2ed573" : "#ff6b6b", fontWeight: 500 }}>
                  Backend Server
                </span>
                <span style={{ color: "rgba(255,255,255,0.4)", marginLeft: "auto" }}>
                  {backendRunning ? "Running" : "Not Running"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <span style={{ fontSize: 14 }}>{ollamaRunning ? "✅" : "❌"}</span>
                <span style={{ color: ollamaRunning ? "#2ed573" : "#ff6b6b", fontWeight: 500 }}>
                  Ollama (Local Models)
                </span>
                <span style={{ color: "rgba(255,255,255,0.4)", marginLeft: "auto" }}>
                  {ollamaRunning ? "Running" : "Not Running"}
                </span>
              </div>
              {hasExternalServices && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                  <span style={{ fontSize: 14 }}>☁️</span>
                  <span style={{ color: "#5B88FF", fontWeight: 500 }}>
                    External AI Services
                  </span>
                  <span style={{ color: "rgba(255,255,255,0.4)", marginLeft: "auto" }}>
                    Configured
                  </span>
                </div>
              )}
            </div>
            {/* Quick fix hints */}
            {!backendRunning && (
              <div style={{
                fontSize: 11, color: "rgba(255,255,255,0.35)",
                textAlign: "center", maxWidth: 400, lineHeight: 1.5,
                marginTop: 4,
              }}>
                💡 Start the backend: <code style={{ background: "rgba(255,255,255,0.08)", padding: "2px 6px", borderRadius: 4, fontFamily: "monospace" }}>python -m uvicorn app.main:app --host 127.0.0.1 --port 8000</code>
              </div>
            )}
            {backendRunning && !ollamaRunning && (
              <div style={{
                fontSize: 11, color: "rgba(255,255,255,0.35)",
                textAlign: "center", maxWidth: 400, lineHeight: 1.5,
                marginTop: 4,
              }}>
                💡 Start Ollama: <code style={{ background: "rgba(255,255,255,0.08)", padding: "2px 6px", borderRadius: 4, fontFamily: "monospace" }}>ollama serve</code>
                {hasExternalServices && " — or switch to an external model in settings"}
              </div>
            )}
            <button
              onClick={recheck}
              style={{
                marginTop: 12,
                padding: "12px 32px",
                borderRadius: 10,
                border: "none",
                background: "linear-gradient(135deg, #5B88FF, #1FE7FF)",
                color: "#fff",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Retry Connection
            </button>
          </div>
        ) : !isAuthenticated ? (
          <LoginPage onLogin={handleLoginSuccess} />
        ) : (
          <>
            <ConnectionToast
              connected={connectionOk}
              liveChecking={liveChecking}
              error={connectionError}
              backendRunning={backendRunning}
              ollamaRunning={ollamaRunning}
              hasExternalServices={hasExternalServices}
            />
            <AuthenticatedLayout
              onLogout={handleLogout}
              userRole={userRole}
              displayName={displayName}
              isAuthenticated={isAuthenticated}
            />
          </>
        )}
      </ModelProvider>
    </ThemeProvider>
  )
}
