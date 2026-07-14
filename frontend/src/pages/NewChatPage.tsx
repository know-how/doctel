import React, { useState, useEffect, useRef } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { chatGlobally, chatGloballyStream, createChatSession, getChatMessages, setChatSessionModel, transcribeAudio, askVision, uploadDocumentWithProgress, getRandomPromptSuggestions, PromptSuggestion } from "../api/client"
import { useModel } from "../context/ModelContext"
import { ChatHeader, WelcomeScreen, ChatMessage, ChatInput } from "../components"
import type { Message, Citation, AttachmentMeta } from "../components/ChatMessage"
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

export const NewChatPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
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
  const [promptSuggestions, setPromptSuggestions] = useState<PromptSuggestion[]>([])
  const [loadingPrompts, setLoadingPrompts] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { selectedModel: model, setSelectedModel: setModel, availableModels: models, modelCapabilities, modelLabels, modelDetails, loading: loadingModels, setModelForTask, v2Providers, taskDefaults } = useModel()

  // Load random prompt suggestions on mount
  useEffect(() => {
    const loadPrompts = async () => {
      setLoadingPrompts(true)
      try {
        // Get model capabilities to filter prompts
        const capabilities: string[] = []
        if (model) {
          const caps = modelCapabilities[model]
          if (caps?.includes("vision")) capabilities.push("vision")
          if (caps?.includes("audio")) capabilities.push("audio")
          if (caps?.includes("code")) capabilities.push("code")
        }
        
        const response = await getRandomPromptSuggestions(6)
        setPromptSuggestions(response.suggestions)
      } catch (e) {
        console.warn("Failed to load prompt suggestions:", e)
        // Fallback to empty array - will show default UI
        setPromptSuggestions([])
      } finally {
        setLoadingPrompts(false)
      }
    }
    
    loadPrompts()
  }, [model, modelCapabilities])

  // On mount, apply Task Mapping for chat — wait until both loading is done
  // AND taskDefaults are populated to prevent the "empty defaults" race.
  useEffect(() => {
    if (!loadingModels && Object.keys(taskDefaults).length > 0) {
      setModelForTask("chat")
    }
  }, [loadingModels, taskDefaults])

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

      const cloudModel = isCloudModel(model, modelDetails, v2Providers)

      // Always use streaming for any model found in the V2 provider catalog.
      // Non-V2 (pure Ollama/local) models can use the non-streaming endpoint.
      if (cloudModel) {
        await chatGloballyStream(
          {
            question: q,
            session_id: sid,
            model: model || undefined,
            scope: "all",
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
        reasoning: m.reasoning ?? undefined,
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

      {/* Header - Professional Enterprise Layout */}
      <ChatHeader t={t} model={model} modelLabels={modelLabels} modelCapabilities={modelCapabilities} messagesLength={messages.length} onModelChange={(id) => { handleModelChange(id); setCapabilityWarning(null); }} models={models} v2Providers={v2Providers} disabled={models.length===0} />

      {/* Messages area */}
      <div style={{
        flex: 1, overflowY: "auto", position: "relative", zIndex: 2,
        padding: showWelcome ? "0 40px" : `${t.spacing.xl}px 40px ${t.spacing.lg}px`,
        display: "flex", flexDirection: "column",
      }}>
        {/* Welcome screen — extracted component */}
        <WelcomeScreen t={t} isDark={isDark} promptSuggestions={promptSuggestions} loadingPrompts={loadingPrompts} onSend={handleSend} />

        {/* Chat history — extracted component */}
        <div style={{maxWidth: 860, width: "100%", margin: "0 auto", display: "flex", flexDirection: "column"}}>
          {messages.map((msg, i) => (
            <ChatMessage key={msg.id || i} msg={msg} prevMsg={i > 0 ? messages[i-1] : undefined} t={t} isDark={isDark} onRetry={handleRetry} renderContent={renderContent} formatTime={formatTime} formatDate={formatDate} />
          ))}
          <div ref={chatEndRef} style={{height: 20}} />
        </div>
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

      {/* Input area — extracted component */}
      <ChatInput t={t} loading={loading} input={input} onInputChange={setInput} onSend={handleSend} isRecording={isRecording} isTranscribing={isTranscribing} onToggleRecording={toggleRecording} onAttachFile={handleAttachFile} model={model} />

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
