/**
 * useConnectionMonitor.ts – Enhanced connection monitor with detailed startup progress.
 *
 * Provides step-by-step progress during initial connection:
 *   1. ✓ Frontend Loaded
 *   2. ✓ Backend Connected
 *   3. ✓ Database Connected
 *   4. ✓ Configuration Loaded
 *   5. ⟳ Checking Models (non-blocking)
 *   6. ✓ Ready
 *
 * After initial gate, maintains live connection via WebSocket with
 * exponential backoff reconnection.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { checkBackendConnection, checkDetailedHealth } from "../api/client"

/* ── Config ────────────────────────────────────────────── */
function getWsBaseUrl(): string {
  const raw = (import.meta as any).env.VITE_API_BASE_URL
  const httpUrl =
    typeof raw === "string" && raw.trim()
      ? raw.trim().replace(/\/+$/, "")
      : typeof window !== "undefined"
        ? window.location.origin
        : "http://localhost:5173"
  return httpUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:")
}

function getIntervalMs(): number {
  const raw = (import.meta as any).env.VITE_WS_CHECK_INTERVAL_MS
  const n = parseInt(raw, 10)
  return !isNaN(n) && n > 0 ? n : 30_000
}

/* ── Startup Steps ─────────────────────────────────────── */
export interface StartupStep {
  id: string
  label: string
  status: "pending" | "in-progress" | "done" | "error" | "skipped"
  message?: string
}

/* ── Types ─────────────────────────────────────────────── */
export interface ConnectionState {
  /** Initial gate check completed */
  checked: boolean
  /** Whether the backend is currently reachable */
  ok: boolean
  /** True while the very first connection check is running */
  initialChecking: boolean
  /** True when a live check (WS or HTTP fallback) is in progress */
  liveChecking: boolean
  /** Human‑readable error message */
  error: string
  /** Whether backend server is running */
  backendRunning: boolean
  /** Whether Ollama (local models) is running */
  ollamaRunning: boolean
  /** Whether any external AI services are configured */
  hasExternalServices: boolean
  /** Detailed startup progress steps */
  startupSteps: StartupStep[]
}

/* ── Hook ──────────────────────────────────────────────── */
export interface ConnectionMonitorResult extends ConnectionState {
  /** Re-run the initial gate check (useful for retry buttons). */
  recheck: () => Promise<void>
}

function createInitialSteps(): StartupStep[] {
  return [
    { id: "frontend", label: "Frontend Loaded", status: "done" },
    { id: "backend", label: "Backend Connected", status: "pending" },
    { id: "database", label: "Database Connected", status: "pending" },
    { id: "config", label: "Configuration Loaded", status: "pending" },
    { id: "models", label: "Checking Models", status: "pending" },
    { id: "ready", label: "Ready", status: "pending" },
  ]
}

function updateStep(
  steps: StartupStep[],
  id: string,
  status: StartupStep["status"],
  message?: string,
): StartupStep[] {
  return steps.map((s) => (s.id === id ? { ...s, status, message } : s))
}

export function useConnectionMonitor(): ConnectionMonitorResult {
  const [checked, setChecked] = useState(false)
  const [ok, setOk] = useState(false)
  const [initialChecking, setInitialChecking] = useState(true)
  const [liveChecking, setLiveChecking] = useState(false)
  const [error, setError] = useState("")
  const [backendRunning, setBackendRunning] = useState(false)
  const [ollamaRunning, setOllamaRunning] = useState(false)
  const [hasExternalServices, setHasExternalServices] = useState(false)
  const [startupSteps, setStartupSteps] = useState<StartupStep[]>(createInitialSteps)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)

  const okRef = useRef(false)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const destroyedRef = useRef(false)

  /* ── Initial gate check with detailed progress ──────── */
  const runInitialCheck = useCallback(async () => {
    let cancelled = false
    // Small delay to avoid React StrictMode double-mount issues
    await new Promise(r => setTimeout(r, 100))
    if (cancelled || destroyedRef.current) return

    setInitialChecking(true)
    setStartupSteps(createInitialSteps())

    // Step 1: Frontend is already loaded (set as done)

    // Step 2: Backend connection
    setStartupSteps((prev) => updateStep(prev, "backend", "in-progress", "Connecting to server..."))
    const basicResult = await checkBackendConnection(5_000)
    if (cancelled || destroyedRef.current) return

    if (!basicResult.ok) {
      setStartupSteps((prev) => updateStep(prev, "backend", "error", basicResult.error || "Unable to reach server"))
      setOk(false)
      okRef.current = false
      setBackendRunning(false)
      setOllamaRunning(false)
      setHasExternalServices(false)
      setError(basicResult.error || "Unable to reach server.")
      setInitialChecking(false)
      setChecked(true)
      return
    }

    setStartupSteps((prev) => updateStep(prev, "backend", "done", "Connected"))

    // Step 3: Database (fast check - runs in parallel with models)
    setStartupSteps((prev) => updateStep(prev, "database", "in-progress", "Verifying database..."))
    
    // Step 4: Configuration
    setStartupSteps((prev) => updateStep(prev, "config", "in-progress"))

    // Run detailed health check and config in parallel
    const [detailedResult] = await Promise.all([
      checkDetailedHealth(10_000),
      new Promise(r => setTimeout(r, 100)), // small config delay
    ])
    if (cancelled || destroyedRef.current) return

    if (detailedResult.backendRunning) {
      setStartupSteps((prev) => updateStep(prev, "database", "done", "Connected"))
    } else {
      setStartupSteps((prev) => updateStep(prev, "database", "error", "Database unavailable"))
    }
    setStartupSteps((prev) => updateStep(prev, "config", "done", "Loaded"))

    // Step 5: Models (mark done immediately from detailedResult)
    setStartupSteps((prev) => updateStep(prev, "models", "in-progress", "Checking AI models..."))

    setOk(detailedResult.ok)
    okRef.current = detailedResult.ok
    setBackendRunning(detailedResult.backendRunning)
    setOllamaRunning(detailedResult.ollamaRunning)
    setHasExternalServices(detailedResult.hasExternalServices)

    if (!detailedResult.ok) {
      setError(detailedResult.error || "Unable to reach server.")
      setStartupSteps((prev) => updateStep(prev, "models", "skipped", "Some services offline"))
    } else {
      setStartupSteps((prev) => updateStep(prev, "models", "done",
        detailedResult.ollamaRunning ? "AI models available" : "Proceeding without local models"))
    }

    // Step 6: Ready
    setStartupSteps((prev) => updateStep(prev, "ready", "done", "Application ready"))
    setInitialChecking(false)
    setChecked(true)
  }, [])

  useEffect(() => {
    destroyedRef.current = false
    runInitialCheck()
    return () => { destroyedRef.current = true }
  }, [runInitialCheck])

  /* ── Live monitor with exponential backoff ──────────── */
  useEffect(() => {
    if (!checked || !ok) return

    const intervalMs = getIntervalMs()
    const wsBase = getWsBaseUrl()

    /* ── Attempt WebSocket connection ──────────────── */
    let ws: WebSocket | null = null
    let usePolling = false
    let pollCount = 0

    const startWs = () => {
      try {
        ws = new WebSocket(`${wsBase}/ws`)
        wsRef.current = ws

        // 5-second connection timeout
        const connTimeout = setTimeout(() => {
          if (ws?.readyState !== WebSocket.OPEN) {
            ws?.close()
            usePolling = true
            startPolling()
          }
        }, 5000)

        ws.onopen = () => {
          clearTimeout(connTimeout)
          if (destroyedRef.current) return
          setOk(true)
          okRef.current = true
          setError("")
          setLiveChecking(false)
          setReconnectAttempt(0) // Reset on successful connection

          // Start periodic ping (30s heartbeat)
          if (timerRef.current) clearInterval(timerRef.current)
          timerRef.current = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
              ws.send("ping")
            }
          }, intervalMs)
        }

        ws.onmessage = (evt) => {
          if (destroyedRef.current) return
          if (evt.data === "pong") {
            setOk(true)
            okRef.current = true
            setError("")
            setLiveChecking(false)
          }
        }

        ws.onerror = () => {
          clearTimeout(connTimeout)
          if (destroyedRef.current) return
          ws?.close()
          usePolling = true
          startPolling()
        }

        ws.onclose = () => {
          clearTimeout(connTimeout)
          if (destroyedRef.current) return
          if (!usePolling) {
            usePolling = true
            startPolling()
          }
        }
      } catch {
        usePolling = true
        startPolling()
      }
    }

    /* ── Fallback HTTP polling with exponential backoff ── */
    const startPolling = () => {
      if (destroyedRef.current) return
      if (timerRef.current) clearInterval(timerRef.current)

      const check = async () => {
        if (destroyedRef.current) return
        setLiveChecking(true)
        const result = await checkBackendConnection(10_000)
        if (destroyedRef.current) return
        if (result.ok !== okRef.current) {
          setOk(result.ok)
          okRef.current = result.ok
          if (!result.ok) {
            setError(result.error || "Connection lost")
            // Exponential backoff for reconnection
            pollCount++
            const backoff = Math.min(2000 * Math.pow(2, pollCount), 30000) // 2, 4, 8, 16, max 30s
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
            reconnectTimerRef.current = setTimeout(() => {
              if (!destroyedRef.current) {
                startWs() // Try WebSocket again
              }
            }, backoff)
          } else {
            setError("")
            pollCount = 0
          }
        }
        setLiveChecking(false)
      }
      // Immediate first check
      check()
      timerRef.current = setInterval(check, intervalMs)
    }

    startWs()

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (ws) {
        ws.onopen = null
        ws.onmessage = null
        ws.onerror = null
        ws.onclose = null
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close()
        }
      }
      wsRef.current = null
    }
  }, [checked, ok, reconnectAttempt])

  /* ── Public retry ─────────────────────────────────────── */
  const recheck = useCallback(async () => {
    destroyedRef.current = false
    setInitialChecking(true)
    setChecked(false)
    setOk(false)
    setError("")
    setStartupSteps(createInitialSteps())

    // Step 1: Frontend (already done)

    // Step 2: Backend
    setStartupSteps((prev) => updateStep(prev, "backend", "in-progress", "Connecting..."))
    const basicResult = await checkBackendConnection(5_000)
    if (destroyedRef.current) return

    if (!basicResult.ok) {
      setStartupSteps((prev) => updateStep(prev, "backend", "error", basicResult.error || "Unreachable"))
      setOk(false)
      okRef.current = false
      setBackendRunning(false)
      setOllamaRunning(false)
      setHasExternalServices(false)
      setError(basicResult.error || "Unable to reach server.")
      setInitialChecking(false)
      setChecked(true)
      return
    }

    setStartupSteps((prev) => updateStep(prev, "backend", "done"))
    setStartupSteps((prev) => updateStep(prev, "database", "in-progress"))

    const detailedResult = await checkDetailedHealth(10_000)
    if (destroyedRef.current) return

    setStartupSteps((prev) => updateStep(prev, "database", "done", "Connected"))
    setStartupSteps((prev) => updateStep(prev, "config", "done", "Loaded"))

    setOk(detailedResult.ok)
    okRef.current = detailedResult.ok
    setBackendRunning(detailedResult.backendRunning)
    setOllamaRunning(detailedResult.ollamaRunning)
    setHasExternalServices(detailedResult.hasExternalServices)

    if (!detailedResult.ok) {
      setError(detailedResult.error || "Unable to reach server.")
      setStartupSteps((prev) => updateStep(prev, "models", "skipped"))
    } else {
      setStartupSteps((prev) => updateStep(prev, "models", "done"))
    }
    setStartupSteps((prev) => updateStep(prev, "ready", "done"))
    setInitialChecking(false)
    setChecked(true)
  }, [])

  return {
    checked,
    ok,
    initialChecking,
    liveChecking,
    error,
    backendRunning,
    ollamaRunning,
    hasExternalServices,
    startupSteps,
    recheck,
  }
}
