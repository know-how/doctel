/**
 * useSyncEvents.ts – React hook that opens a Server-Sent Events connection
 * to /api/sync/events and fires callbacks for key events.
 *
 * Events handled:
 *   session.logout  → onLogout()
 *   training.complete → onTrainingComplete(data)
 *   connected       → internal heartbeat (ignored)
 */
import { useEffect, useRef } from "react"

const BASE_URL =
  (import.meta as any).env.VITE_API_BASE_URL ?? "http://localhost:8000"
const AUTH_TOKEN_KEY = "docintel_auth_token"

interface SyncEventOptions {
  onLogout?: () => void
  onTrainingComplete?: (data: any) => void
  enabled?: boolean
}

export function useSyncEvents({ onLogout, onTrainingComplete, enabled = true }: SyncEventOptions) {
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!enabled) return

    const token = window.localStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return

    // EventSource doesn't support custom headers directly – we pass token as query param
    const url = `${BASE_URL}/api/sync/events?token=${encodeURIComponent(token)}`

    // Some backends accept the token via cookie; we use a simple fetch-based SSE
    // so we can attach the Authorization header
    let aborted = false
    const controller = new AbortController()

    const connect = async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/sync/events`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        if (!res.body) return
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ""

        while (!aborted) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines = buf.split("\n")
          buf = lines.pop() ?? ""
          for (const line of lines) {
            if (!line.startsWith("data:")) continue
            const raw = line.slice(5).trim()
            if (!raw) continue
            try {
              const payload = JSON.parse(raw)
              const event = payload.event as string
              const data = payload.data ?? {}
              if (event === "session.logout") {
                onLogout?.()
              } else if (event === "training.complete") {
                onTrainingComplete?.(data)
              }
            } catch {
              // malformed JSON – ignore
            }
          }
        }
      } catch (err: any) {
        if (err?.name !== "AbortError" && !aborted) {
          // Reconnect after 5 s on unexpected disconnect
          setTimeout(connect, 5000)
        }
      }
    }

    connect()

    return () => {
      aborted = true
      controller.abort()
    }
  }, [enabled, onLogout, onTrainingComplete])
}
