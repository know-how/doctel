import React, { useEffect, useState } from "react"
import { View, Text, FlatList, Pressable, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getChatSessions } from "../api/client"

interface ChatSession {
  session_id: string
  title?: string
  started_at: string
  document_id?: string
  message_count?: number
}

interface ChatSessionsScreenProps {
  onSelectSession: (sessionId: string) => void
  onCreateNewSession: () => void
}

export function ChatSessionsScreen({ onSelectSession, onCreateNewSession }: ChatSessionsScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    const loadSessions = async () => {
      try { setLoading(true); setError(""); const res = await getChatSessions(); setSessions(res.sessions || []) }
      catch (err: any) { setError(err.message || "Failed to load chat sessions") }
      finally { setLoading(false) }
    }
    loadSessions()
  }, [])

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading sessions...</Text>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm, backgroundColor: c.bg }}>
      <Text style={{ fontSize: 20, fontWeight: "700", color: c.text, marginBottom: t.spacing.md }}>💬 Chat Sessions</Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <Pressable onPress={onCreateNewSession} style={{ backgroundColor: c.primary, borderRadius: t.radii.md, paddingVertical: t.spacing.sm + 2, alignItems: "center", marginBottom: t.spacing.md }}>
        <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 14 }}>+ New Chat Session</Text>
      </Pressable>

      <FlatList
        data={sessions}
        keyExtractor={(item) => item.session_id}
        numColumns={isTablet ? 2 : 1}
        renderItem={({ item }) => (
          <Pressable onPress={() => onSelectSession(item.session_id)} style={{ backgroundColor: c.cardBg, borderWidth: 1, borderColor: c.border, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, marginHorizontal: isTablet ? t.spacing.xs : 0 }}>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: 4 }}>{item.title || "Untitled Chat"}</Text>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ fontSize: 12, color: c.textMuted }}>{new Date(item.started_at).toLocaleDateString()}</Text>
              {item.message_count && (
                <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, paddingHorizontal: t.spacing.sm, paddingVertical: 4 }}>
                  <Text style={{ fontSize: 11, color: c.primary, fontWeight: "600" }}>{item.message_count} msg{item.message_count !== 1 ? "s" : ""}</Text>
                </View>
              )}
            </View>
          </Pressable>
        )}
        scrollEnabled={true}
        ListEmptyComponent={
          <View style={{ alignItems: "center", paddingVertical: 40 }}>
            <Text style={{ color: c.textMuted, fontSize: 14, marginBottom: t.spacing.sm }}>No chat sessions yet</Text>
            <Pressable onPress={onCreateNewSession} style={{ backgroundColor: c.primary, borderRadius: t.radii.sm, paddingHorizontal: t.spacing.lg, paddingVertical: t.spacing.sm }}>
              <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 12 }}>Create One</Text>
            </Pressable>
          </View>
        }
      />
    </View>
  )
}
