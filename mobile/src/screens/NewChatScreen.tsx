import React, { useState, useEffect, useRef } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions, Alert, KeyboardAvoidingView, Platform } from "react-native"
import { Audio } from "expo-av"
import * as DocumentPicker from "expo-document-picker"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { chatGlobally, chatGloballyStream, transcribeAudio, askVision, uploadDocument, createChatSession, getChatMessages, setChatSessionModel, getRandomPromptSuggestions } from "../api/client"
import { useModel } from "../context/ModelContext"
import { ChatHeader } from "../components/ChatHeader"
import { WelcomeScreen } from "../components/WelcomeScreen"
import { ChatMessage, Message } from "../components/ChatMessage"
import { ChatInput } from "../components/ChatInput"
import { isCloudModel } from "../utils/modelUtils"

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

const formatTime = (iso?: string) => {
  if (!iso) return ""
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ""
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch { return "" }
}

const formatDate = (iso?: string) => {
  if (!iso) return ""
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ""
    const today = new Date()
    const isToday = d.toDateString() === today.toDateString()
    if (isToday) return formatTime(iso)
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + formatTime(iso)
  } catch { return "" }
}

interface AttachmentInfo {
  uri: string
  name: string
  mimeType: string
  type: "image" | "document" | "audio"
}

const imageMimeTypes = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/jpg", "image/heic", "image/heif"]

interface NewChatScreenProps {
  onOpenDocument?: (documentId: string, filename?: string) => void
}

export function NewChatScreen({ onOpenDocument }: NewChatScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [attachedFile, setAttachedFile] = useState<AttachmentInfo | null>(null)
  const [attachedPreview, setAttachedPreview] = useState<string | null>(null)
  const [promptSuggestions, setPromptSuggestions] = useState<{ id: number; title: string; prompt_text: string; icon: string; category: string }[]>([])
  const [loadingPrompts, setLoadingPrompts] = useState(false)
  const recordingRef = useRef<Audio.Recording | null>(null)
  const scrollRef = useRef<ScrollView>(null)
  const { selectedModel, setSelectedModel, availableModels: models, modelCapabilities, modelLabels, loading: loadingModels, v2Providers, taskDefaults, setModelForTask } = useModel()
  const cloudModel = isCloudModel(selectedModel, v2Providers)

  // Load prompt suggestions
  useEffect(() => {
    const loadPrompts = async () => {
      setLoadingPrompts(true)
      try {
        const response = await getRandomPromptSuggestions(6)
        setPromptSuggestions(response.suggestions)
      } catch {
        setPromptSuggestions([])
      } finally {
        setLoadingPrompts(false)
      }
    }
    loadPrompts()
  }, [])

  // Apply task mapping for chat
  useEffect(() => {
    if (!loadingModels && Object.keys(taskDefaults).length > 0) {
      setModelForTask("chat")
    }
  }, [loadingModels, taskDefaults])

  // Create session on mount
  useEffect(() => {
    const initSession = async () => {
      try {
        const session = await createChatSession(null, "global")
        setSessionId(session.session_id)
      } catch {}
    }
    initSession()
  }, [])

  // Persist model to session
  useEffect(() => {
    if (sessionId && selectedModel) {
      setChatSessionModel(sessionId, selectedModel).catch(() => {})
    }
  }, [sessionId, selectedModel])

  // Scroll to end on new messages
  useEffect(() => {
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50)
  }, [messages])

  const pickAttachment = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          "application/pdf",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "text/plain",
          "image/jpeg",
          "image/png",
          "image/webp",
          "image/gif",
        ],
        copyToCacheDirectory: true,
      })
      if (result.canceled) return
      const asset = result.assets[0]
      const mt = asset.mimeType || "application/octet-stream"
      let ftype: "image" | "document" | "audio" = "document"
      if (imageMimeTypes.includes(mt)) ftype = "image"
      setAttachedFile({
        uri: asset.uri,
        name: asset.name || "file",
        mimeType: mt,
        type: ftype,
      })
      if (ftype === "image") {
        setAttachedPreview(asset.uri)
      } else {
        setAttachedPreview(null)
      }
    } catch {
      Alert.alert("Error", "Failed to pick file")
    }
  }

  const clearAttachment = () => {
    setAttachedFile(null)
    setAttachedPreview(null)
  }

  const startRecording = async () => {
    try {
      const { status } = await Audio.requestPermissionsAsync()
      if (status !== "granted") return
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true })
      const recording = new Audio.Recording()
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY)
      await recording.startAsync()
      recordingRef.current = recording
      setIsRecording(true)
    } catch { setIsRecording(false) }
  }

  const stopRecording = async () => {
    try {
      const recording = recordingRef.current
      if (!recording) return
      await recording.stopAndUnloadAsync()
      const uri = recording.getURI() || ""
      setIsRecording(false)
      setIsTranscribing(true)
      try {
        const result = await transcribeAudio(uri, "recording.m4a", "audio/m4a")
        if (result.text?.trim()) setInput(result.text.trim())
      } catch {} finally { setIsTranscribing(false) }
    } catch { setIsRecording(false) }
  }

  const toggleRecording = () => {
    if (isRecording) stopRecording()
    else startRecording()
  }

  const handleSend = async (text?: string) => {
    const q = (text || input).trim()
    if ((!q && !attachedFile) || loading) return

    const userMsgId = generateId()
    const thinkingId = generateId()
    let content = q || (attachedFile ? `[Attachment: ${attachedFile.name}]` : "")

    const file = attachedFile
    const preview = attachedPreview
    setInput("")
    setLoading(true)
    clearAttachment()

    const userMessage: Message = {
      id: userMsgId,
      role: "user",
      content,
      uiStatus: "done",
      citations: [],
      createdAt: new Date().toISOString(),
      attachment: file ? { name: file.name, type: file.type, dataUrl: preview || undefined } : null,
    }
    const thinkingMessage: Message = {
      id: thinkingId,
      role: "assistant",
      content: "",
      uiStatus: "waiting",
      citations: [],
    }
    setMessages((prev) => [...prev, userMessage, thinkingMessage])

    try {
      // Handle vision for images
      if (file && file.type === "image" && selectedModel && (modelCapabilities[selectedModel] || []).includes("vision")) {
        const visionRes = await askVision(file.uri, content)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === thinkingId
              ? { ...m, content: visionRes.answer || "No response", uiStatus: "done" as const }
              : m,
          ),
        )
        setLoading(false)
        return
      }

      // Upload file if present
      if (file) {
        try {
          const uploadRes = await uploadDocument(file.uri, file.name, file.mimeType, {})
          const docId = uploadRes?.id || ""
          if (docId) {
            content = `Regarding the uploaded document "${file.name}" (ID: ${docId}): ${content}`
          }
        } catch (uploadErr: any) {
          // Continue even if upload fails
        }
      }

      let sid = sessionId
      if (!sid) {
        const created = await createChatSession(null, "global")
        sid = created.session_id
        setSessionId(sid)
      }

      if (selectedModel) {
        try { await setChatSessionModel(sid, selectedModel) } catch {}
      }

      const isStreamingModel = cloudModel

      if (isStreamingModel) {
        // ── Streaming path (for cloud/V2 models) ──
        // Matches the web frontend's chatGloballyStream flow
        setMessages((prev) =>
          prev.map((m) =>
            m.id === thinkingId
              ? { ...m, content: "", uiStatus: "streaming" as const }
              : m,
          ),
        )

        let fullAnswer = ""
        await chatGloballyStream(
          {
            question: q,
            session_id: sid,
            model: selectedModel || undefined,
            scope: "all",
          },
          {
            onChunk: (chunk) => {
              fullAnswer += chunk
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === thinkingId
                    ? { ...m, content: (m.content || "") + chunk, uiStatus: "streaming" as const }
                    : m,
                ),
              )
            },
            onReasoning: (reasoning) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === thinkingId
                    ? { ...m, reasoning: (m.reasoning || "") + reasoning }
                    : m,
                ),
              )
            },
            onDone: () => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === thinkingId
                    ? { ...m, uiStatus: "done" as const }
                    : m,
                ),
              )
            },
            onError: (error) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === thinkingId
                    ? { ...m, content: error, uiStatus: "error" as const }
                    : m,
                ),
              )
            },
          },
        )
      } else {
        // ── Non-streaming path (for local/Ollama models) ──
        const res = await chatGlobally({
          question: q,
          session_id: sid,
          model: selectedModel || undefined,
        })

        // Load full message history to get proper message list
        try {
          const history = await getChatMessages(sid, 100)
          const realMessages: Message[] = (history.messages || []).map((m: any) => ({
            id: m.id ?? generateId(),
            role: m.role ?? "assistant",
            content: m.content ?? "",
            reasoning: m.reasoning ?? undefined,
            uiStatus: (m.status === "failed" || m.status === "error") ? "error" : "done",
            citations: m.citations ?? [],
            createdAt: m.created_at ?? "",
          }))
          if (realMessages.length > 0) {
            setMessages(realMessages)
          } else {
            setMessages((prev) => prev.map((m) =>
              m.id === thinkingId
                ? { ...m, content: (res as any).answer || "No response", uiStatus: "done" as const }
                : m,
            ))
          }
        } catch {
          setMessages((prev) => prev.map((m) =>
            m.id === thinkingId
              ? { ...m, content: (res as any).answer || "No response", uiStatus: "done" as const }
              : m,
          ))
        }
      }
    } catch (err: any) {
      setMessages((prev) => prev.map((m) =>
        m.id === thinkingId
          ? { ...m, content: err.message || "Failed to get response", uiStatus: "error" as const }
          : m,
      ))
    } finally {
      setLoading(false)
    }
  }

  const handleRetry = (msg: Message) => {
    setMessages((prev) => prev.filter((m) => m.id !== msg.id))
    const lastUser = [...messages].reverse().find((m) => m.role === "user")
    if (lastUser) handleSend(lastUser.content)
  }

  const showWelcome = messages.length === 0

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.bg }}
      behavior="padding"
      keyboardVerticalOffset={Platform.OS === "ios" ? 50 : 0}
    >
      <View style={{ flex: 1 }}>
        {/* Header */}
        <ChatHeader
          model={selectedModel}
          modelLabels={modelLabels}
          modelCapabilities={modelCapabilities}
          messagesLength={messages.length}
          onModelChange={setSelectedModel}
          availableModels={models}
          v2Providers={v2Providers}
          loadingModels={loadingModels}
        />

        {/* Messages area */}
        <ScrollView
          ref={scrollRef}
          style={{ flex: 1 }}
          contentContainerStyle={{
            padding: showWelcome ? 0 : 16,
            paddingBottom: 20,
            flexGrow: 1,
          }}
          keyboardShouldPersistTaps="handled"
        >
          {showWelcome ? (
            <WelcomeScreen
              promptSuggestions={promptSuggestions}
              loadingPrompts={loadingPrompts}
              onSend={handleSend}
            />
          ) : (
            <View style={{ maxWidth: 860, width: "100%", alignSelf: "center" }}>
              {messages.map((msg, i) => (
                <ChatMessage
                  key={msg.id || i}
                  msg={msg}
                  prevMsg={i > 0 ? messages[i - 1] : undefined}
                  onRetry={handleRetry}
                  formatTime={formatTime}
                  formatDate={formatDate}
                  onOpenDocument={onOpenDocument}
                />
              ))}
              <View style={{ height: 12 }} />
            </View>
          )}
        </ScrollView>

        {/* Attachment preview */}
        {attachedFile && (
          <View style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 8,
            paddingHorizontal: 12,
            paddingBottom: 4,
          }}>
            <View style={{
              flex: 1,
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: c.cardBg,
              borderRadius: t.radii.md,
              paddingHorizontal: 10,
              paddingVertical: 6,
              borderWidth: 1,
              borderColor: c.border,
            }}>
              {attachedPreview ? (
                <View style={{ width: 32, height: 32, borderRadius: 6, backgroundColor: c.bgSecondary, alignItems: "center", justifyContent: "center", marginRight: 8 }}>
                  <Text style={{ fontSize: 16 }}>🖼️</Text>
                </View>
              ) : (
                <Text style={{ fontSize: 16, marginRight: 6 }}>📎</Text>
              )}
              <Text style={{ flex: 1, fontSize: 12, color: c.text }} numberOfLines={1}>{attachedFile.name}</Text>
              <Pressable onPress={clearAttachment} hitSlop={8}>
                <Text style={{ fontSize: 14, color: c.error, fontWeight: "600" }}>✕</Text>
              </Pressable>
            </View>
          </View>
        )}

        {/* Input area */}
        <View style={{
          paddingHorizontal: 12,
          paddingVertical: 8,
          paddingBottom: Platform.OS === "ios" ? 8 : 12,
        }}>
          <ChatInput
            loading={loading}
            input={input}
            onInputChange={setInput}
            onSend={() => handleSend()}
            isRecording={isRecording}
            isTranscribing={isTranscribing}
            onToggleRecording={toggleRecording}
            onAttachFile={pickAttachment}
            model={selectedModel}
          />
        </View>
      </View>
    </KeyboardAvoidingView>
  )
}
