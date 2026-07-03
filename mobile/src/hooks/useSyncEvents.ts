import { useEffect, useRef } from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const AUTH_TOKEN_KEY = "docintel_auth_token"
const POLL_INTERVAL_MS = 30000

interface SyncEventOptions {
  onLogout?: () => void
  onTrainingComplete?: (data: any) => void
  enabled?: boolean
}

export function useSyncEvents({ onLogout, onTrainingComplete, enabled = true }: SyncEventOptions) {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!enabled) return

    const poll = async () => {
      const token = await AsyncStorage.getItem(AUTH_TOKEN_KEY)
      if (!token) return
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 15000)
        const res = await fetch(`${BASE_URL}/api/sync/poll`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        clearTimeout(timer)
        if (!res.ok) return
        const payload = await res.json()
        const event = payload.event as string
        const data = payload.data ?? {}
        if (event === "session.logout") onLogout?.()
        else if (event === "training.complete") onTrainingComplete?.(data)
      } catch {
      }
    }

    poll()
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [enabled, onLogout, onTrainingComplete])
}
