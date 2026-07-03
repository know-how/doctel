import React, { useEffect, useRef, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, KeyboardAvoidingView, Platform, ActivityIndicator, useWindowDimensions } from "react-native"
import { Audio } from "expo-av"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  chatWithDocument,
  getDocumentPrompts,
  getUserHistory,
  getSummaryHistory,
  getDocumentAnalysis,
  transcribeAudio,
} from "../api/client"
import { DocumentAnalysisResponse } from "../types/api"
import { RobotSearching } from "../components/RobotSearching"
import { UserIcon } from "../components/UserIcon"
import { useModel } from "../context/ModelContext"

type MobMsgStatus = "sending" | "waiting" | "success" | "error"

interface MobileMessage {
  id: string
  question: string
  answer: string
  status: MobMsgStatus
  sources: Array<{ chunk_id: string }>
}

export function ChatScreen({ documentId }: { documentId: string }) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768
  const maxBubbleWidth = isTablet ? "70%" : "84%"
  const { selectedModel, setSelectedModel, availableModels, modelCapabilities, loading: loadingModels } = useModel()

  const [messages, setMessages] = useState<MobileMessage[]>([])
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null)
  const [loadingAnalysis, setLoadingAnalysis] = useState(true)
  const [history, setHistory] = useState<any[]>([])
  const [summaryHistory, setSummaryHistory] = useState<any[]>([])
  const [prompts, setPrompts] = useState<string[]>(["Summarize this document", "What are key insights?", "Identify risks"])
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const recordingRef = useRef<Audio.Recording | null>(null)
  const scrollRef = useRef<ScrollView>(null)

  useEffect(() => {
    if (!documentId) { setError("No document selected"); setLoadingAnalysis(false); return }
    loadInitialData()
  }, [documentId])

  const loadInitialData = async () => {
    try {
      setLoadingAnalysis(true)
      const [analysisData, historyData, summaryData, promptsData] = await Promise.all([
        getDocumentAnalysis(documentId), getUserHistory(), getSummaryHistory(), getDocumentPrompts(documentId),
      ])
      setAnalysis(analysisData)
      setHistory((historyData as any)?.history || historyData || [])
      setSummaryHistory((summaryData as any)?.history || summaryData || [])
      if ((promptsData as any)?.suggested_prompts?.length) setPrompts((promptsData as any).suggested_prompts)
      else if (promptsData?.prompts?.length) setPrompts(promptsData.prompts)
    } catch (err) {
      setError("Failed to load analysis")
    } finally {
      setLoadingAnalysis(false)
    }
  }

  const handleAsk = async (text: string) => {
    if (!text.trim()) return
    try {
      setLoading(true)
      setError("")
      const msgId = Date.now().toString()
      const optimisticMsg: MobileMessage = { id: msgId, question: text, answer: "", status: "waiting", sources: [] }
      setMessages((prev) => [...prev, optimisticMsg])
      setQuestion("")
      try {
        const response = await chatWithDocument(documentId, { question: text, model: selectedModel || undefined } as any) as any
        setMessages((prev) => prev.map((msg) => msg.id === msgId ? { ...msg, answer: response.answer || "No response", sources: response.sources || response.citations || [], status: "success" } : msg))
      } catch (chatErr: any) {
        setMessages((prev) => prev.map((msg) => msg.id === msgId ? { ...msg, status: "error", answer: chatErr?.message || "Failed to get response" } : msg))
        setError(chatErr?.message || "Failed to send message")
      }
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = async (msg: MobileMessage) => {
    setMessages((prev) => prev.filter((m) => m.id !== msg.id))
    await handleAsk(msg.question)
  }

  const startRecording = async () => {
    try { const { status } = await Audio.requestPermissionsAsync(); if (status !== "granted") return; await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true }); const recording = new Audio.Recording(); await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY); await recording.startAsync(); recordingRef.current = recording; setIsRecording(true) }
    catch { setIsRecording(false) }
  }

  const stopRecording = async () => {
    try {
      const recording = recordingRef.current; if (!recording) return; await recording.stopAndUnloadAsync(); const uri = recording.getURI() || ""; setIsRecording(false); setIsTranscribing(true)
      try { const result = await transcribeAudio(uri, "recording.m4a", "audio/m4a"); if (result.text?.trim()) setQuestion(result.text.trim()) } catch {} finally { setIsTranscribing(false) }
    } catch { setIsRecording(false) }
  }

  const toggleRecording = () => { if (isRecording) stopRecording(); else startRecording() }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1, backgroundColor: c.bg }} keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}>
      <View style={{ flex: 1, paddingHorizontal: t.spacing.md, paddingTop: t.spacing.md, paddingBottom: t.spacing.xs }}>
        <View style={{ marginBottom: t.spacing.sm }}>
          <Text style={{ fontSize: 18, fontWeight: "800", color: c.text, letterSpacing: -0.3 }}>AI Copilot</Text>
          <Text style={{ fontSize: 12, color: c.textMuted, marginTop: 2 }}>Ask questions about your document</Text>
          {!loadingModels && availableModels.length > 0 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: t.spacing.sm }}>
              {availableModels.map((m, i) => {
                const caps = modelCapabilities[m] || []
                const icons = caps.slice(0, 3).map((cap: string) => ({ reasoning: "🧠", vision: "👁️", audio: "🎤", code: "💻", fast: "⚡", large: "🐘", text: "💬", embedding: "📊" })[cap] || "").filter(Boolean).join(" ")
                return (
                  <Pressable key={`cmodel-${i}`} onPress={() => setSelectedModel(m)} style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: t.radii.lg, marginRight: 6, backgroundColor: m === selectedModel ? c.primary : c.surface }}>
                    <Text style={{ fontSize: 11, color: m === selectedModel ? "#FFF" : c.textSecondary, fontWeight: "600" }}>{m}</Text>
                    {icons ? <Text style={{ fontSize: 9, color: m === selectedModel ? "#FFD" : c.textMuted, marginTop: 1, textAlign: "center" }}>{icons}</Text> : null}
                  </Pressable>
                )
              })}
            </ScrollView>
          )}
          {loadingModels && <ActivityIndicator size="small" color={c.primary} style={{ marginTop: 6 }} />}
        </View>

        {error ? (
          <View style={{ padding: 10, borderRadius: t.radii.md, backgroundColor: c.error + "14", borderWidth: 1, borderColor: c.error + "28", marginBottom: 10 }}>
            <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
          </View>
        ) : null}

        <ScrollView ref={scrollRef} style={{ flex: 1, marginBottom: t.spacing.sm }} onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })} showsVerticalScrollIndicator={false}>
          {loadingAnalysis && <Text style={{ color: c.textMuted, marginBottom: t.spacing.sm, fontSize: 13 }}>Loading analysis…</Text>}

          {messages.length === 0 && !loadingAnalysis && (
            <View style={{ alignItems: "center", paddingVertical: 40, gap: 10 }}>
              <Text style={{ fontSize: 36 }}>✦</Text>
              <Text style={{ fontSize: 15, fontWeight: "700", color: c.textSecondary }}>Ask me anything</Text>
              <Text style={{ fontSize: 13, color: c.textMuted, textAlign: "center" }}>I'm grounded in your document and will cite sources.</Text>
            </View>
          )}

          {messages.map((msg) => (
            <View key={msg.id} style={{ marginBottom: t.spacing.md }}>
              <View style={{ alignItems: "flex-end", marginBottom: t.spacing.sm }}>
                <View style={{ flexDirection: "row-reverse", alignItems: "flex-end", gap: t.spacing.sm, maxWidth: maxBubbleWidth }}>
                  <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: c.primary, alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <UserIcon />
                  </View>
                  <View style={{ backgroundColor: c.primary, paddingHorizontal: 14, paddingVertical: 10, borderRadius: t.radii.lg, borderBottomRightRadius: 4, flex: 1 }}>
                    <Text style={{ color: "#FFFFFF", fontSize: 14, lineHeight: 20 }}>{msg.question}</Text>
                  </View>
                </View>
              </View>

              {msg.status === "waiting" ? (
                <View style={{ alignItems: "flex-start", marginLeft: 4 }}><RobotSearching /></View>
              ) : msg.status === "error" ? (
                <View style={{ alignItems: "flex-start" }}>
                  <View style={{ flexDirection: "row", alignItems: "flex-start", gap: t.spacing.sm, maxWidth: maxBubbleWidth }}>
                    <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: c.error + "18", borderWidth: 1, borderColor: c.error + "30", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <Text style={{ fontSize: 12 }}>⚠️</Text>
                    </View>
                    <View style={{ backgroundColor: c.error + "10", borderWidth: 1, borderColor: c.error + "20", paddingHorizontal: 14, paddingVertical: 10, borderRadius: 4, borderBottomLeftRadius: t.radii.lg, borderTopRightRadius: t.radii.lg, borderBottomRightRadius: t.radii.lg, flex: 1, gap: t.spacing.sm }}>
                      <Text style={{ color: c.error, fontSize: 14, lineHeight: 20 }}>{msg.answer || "Failed to get a response."}</Text>
                      <Pressable onPress={() => handleRetry(msg)} style={{ backgroundColor: c.error + "18", borderWidth: 1, borderColor: c.error + "30", paddingVertical: 6, paddingHorizontal: 12, borderRadius: t.radii.sm, alignSelf: "flex-start" }}>
                        <Text style={{ color: c.error, fontSize: 12, fontWeight: "600" }}>↩ Retry</Text>
                      </Pressable>
                    </View>
                  </View>
                </View>
              ) : (
                <View style={{ alignItems: "flex-start" }}>
                  <View style={{ flexDirection: "row", alignItems: "flex-start", gap: t.spacing.sm, maxWidth: maxBubbleWidth }}>
                    <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                      <Text style={{ color: c.textSecondary, fontSize: 10, fontWeight: "700" }}>AI</Text>
                    </View>
                    <View style={{ backgroundColor: c.cardBg, borderWidth: 1, borderColor: c.border, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 4, borderBottomLeftRadius: t.radii.lg, borderTopRightRadius: t.radii.lg, borderBottomRightRadius: t.radii.lg, flex: 1, gap: t.spacing.sm }}>
                      <Text style={{ color: c.text, fontSize: 14, lineHeight: 22 }}>{msg.answer}</Text>
                      {msg.sources.length > 0 && (
                        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 5, marginTop: 4 }}>
                          {msg.sources.slice(0, 3).map((src) => (
                            <View key={src.chunk_id} style={{ paddingHorizontal: t.spacing.sm, paddingVertical: 3, borderRadius: t.radii.sm, backgroundColor: c.primary + "14", borderWidth: 1, borderColor: c.primary + "28" }}>
                              <Text style={{ color: c.primary, fontSize: 10 }}>📄 chunk {src.chunk_id.slice(0, 8)}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                    </View>
                  </View>
                </View>
              )}
            </View>
          ))}
        </ScrollView>

        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {prompts.slice(0, 4).map((p) => (
            <Pressable key={p} onPress={() => handleAsk(p)} style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: t.radii.md, backgroundColor: c.warning + "10", borderWidth: 1, borderColor: c.warning + "28" }}>
              <Text style={{ color: c.warning, fontSize: 12 }}>{p}</Text>
            </Pressable>
          ))}
        </View>

        <View style={{ flexDirection: "row", gap: t.spacing.sm, backgroundColor: c.cardBg, borderRadius: t.radii.lg, borderWidth: 1, borderColor: c.border, padding: t.spacing.xs, alignItems: "center" }}>
          <TextInput value={question} onChangeText={setQuestion} placeholder={isTranscribing ? "Transcribing voice..." : "Ask about this document…"} placeholderTextColor={c.textMuted} editable={!loading && !isTranscribing} style={{ flex: 1, borderWidth: 0, borderRadius: t.radii.md, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: "transparent", color: c.text, fontSize: 14, opacity: loading || isTranscribing ? 0.6 : 1 }} />
          <Pressable onPress={toggleRecording} disabled={isTranscribing} style={{ width: 40, height: 40, borderRadius: t.radii.md, alignItems: "center", justifyContent: "center", backgroundColor: isRecording ? "#EF4444" : c.primary, opacity: isTranscribing ? 0.5 : 1 }}>
            <Text style={{ color: "#FFFFFF", fontSize: 16 }}>{isRecording ? "⏹" : "🎙"}</Text>
          </Pressable>
          <Pressable onPress={() => handleAsk(question)} style={{ width: 40, height: 40, backgroundColor: c.primary, borderRadius: t.radii.md, alignItems: "center", justifyContent: "center", opacity: loading ? 0.6 : 1 }} disabled={loading}>
            <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 14 }}>{loading ? "…" : "➜"}</Text>
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  )
}
