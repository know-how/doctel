/**
 * useConnectionMonitor.ts – Persistent live connection monitor (React Native).
 *
 * Behaviour:
 *   1. Performs a multi-step startup sequence (Backend→Database→Config→Models→Ready)
 *      displayed as a step-by-step progress gate on first load.
 *   2. After passing the gate, opens a WebSocket to ws://HOST/ws
 *      and exchanges ping/pong every N seconds.
 *   3. If the WebSocket fails, falls back to HTTP polling every N seconds
 *      with exponential backoff and periodic WebSocket re-try.
 *   4. Exposes states so the app can show a full‑screen gate on first load
 *      and a floating toast when the connection drops mid‑session.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { checkBackendConnection, checkDetailedHealth } from "../api/client"

/* ── Config ────────────────────────────────────────────── */
function getWsBaseUrl(): string {
  const httpUrl =
    process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://172.16.4.60:8000"
  return httpUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:")
}

function getIntervalMs(): number {
  const raw = process.env.EXPO_PUBLIC_WS_CHECK_INTERVAL_MS
  const n = parseInt(raw ?? "", 10)
  return !isNaN(n) && n > 0 ? n : 30_000
}

/* ── Startup Step Types ────────────────────────────────── */
export interface StartupStep {
  id: string
  label: string
  status: "pending" | "in-progress" | "done" | "error" | "skipped"
  message?: string
}

function createInitialSteps(): StartupStep[] {
  return [
    { id: "backend", label: "Backend Connect", status: "pending" },
    { id: "database", label: "Database Status", status: "pending" },
    { id: "config", label: "Configuration", status: "pending" },
    { id: "models", label: "Model Status", status: "pending" },
    { id: "ready", label: "Ready", status: "pending" },
  ]
}

function updateStep(
  steps: StartupStep[],
  id: string,
  updates: Partial<StartupStep>,
): StartupStep[] {
  return steps.map((s) => (s.id === id ? { ...s, ...updates } : s))
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
  /** Startup progress steps (shown on the initial connection gate) */
  startupSteps: StartupStep[]
  /** Detailed health info */
  backendRunning: boolean
  ollamaRunning: boolean
  hasExternalServices: boolean
  /** Number of reconnection attempts (0 = connected) */
  reconnectAttempt: number
}

export interface ConnectionMonitorResult extends ConnectionState {
  /** Re-run the initial gate check (useful for retry buttons). */
  recheck: () => Promise<void>
}

/* ── Hook ──────────────────────────────────────────────── */
export function useConnectionMonitor(): ConnectionMonitorResult {
  const [checked, setChecked] = useState(false)
  const [ok, setOk] = useState(false)
  const [initialChecking, setInitialChecking] = useState(true)
  const [liveChecking, setLiveChecking] = useState(false)
  const [error, setError] = useState("")
  const [startupSteps, setStartupSteps] = useState<StartupStep[]>(createInitialSteps)
  const [backendRunning, setBackendRunning] = useState(false)
  const [ollamaRunning, setOllamaRunning] = useState(false)
  const [hasExternalServices, setHasExternalServices] = useState(false)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)

  const okRef = useRef(false)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const destroyedRef = useRef(false)
  const pollCountRef = useRef(0)
  const recheckInFlightRef = useRef(false)

  /* ── Helper to run a single check step ─────────────────── */
  const runStep = useCallback(async (steps: StartupStep[], id: string) => {
    // Mark step as in-progress
    setStartupSteps(updateStep(steps, id, { status: "in-progress" }))

    if (id === "backend") {
      const result = await checkBackendConnection(10_000)
      return { ok: result.ok, steps: updateStep(steps, id, { status: result.ok ? "done" : "error" }) }
    }

    if (id === "database") {
      const httpBase = getWsBaseUrl().replace(/^ws:/, "http:").replace(/^wss:/, "https:")
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 5_000)
        const res = await fetch(`${httpBase}/health/database`, {
          method: "GET",
          signal: controller.signal,
        })
        clearTimeout(timer)
        if (res.ok) {
          const data = await res.json()
          if (data?.connected) {
            return { ok: true, steps: updateStep(steps, id, { status: "done" }) }
          }
          return { ok: true, steps: updateStep(steps, id, { status: "done", message: data?.error || "Connected with warnings" }) }
        }
        return { ok: true, steps: updateStep(steps, id, { status: "done", message: "DB check returned " + res.status }) }
      } catch {
        return { ok: true, steps: updateStep(steps, id, { status: "done", message: "DB check skipped" }) }
      }
    }

    if (id === "config") {
      const httpBase = getWsBaseUrl().replace(/^ws:/, "http:").replace(/^wss:/, "https:")
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 5_000)
        const res = await fetch(`${httpBase}/api/health/detailed`, {
          method: "GET",
          signal: controller.signal,
        })
        clearTimeout(timer)
        if (res.ok) {
          return { ok: true, steps: updateStep(steps, id, { status: "done" }) }
        }
        return { ok: true, steps: updateStep(steps, id, { status: "done", message: "Config check returned " + res.status }) }
      } catch {
        return { ok: true, steps: updateStep(steps, id, { status: "done", message: "Config check skipped" }) }
      }
    }

    if (id === "models") {
      const result = await checkDetailedHealth(10_000)
      setBackendRunning(result.backendRunning)
      setOllamaRunning(result.ollamaRunning)
      setHasExternalServices(result.hasExternalServices)

      if (result.ollamaRunning) {
        return { ok: true, steps: updateStep(steps, id, { status: "done" }) }
      }
      if (result.hasExternalServices) {
        return { ok: true, steps: updateStep(steps, id, { status: "done", message: "Using cloud models" }) }
      }
      return { ok: true, steps: updateStep(steps, id, { status: "done", message: result.ollamaError || "No models configured" }) }
    }

    return { ok: true, steps }
  }, [])

  /* ── Initial multi-step startup sequence ──────────────── */
  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (recheckInFlightRef.current) return
      setInitialChecking(true)

      const steps = createInitialSteps()
      setStartupSteps(steps)

      // Step 1: Backend
      const r1 = await runStep(steps, "backend")
      if (cancelled) return
      if (!r1.ok) {
        setError("Backend server is not responding.")
        setOk(false)
        okRef.current = false
        setBackendRunning(false)
        setStartupSteps(r1.steps)
        setInitialChecking(false)
        setChecked(true)
        return
      }
      setStartupSteps(r1.steps)

      // Step 2: Database
      const r2 = await runStep(r1.steps, "database")
      if (cancelled) return
      setStartupSteps(r2.steps)

      // Step 3: Configuration
      const r3 = await runStep(r2.steps, "config")
      if (cancelled) return
      setStartupSteps(r3.steps)

      // Step 4: Models
      const r4 = await runStep(r3.steps, "models")
      if (cancelled) return
      setStartupSteps(r4.steps)

      // Step 5: Ready
      const readySteps = updateStep(r4.steps, "ready", { status: "done" })
      setStartupSteps(readySteps)
      setOk(true)
      okRef.current = true
      setError("")
      setInitialChecking(false)
      setChecked(true)
    }
    run()
    return () => { cancelled = true; destroyedRef.current = true }
    // Intentionally run only once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* ── Live monitor (starts after initial gate passes) ─── */
  useEffect(() => {
    if (!checked || !ok) return

    const intervalMs = getIntervalMs()
    const wsBase = getWsBaseUrl()

    let ws: WebSocket | null = null
    let usePolling = false

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
            setReconnectAttempt((prev) => prev + 1)
            // Exponential backoff for reconnection
            pollCountRef.current++
            const backoff = Math.min(2000 * Math.pow(2, pollCountRef.current), 30000)
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
            reconnectTimerRef.current = setTimeout(() => {
              if (!destroyedRef.current) {
                usePolling = false
                startWs() // Try WebSocket again
              }
            }, backoff)
          } else {
            setError("")
            setReconnectAttempt(0)
            pollCountRef.current = 0
          }
        }
        setLiveChecking(false)
      }
      // Immediate first check
      check()
      timerRef.current = setInterval(check, intervalMs)
    }

    /* ── WebSocket with 5-second connection timeout ────── */
    const startWs = () => {
      try {
        ws = new WebSocket(`${wsBase}/ws`)
        wsRef.current = ws

        // 5-second connection timeout
        const connTimeout = setTimeout(() => {
          if (ws?.readyState !== WebSocket.OPEN) {
            ws?.close()
            if (!usePolling) {
              usePolling = true
              startPolling()
            }
          }
        }, 5000)

        ws.onopen = () => {
          clearTimeout(connTimeout)
          if (destroyedRef.current) return
          setOk(true)
          okRef.current = true
          setError("")
          setLiveChecking(false)
          setReconnectAttempt(0)
          pollCountRef.current = 0

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
          if (!usePolling) {
            usePolling = true
            startPolling()
          }
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
        if (!usePolling) {
          usePolling = true
          startPolling()
        }
      }
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
  }, [checked, ok])

  /* ── Public retry ─────────────────────────────────────── */
  const recheck = useCallback(async () => {
    if (recheckInFlightRef.current) return
    recheckInFlightRef.current = true

    // Clean up live monitor
    if (timerRef.current) clearInterval(timerRef.current)
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    if (wsRef.current) {
      const w = wsRef.current
      w.onopen = null
      w.onmessage = null
      w.onerror = null
      w.onclose = null
      if (w.readyState === WebSocket.OPEN || w.readyState === WebSocket.CONNECTING) {
        w.close()
      }
      wsRef.current = null
    }
    pollCountRef.current = 0
    setReconnectAttempt(0)

    setInitialChecking(true)
    setChecked(false)
    setError("")
    setOk(false)
    okRef.current = false

    const steps = createInitialSteps()
    setStartupSteps(steps)

    // Run full startup sequence again
    const r1 = await runStep(steps, "backend")
    if (destroyedRef.current) { recheckInFlightRef.current = false; return }
    if (!r1.ok) {
      setError("Backend server is not responding.")
      setOk(false)
      okRef.current = false
      setBackendRunning(false)
      setStartupSteps(r1.steps)
      setInitialChecking(false)
      setChecked(true)
      recheckInFlightRef.current = false
      return
    }
    setStartupSteps(r1.steps)

    const r2 = await runStep(r1.steps, "database")
    if (destroyedRef.current) { recheckInFlightRef.current = false; return }
    setStartupSteps(r2.steps)

    const r3 = await runStep(r2.steps, "config")
    if (destroyedRef.current) { recheckInFlightRef.current = false; return }
    setStartupSteps(r3.steps)

    const r4 = await runStep(r3.steps, "models")
    if (destroyedRef.current) { recheckInFlightRef.current = false; return }
    setStartupSteps(r4.steps)

    const readySteps = updateStep(r4.steps, "ready", { status: "done" })
    setStartupSteps(readySteps)
    setOk(true)
    okRef.current = true
    setError("")
    setInitialChecking(false)
    setChecked(true)
    recheckInFlightRef.current = false
  }, [runStep])

  return {
    checked,
    ok,
    initialChecking,
    liveChecking,
    error,
    startupSteps,
    backendRunning,
    ollamaRunning,
    hasExternalServices,
    reconnectAttempt,
    recheck,
  }
}
