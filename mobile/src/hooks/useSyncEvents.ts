/**
 * useSyncEvents.ts (React Native) – subscribes to the backend SSE
 * /api/sync/events stream and fires callbacks for logout and training events.
 */
import { useEffect, useRef } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const AUTH_TOKEN_KEY = "docintel_auth_token"

interface SyncEventOptions {
  onLogout?: () => void
  onTrainingComplete?: (data: any) => void
  enabled?: boolean
}

export function useSyncEvents({ onLogout, onTrainingComplete, enabled = true }: SyncEventOptions) {
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!enabled) return

    let active = true
    const controller = new AbortController()
    abortRef.current = controller

    const connect = async () => {
      const token = await AsyncStorage.getItem(AUTH_TOKEN_KEY)
      if (!token || !active) return

      try {
        const res = await fetch(`${BASE_URL}/api/sync/events`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        if (!res.body) return

        const reader = (res.body as any).getReader()
        const decoder = new TextDecoder()
        let buf = ""

        while (active) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines: string[] = buf.split("\n")
          buf = lines.pop() ?? ""
          for (const line of lines) {
            if (!line.startsWith("data:")) continue
            const raw = line.slice(5).trim()
            if (!raw) continue
            try {
              const payload = JSON.parse(raw)
              const event = payload.event as string
              const data = payload.data ?? {}
              if (event === "session.logout") onLogout?.()
              else if (event === "training.complete") onTrainingComplete?.(data)
            } catch {
              // ignore malformed JSON
            }
          }
        }
      } catch (err: any) {
        if (err?.name !== "AbortError" && active) {
          // Reconnect after 5 s on unexpected disconnect
          setTimeout(connect, 5000)
        }
      }
    }

    connect()

    return () => {
      active = false
      controller.abort()
    }
  }, [enabled, onLogout, onTrainingComplete])
}
