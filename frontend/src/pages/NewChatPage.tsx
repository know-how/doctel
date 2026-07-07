import React, { useState, useEffect, useRef } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { chatGlobally, chatGloballyStream, getAvailableModels, createChatSession, getChatMessages, setChatSessionModel, transcribeAudio, askVision, uploadDocument, uploadDocumentWithProgress } from "../api/client"
import { useModel } from "../context/ModelContext"
import { ModelConfigPanel } from "../components/ModelConfigPanel"
import { isCloudModel } from "../utils/modelUtils"

interface Citation {
  filename?: string
  chunk_index?: number
  text?: string
}

interface AttachmentMeta {
  name: string
  type: "image" | "document" | "audio"
  dataUrl?: string
}

interface Message {
  id: number | string
  role: "user" | "assistant" | "system"
  content: string
  uiStatus: "waiting" | "streaming" | "done" | "error"
  citations: Citation[]
  createdAt?: string
  attachment?: AttachmentMeta | null
}

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

export const NewChatPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const [attachedPreview, setAttachedPreview] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [uploadStatusMsg, setUploadStatusMsg] = useState<string | null>(null)
  const [capabilityWarning, setCapabilityWarning] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { selectedModel: model, setSelectedModel: setModel, availableModels: models, modelCapabilities, modelLabels, modelDetails, loading: loadingModels, setModelForTask } = useModel()

  // On mount, ensure we have the best chat-optimized model
  useEffect(() => {
    if (!loadingModels && !model) {
      setModelForTask("chat")
    }
  }, [loadingModels, model, setModelForTask])

  // When model changes and a session exists, persist to backend
  const handleModelChange = async (nextModel: string) => {
    setModel(nextModel)
    if (sessionId) {
      try {
        await setChatSessionModel(sessionId, nextModel)
        console.log("Chat model updated to:", nextModel)
      } catch (e) {
        console.warn("Failed to persist model to session:", e)
      }
    }
  }

  // Restore session model when loading existing session
  useEffect(() => {
    if (!sessionId) return
    ;(async () => {
      try {
        const msgs = await getChatMessages(sessionId, 1)
        const sessionInfo = msgs as any
        const savedModel = sessionInfo?.model_name || sessionInfo?.model
        if (savedModel && savedModel !== model && models.includes(savedModel)) {
          setModel(savedModel)
        }
      } catch {}
    })()
  }, [sessionId])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" })
      audioChunksRef.current = []
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" })
        await transcribeRecording(blob)
      }
      mediaRecorderRef.current = mediaRecorder
      mediaRecorder.start()
      setIsRecording(true)
    } catch {
      setIsRecording(false)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const transcribeRecording = async (blob: Blob) => {
    setIsTranscribing(true)
    try {
      const result = await transcribeAudio(blob)
      const text = result.text?.trim()
      if (text) {
        setInput(text)
      }
    } catch {
    } finally {
      setIsTranscribing(false)
    }
  }

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const handleAttachFile = () => {
    fileInputRef.current?.click()
  }

  const onFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAttachedFile(file)
    if (file.type.startsWith("image/")) {
      const reader = new FileReader()
      reader.onload = (ev) => setAttachedPreview(ev.target?.result as string)
      reader.readAsDataURL(file)
    } else {
      setAttachedPreview(null)
    }

    // Capability validation
    const caps = model ? (modelCapabilities[model] || []) : []
    let warning: string | null = null
    if (file.type.startsWith("image/") && !caps.includes("vision")) {
      warning = `The model "${model}" does not support image understanding (vision). Uploading as a document instead.`
    } else if (file.type.startsWith("audio/") && !caps.includes("audio")) {
      warning = `The model "${model}" does not support audio processing. Uploading as a document instead.`
    }
    setCapabilityWarning(warning)

    e.target.value = ""
  }

  const clearAttachment = () => {
    setAttachedFile(null)
    setAttachedPreview(null)
    setCapabilityWarning(null)
  }

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

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
    setUploadProgress(null)
    setUploadStatusMsg(file ? "Uploading..." : null)
    clearAttachment()
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content, uiStatus: "done", citations: [], createdAt: new Date().toISOString(), attachment: file ? { name: file.name, type: file.type.startsWith("image/") ? "image" : file.type.startsWith("audio/") ? "audio" : "document", dataUrl: preview || undefined } : null },
      { id: thinkingId, role: "assistant", content: "", uiStatus: "waiting", citations: [] },
    ])

    try {
      const caps = model ? (modelCapabilities[model] || []) : []

      if (file && file.type.startsWith("image/") && caps.includes("vision")) {
        // Model supports vision — send image directly
        const visionRes = await askVision(file, content)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === thinkingId
              ? { ...m, content: visionRes.answer || "No response", uiStatus: "done" as const }
              : m,
          ),
        )
        setLoading(false)
        inputRef.current?.focus()
        return
      }

      if (file && (file.type.startsWith("audio/") && !caps.includes("audio"))) {
        // Audio on a model that doesn't support it — upload as document
        setUploadStatusMsg(`Uploading ${file.name} as document (audio not supported by ${model})...`)
      }

      if (file) {
        try {
          setUploadStatusMsg(`Uploading ${file.name}...`)
          const uploadRes = await uploadDocumentWithProgress(
            file,
            (pct) => setUploadProgress(pct),
            { document_type: "attachment" },
          ) as any
          setUploadProgress(100)
          setUploadStatusMsg("Processing...")
          const docId = uploadRes?.id || ""
          if (docId) {
            content = `Regarding the uploaded document "${file.name}" (ID: ${docId}): ${content}`
          }
          setUploadProgress(null)
          setUploadStatusMsg(null)
        } catch (uploadErr: any) {
          setUploadStatusMsg(`Upload failed: ${uploadErr.message || "Unknown error"}`)
          setUploadProgress(null)
          setTimeout(() => setUploadStatusMsg(null), 5000)
        }
      }

      let sid = sessionId
      if (!sid) {
        const created = await createChatSession(null, "global")
        sid = created.session_id
        setSessionId(sid)
        localStorage.setItem("docintel_newchat_session", sid)
      }

      const cloudModel = isCloudModel(model, modelDetails)

      if (cloudModel) {
        await chatGloballyStream(
          {
            question: q,
            session_id: sid,
            model: model || undefined,
          },
          {
            onChunk: (chunk) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === thinkingId
                    ? { ...m, content: (m.content || "") + chunk, uiStatus: "streaming" as const }
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
              setLoading(false)
            },
            onError: (error) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === thinkingId
                    ? { ...m, content: `Error: ${error}`, uiStatus: "error" as const }
                    : m,
                ),
              )
              setLoading(false)
            },
          },
        )
        return
      }

      await chatGlobally({
        question: q,
        session_id: sid,
        model: model || undefined,
      })

      const history = await getChatMessages(sid, 100)
      const realMessages: Message[] = (history.messages || []).map((m: any) => ({
        id: m.id ?? generateId(),
        role: m.role ?? "assistant",
        content: m.content ?? "",
        uiStatus: (m.status === "failed" || m.status === "error") ? "error" : "done",
        citations: m.citations ?? [],
        createdAt: m.created_at ?? "",
      }))

      if (realMessages.length > 0) {
        setMessages(realMessages)
      } else {
        setMessages((prev) => prev.map((m) =>
          m.id === thinkingId ? { ...m, uiStatus: "error", content: "No response received. Please try again." } : m
        ))
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== thinkingId)
          .concat({
            id: generateId(),
            role: "system",
            content: err.message || "Connection failed. Check that the backend is running.",
            uiStatus: "error",
            citations: [],
          })
      )
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleRetry = (msg: Message) => {
    setMessages((prev) => prev.filter((m) => m.id !== msg.id))
    const lastUser = [...messages].reverse().find((m) => m.role === "user")
    if (lastUser) handleSend(lastUser.content)
  }

  const renderContent = (content: string) => {
    if (!content) return null
    const parts = content.split(/(```[\s\S]*?```|`[^`]*`|\*\*.*?\*\*|\*[^*]+\*)/g)
    return parts.map((part, i) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        const code = part.slice(3, -3).replace(/\n$/, "")
        return (
          <pre key={i} style={{
            background: "rgba(0,0,0,0.25)", borderRadius: 8,
            padding: "14px 18px", margin: "10px 0", overflow: "auto",
            fontSize: 12.5, lineHeight: 1.6, fontFamily: "'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace",
          }}>
            <code>{code}</code>
          </pre>
        )
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={i} style={{
          background: "rgba(0,0,0,0.2)", borderRadius: 4,
          padding: "2px 6px", fontSize: 12.5, fontFamily: "monospace",
        }}>{part.slice(1, -1)}</code>
      }
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={i}>{part.slice(1, -1)}</em>
      }
      return <span key={i} style={{ whiteSpace: "pre-wrap" }}>{part}</span>
    })
  }

  const isDark = theme === "dark"
  const showWelcome = messages.length === 0

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100%",
      background: t.colors.bg, position: "relative",
      maxWidth: 1200, margin: "0 auto", width: "100%",
    }}>
      {/* Ambient background */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: isDark
          ? "radial-gradient(ellipse at 50% 0%, rgba(91,136,255,0.05) 0%, transparent 50%), radial-gradient(ellipse at 80% 100%, rgba(31,231,255,0.03) 0%, transparent 40%)"
          : "radial-gradient(ellipse at 50% 0%, rgba(11,78,162,0.04) 0%, transparent 50%), radial-gradient(ellipse at 80% 100%, rgba(0,151,178,0.02) 0%, transparent 40%)",
      }} />

      {/* Header */}
      <div style={{
        flexShrink: 0, position: "relative", zIndex: 10,
        padding: `${t.spacing.lg}px 40px`,
        borderBottom: `1px solid ${t.colors.border}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <h1 style={{
            fontSize: 22, fontWeight: 800, color: t.colors.text, margin: 0,
            letterSpacing: "-0.3px",
            background: `linear-gradient(135deg, ${t.colors.text} 0%, ${t.colors.primary} 100%)`,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}>
            New Chat
          </h1>
          <p style={{ fontSize: 12, color: t.colors.textMuted, margin: "3px 0 0 0" }}>
            Chatting with {modelLabels[model] || model || "AI"} · {messages.length} messages
          </p>
          {model && modelCapabilities[model] && modelCapabilities[model].length > 0 && (
            <div style={{ display: "flex", gap: 4, marginTop: 4, alignItems: "center" }}>
              <span style={{ fontSize: 10, color: t.colors.textMuted, fontWeight: 500, marginRight: 2 }}>Tools:</span>
              {modelCapabilities[model].map(cap => {
                const icon = cap === "reasoning" ? "🧠" : cap === "vision" ? "👁️" : cap === "audio" ? "🎤" : cap === "code" ? "💻" : cap === "fast" ? "⚡" : cap === "large" ? "🐘" : "🔧"
                const label = cap === "reasoning" ? "Reasoning" : cap === "vision" ? "Vision" : cap === "audio" ? "Audio" : cap === "code" ? "Code" : cap === "fast" ? "Fast" : cap === "large" ? "Large" : cap
                return (
                  <span key={cap} style={{
                    fontSize: 10, padding: "1px 6px", borderRadius: 4,
                    border: `1px solid ${t.colors.border}`,
                    backgroundColor: t.colors.surface,
                    color: t.colors.textSecondary, lineHeight: "16px",
                    display: "inline-flex", alignItems: "center", gap: 3,
                  }}>
                    {icon} {label}
                  </span>
                )
              })}
            </div>
          )}
        </div>
        {models.length > 0 && (
          <ModelConfigPanel
            selectedModel={model}
            availableModels={models}
            modelCapabilities={modelCapabilities}
            modelLabels={modelLabels}
            onSelect={(m) => { handleModelChange(m); setCapabilityWarning(null); }}
            loading={loadingModels}
          />
        )}
      </div>

      {/* Messages area */}
      <div style={{
        flex: 1, overflowY: "auto", position: "relative", zIndex: 2,
        padding: showWelcome ? "0 40px" : `${t.spacing.xl}px 40px ${t.spacing.lg}px`,
        display: "flex", flexDirection: "column",
      }}>
        {/* Welcome state */}
        {showWelcome && (
          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            paddingBottom: 40,
          }}>
            <div style={{
              width: 88, height: 88, borderRadius: "50%",
              background: `radial-gradient(circle, ${t.colors.primary}25, transparent 75%)`,
              display: "flex", alignItems: "center", justifyContent: "center",
              animation: "docintel-pulse 2.5s ease-in-out infinite",
              marginBottom: 20,
            }}>
              <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
                <rect x="14" y="8" width="20" height="24" rx="6" fill="none" stroke={t.colors.primary} strokeWidth="2.5"/>
                <circle cx="24" cy="20" r="4" fill={t.colors.primary} opacity="0.8"/>
                <line x1="24" y1="26" x2="24" y2="32" stroke={t.colors.primary} strokeWidth="2" strokeLinecap="round"/>
                <line x1="18" y1="32" x2="30" y2="32" stroke={t.colors.primary} strokeWidth="2" strokeLinecap="round" opacity="0.4"/>
                <line x1="20" y1="4" x2="28" y2="4" stroke={t.colors.secondary} strokeWidth="2" strokeLinecap="round" opacity="0.6"/>
                <circle cx="24" cy="1.5" r="3" fill={t.colors.secondary} opacity="0.7"/>
              </svg>
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: t.colors.text, marginBottom: 8 }}>
              Start a conversation
            </div>
            <div style={{
              fontSize: 13.5, color: t.colors.textMuted, textAlign: "center",
              maxWidth: 440, lineHeight: 1.7, marginBottom: 24,
            }}>
              Chat with the ZETDC AI assistant. Ask about policies, procedures,
              reports, or request responses in Shona — no document upload needed.
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center", maxWidth: 500 }}>
              {[
                { label: "ZETDC outage reporting process", icon: "⚡" },
                { label: "Explain ZETDC net metering policy", icon: "📋" },
                { label: "Summarize in Shona", icon: "🇿🇼" },
                { label: "ZETDC safety procedures", icon: "🏗️" },
              ].map((q) => (
                <button
                  key={q.label}
                  onClick={() => handleSend(q.label)}
                  style={{
                    display: "flex", alignItems: "center", gap: 8,
                    background: t.colors.cardBg,
                    color: t.colors.text, border: `1px solid ${t.colors.border}`,
                    borderRadius: 24, padding: "10px 18px", fontSize: 13,
                    cursor: "pointer", transition: "all 0.2s ease",
                    whiteSpace: "nowrap",
                  }}
                  onMouseEnter={(e) => {
                    const el = e.target as HTMLElement
                    el.style.background = t.colors.surfaceActive
                    el.style.borderColor = t.colors.primary + "60"
                  }}
                  onMouseLeave={(e) => {
                    const el = e.target as HTMLElement
                    el.style.background = t.colors.cardBg
                    el.style.borderColor = t.colors.border
                  }}
                >
                  <span>{q.icon}</span> {q.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Chat history */}
        {!showWelcome && (
          <div style={{
            maxWidth: 860, width: "100%", margin: "0 auto",
            display: "flex", flexDirection: "column",
          }}>
            {messages.map((msg, i) => {
              const isUser = msg.role === "user"
              const isWaiting = msg.uiStatus === "waiting"
              const isError = msg.uiStatus === "error"
              const showAvatar = i === 0 || messages[i - 1]?.role !== msg.role

              return (
                <div key={msg.id || i} style={{ marginBottom: showAvatar ? 28 : 8 }}>
                  {/* Date separator for long gaps */}
                  {i > 0 && messages[i - 1]?.createdAt && msg.createdAt && (() => {
                    try {
                      const prev = new Date(messages[i - 1].createdAt!).getTime()
                      const curr = new Date(msg.createdAt!).getTime()
                      if (isNaN(prev) || isNaN(curr)) return null
                      if (curr - prev > 30 * 60 * 1000) {
                        return (
                          <div style={{
                            display: "flex", justifyContent: "center", marginBottom: 20,
                          }}>
                            <span style={{
                              fontSize: 11, color: t.colors.textMuted,
                              background: t.colors.cardBg, borderRadius: 12,
                              padding: "4px 14px", border: `1px solid ${t.colors.border}`,
                            }}>
                              {formatDate(msg.createdAt)}
                            </span>
                          </div>
                        )
                      }
                    } catch { return null }
                    return null
                  })()}

                  <div style={{
                    display: "flex", alignItems: "flex-start",
                    flexDirection: isUser ? "row-reverse" : "row",
                    gap: 14,
                    animation: "msg-slide-up 0.35s ease forwards",
                  }}>
                    {/* Avatar */}
                    {showAvatar ? (
                      <div style={{
                        width: 38, height: 38, borderRadius: "50%", flexShrink: 0,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        background: isUser
                          ? `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`
                          : `linear-gradient(135deg, ${t.colors.secondary}20, ${t.colors.primary}25)`,
                        border: isUser
                          ? `2px solid ${t.colors.primary}60`
                          : `2px solid ${t.colors.border}`,
                        boxShadow: isUser
                          ? `0 2px 12px ${t.colors.primary}30`
                          : isWaiting ? `0 0 20px ${t.colors.primary}40` : "none",
                        marginTop: 2,
                        transition: "box-shadow 0.3s",
                      }}>
                        {isUser ? (
                          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                            <circle cx="12" cy="7" r="4" />
                          </svg>
                        ) : (
                          <svg width="17" height="17" viewBox="0 0 48 48" fill="none">
                            <rect x="14" y="8" width="20" height="24" rx="6" stroke={t.colors.primary} strokeWidth="2.5" fill="none"/>
                            <circle cx="24" cy="20" r="3" fill={t.colors.primary} opacity="0.7"/>
                            <line x1="24" y1="25" x2="24" y2="30" stroke={t.colors.primary} strokeWidth="2" strokeLinecap="round"/>
                            <line x1="19" y1="30" x2="29" y2="30" stroke={t.colors.primary} strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
                          </svg>
                        )}
                      </div>
                    ) : (
                      <div style={{ width: 38, flexShrink: 0 }} />
                    )}

                    <div style={{
                      maxWidth: "72%",
                      minWidth: 80,
                    }}>
                      {/* Message bubble */}
                      <div style={{
                        padding: isWaiting ? "14px 20px" : "14px 18px",
                        borderRadius: isUser
                          ? showAvatar
                            ? "18px 18px 4px 18px"
                            : "18px 4px 4px 18px"
                          : showAvatar
                            ? "18px 18px 18px 4px"
                            : "4px 18px 18px 4px",
                        background: isError
                          ? t.colors.cardBg
                          : isUser
                            ? `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`
                            : t.colors.cardBg,
                        color: isUser ? "#FFFFFF" : isError ? t.colors.error : t.colors.text,
                        fontSize: 14, lineHeight: 1.72,
                        border: isUser ? "none" : `1px solid ${t.colors.border}`,
                        boxShadow: isUser
                          ? `0 2px 16px ${t.colors.primary}25`
                          : "0 1px 2px rgba(0,0,0,0.06)",
                      }}>
                        {msg.attachment && msg.role === "user" && (
                          msg.attachment.type === "image" && msg.attachment.dataUrl ? (
                            <img src={msg.attachment.dataUrl} alt={msg.attachment.name} style={{ width: "100%", maxHeight: 180, borderRadius: 8, objectFit: "cover", marginBottom: 8 }} />
                          ) : (
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, background: isUser ? "rgba(255,255,255,0.15)" : t.colors.surfaceActive, borderRadius: 8, padding: "6px 10px" }}>
                              <span style={{ fontSize: 16 }}>{msg.attachment.type === "audio" ? "🎵" : "📎"}</span>
                              <span style={{ fontSize: 12, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{msg.attachment.name}</span>
                            </div>
                          )
                        )}
                        {/* Waiting animation */}
                        {isWaiting ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0" }}>
                            <div style={{
                              width: 9, height: 9, borderRadius: "50%",
                              background: t.colors.primary,
                              animation: "dot-bounce 1.4s ease-in-out infinite",
                            }} />
                            <div style={{
                              width: 9, height: 9, borderRadius: "50%",
                              background: t.colors.primary,
                              animation: "dot-bounce 1.4s ease-in-out infinite 0.2s",
                            }} />
                            <div style={{
                              width: 9, height: 9, borderRadius: "50%",
                              background: t.colors.primary,
                              animation: "dot-bounce 1.4s ease-in-out infinite 0.4s",
                            }} />
                            <span style={{ fontSize: 12, color: t.colors.textMuted, marginLeft: 6 }}>
                              Thinking...
                            </span>
                          </div>
                        ) : msg.uiStatus === "streaming" ? (
                          <div>
                            {renderContent(msg.content)}
                            <span style={{ display: "inline-block", width: 2, height: "1em", backgroundColor: t.colors.primary, marginLeft: 2, animation: "streaming-blink 1s step-end infinite", verticalAlign: "text-bottom" }} />
                          </div>
                        ) : isError ? (
                          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                            <span>⚠️</span>
                            <div style={{ flex: 1 }}>
                              <div style={{ marginBottom: 8 }}>{msg.content}</div>
                              <button
                                onClick={() => handleRetry(msg)}
                                style={{
                                  background: t.colors.surfaceActive,
                                  color: t.colors.primary, border: "none",
                                  borderRadius: 6, padding: "4px 12px",
                                  cursor: "pointer", fontSize: 12, fontWeight: 600,
                                }}
                              >
                                Retry
                              </button>
                            </div>
                          </div>
                        ) : msg.content ? (
                          <div>{renderContent(msg.content)}</div>
                        ) : null}

                        {/* Citations */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div style={{
                            marginTop: 12, paddingTop: 10,
                            borderTop: `1px solid ${t.colors.border}`,
                            display: "flex", flexWrap: "wrap", gap: 6,
                            alignItems: "center",
                          }}>
                            <span style={{ fontSize: 10.5, color: t.colors.textMuted, fontWeight: 600 }}>
                              Sources
                            </span>
                            {msg.citations.map((c, ci) => (
                              <span key={ci} style={{
                                fontSize: 10.5, fontWeight: 500,
                                background: isUser ? "rgba(255,255,255,0.15)" : t.colors.surfaceActive,
                                color: isUser ? "rgba(255,255,255,0.85)" : t.colors.textSecondary,
                                borderRadius: 6, padding: "3px 8px",
                              }}>
                                {c.filename || `Chunk ${(c.chunk_index ?? ci) + 1}`}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Timestamp */}
                      {msg.createdAt && (
                        <div style={{
                          display: "flex", gap: 12, marginTop: 5,
                          justifyContent: isUser ? "flex-end" : "flex-start",
                          paddingRight: isUser ? 4 : 0,
                          paddingLeft: isUser ? 0 : 4,
                        }}>
                          <span style={{ fontSize: 10.5, color: t.colors.textMuted, opacity: 0.55 }}>
                            {formatTime(msg.createdAt)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
            <div ref={chatEndRef} style={{ height: 20 }} />
          </div>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,application/pdf,text/plain,.docx,.doc"
        onChange={onFilePicked}
        style={{ display: "none" }}
      />

      {/* Attachment preview */}
      {attachedFile && (
        <div style={{
          flexShrink: 0, position: "relative", zIndex: 2,
          padding: `0 40px 6px`,
        }}>
          <div style={{
            maxWidth: 860, margin: "0 auto",
            display: "flex", alignItems: "center", gap: 10,
            background: t.colors.cardBg,
            borderRadius: t.radii.md,
            padding: "8px 14px",
            border: `1px solid ${t.colors.border}`,
          }}>
            {attachedPreview ? (
              <img src={attachedPreview} alt="preview" style={{ width: 36, height: 36, borderRadius: 6, objectFit: "cover" }} />
            ) : (
              <span style={{ fontSize: 18 }}>📎</span>
            )}
            <span style={{ flex: 1, fontSize: 13, color: t.colors.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {attachedFile.name}
            </span>
            <button
              onClick={clearAttachment}
              style={{
                background: "none", border: "none", color: t.colors.error,
                cursor: "pointer", fontSize: 16, padding: "2px 6px",
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Capability warning */}
      {capabilityWarning && (
        <div style={{
          flexShrink: 0, position: "relative", zIndex: 2,
          padding: "0 40px 6px",
        }}>
          <div style={{
            maxWidth: 860, margin: "0 auto",
            background: "#FEF3C7", borderRadius: t.radii.md,
            padding: "8px 14px",
            border: "1px solid #F59E0B",
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <span style={{ fontSize: 14 }}>⚠️</span>
            <span style={{ flex: 1, fontSize: 12, color: "#92400E", lineHeight: 1.4 }}>
              {capabilityWarning}
            </span>
            <button
              onClick={() => setCapabilityWarning(null)}
              style={{
                background: "none", border: "none", color: "#92400E",
                cursor: "pointer", fontSize: 14, padding: "2px 4px", opacity: 0.6,
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Upload progress bar */}
      {(uploadProgress !== null || uploadStatusMsg) && (
        <div style={{
          flexShrink: 0, position: "relative", zIndex: 2,
          padding: "0 40px 6px",
        }}>
          <div style={{
            maxWidth: 860, margin: "0 auto",
            background: t.colors.cardBg,
            borderRadius: t.radii.md,
            padding: "10px 14px",
            border: `1px solid ${t.colors.border}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: uploadProgress !== null ? 6 : 0 }}>
              <span style={{ fontSize: 14 }}>📄</span>
              <span style={{ flex: 1, fontSize: 13, color: t.colors.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {uploadStatusMsg || "Uploading..."}
              </span>
              {uploadProgress !== null && (
                <span style={{ fontSize: 12, color: t.colors.textMuted, fontVariantNumeric: "tabular-nums" }}>
                  {uploadProgress}%
                </span>
              )}
            </div>
            {uploadProgress !== null && (
              <div style={{
                width: "100%", height: 6,
                background: t.colors.border,
                borderRadius: 3, overflow: "hidden",
              }}>
                <div style={{
                  width: `${uploadProgress}%`,
                  height: "100%",
                  background: `linear-gradient(90deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
                  borderRadius: 3,
                  transition: "width 0.3s ease",
                }} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Input area */}
      <div style={{
        flexShrink: 0, position: "relative", zIndex: 2,
        padding: `${t.spacing.md}px 40px ${t.spacing.lg}px`,
      }}>
        <div style={{ maxWidth: 860, margin: "0 auto" }}>
          <div style={{
            display: "flex", gap: 12, alignItems: "flex-end",
            background: t.colors.cardBg,
            border: `1.5px solid ${loading ? t.colors.primary + "50" : t.colors.border}`,
            borderRadius: t.radii.lg,
            padding: "6px 8px",
            boxShadow: loading
              ? `0 0 0 4px ${t.colors.primary}12, 0 4px 20px rgba(0,0,0,0.05)`
              : "0 2px 8px rgba(0,0,0,0.04)",
            transition: "border-color 0.2s, box-shadow 0.2s",
          }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder={`Message ${model || "AI"}...`}
              disabled={loading}
              rows={1}
              style={{
                flex: 1, background: "transparent", color: t.colors.text,
                border: "none", padding: "10px 8px", fontSize: 14.5,
                outline: "none", resize: "none", fontFamily: "inherit",
                lineHeight: 1.55, maxHeight: 150,
                caretColor: t.colors.primary,
                minHeight: 24,
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = "auto"
                target.style.height = Math.min(target.scrollHeight, 150) + "px"
              }}
            />
            <div style={{
              display: "flex", alignItems: "center", gap: 4,
              flexShrink: 0, alignSelf: "flex-end", paddingBottom: 1,
            }}>
              {isTranscribing && (
                <div style={{
                  fontSize: 11, color: t.colors.primary, whiteSpace: "nowrap",
                  animation: "pulse 1.5s ease-in-out infinite",
                }}>
                  Transcribing...
                </div>
              )}
              <button
                onClick={handleAttachFile}
                disabled={loading}
                title="Attach file or image"
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: attachedFile ? t.colors.primary + "20" : "transparent",
                  color: attachedFile ? t.colors.primary : t.colors.textMuted,
                  border: attachedFile ? `1px solid ${t.colors.primary}60` : `1px solid ${t.colors.border}`,
                  cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 14,
                  transition: "all 0.2s ease",
                }}
              >
                📎
              </button>
              <button
                onClick={toggleRecording}
                disabled={isTranscribing}
                title={isRecording ? "Stop recording" : "Record voice message"}
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: isRecording
                    ? "#EF4444"
                    : t.colors.primary,
                  color: "#FFFFFF",
                  border: "none",
                  cursor: isTranscribing ? "not-allowed" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 14,
                  transition: "all 0.2s ease",
                  animation: isRecording ? "pulse 1.5s ease-in-out infinite" : "none",
                  boxShadow: isRecording ? "none" : `0 2px 8px ${t.colors.primary}30`,
                }}
              >
                {isRecording ? "⏹" : "🎙"}
              </button>
              <span style={{
                fontSize: 9.5, color: t.colors.textMuted, opacity: 0.4,
                display: input.trim().length > 0 || isRecording || isTranscribing ? "none" : "block",
                whiteSpace: "nowrap", paddingRight: 4,
              }}>
                Voice
              </span>
              <span style={{
                fontSize: 9.5, color: t.colors.textMuted, opacity: 0.4,
                display: input.trim().length > 0 ? "none" : "block",
                whiteSpace: "nowrap", paddingRight: 4,
              }}>
                Shift+↵ new line
              </span>
              <button
                onClick={() => handleSend()}
                disabled={loading || (!input.trim() && !attachedFile)}
                style={{
                  width: 38, height: 38, borderRadius: "50%",
                  background: loading || (!input.trim() && !attachedFile)
                    ? "transparent"
                    : `linear-gradient(135deg, ${t.colors.primary}, ${t.colors.primaryHover})`,
                  color: loading || (!input.trim() && !attachedFile) ? t.colors.textMuted : "#FFFFFF",
                  border: "none", cursor: loading || (!input.trim() && !attachedFile) ? "default" : "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, fontSize: 16, fontWeight: 700,
                  transition: "all 0.2s ease",
                  opacity: loading || (!input.trim() && !attachedFile) ? 0.3 : 1,
                }}
              >
                ↑
              </button>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes dot-bounce {
          0%, 100% { opacity: 0.2; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.15); }
        }
        @keyframes msg-slide-up {
          from { opacity: 0; transform: translateY(14px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes docintel-pulse {
          0%, 100% { transform: scale(1); opacity: 0.7; }
          50% { transform: scale(1.04); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
