import React, { useState, useEffect, useRef } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions, Alert, Image } from "react-native"
import { Audio } from "expo-av"
import * as FileSystem from "expo-file-system"
import * as DocumentPicker from "expo-document-picker"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { chatGlobally, transcribeAudio, askVision, uploadDocument } from "../api/client"
import { useModel } from "../context/ModelContext"

interface Message {
  role: "user" | "assistant"
  content: string
  status: "sending" | "done" | "error"
  sources?: string[]
  attachment?: AttachmentInfo | null
}

interface AttachmentInfo {
  uri: string
  name: string
  mimeType: string
  type: "image" | "document" | "audio"
}

const imageMimeTypes = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/jpg", "image/heic", "image/heif"]
const audioMimeTypes = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg", "audio/webm", "audio/flac", "audio/m4a"]

export function NewChatScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [attachedFile, setAttachedFile] = useState<AttachmentInfo | null>(null)
  const recordingRef = useRef<Audio.Recording | null>(null)
  const scrollRef = useRef<ScrollView>(null)
  const { selectedModel, setSelectedModel, availableModels: models, modelCapabilities, loading: loadingModels } = useModel()

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
      else if (audioMimeTypes.includes(mt)) ftype = "audio"
      setAttachedFile({
        uri: asset.uri,
        name: asset.name || "file",
        mimeType: mt,
        type: ftype,
      })
    } catch {
      Alert.alert("Error", "Failed to pick file")
    }
  }

  const clearAttachment = () => setAttachedFile(null)

  const handleSend = async () => {
    if ((!input.trim() && !attachedFile) || loading) return
    const content = input.trim() || (attachedFile ? `[Attachment: ${attachedFile.name}]` : "")
    const userMsg: Message = { role: "user", content, status: "done", attachment: attachedFile }
    const aiMsg: Message = { role: "assistant", content: "", status: "sending" }
    setMessages((prev) => [...prev, userMsg, aiMsg])
    setInput("")
    setLoading(true)
    const file = attachedFile
    clearAttachment()
    try {
      let res: any
      if (file && file.type === "image") {
        res = await askVision(file.uri, content)
      } else if (file) {
        const uploadRes = await uploadDocument(file.uri, file.name, file.mimeType, {})
        const docId = uploadRes?.id || ""
        const questionWithDoc = docId
          ? `Regarding the uploaded document "${file.name}" (ID: ${docId}): ${content}`
          : content
        res = await chatGlobally({ question: questionWithDoc, model: selectedModel || undefined } as any)
      } else {
        res = await chatGlobally({ question: content, model: selectedModel || undefined } as any)
      }
      setMessages((prev) => { const updated = [...prev]; const last = updated[updated.length - 1]; last.content = res.answer || res.response || "No response"; last.status = "done"; last.sources = res.sources || []; return updated })
    } catch (err: any) {
      setMessages((prev) => { const updated = [...prev]; const last = updated[updated.length - 1]; last.content = err.message || "Failed to get response"; last.status = "error"; return updated })
    } finally { setLoading(false) }
  }

  const startRecording = async () => {
    try { const { status } = await Audio.requestPermissionsAsync(); if (status !== "granted") return; await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true }); const recording = new Audio.Recording(); await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY); await recording.startAsync(); recordingRef.current = recording; setIsRecording(true) }
    catch { setIsRecording(false) }
  }

  const stopRecording = async () => {
    try {
      const recording = recordingRef.current; if (!recording) return; await recording.stopAndUnloadAsync(); const uri = recording.getURI() || ""; setIsRecording(false); setIsTranscribing(true)
      try { const result = await transcribeAudio(uri, "recording.m4a", "audio/m4a"); if (result.text?.trim()) setInput(result.text.trim()) } catch {} finally { setIsTranscribing(false) }
    } catch { setIsRecording(false) }
  }

  const toggleRecording = () => { if (isRecording) stopRecording(); else startRecording() }

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <View style={{ padding: t.spacing.md, borderBottomWidth: 1, borderBottomColor: c.border }}>
        <Text style={{ fontSize: 18, fontWeight: "800", color: c.text, marginBottom: 4 }}>New Chat</Text>
        <Text style={{ fontSize: 12, color: c.textMuted }}>Chat freely with the AI — no documents required</Text>
        {!loadingModels && models.length > 0 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: t.spacing.sm }}>
            {models.map((m, i) => {
              const caps = modelCapabilities[m] || []
              const icons = caps.slice(0, 3).map((cap: string) => ({ reasoning: "🧠", vision: "👁️", audio: "🎤", code: "💻", fast: "⚡", large: "🐘", text: "💬", embedding: "📊" })[cap] || "").filter(Boolean).join(" ")
              return (
                <Pressable key={`nmodel-${i}`} onPress={() => setSelectedModel(m)} style={{ paddingHorizontal: t.spacing.sm, paddingVertical: t.spacing.xs, borderRadius: t.radii.lg, marginRight: 6, backgroundColor: m === selectedModel ? c.primary : c.surface }}>
                  <Text style={{ fontSize: 12, color: m === selectedModel ? "#FFF" : c.textSecondary }}>{m}</Text>
                  {icons ? <Text style={{ fontSize: 9, color: m === selectedModel ? "#FFD" : c.textMuted, marginTop: 1, textAlign: "center" }}>{icons}</Text> : null}
                </Pressable>
              )
            })}
          </ScrollView>
        )}
      </View>

      <ScrollView ref={scrollRef} style={{ flex: 1, padding: t.spacing.md }} onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}>
        {messages.length === 0 && (
          <View style={{ flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 80 }}>
            <Text style={{ fontSize: 40, opacity: 0.3 }}>💬</Text>
            <Text style={{ fontSize: 16, fontWeight: "600", color: c.textSecondary, marginTop: 12 }}>Start a ZETDC conversation</Text>
            <Text style={{ fontSize: 12, color: c.textMuted, textAlign: "center", marginTop: 6, paddingHorizontal: 40 }}>Ask about policies, procedures, reports, or request Shona responses.</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "center", marginTop: t.spacing.md, gap: t.spacing.sm }}>
              {[
                { label: "⚡ ZETDC outage process", q: "Explain the ZETDC outage reporting and restoration process" },
                { label: "📋 Net metering policy", q: "What is ZETDC's net metering policy for solar installations?" },
                { label: "🇿🇼 Summarize in Shona", q: "Please summarize this in Shona: ZETDC power supply guidelines" },
                { label: "🏗️ Safety procedures", q: "What are the ZETDC electrical safety procedures for field workers?" },
              ].map((item) => (
                <Pressable key={item.label} onPress={() => { setInput(item.q) }} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.lg, paddingHorizontal: t.spacing.sm, paddingVertical: t.spacing.xs, borderWidth: 1, borderColor: c.border }}>
                  <Text style={{ fontSize: 12, color: c.text, fontWeight: "500" }}>{item.label}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        )}
        {messages.map((msg, i) => (
          <View key={i} style={{ alignItems: msg.role === "user" ? "flex-end" : "flex-start", marginBottom: t.spacing.sm }}>
            <View style={{ maxWidth: "80%", padding: t.spacing.sm, borderRadius: t.radii.lg, borderTopRightRadius: msg.role === "user" ? 4 : t.radii.lg, borderTopLeftRadius: msg.role === "user" ? t.radii.lg : 4, backgroundColor: msg.role === "user" ? c.primary : c.cardBg, borderWidth: msg.role === "user" ? 0 : 1, borderColor: c.border }}>
              {msg.attachment && msg.attachment.type === "image" && msg.role === "user" && (
                <Image source={{ uri: msg.attachment.uri }} style={{ width: "100%", height: 160, borderRadius: t.radii.sm, marginBottom: t.spacing.xs }} resizeMode="cover" />
              )}
              {msg.attachment && msg.attachment.type !== "image" && msg.role === "user" && (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: t.spacing.xs, backgroundColor: msg.role === "user" ? "rgba(255,255,255,0.15)" : c.bgSecondary, borderRadius: t.radii.sm, paddingHorizontal: t.spacing.sm, paddingVertical: 6 }}>
                  <Text style={{ fontSize: 16 }}>{msg.attachment.type === "audio" ? "🎵" : "📎"}</Text>
                  <Text style={{ flex: 1, fontSize: 12, color: msg.role === "user" ? "#FFF" : c.text, fontWeight: "500" }} numberOfLines={1}>{msg.attachment.name}</Text>
                </View>
              )}
              {msg.status === "sending" ? (
                <ActivityIndicator size="small" color={c.primary} />
              ) : msg.status === "error" ? (
                <Text style={{ color: c.error, fontSize: 14 }}>⚠️ {msg.content}<Text style={{ color: c.primary, textDecorationLine: "underline" }} onPress={handleSend}> Retry</Text></Text>
              ) : (
                <Text style={{ color: msg.role === "user" ? "#FFF" : c.text, fontSize: 14, lineHeight: 20 }}>{msg.content}</Text>
              )}
              {msg.sources && msg.sources.length > 0 && (
                <Text style={{ fontSize: 10, color: c.textMuted, marginTop: 6, borderTopWidth: 1, borderTopColor: c.border, paddingTop: 4 }}>Sources: {msg.sources.join(", ")}</Text>
              )}
            </View>
          </View>
        ))}
      </ScrollView>

      {attachedFile && (
        <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm, paddingHorizontal: t.spacing.md, paddingBottom: 4, backgroundColor: c.bg }}>
          <View style={{ flex: 1, flexDirection: "row", alignItems: "center", backgroundColor: c.cardBg, borderRadius: t.radii.md, paddingHorizontal: t.spacing.sm, paddingVertical: 6, borderWidth: 1, borderColor: c.border }}>
            <Text style={{ fontSize: 16, marginRight: 6 }}>{attachedFile.type === "image" ? "🖼️" : "📎"}</Text>
            <Text style={{ flex: 1, fontSize: 12, color: c.text }} numberOfLines={1}>{attachedFile.name}</Text>
            <Pressable onPress={clearAttachment} hitSlop={8} style={{ marginLeft: 4 }}>
              <Text style={{ fontSize: 14, color: c.error, fontWeight: "600" }}>✕</Text>
            </Pressable>
          </View>
        </View>
      )}
      <View style={{ flexDirection: "row", gap: t.spacing.sm, padding: t.spacing.md, borderTopWidth: 1, borderTopColor: c.border, alignItems: "center" }}>
        <TextInput value={input} onChangeText={setInput} placeholder={isTranscribing ? "Transcribing voice..." : "Type a message..."} placeholderTextColor={c.textMuted} onSubmitEditing={handleSend} editable={!loading && !isTranscribing} style={{ flex: 1, backgroundColor: c.inputBg, color: c.text, borderRadius: t.radii.md, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, borderWidth: 1, borderColor: c.border }} />
        <Pressable onPress={pickAttachment} disabled={loading} style={{ backgroundColor: c.primary + "18", borderRadius: t.radii.md, width: 42, height: 42, justifyContent: "center", alignItems: "center", borderWidth: 1, borderColor: c.primary + "40" }}>
          <Text style={{ fontSize: 18 }}>📎</Text>
        </Pressable>
        <Pressable onPress={toggleRecording} disabled={isTranscribing} style={{ backgroundColor: isRecording ? c.error : c.primary, borderRadius: t.radii.md, width: 42, height: 42, justifyContent: "center", alignItems: "center", opacity: isTranscribing ? 0.5 : 1 }}>
          <Text style={{ color: "#FFF", fontSize: 18 }}>{isRecording ? "⏹" : "🎙"}</Text>
        </Pressable>
        <Pressable onPress={handleSend} disabled={loading || (!input.trim() && !attachedFile)} style={{ backgroundColor: loading || (!input.trim() && !attachedFile) ? c.textMuted : c.primary, borderRadius: t.radii.md, paddingHorizontal: 20, height: 42, justifyContent: "center", opacity: loading || (!input.trim() && !attachedFile) ? 0.5 : 1 }}>
          <Text style={{ color: "#FFF", fontWeight: "600", fontSize: 14 }}>{loading ? "..." : "Send"}</Text>
        </Pressable>
      </View>
    </View>
  )
}
