import React, { useCallback, useEffect, useState } from "react"
import { AppShell } from "./components/layout/AppShell"
import { IntroOverlay } from "./components/IntroOverlay"
import { DocumentViewPage } from "./pages/DocumentViewPage"
import { MyWorkPage } from "./pages/MyWorkPage"
import { AdminSettingsPage } from "./pages/AdminSettingsPage"
import { TrainingRoomPage } from "./pages/TrainingRoomPage"
import { useEcNumber } from "./hooks/useEcNumber"
import { useSyncEvents } from "./hooks/useSyncEvents"
import { colors } from "./theme/colors"
import { login, setAuthToken, requestEmailOtp, verifyEmailOtp, logout, clearAuthToken, getMe, getUiSettings } from "./api/client"
import zetdcLogo from "./assets/zetdc-logo.png"

export const App: React.FC = () => {
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [page, setPage] = useState<"copilot" | "mywork" | "admin" | "training">("copilot")
  const { ecNumber, setEcNumber } = useEcNumber()
  const [inputValue, setInputValue] = useState(ecNumber)
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [emailCode, setEmailCode] = useState("")
  const [emailSent, setEmailSent] = useState(false)
  const [loginMode, setLoginMode] = useState<"ec" | "email">("ec")
  const [touched, setTouched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
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

  const hasEc = !!ecNumber
  const isAuthenticated = hasEc && hasToken
  const showError = touched && !inputValue.trim()
  const showPasswordError = touched && !password.trim()
  const showEmailError = touched && !email.trim()
  const showEmailCodeError = touched && !emailCode.trim()
  const isValidZetdcEmail =
    !!email.trim() && email.trim().toLowerCase().endsWith("@zetdc.co.zw")

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
      } catch {
      }
    }
    loadMe()
  }, [hasToken, authEpoch])

  useEffect(() => {
    const loadUi = async () => {
      if (!hasToken) return
      try {
        const ui = await getUiSettings()
        setUiCfg(ui || {})
      } catch {
      }
    }
    loadUi()
  }, [hasToken, authEpoch])

  const handleLogout = useCallback(async () => {
    try {
      await logout()
    } catch {
    } finally {
      clearAuthToken()
      setEcNumber("")
      setInputValue("")
      setDocumentId(null)
      setPassword("")
      setEmail("")
      setEmailCode("")
      setEmailSent(false)
      setTouched(false)
      setAuthError(null)
      setDisplayName("")
      setAuthEpoch((v) => v + 1)
      window.dispatchEvent(new CustomEvent("docintel_logout"))
      // Cross-tab sync via BroadcastChannel
      try {
        const bc = new BroadcastChannel("doctel_sync")
        bc.postMessage({ event: "session.logout" })
        bc.close()
      } catch {
        // BroadcastChannel not supported – ignore
      }
    }
  }, [setEcNumber])

  // Cross-tab logout listener (BroadcastChannel – same browser, multiple tabs)
  useEffect(() => {
    let bc: BroadcastChannel | null = null
    try {
      bc = new BroadcastChannel("doctel_sync")
      bc.onmessage = (e) => {
        if (e.data?.event === "session.logout") handleLogout()
      }
    } catch {
      // ignore
    }
    return () => { bc?.close() }
  }, [handleLogout])

  // SSE cross-platform logout (web → mobile and vice-versa via server)
  useSyncEvents({
    enabled: isAuthenticated,
    onLogout: () => handleLogout(),
  })

  return (
    <AppShell
      nav={
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button
            type="button"
            onClick={() => setPage("copilot")}
            style={{
              padding: "6px 10px",
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.6)",
              backgroundColor: page === "copilot" ? "rgba(255,255,255,0.25)" : "transparent",
              color: "#FFFFFF",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Copilot
          </button>
          <button
            type="button"
            onClick={() => setPage("mywork")}
            style={{
              padding: "6px 10px",
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.6)",
              backgroundColor: page === "mywork" ? "rgba(255,255,255,0.25)" : "transparent",
              color: "#FFFFFF",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            My Work
          </button>
          {userRole === "admin" && (
            <>
              <button
                type="button"
                onClick={() => setPage("admin")}
                style={{
                  padding: "6px 10px",
                  borderRadius: 999,
                  border: "1px solid rgba(255,255,255,0.6)",
                  backgroundColor: page === "admin" ? "rgba(255,255,255,0.25)" : "transparent",
                  color: "#FFFFFF",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Admin
              </button>
              <button
                type="button"
                onClick={() => setPage("training")}
                style={{
                  padding: "6px 10px",
                  borderRadius: 999,
                  border: "1px solid rgba(255,255,255,0.6)",
                  backgroundColor: page === "training" ? "rgba(255,255,255,0.25)" : "transparent",
                  color: "#FFFFFF",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                🧠 Training
              </button>
            </>
          )}
          {isAuthenticated && (
            <button
              type="button"
              onClick={handleLogout}
              style={{
                padding: "6px 10px",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.6)",
                backgroundColor: "transparent",
                color: "#FFFFFF",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              Logout
            </button>
          )}
        </div>
      }
    >
      <IntroOverlay
        visible={introVisible}
        durationMs={Number(uiCfg?.intro_duration_ms) || 2400}
        showGreeting={Boolean(uiCfg?.show_greeting_message)}
        greetingMessages={(uiCfg?.greeting_messages || []) as string[]}
        displayName={displayName}
        onDone={() => setIntroVisible(false)}
      />
      {!isAuthenticated && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(11,78,162,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "#FFFFFF",
              padding: 24,
              borderRadius: 12,
              width: "90%",
              maxWidth: 400,
              boxShadow: "0 12px 30px rgba(11,78,162,0.25)",
              border: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <img
                src={zetdcLogo}
                alt="ZETDC logo"
                style={{
                  width: 44,
                  height: 44,
                  objectFit: "contain",
                }}
              />
              <div>
                <div style={{ fontSize: 12, color: colors.textMuted, fontWeight: 600 }}>
                  Zimbabwe Electricity Transmission & Distribution
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: colors.textPrimary }}>
                  DocIntel Portal
                </div>
              </div>
            </div>
            <h2
              style={{
                marginTop: 0,
                marginBottom: 8,
                fontSize: 20,
                color: colors.textPrimary,
              }}
            >
              Welcome back
            </h2>
            <p
              style={{
                marginTop: 0,
                marginBottom: 16,
                fontSize: 14,
                color: colors.textMuted,
              }}
            >
              Sign in with your EC number or ZETDC email. Your history is linked
              to your account for future reference.
            </p>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <button
                type="button"
                onClick={() => {
                  setLoginMode("ec")
                  setAuthError(null)
                  setTouched(false)
                }}
                style={{
                  flex: 1,
                  padding: "6px 10px",
                  borderRadius: 999,
                  border:
                    loginMode === "ec" ? `1px solid ${colors.primary}` : `1px solid ${colors.border}`,
                  backgroundColor: loginMode === "ec" ? "#E7F0FF" : "#FFFFFF",
                  color: colors.textPrimary,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                EC + Password
              </button>
              <button
                type="button"
                onClick={() => {
                  setLoginMode("email")
                  setAuthError(null)
                  setTouched(false)
                }}
                style={{
                  flex: 1,
                  padding: "6px 10px",
                  borderRadius: 999,
                  border:
                    loginMode === "email"
                      ? `1px solid ${colors.primary}`
                      : `1px solid ${colors.border}`,
                  backgroundColor: loginMode === "email" ? "#E7F0FF" : "#FFFFFF",
                  color: colors.textPrimary,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                ZETDC Email
              </button>
            </div>
            <form
              onSubmit={async (e) => {
                e.preventDefault()
                setTouched(true)
                setAuthError(null)
                if (loginMode === "ec") {
                  if (!inputValue.trim() || !password.trim()) return
                  try {
                    setLoading(true)
                    const res = await login({
                      ec_number: inputValue.trim(),
                      password: password,
                    })
                    setEcNumber(res.ec_number)
                    setAuthToken(res.access_token)
                    setHasToken(true)
                    setDocumentId(null)
                    setPage("mywork")
                    if ((res as any).role) setUserRole((res as any).role)
                    if ((res as any).display_name) setDisplayName((res as any).display_name)
                    try {
                      const ui = await getUiSettings()
                      setUiCfg(ui || {})
                      const showIntro = Boolean(ui?.show_intro_animation) || Boolean(ui?.show_greeting_message)
                      if (showIntro) setIntroVisible(true)
                    } catch {
                    }
                    window.dispatchEvent(new CustomEvent("docintel_auth_restored"))
                    setPassword("")
                  } catch (e: any) {
                    setAuthError(e.message ?? "Login failed")
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
                    const res = await verifyEmailOtp({
                      email: email.trim(),
                      code: emailCode.trim(),
                    })
                    setEcNumber(res.ec_number)
                    setAuthToken(res.access_token)
                    setHasToken(true)
                    setDocumentId(null)
                    setPage("mywork")
                    if ((res as any).role) setUserRole((res as any).role)
                    if ((res as any).display_name) setDisplayName((res as any).display_name)
                    try {
                      const ui = await getUiSettings()
                      setUiCfg(ui || {})
                      const showIntro = Boolean(ui?.show_intro_animation) || Boolean(ui?.show_greeting_message)
                      if (showIntro) setIntroVisible(true)
                    } catch {
                    }
                    window.dispatchEvent(new CustomEvent("docintel_auth_restored"))
                    setEmailCode("")
                  }
                } catch (e: any) {
                  setAuthError(e.message ?? "Verification failed")
                } finally {
                  setLoading(false)
                }
              }}
            >
              {loginMode === "ec" ? (
                <>
                  <label
                    style={{
                      display: "block",
                      fontSize: 13,
                      marginBottom: 4,
                      color: colors.textPrimary,
                    }}
                  >
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
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: showError
                        ? `1px solid ${colors.danger}`
                        : `1px solid ${colors.border}`,
                      fontSize: 14,
                      marginBottom: 8,
                      backgroundColor: "#FFFFFF",
                    }}
                  />
                  {showError && (
                    <div
                      style={{
                        fontSize: 12,
                        color: colors.danger,
                        marginBottom: 8,
                      }}
                    >
                      EC number is required.
                    </div>
                  )}
                  <label
                    style={{
                      display: "block",
                      fontSize: 13,
                      marginBottom: 4,
                      color: colors.textPrimary,
                    }}
                  >
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
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: showPasswordError
                        ? `1px solid ${colors.danger}`
                        : `1px solid ${colors.border}`,
                      fontSize: 14,
                      marginBottom: 8,
                      backgroundColor: "#FFFFFF",
                    }}
                  />
                  {showPasswordError && (
                    <div
                      style={{
                        fontSize: 12,
                        color: colors.danger,
                        marginBottom: 8,
                      }}
                    >
                      Password is required.
                    </div>
                  )}
                </>
              ) : (
                <>
                  <label
                    style={{
                      display: "block",
                      fontSize: 13,
                      marginBottom: 4,
                      color: colors.textPrimary,
                    }}
                  >
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
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: showEmailError || (touched && !isValidZetdcEmail)
                        ? `1px solid ${colors.danger}`
                        : `1px solid ${colors.border}`,
                      fontSize: 14,
                      marginBottom: 8,
                      backgroundColor: "#FFFFFF",
                    }}
                  />
                  {(showEmailError || (touched && !isValidZetdcEmail)) && (
                    <div
                      style={{
                        fontSize: 12,
                        color: colors.danger,
                        marginBottom: 8,
                      }}
                    >
                      Enter a valid ZETDC email.
                    </div>
                  )}
                  {emailSent && (
                    <>
                      <label
                        style={{
                          display: "block",
                          fontSize: 13,
                          marginBottom: 4,
                          color: colors.textPrimary,
                        }}
                      >
                        Verification Code
                      </label>
                      <input
                        type="text"
                        value={emailCode}
                        onChange={(e) => setEmailCode(e.target.value)}
                        onBlur={() => setTouched(true)}
                        placeholder="6-digit code"
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          borderRadius: 8,
                          border: showEmailCodeError
                            ? `1px solid ${colors.danger}`
                            : `1px solid ${colors.border}`,
                          fontSize: 14,
                          marginBottom: 8,
                          backgroundColor: "#FFFFFF",
                        }}
                      />
                      {showEmailCodeError && (
                        <div
                          style={{
                            fontSize: 12,
                            color: colors.danger,
                            marginBottom: 8,
                          }}
                        >
                          Code is required.
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={async () => {
                          if (!email.trim() || !isValidZetdcEmail) return
                          try {
                            setLoading(true)
                            setAuthError(null)
                            await requestEmailOtp({ email: email.trim() })
                            setEmailCode("")
                          } catch (e: any) {
                            setAuthError(e.message ?? "Failed to resend code")
                          } finally {
                            setLoading(false)
                          }
                        }}
                        style={{
                          padding: 0,
                          border: "none",
                          background: "none",
                          color: colors.primary,
                          fontSize: 13,
                          cursor: loading ? "default" : "pointer",
                          textAlign: "left",
                          marginBottom: 8,
                        }}
                        disabled={loading}
                      >
                        Resend code
                      </button>
                    </>
                  )}
                </>
              )}
              {authError && (
                <div
                  style={{
                    fontSize: 12,
                    color: colors.danger,
                    marginBottom: 8,
                  }}
                >
                  {authError}
                </div>
              )}
              <button
                type="submit"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "none",
                  background: `linear-gradient(90deg, ${colors.primary} 0%, ${colors.accentOrange} 70%)`,
                  color: "#FFFFFF",
                  fontSize: 14,
                  cursor: loading ? "default" : "pointer",
                  opacity: loading ? 0.8 : 1,
                }}
                disabled={loading}
              >
                {loading
                  ? loginMode === "email" && !emailSent
                    ? "Sending..."
                    : "Signing in..."
                  : loginMode === "email" && !emailSent
                    ? "Send Code"
                    : "Continue"}
              </button>
            </form>
          </div>
        </div>
      )}
      {everAuthed && page === "copilot" && (
        <DocumentViewPage
          documentId={documentId}
          isAuthenticated={isAuthenticated}
          authEpoch={authEpoch}
        />
      )}
      {isAuthenticated && page === "mywork" && (
        <MyWorkPage
          onOpenDocument={(id) => {
            setDocumentId(id)
            setPage("copilot")
          }}
        />
      )}
      {isAuthenticated && userRole === "admin" && page === "admin" && <AdminSettingsPage />}
      {isAuthenticated && userRole === "admin" && page === "training" && <TrainingRoomPage />}
    </AppShell>
  )
}
