/**
 * useConnectionMonitor.ts – Persistent live connection monitor (React Native).
 *
 * Behaviour:
 *   1. Performs an initial HTTP GET /healthz gate check.
 *   2. After passing the gate, opens a WebSocket to ws://HOST/ws
 *      and exchanges ping/pong every N seconds.
 *   3. If the WebSocket fails, falls back to HTTP polling every N seconds.
 *   4. Exposes states so the app can show a full‑screen gate on first load
 *      and a floating toast when the connection drops mid‑session.
 */

import { useEffect, useRef, useState } from "react"
import { checkBackendConnection } from "../api/client"

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

  const okRef = useRef(false)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const destroyedRef = useRef(false)

  /* ── Initial gate check ─────────────────────────────── */
  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setInitialChecking(true)
      const result = await checkBackendConnection()
      if (cancelled) return
      setOk(result.ok)
      okRef.current = result.ok
      if (!result.ok) setError(result.error || "Unable to reach server.")
      setInitialChecking(false)
      setChecked(true)
    }
    run()
    return () => { cancelled = true; destroyedRef.current = true }
  }, [])

  /* ── Live monitor (starts after initial gate passes) ─── */
  useEffect(() => {
    if (!checked || !ok) return

    const intervalMs = getIntervalMs()
    const wsBase = getWsBaseUrl()

    let ws: WebSocket | null = null
    let usePolling = false

    const startPolling = () => {
      if (destroyedRef.current) return
      if (timerRef.current) clearInterval(timerRef.current)
      const check = async () => {
        if (destroyedRef.current) return
        setLiveChecking(true)
        const result = await checkBackendConnection()
        if (destroyedRef.current) return
        if (result.ok !== okRef.current) {
          setOk(result.ok)
          okRef.current = result.ok
          if (!result.ok) setError(result.error || "Connection lost")
          else setError("")
        }
        setLiveChecking(false)
      }
      check()
      timerRef.current = setInterval(check, intervalMs)
    }

    const startWs = () => {
      try {
        ws = new WebSocket(`${wsBase}/ws`)
        wsRef.current = ws

        ws.onopen = () => {
          if (destroyedRef.current) return
          setOk(true)
          okRef.current = true
          setError("")
          setLiveChecking(false)
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
          if (destroyedRef.current) return
          ws?.close()
          usePolling = true
          startPolling()
        }

        ws.onclose = () => {
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

    startWs()

    return () => {
      destroyedRef.current = true
      if (timerRef.current) clearInterval(timerRef.current)
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
  const recheck = async () => {
    setInitialChecking(true)
    setChecked(false)
    setError("")
    const result = await checkBackendConnection()
    if (destroyedRef.current) return
    setOk(result.ok)
    okRef.current = result.ok
    if (!result.ok) setError(result.error || "Unable to reach server.")
    setInitialChecking(false)
    setChecked(true)
  }

  return { checked, ok, initialChecking, liveChecking, error, recheck }
}
