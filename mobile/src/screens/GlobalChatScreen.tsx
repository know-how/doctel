import React, { useEffect, useRef, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, KeyboardAvoidingView, Platform, ActivityIndicator, useWindowDimensions } from "react-native"
import { Audio } from "expo-av"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { chatGlobally, setChatSessionModel, createChatSession, transcribeAudio } from "../api/client"
import { useModel } from "../context/ModelContext"
import { RobotSearching } from "../components/RobotSearching"
import { UserIcon } from "../components/UserIcon"
import { ModelDropdown } from "../components/ModelDropdown"
import { ReasoningBlock } from "../components/ReasoningBlock"

interface MobileMessage {
  id: string
  question: string
  answer: string
  reasoning?: string
  sources: any
  status: "sending" | "waiting" | "success" | "error"
  model?: string
}

interface GlobalChatScreenProps {
  onBack?: () => void
}

export function GlobalChatScreen({ onBack }: GlobalChatScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState<MobileMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const { availableModels, selectedModel, setSelectedModel, loading: modelsLoading, modelCapabilities, modelLabels, v2Providers } = useModel()
  const [sessionId, setSessionId] = useState<string>("")
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const recordingRef = useRef<Audio.Recording | null>(null)
  const scrollRef = useRef<ScrollView>(null)

  useEffect(() => {
    const createSession = async () => {
      try { const session = await createChatSession(undefined, "global"); setSessionId(session.session_id || "") } catch {}
    }
    createSession()
  }, [])

  const handleAsk = async (q: string) => {
    if (!q.trim() || loading) return
    const ts = Date.now()
    const msgId = `msg_${ts}`
    setQuestion("")
    setError("")
    setLoading(true)
    setMessages((prev) => [...prev, { id: msgId, question: q, answer: "", sources: [], status: "waiting", model: selectedModel }])
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50)
    try {
      if (sessionId && selectedModel) { try { await setChatSessionModel(sessionId, selectedModel) } catch {} }
      const res = (await chatGlobally({ question: q, model: selectedModel, session_id: sessionId })) as any
      setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, answer: res.answer, reasoning: res.reasoning || undefined, sources: res.sources || res.citations || [], status: "success" } : m))
    } catch (e: any) {
      setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, answer: e.message || "Failed to get answer", status: "error" } : m))
    } finally {
      setLoading(false)
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80)
    }
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
    <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }} keyboardVerticalOffset={Platform.OS === "ios" ? 50 : 0}>
      <View style={{ flex: 1, backgroundColor: c.bg }}>
        <View style={{ paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm, borderBottomWidth: 1, borderBottomColor: c.border, backgroundColor: c.cardBg }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.sm }}>
            <Text style={{ fontSize: 18, fontWeight: "700", color: c.text }}>🌍 Global Chat</Text>
            {onBack && (<Pressable onPress={onBack}><Text style={{ fontSize: 14, color: c.primary }}>← Back</Text></Pressable>)}
          </View>
          <ModelDropdown
            v2Providers={v2Providers}
            availableModels={availableModels}
            selectedModel={selectedModel}
            modelCapabilities={modelCapabilities}
            modelLabels={modelLabels}
            loading={modelsLoading}
            onSelect={setSelectedModel}
          />
        </View>

        <ScrollView ref={scrollRef} style={{ flex: 1, paddingHorizontal: t.spacing.sm + 2, paddingVertical: t.spacing.sm }} contentContainerStyle={{ paddingBottom: t.spacing.md }}>
          {error && <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm }}><Text style={{ color: c.error, fontSize: 13 }}>{error}</Text></View>}
          {messages.length === 0 && !loading && (
            <View style={{ alignItems: "center", marginTop: 40 }}><Text style={{ fontSize: 16, color: c.textMuted, textAlign: "center" }}>Start a global conversation across all your documents</Text></View>
          )}
          {messages.map((msg) => (
            <View key={msg.id} style={{ marginBottom: t.spacing.sm }}>
              <View style={{ alignItems: "flex-end" }}>
                <View style={{ backgroundColor: c.primary, borderRadius: t.radii.md, paddingHorizontal: t.spacing.sm, paddingVertical: 10, marginBottom: t.spacing.sm, marginLeft: 24, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
                  <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: "rgba(255,255,255,0.2)", alignItems: "center", justifyContent: "center" }}><UserIcon /></View>
                  <Text style={{ color: "#FFFFFF", fontSize: 14, fontWeight: "500" }}>{msg.question}</Text>
                </View>
              </View>
              <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, paddingHorizontal: t.spacing.sm, paddingVertical: 10, marginRight: 24 }}>
                {msg.status === "waiting" ? (
                  <View style={{ paddingVertical: 4 }}><RobotSearching /></View>
                ) : (
                  <>
                    <Text style={{ color: c.text, fontSize: 14, lineHeight: 20 }}>{msg.answer}</Text>
                    {msg.reasoning && <ReasoningBlock reasoning={msg.reasoning} colors={c} />}
                    {msg.sources && msg.sources.length > 0 && (
                      <View style={{ marginTop: t.spacing.sm }}>
                        <Text style={{ fontSize: 12, color: c.textMuted, fontWeight: "600", marginBottom: 4 }}>Sources:</Text>
                        {msg.sources.map((source, idx) => (<Text key={idx} style={{ fontSize: 11, color: c.primary, marginBottom: 2 }}>• {source.document_name}</Text>))}
                      </View>
                    )}
                  </>
                )}
              </View>
            </View>
          ))}
        </ScrollView>

        <View style={{ paddingHorizontal: t.spacing.sm + 2, paddingVertical: t.spacing.sm, borderTopWidth: 1, borderTopColor: c.border, backgroundColor: c.cardBg }}>
          <View style={{ flexDirection: "row", gap: t.spacing.sm }}>
            <TextInput value={question} onChangeText={setQuestion} placeholder={isTranscribing ? "Transcribing voice..." : "Ask something..."} placeholderTextColor={c.textMuted} multiline editable={!loading && !isTranscribing} style={{ flex: 1, minHeight: 40, maxHeight: 100, backgroundColor: c.inputBg, borderRadius: t.radii.md, paddingHorizontal: t.spacing.sm, paddingVertical: t.spacing.xs, fontSize: 14, color: c.text, borderWidth: 1, borderColor: c.border }} />
            <Pressable onPress={toggleRecording} disabled={isTranscribing} style={{ width: 40, height: 40, borderRadius: t.radii.md, justifyContent: "center", alignItems: "center", backgroundColor: isRecording ? "#EF4444" : c.primary, opacity: isTranscribing ? 0.5 : 1 }}>
              <Text style={{ color: "#FFFFFF", fontSize: 16 }}>{isRecording ? "⏹" : "🎙"}</Text>
            </Pressable>
            <Pressable onPress={() => handleAsk(question)} disabled={loading || !question.trim()} style={{ backgroundColor: loading || !question.trim() ? c.textMuted : c.primary, borderRadius: t.radii.md, justifyContent: "center", alignItems: "center", paddingHorizontal: t.spacing.sm }}>
              {loading ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Text style={{ color: "#FFFFFF", fontWeight: "600" }}>Send</Text>}
            </Pressable>
          </View>
        </View>
      </View>
    </KeyboardAvoidingView>
  )
}
