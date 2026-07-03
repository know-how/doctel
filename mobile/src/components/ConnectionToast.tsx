/**
 * ConnectionToast.tsx – Floating toast that shows mid‑session connection
 * drops / restores without blocking the full screen.
 *
 * States (controlled by parent via `connected` + `liveChecking`):
 *   - connected=true, liveChecking=false       → hidden (returns null)
 *   - connected=false, liveChecking=true        → "Reconnecting…" (amber)
 *   - connected=false, liveChecking=false       → "Connection Lost" (red + dismiss)
 *   - toggled false→true (after being false)    → "Connection restored ✓" (2s auto-dismiss)
 */

import React, { useCallback, useEffect, useRef, useState } from "react"
import {
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"

interface ConnectionToastProps {
  connected: boolean
  liveChecking: boolean
}

export default function ConnectionToast({
  connected,
  liveChecking,
}: ConnectionToastProps) {
  const insets = useSafeAreaInsets()
  const translateY = useRef(new Animated.Value(-120)).current
  const [visible, setVisible] = useState(false)
  const [showRestored, setShowRestored] = useState(false)
  const [prevConnected, setPrevConnected] = useState(connected)
  const restoredTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Slide helpers
  const slideIn = useCallback(() => {
    setVisible(true)
    Animated.timing(translateY, {
      toValue: 0,
      duration: 300,
      useNativeDriver: true,
    }).start()
  }, [translateY])

  const slideOut = useCallback(() => {
    Animated.timing(translateY, {
      toValue: -120,
      duration: 250,
      useNativeDriver: true,
    }).start(() => {
      setVisible(false)
      setShowRestored(false)
    })
  }, [translateY])

  // Track connected transitions
  useEffect(() => {
    const wasConnected = prevConnected
    setPrevConnected(connected)

    if (connected && !wasConnected) {
      // Just recovered – show "Restored" for 2 seconds
      setShowRestored(true)
      slideIn()
      if (restoredTimer.current) clearTimeout(restoredTimer.current)
      restoredTimer.current = setTimeout(() => {
        slideOut()
      }, 2000)
    } else if (!connected) {
      // Disconnected
      setShowRestored(false)
      if (restoredTimer.current) clearTimeout(restoredTimer.current)
      slideIn()
    } else {
      // Connected and was already connected – hide
      slideOut()
    }

    return () => {
      if (restoredTimer.current) clearTimeout(restoredTimer.current)
    }
  }, [connected, prevConnected, slideIn, slideOut])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (restoredTimer.current) clearTimeout(restoredTimer.current)
    }
  }, [])

  if (!visible) return null

  // ── Determine appearance ───────────────────────────────
  const isRestored = showRestored && connected
  const isLost = !connected && !liveChecking
  const isReconnecting = !connected && liveChecking

  let bgColor: string
  let textColor: string
  let message: string
  let description: string | null
  let showDismiss: boolean

  if (isRestored) {
    bgColor = "#1A3A2A"
    textColor = "#4ADE80"
    message = "Connection restored ✓"
    description = null
    showDismiss = false
  } else if (isReconnecting) {
    bgColor = "#3A2F1A"
    textColor = "#FBBF24"
    message = "Reconnecting…"
    description = "Attempting to re-establish connection"
    showDismiss = false
  } else {
    // Lost
    bgColor = "#3A1A1A"
    textColor = "#F87171"
    message = "Connection Lost"
    description = "Server is not responding. Retrying automatically…"
    showDismiss = true
  }

  return (
    <Animated.View
      style={[
        styles.container,
        {
          backgroundColor: bgColor,
          top: insets.top + 12,
          transform: [{ translateY }],
        },
      ]}
      pointerEvents="box-none"
    >
      <View style={styles.content}>
        <View style={styles.textWrap}>
          <Text style={[styles.title, { color: textColor }]}>{message}</Text>
          {description && (
            <Text style={styles.description}>{description}</Text>
          )}
        </View>
        {showDismiss && (
          <TouchableOpacity onPress={slideOut} style={styles.dismissBtn}>
            <Text style={styles.dismissText}>Dismiss</Text>
          </TouchableOpacity>
        )}
      </View>
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    left: 16,
    right: 16,
    zIndex: 99999,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 18,
    // Shadow
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  textWrap: {
    flex: 1,
    marginRight: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: "700",
  },
  description: {
    fontSize: 12,
    color: "rgba(255,255,255,0.6)",
    marginTop: 2,
  },
  dismissBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: "rgba(255,255,255,0.12)",
  },
  dismissText: {
    fontSize: 12,
    fontWeight: "600",
    color: "rgba(255,255,255,0.8)",
  },
})
