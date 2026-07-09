import React, { useEffect, useRef, useState } from "react"
import {
  getDocumentLibrary,
  getMyDocuments,
  createChatSession,
  getChatMessages,
  chatWithDocument,
  chatWithDocumentStream,
  chatGlobally,
  chatGloballyStream,
  setChatSessionModel,
  listChatSessions,
  suggestPrompts,
  transcribeAudio,
  ApiError,
} from "../api/client"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { useModel } from "../context/ModelContext"
import { isCloudModel } from "../utils/modelUtils"
import { ModelSelector } from "../components/ModelSelector"

type Message = {
  id: string | number
  role: "user" | "assistant" | "system"
  content: string
  citations: { filename: string; chunk_index: number; text: string }[]
  status: "pending" | "done" | "failed"
  uiStatus?: "sending" | "waiting" | "streaming" | "error"
  retryText?: string
}

type DocumentItem = { id: string; filename: string; status: string }
type SessionItem = { session_id: string; title?: string; updated_at?: string }

const SUGGESTED_PROMPTS = [
  "Summarize the selected documents",
  "What are the key entities and topics?",
  "Compare findings across all selected documents",
  "Extract action items and decisions",
]

export const AnalyzeChatPage: React.FC = () => {
  const { theme: themeName, isDark } = useTheme()
  const t = getTokens(themeName)

  const chatScrollRef = useRef<HTMLDivElement>(null)

  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [docsError, setDocsError] = useState<string | null>(null)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const { selectedModel, setSelectedModel, availableModels, modelCapabilities, modelDetails, loading: loadingModels, setModelForTask, v2Providers } = useModel()

  // On mount, ensure we have the best model for document analysis / RAG
  useEffect(() => {
    if (!loadingModels && !selectedModel) {
      setModelForTask("rag")
    }
  }, [loadingModels, selectedModel, setModelForTask])
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState("")
  const [loadingChat, setLoadingChat] = useState(false)
  const [info, setInfo] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [isSessionMenuOpen, setIsSessionMenuOpen] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false)

  const sessionMenuRef = useRef<HTMLDivElement>(null)
  const [docSearch, setDocSearch] = useState("")
  const [suggestedPrompts, setSuggestedPrompts] = useState<string[]>(SUGGESTED_PROMPTS)

  const isWaiting = loadingChat || messages.some((m) => m.uiStatus === "waiting")

  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

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
        setQuestion(text)
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

  useEffect(() => {
    const load = async () => {
      try {
        setLoadingDocs(true)
        setDocsError(null)
        const res = await getMyDocuments(1, 5)
        const docs: DocumentItem[] = res.documents || []
        setDocuments(docs)
      } catch (e: any) {
        setDocsError(e.message ?? "Failed to load documents")
      } finally {
        setLoadingDocs(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!docSearch.trim()) {
      getMyDocuments(1, 5).then((res) => {
        const docs: DocumentItem[] = res.documents || []
        setDocuments(docs)
      }).catch(() => {})
    } else {
      getDocumentLibrary({ search: docSearch, page_size: 200 }).then((res) => {
        const docs: DocumentItem[] = res.documents || res.items || []
        setDocuments(docs)
      }).catch(() => {})
    }
  }, [docSearch])

  useEffect(() => {
    if (selectedDocIds.length === 0) { setSuggestedPrompts(SUGGESTED_PROMPTS); return }
    const id = selectedDocIds[selectedDocIds.length - 1]
    suggestPrompts(id).then((res) => {
      if (res.prompts && res.prompts.length > 0) setSuggestedPrompts(res.prompts)
    }).catch(() => {})
  }, [selectedDocIds])

  useEffect(() => {
    if (!chatScrollRef.current) return
    chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    const styleId = "analyze-chat-anim"
    if (document.getElementById(styleId)) return
    const style = document.createElement("style")
    style.id = styleId
    style.textContent = [
      "@keyframes dot-bounce {",
      "  0%, 80%, 100% { transform: scale(0.3); opacity: 0.4; }",
      "  40% { transform: scale(1); opacity: 1; }",
      "}",
      ".typing-dot {",
      "  display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin: 0 2px;",
      "  animation: dot-bounce 1.4s infinite ease-in-out both;",
      "}",
      ".typing-dot:nth-child(1) { animation-delay: 0s; }",
      ".typing-dot:nth-child(2) { animation-delay: 0.2s; }",
      ".typing-dot:nth-child(3) { animation-delay: 0.4s; }",
      "@keyframes skeleton-pulse {",
      "  0%, 100% { opacity: 0.4; }",
      "  50% { opacity: 0.7; }",
      "}",
      ".skeleton-line {",
      "  border-radius: 4px; animation: skeleton-pulse 1.5s infinite ease-in-out;",
      "}",
      "@keyframes pulse {",
      "  0%, 100% { transform: scale(1); opacity: 1; }",
      "  50% { transform: scale(1.05); opacity: 0.7; }",
      "}",
    ].join("\n")
    document.head.appendChild(style)
    return () => {
      document.getElementById(styleId)?.remove()
    }
  }, [])

  useEffect(() => {
    if (!isSessionMenuOpen) return
    const handler = (e: MouseEvent) => {
      if (sessionMenuRef.current && !sessionMenuRef.current.contains(e.target as Node)) {
        setIsSessionMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [isSessionMenuOpen])

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    )
    setSessionId(null)
    setMessages([])
  }

  const selectAll = () => {
    setSelectedDocIds(documents.map((d) => d.id))
    setSessionId(null)
    setMessages([])
  }

  const clearSelection = () => {
    setSelectedDocIds([])
    setSessionId(null)
    setMessages([])
  }

  const loadSessions = async () => {
    try {
      setIsSessionMenuOpen(true)
      setSessionLoading(true)
      const res = await listChatSessions(undefined, 50)
      setSessions(res.sessions || [])
    } catch {
      setSessions([])
    } finally {
      setSessionLoading(false)
    }
  }

  const selectSession = async (sid: string) => {
    if (!sid) return
    setIsSessionMenuOpen(false)
    setSessionId(sid)
    setError(null)
    setInfo(null)
    try {
      const history = await getChatMessages(sid, 1000)
      setMessages(history.messages || [])
    } catch (e: any) {
      setInfo(e.message ?? "Failed to load session")
    }
  }

  const handleModelChange = async (model: string) => {
    if (!model || model === selectedModel) {
      return
    }
    setSelectedModel(model)
    if (sessionId) {
      try {
        await setChatSessionModel(sessionId, model)
      } catch (e: any) {
        setInfo(e.message ?? "Failed to set model")
      }
    }
  }

  const send = async (overrideText?: string) => {
    const text = (overrideText ?? question).trim()
    if (!text || isWaiting) return
    if (selectedDocIds.length === 0) {
      setError("Select at least one document first")
      return
    }

    const ts = Date.now()
    const userMsgId = `user_${ts}`
    const thinkingId = `thinking_${ts}`

    setQuestion("")
    setError(null)
    setInfo(null)
    setLoadingChat(true)
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        content: text,
        citations: [],
        status: "pending",
        uiStatus: "sending",
      },
      {
        id: thinkingId,
        role: "assistant",
        content: "",
        citations: [],
        status: "pending",
        uiStatus: "waiting",
      },
    ])

    const replaceWithError = (errMsg: string) => {
      setMessages((prev) => [
        ...prev
          .filter((m) => m.id !== thinkingId)
          .map((m) =>
            m.id === userMsgId ? ({ ...m, uiStatus: "error" }) : m,
          ),
        {
          id: `err_${ts}`,
          role: "system",
          content: errMsg,
          citations: [],
          status: "failed",
          uiStatus: "error",
          retryText: text,
        },
      ])
    }

    try {
      let sid = sessionId
      if (!sid) {
        const isSingle = selectedDocIds.length === 1
        const created = await createChatSession(
          isSingle ? selectedDocIds[0] : null,
          isSingle ? "document" : "global",
        )
        sid = created.session_id
        setSessionId(sid)
      }

      const payload = {
        question: text,
        session_id: sid,
        model: selectedModel || undefined,
        scope: (selectedDocIds.length === 1 ? "project" : "all") as "project" | "all",
      }

      const isCloudModelFlag = isCloudModel(selectedModel, modelDetails)

      if (isCloudModelFlag) {
        const streamCallbacks = {
          onChunk: (chunk: string) => {
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
                  ? { ...m, uiStatus: undefined }
                  : m,
              ),
            )
            setLoadingChat(false)
          },
          onError: (error: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === thinkingId
                  ? { ...m, content: `Error: ${error}`, uiStatus: "error" as const }
                  : m,
              ),
            )
            setLoadingChat(false)
          },
        }
        if (selectedDocIds.length === 1) {
          await chatWithDocumentStream(selectedDocIds[0], payload, streamCallbacks)
        } else {
          await chatGloballyStream(payload, streamCallbacks)
        }
        return
      }

      const res =
        selectedDocIds.length === 1
          ? await chatWithDocument(selectedDocIds[0], payload)
          : await chatGlobally(payload)

      if ("status" in res && (res.status === "queued" || res.status === "pending_analysis")) {
        let attempts = 0
        const wait = async () => {
          try {
            const retryRes = await chatGlobally({
              question: text,
              session_id: sid,
              pending_message_id: (res as any).pending_message_id,
              model: selectedModel || undefined,
            } as any)
            if (!("status" in retryRes)) {
              const history = await getChatMessages(sid, 100)
              setMessages(history.messages)
            }
            setLoadingChat(false)
          } catch (pollErr: any) {
            if (attempts < 30) {
              attempts++
              window.setTimeout(wait, 2000)
            } else {
              replaceWithError("Request timed out. Please try again.")
              setLoadingChat(false)
            }
          }
        }
        window.setTimeout(wait, (res as any).retry_after_ms ?? 2000)
        return
      }

      const history = await getChatMessages(sid, 100)
      setMessages(history.messages)
    } catch (e: any) {
      if (e instanceof ApiError) {
        if (e.status === 403) {
          replaceWithError("You don't have access to this resource. Contact your administrator for permissions.")
        } else if (e.status === 404) {
          replaceWithError("Document not found. It may have been deleted or you may not have access.")
        } else {
          replaceWithError(e?.message ?? "Failed to get a response")
        }
      } else {
        replaceWithError(e?.message ?? "Failed to get a response")
      }
    } finally {
      setLoadingChat(false)
    }
  }

  const retryMessage = (retryText: string, errId: string | number) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === errId)
      if (idx < 0) return prev
      const filtered = prev.filter((m) => m.id !== errId)
      if (idx > 0 && filtered[idx - 1]?.uiStatus === "error" && filtered[idx - 1]?.role === "user") {
        return filtered.filter((_, i) => i !== idx - 1)
      }
      return filtered
    })
    setQuestion(retryText)
  }

  const keyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const modelLabel = (m: string) => {
    const parts = m.split(":")
    return parts[parts.length - 1]?.replace(/-/g, " ") || m
  }

  const colors = t.colors

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: "0 auto", fontFamily: t.font.sans, color: colors.text }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 24px 0" }}>
        Ask Documents
      </h1>

      {/* Document Selector */}
      <div style={{
        backgroundColor: colors.cardBg,
        borderRadius: 12,
        border: `1px solid ${colors.border}`,
        padding: 16,
        marginBottom: 16,
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>
            Documents ({selectedDocIds.length} selected)
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={selectAll} style={btnSmStyle(colors)}>Select All</button>
            <button onClick={clearSelection} style={btnSmStyle(colors)}>Clear</button>
          </div>
        </div>

        {loadingDocs && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-line" style={{
                height: 28, width: `${60 + i * 12}%`,
                backgroundColor: colors.surface,
              }} />
            ))}
          </div>
        )}

        {docsError && (
          <div style={{ color: colors.error, fontSize: 13, padding: "8px 0" }}>
            {docsError}
          </div>
        )}

        {!loadingDocs && !docsError && (
          <>
            <input
              type="text"
              placeholder="Search documents..."
              value={docSearch}
              onChange={(e) => setDocSearch(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${colors.border}`,
                backgroundColor: colors.inputBg,
                color: colors.text,
                fontSize: 13,
                marginBottom: 8,
                outline: "none",
                boxSizing: "border-box",
                fontFamily: "inherit",
              }}
            />
            {documents.length === 0 ? (
              <div style={{ color: colors.textMuted, fontSize: 13, padding: "8px 0" }}>
                {docSearch ? "No documents match your search." : "No documents available. Upload documents to get started."}
              </div>
            ) : (
              <div style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                maxHeight: 160,
                overflowY: "auto",
              }}>
                {documents
                  .filter((d) => !docSearch.trim() || d.filename.toLowerCase().includes(docSearch.toLowerCase()))
                  .map((doc) => {
                const checked = selectedDocIds.includes(doc.id)
                return (
                  <label
                    key={doc.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "6px 12px",
                      borderRadius: 8,
                      backgroundColor: checked ? colors.surfaceActive : colors.surface,
                      border: `1px solid ${checked ? colors.borderFocus : colors.border}`,
                      cursor: "pointer",
                      fontSize: 13,
                      userSelect: "none",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleDoc(doc.id)}
                      style={{ accentColor: colors.primary }}
                    />
                    {doc.filename}
                  </label>
                )
                  })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Top toolbar: model + sessions */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div style={{ width: "280px" }}>
          <ModelSelector
            providers={v2Providers}
            value={selectedModel}
            onChange={(modelId) => handleModelChange(modelId)}
            placeholder="Select Model"
            disabled={isWaiting}
            selectableOnly={true}
            includeLocalModels={true}
          />
        </div>

        <div style={{ position: "relative" }} ref={sessionMenuRef}>
          <button
            onClick={loadSessions}
            disabled={isWaiting}
            style={{
              ...btnToolbarStyle(colors),
              opacity: isWaiting ? 0.5 : 1,
            }}
          >
            Sessions
            <span style={{ marginLeft: 6, fontSize: 10 }}>&#9660;</span>
          </button>
          {isSessionMenuOpen && (
            <div style={{
              position: "absolute",
              top: 40,
              left: 0,
              minWidth: 280,
              maxHeight: 360,
              overflowY: "auto",
              backgroundColor: isDark ? "#1a1f35" : "#fff",
              border: `1px solid ${colors.border}`,
              borderRadius: 10,
              boxShadow: isDark ? "0 8px 32px rgba(0,0,0,0.5)" : "0 8px 32px rgba(0,0,0,0.1)",
              zIndex: 1000,
              padding: 6,
            }}>
              {sessionLoading ? (
                <div style={{ padding: 12, fontSize: 13, color: colors.textMuted }}>Loading...</div>
              ) : sessions.length === 0 ? (
                <div style={{ padding: 12, fontSize: 13, color: colors.textMuted }}>No sessions</div>
              ) : (
                sessions.map((s) => (
                  <div
                    key={s.session_id}
                    onClick={() => selectSession(s.session_id)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 6,
                      cursor: "pointer",
                      fontSize: 13,
                      backgroundColor: s.session_id === sessionId ? colors.surfaceActive : "transparent",
                      color: colors.text,
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>
                      {s.title || s.session_id.slice(0, 8) + "..."}
                    </div>
                    {s.updated_at && (
                      <div style={{ fontSize: 11, color: colors.textMuted }}>
                        {new Date(s.updated_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {sessionId && (
          <button
            onClick={() => { setSessionId(null); setMessages([]) }}
            disabled={isWaiting}
            style={{
              ...btnToolbarStyle(colors),
              color: colors.warning,
              borderColor: colors.warning,
            }}
          >
            New Chat
          </button>
        )}

        {info && (
          <span style={{ fontSize: 12, color: colors.textMuted, marginLeft: 8 }}>{info}</span>
        )}
      </div>

      {/* Chat Messages */}
      <div
        ref={chatScrollRef}
        style={{
          backgroundColor: colors.cardBg,
          borderRadius: 12,
          border: `1px solid ${colors.border}`,
          padding: 16,
          minHeight: 300,
          maxHeight: 500,
          overflowY: "auto",
          marginBottom: 12,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.length === 0 && !loadingChat && (
          <div style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: colors.textMuted,
            fontSize: 14,
          }}>
            {selectedDocIds.length === 0
              ? "Select documents and ask a question"
              : "Start the conversation by asking a question"}
          </div>
        )}

        {loadingChat && messages.length === 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[1, 2].map((i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div className="skeleton-line" style={{
                  height: 14, width: "30%", backgroundColor: colors.surface,
                  alignSelf: i === 1 ? "flex-end" : "flex-start",
                }} />
                <div className="skeleton-line" style={{
                  height: 50, width: "70%", backgroundColor: colors.surface,
                  alignSelf: i === 1 ? "flex-end" : "flex-start",
                }} />
              </div>
            ))}
          </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.role === "user"
          const isSystem = msg.role === "system"
          const isThinking = msg.uiStatus === "waiting"
          const bubbleBg = isUser
            ? colors.primary
            : isSystem
              ? "transparent"
              : colors.surface
          const bubbleColor = isUser ? "#fff" : colors.text
          const align = isUser ? "flex-end" : "flex-start"

          return (
            <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: align }}>
              <div style={{
                maxWidth: "80%",
                padding: "10px 16px",
                borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                backgroundColor: bubbleBg,
                color: bubbleColor,
                fontSize: 14,
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                border: isSystem ? `1px solid ${colors.warning}` : undefined,
                opacity: isThinking ? 0.7 : 1,
              }}>
                {isThinking ? (
                  <div style={{ display: "flex", alignItems: "center", padding: "4px 0" }}>
                    <span
                      className="typing-dot"
                      style={{ backgroundColor: colors.textSecondary }}
                    />
                    <span
                      className="typing-dot"
                      style={{ backgroundColor: colors.textSecondary }}
                    />
                    <span
                      className="typing-dot"
                      style={{ backgroundColor: colors.textSecondary }}
                    />
                  </div>
                ) : msg.uiStatus === "streaming" ? (
                  <>
                    {msg.content}
                    <span style={{ display: "inline-block", width: 2, height: "1em", backgroundColor: colors.primary, marginLeft: 2, animation: "streaming-blink 1s step-end infinite", verticalAlign: "text-bottom" }} />
                  </>
                ) : (
                  msg.content || (msg.uiStatus === "sending" ? "Sending..." : "")
                )}
              </div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div style={{
                  marginTop: 6,
                  fontSize: 12,
                  color: colors.textSecondary,
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  alignItems: align,
                }}>
                  {msg.citations.map((cit, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "4px 10px",
                        backgroundColor: colors.surface,
                        borderRadius: 6,
                        border: `1px solid ${colors.border}`,
                        maxWidth: "85%",
                      }}
                    >
                      <strong>{cit.filename}</strong> &mdash; {cit.text.slice(0, 200)}
                      {cit.text.length > 200 ? "..." : ""}
                    </div>
                  ))}
                </div>
              )}

              {/* Retry button for errors */}
              {msg.uiStatus === "error" && msg.retryText && (
                <button
                  onClick={() => retryMessage(msg.retryText!, msg.id)}
                  style={{
                    marginTop: 4,
                    padding: "4px 12px",
                    borderRadius: 6,
                    border: `1px solid ${colors.error}`,
                    backgroundColor: "transparent",
                    color: colors.error,
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  Retry
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* Suggested prompts */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {suggestedPrompts.map((p) => (
          <button
            key={p}
            onClick={() => { setQuestion(p); send(p) }}
            disabled={isWaiting || selectedDocIds.length === 0}
            style={{
              padding: "7px 14px",
              borderRadius: 20,
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.surface,
              color: colors.textSecondary,
              fontSize: 12,
              cursor: isWaiting || selectedDocIds.length === 0 ? "not-allowed" : "pointer",
              opacity: isWaiting || selectedDocIds.length === 0 ? 0.4 : 1,
              fontFamily: "inherit",
              transition: "all 0.15s ease",
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input / send */}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={keyDown}
          placeholder={
            selectedDocIds.length === 0
              ? "Select documents to begin..."
              : isTranscribing
              ? "Transcribing voice..."
              : "Ask a question about the selected documents..."
          }
          disabled={isWaiting || isTranscribing || selectedDocIds.length === 0}
          style={{
            flex: 1,
            padding: "12px 16px",
            borderRadius: 12,
            border: `1px solid ${colors.border}`,
            backgroundColor: colors.inputBg,
            color: colors.text,
            fontSize: 14,
            fontFamily: "inherit",
            outline: "none",
            opacity: isWaiting || selectedDocIds.length === 0 ? 0.5 : 1,
          }}
        />
        {isTranscribing && (
          <div style={{
            fontSize: 12, color: colors.primary, whiteSpace: "nowrap",
            animation: "pulse 1.5s ease-in-out infinite",
          }}>
            Transcribing...
          </div>
        )}
        <button
          onClick={toggleRecording}
          disabled={isTranscribing}
          title={isRecording ? "Stop recording" : "Record voice message"}
          style={{
            width: 42, height: 42, borderRadius: "50%",
            background: isRecording ? "#EF4444" : colors.primary,
            color: "#FFFFFF",
            border: "none",
            cursor: isTranscribing ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0, fontSize: 16,
            transition: "all 0.2s ease",
            opacity: isTranscribing ? 0.5 : 1,
          }}
        >
          {isRecording ? "⏹" : "🎙"}
        </button>
        <button
          onClick={send}
          disabled={isWaiting || !question.trim() || selectedDocIds.length === 0}
          style={{
            padding: "12px 24px",
            borderRadius: 12,
            border: "none",
            backgroundColor: colors.primary,
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            cursor: isWaiting || !question.trim() || selectedDocIds.length === 0 ? "not-allowed" : "pointer",
            opacity: isWaiting || !question.trim() || selectedDocIds.length === 0 ? 0.5 : 1,
            fontFamily: "inherit",
            transition: "all 0.15s ease",
          }}
        >
          Send
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 12, padding: "8px 14px", borderRadius: 8, backgroundColor: isDark ? "rgba(239,68,68,0.15)" : "rgba(220,38,38,0.1)", color: colors.error, fontSize: 13 }}>
          {error}
        </div>
      )}
    </div>
  )
}

function btnSmStyle(c: ReturnType<typeof getTokens>["colors"]): React.CSSProperties {
  return {
    padding: "4px 12px",
    borderRadius: 6,
    border: `1px solid ${c.border}`,
    backgroundColor: c.surface,
    color: c.textSecondary,
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  }
}

function btnToolbarStyle(c: ReturnType<typeof getTokens>["colors"]): React.CSSProperties {
  return {
    padding: "7px 14px",
    borderRadius: 8,
    border: `1px solid ${c.border}`,
    backgroundColor: c.surface,
    color: c.text,
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
    display: "flex",
    alignItems: "center",
    gap: 4,
  }
}
