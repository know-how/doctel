import React, { useEffect, useRef, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, KeyboardAvoidingView, Platform, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { chatWithDocument, chatGlobally, getMyDocuments } from "../api/client"
import { useModel } from "../context/ModelContext"
import { MyDocument } from "../types/api"

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  citations: string[]
  citationsFull?: { filename: string; chunk_index: number; text: string }[]
}

const suggestedPrompts = [
  "Summarize selected documents",
  "What are the key insights?",
  "Find risks and issues",
  "Compare the selected documents",
  "Extract action items",
]

interface AnalyzeChatScreenProps {
  documentId?: string
}

export function AnalyzeChatScreen({ documentId }: AnalyzeChatScreenProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [documents, setDocuments] = useState<MyDocument[]>([])
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [loadingDocs, setLoadingDocs] = useState(true)
  const scrollRef = useRef<ScrollView>(null)
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768
  const { selectedModel, setSelectedModel, availableModels, modelCapabilities, loading: loadingModels } = useModel()

  useEffect(() => {
    loadDocuments()
  }, [])

  useEffect(() => {
    if (documentId && documents.length > 0) {
      setSelectedDocs(new Set([documentId]))
    }
  }, [documentId, documents])

  const loadDocuments = async () => {
    try {
      setLoadingDocs(true)
      const res = await getMyDocuments()
      setDocuments(res?.documents || [])
    } catch {
      setError("Failed to load documents")
    } finally {
      setLoadingDocs(false)
    }
  }

  const toggleDoc = (id: string) => {
    setSelectedDocs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleSend = async (text?: string) => {
    const q = (text || question).trim()
    if (!q) return
    try {
      setLoading(true)
      setError("")
      const msgId = Date.now().toString()
      const userMsg: ChatMessage = { id: msgId, role: "user", content: q, citations: [] }
      setMessages((prev) => [...prev, userMsg])
      setQuestion("")

      let response: any
      const selectedDocArr = Array.from(selectedDocs)
      if (selectedDocArr.length === 1) {
        response = await chatWithDocument(selectedDocArr[0], { question: q, model: selectedModel || undefined })
      } else {
        response = await chatGlobally({ question: q, model: selectedModel || undefined })
      }

      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response?.answer || "No response",
        citations: response?.citations?.map((cit: any) => cit.filename) || [],
        citationsFull: response?.citations || [],
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch (err: any) {
      setError(err.message || "Chat request failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={90}
    >
      {loadingDocs ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <Text style={{ color: c.textMuted, fontSize: 14 }}>Loading documents...</Text>
        </View>
      ) : (
        <>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={{ maxHeight: 52, paddingHorizontal: t.spacing.md, paddingVertical: 8, backgroundColor: c.bg, borderBottomWidth: 1, borderBottomColor: c.border }}
          >
            {documents.map((doc) => (
              <Pressable
                key={doc.id}
                onPress={() => toggleDoc(doc.id)}
                style={{
                  paddingHorizontal: 12,
                  paddingVertical: 6,
                  borderRadius: 20,
                  backgroundColor: selectedDocs.has(doc.id) ? c.primary : c.bgSecondary,
                  marginRight: 8,
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <Text style={{ fontSize: 12, color: selectedDocs.has(doc.id) ? "#FFFFFF" : c.text }}>
                  {selectedDocs.has(doc.id) ? "✓ " : "○ "}{doc.filename.length > 20 ? doc.filename.slice(0, 18) + "..." : doc.filename}
                </Text>
              </Pressable>
            ))}
          </ScrollView>

          <ScrollView
            ref={scrollRef}
            style={{ flex: 1, paddingHorizontal: isTablet ? t.spacing.lg : t.spacing.md }}
            contentContainerStyle={{ paddingVertical: 12, paddingBottom: 16 }}
            onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          >
            {error ? (
              <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: 10, marginBottom: 10, borderWidth: 1, borderColor: c.error + "28" }}>
                <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
              </View>
            ) : null}

            {messages.length === 0 && (
              <View style={{ alignItems: "center", paddingVertical: 40 }}>
                <Text style={{ fontSize: 40, marginBottom: 12 }}>💬</Text>
                <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: 4 }}>
                  Start a conversation
                </Text>
                <Text style={{ fontSize: 13, color: c.textMuted, textAlign: "center" }}>
                  Select documents above and ask a question
                </Text>
              </View>
            )}

            {messages.map((msg) => (
              <View key={msg.id} style={{ marginBottom: 12 }}>
                <View
                  style={{
                    alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                    backgroundColor: msg.role === "user" ? c.primary : c.cardBg,
                    borderRadius: t.radii.md,
                    padding: 12,
                    maxWidth: isTablet ? "70%" : "85%",
                    borderWidth: 1,
                    borderColor: msg.role === "user" ? c.primary : c.border,
                  }}
                >
                  <Text style={{ fontSize: 14, color: msg.role === "user" ? "#FFFFFF" : c.text, lineHeight: 20 }}>
                    {msg.content}
                  </Text>
                </View>
                {msg.role === "assistant" && msg.citationsFull && msg.citationsFull.length > 0 && (
                  <View style={{ marginTop: 6, marginLeft: 4 }}>
                    <Text style={{ fontSize: 11, fontWeight: "600", color: c.textMuted, marginBottom: 4 }}>
                      Sources:
                    </Text>
                    {msg.citationsFull.map((cite, i) => (
                      <View key={i} style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, padding: 8, marginBottom: 4 }}>
                        <Text style={{ fontSize: 11, fontWeight: "600", color: c.primary }}>{cite.filename}</Text>
                        <Text style={{ fontSize: 11, color: c.textMuted }}>{cite.text}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            ))}

            {loading && (
              <View style={{ flexDirection: "row", padding: 12, gap: 4 }}>
                {[0, 1, 2].map((i) => (
                  <View
                    key={i}
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: c.primary,
                      opacity: 0.3 + (i * 0.3),
                    }}
                  />
                ))}
                <Text style={{ marginLeft: 8, fontSize: 12, color: c.textMuted }}>AI is typing...</Text>
              </View>
            )}
          </ScrollView>

          <View style={{ paddingHorizontal: isTablet ? t.spacing.lg : t.spacing.md, paddingVertical: 4, backgroundColor: c.cardBg, borderTopWidth: 1, borderTopColor: c.border }}>
            {!loadingModels && availableModels.length > 0 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8, marginTop: 4 }}>
                {availableModels.map((m, i) => {
                  const caps = modelCapabilities[m] || []
                  const icons = caps.slice(0, 3).map((cap: string) => ({ reasoning: "🧠", vision: "👁️", audio: "🎤", code: "💻", fast: "⚡", large: "🐘", text: "💬", embedding: "📊" })[cap] || "").filter(Boolean).join(" ")
                  return (
                    <Pressable
                      key={`amodel-${i}`}
                      onPress={() => setSelectedModel(m)}
                      style={{
                        paddingHorizontal: 10,
                        paddingVertical: 5,
                        borderRadius: t.radii.lg,
                        marginRight: 6,
                        backgroundColor: m === selectedModel ? c.primary : c.surface,
                        borderWidth: 1,
                        borderColor: m === selectedModel ? c.primary : c.border,
                      }}
                    >
                      <Text style={{ fontSize: 11, color: m === selectedModel ? "#FFF" : c.textSecondary, fontWeight: "600" }}>
                        {m.length > 25 ? m.slice(0, 23) + "..." : m}
                      </Text>
                      {icons ? <Text style={{ fontSize: 9, color: m === selectedModel ? "#FFD" : c.textMuted, marginTop: 1, textAlign: "center" }}>{icons}</Text> : null}
                    </Pressable>
                  )
                })}
              </ScrollView>
            )}
            {loadingModels && <ActivityIndicator size="small" color={c.primary} style={{ marginBottom: 8 }} />}

            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
              {suggestedPrompts.map((prompt, i) => (
                <Pressable
                  key={i}
                  onPress={() => handleSend(prompt)}
                  style={{
                    backgroundColor: c.primary + "14",
                    borderRadius: 20,
                    paddingHorizontal: 12,
                    paddingVertical: 6,
                    marginRight: 8,
                    borderWidth: 1,
                    borderColor: c.border,
                  }}
                >
                  <Text style={{ fontSize: 12, color: c.primary, fontWeight: "500" }}>{prompt}</Text>
                </Pressable>
              ))}
            </ScrollView>

            <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
              <TextInput
                placeholder="Ask about documents..."
                value={question}
                onChangeText={setQuestion}
                placeholderTextColor={c.textMuted}
                multiline
                style={{
                  flex: 1,
                  backgroundColor: c.cardBg,
                  borderRadius: t.radii.sm,
                  padding: 12,
                  borderWidth: 1,
                  borderColor: c.border,
                  color: c.text,
                  maxHeight: 80,
                }}
              />
              <Pressable
                onPress={() => handleSend()}
                disabled={loading || !question.trim()}
                style={{
                  backgroundColor: loading || !question.trim() ? c.textMuted : c.primary,
                  borderRadius: t.radii.sm,
                  paddingHorizontal: 18,
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <Text style={{ fontSize: 20 }}>{loading ? "⏳" : "➤"}</Text>
              </Pressable>
            </View>
          </View>
        </>
      )}
    </KeyboardAvoidingView>
  )
}
