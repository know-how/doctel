import React, { useEffect, useRef, useState } from "react"
import { MermaidView } from "../components/MermaidView"
import {
  DocumentAnalysisResponse,
  ChatMessage,
  SummaryHistoryEntry,
} from "../types/api"
import {
  getDocumentAnalysis,
  getDocumentPrompts,
  suggestPrompts,
  chatWithDocument,
  chatGlobally,
  getSummaryHistory,
  uploadDocument,
  getProjects,
  downloadDocumentFile,
  getIngestStatus,
  retryIngest,
  createChatSession,
  getChatMessages,
  listChatSessions,
  getAvailableModels,
  setChatSessionModel,
  startModelPull,
  getModelPullStatus,
  getBootstrapStatus,
  getUiSettings,
  ApiError,
  flowchartGenerate,
  chartsAnalyze,
  chartsBuild,
} from "../api/client"
import { colors } from "../theme/colors"

interface DocumentViewPageProps {
  documentId: string | null
  isAuthenticated: boolean
  authEpoch: number
}

type UIMessageStatus = "idle" | "sending" | "waiting" | "success" | "error"
type UIChatMessage = Omit<ChatMessage, "id"> & {
  id: string | number
  uiStatus?: UIMessageStatus
  retryText?: string
}

const GLOBAL_CHAT_SESSION_KEY = "docintel_chat_session_global"
const GLOBAL_SUGGESTED_PROMPTS = [
  "What are the main ZETDC governance, compliance, and operational priorities I should know?",
  "Summarize what internal knowledge says about this topic and note any conflicting guidance.",
  "Search the web if needed and give me the latest external guidance in plain language.",
  "Use transferred learning and organizational context to suggest the best next steps.",
]

function renderRichContent(apiBaseUrl: string, content: string) {
  const text = String(content || "")
  const chartMatch = text.match(/Chart generated:\s*(\/api\/charts\/[^\s]+)/i)
  const chartUrl = chartMatch ? chartMatch[1] : null

  if (text.includes("```")) {
    const blocks: React.ReactNode[] = []
    const parts = text.split("```")
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (i % 2 === 0) {
        if (part.trim()) {
          blocks.push(<div key={`t_${i}`} style={{ whiteSpace: "pre-wrap" }}>{part}</div>)
        }
      } else {
        const firstNl = part.indexOf("\n")
        const lang = (firstNl >= 0 ? part.slice(0, firstNl) : "").trim().toLowerCase()
        const code = (firstNl >= 0 ? part.slice(firstNl + 1) : part).trim()
        if (lang === "mermaid") {
          blocks.push(
            <div key={`m_${i}`} style={{ marginTop: 8 }}>
              <MermaidView code={code} />
            </div>,
          )
        } else {
          blocks.push(
            <pre
              key={`c_${i}`}
              style={{
                margin: 0,
                padding: 12,
                borderRadius: 12,
                backgroundColor: "#0F172A",
                color: "#E2E8F0",
                fontSize: 12,
                overflowX: "auto",
                whiteSpace: "pre",
              }}
            >
              {code}
            </pre>,
          )
        }
      }
    }
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {blocks}
        {chartUrl && (
          <img
            alt="chart"
            src={`${apiBaseUrl}${chartUrl}`}
            style={{ maxWidth: "100%", borderRadius: 12, border: "1px solid rgba(148,163,184,0.18)" }}
          />
        )}
      </div>
    )
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ whiteSpace: "pre-wrap" }}>{text}</div>
      {chartUrl && (
        <img
          alt="chart"
          src={`${apiBaseUrl}${chartUrl}`}
          style={{ maxWidth: "100%", borderRadius: 12, border: "1px solid rgba(148,163,184,0.18)" }}
        />
      )}
    </div>
  )
}

export const DocumentViewPage: React.FC<DocumentViewPageProps> = ({
  documentId,
  isAuthenticated,
  authEpoch,
}) => {
  const apiBaseUrl =
    (import.meta as any).env.VITE_API_BASE_URL ?? "http://localhost:8000"
  const [activeDocumentId, setActiveDocumentId] = useState(documentId)
  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null)
  const [prompts, setPrompts] = useState<string[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chatMessages, setChatMessages] = useState<UIChatMessage[]>([])
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const [summaryHistory, setSummaryHistory] = useState<SummaryHistoryEntry[]>([])
  const [question, setQuestion] = useState("")
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [loadingChat, setLoadingChat] = useState(false)
  const [chatInfo, setChatInfo] = useState<string | null>(null)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [installedModels, setInstalledModels] = useState<string[]>([])
  const [modelsOffline, setModelsOffline] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string>("")
  const [searchScope, setSearchScope] = useState<"project" | "all">("project")
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false)
  const [isScopeMenuOpen, setIsScopeMenuOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [historyQuery, setHistoryQuery] = useState("")
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historySessions, setHistorySessions] = useState<
    { session_id: string; title?: string; updated_at?: string; scope?: string; model?: string; document_id?: string | null }[]
  >([])
  const [isDiagramOpen, setIsDiagramOpen] = useState(false)
  const [diagramText, setDiagramText] = useState("")
  const [diagramMermaid, setDiagramMermaid] = useState<string | null>(null)
  const [isChartOpen, setIsChartOpen] = useState(false)
  const [chartFile, setChartFile] = useState<File | null>(null)
  const [chartColumns, setChartColumns] = useState<string[]>([])
  const [chartNumeric, setChartNumeric] = useState<string[]>([])
  const [chartX, setChartX] = useState<string>("")
  const [chartY, setChartY] = useState<string[]>([])
  const [chartType, setChartType] = useState<string>("bar")
  const [chartUrl, setChartUrl] = useState<string | null>(null)
  const [chartRows, setChartRows] = useState<any[]>([])
  const [isPullOpen, setIsPullOpen] = useState(false)
  const [pullModel, setPullModel] = useState<string>("")
  const [pullLogs, setPullLogs] = useState<string[]>([])
  const [pullStatus, setPullStatus] = useState<string>("")
  const [pullError, setPullError] = useState<string | null>(null)
  const [pullAttempts, setPullAttempts] = useState(0)
  const [pullPercent, setPullPercent] = useState(0)
  const [pullEta, setPullEta] = useState<number | null>(null)
  const [pullStates, setPullStates] = useState<Record<string, any>>({})
  const [pollIngestMs, setPollIngestMs] = useState(1500)
  const [pollPullMs, setPollPullMs] = useState(800)
  const [clearOnSend, setClearOnSend] = useState(true)
  const pendingAskRef = useRef<{ documentId: string; text: string } | null>(null)
  const [bootstrapRunning, setBootstrapRunning] = useState(false)
  const [bootstrapPercent, setBootstrapPercent] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [ingestStatus, setIngestStatus] = useState<{
    status: string
    step: string
    percent: number
    message: string
    error_message?: string
    updated_at: string
  } | null>(null)
  const [metadataFile, setMetadataFile] = useState<File | null>(null)
  const [projects, setProjects] = useState<
    { id: string; name: string; document_count: number }[]
  >([])
  const [selectedProjectId, setSelectedProjectId] = useState("")
  const [newProjectName, setNewProjectName] = useState("")
  const [metadataDocumentType, setMetadataDocumentType] = useState("")
  const [metadataDocumentDate, setMetadataDocumentDate] = useState("")
  const [isMetadataOpen, setIsMetadataOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 768 : false,
  )
  const sessionStorageKey = activeDocumentId
    ? `docintel_chat_session_${activeDocumentId}`
    : GLOBAL_CHAT_SESSION_KEY
  const effectiveSearchScope: "project" | "all" = activeDocumentId ? searchScope : "all"

  useEffect(() => {
    setActiveDocumentId(documentId)
    if (!documentId) {
      setAnalysis(null)
      setPrompts(GLOBAL_SUGGESTED_PROMPTS)
      setSessionId(null)
      setChatMessages([])
      setSummaryHistory([])
      setQuestion("")
      setChatInfo(null)
      setIngestStatus(null)
      setError(null)
      setLoadingAnalysis(false)
      setLoadingChat(false)
    }
  }, [documentId])

  useEffect(() => {
    const key = sessionStorageKey
    const stored =
      typeof window !== "undefined" ? window.localStorage.getItem(key) : null
    setSessionId(stored)
    setChatMessages([])
    setChatInfo(null)
  }, [sessionStorageKey])

  const openHistory = async () => {
    try {
      setIsHistoryOpen(true)
      setHistoryLoading(true)
      const res = await listChatSessions(undefined, 50)
      setHistorySessions(res.sessions || [])
    } catch {
      setHistorySessions([])
    } finally {
      setHistoryLoading(false)
    }
  }

  const selectConversation = async (sid: string) => {
    if (!sid) return
    setIsHistoryOpen(false)
    setHistoryQuery("")
    setSessionId(sid)
    try {
      window.localStorage.setItem(sessionStorageKey, sid)
    } catch {
    }
    try {
      const history = await getChatMessages(sid, 1000)
      setChatMessages(history.messages)
    } catch (e: any) {
      setChatInfo(e.message ?? "Failed to load conversation")
    }
  }

  const openDiagram = () => {
    const seed =
      (analysis?.executive_summary || "").trim() ||
      (analysis?.detailed_summary || []).slice(0, 6).join("\n")
    setDiagramText(seed || "Describe the process you want to draw.")
    setDiagramMermaid(null)
    setIsDiagramOpen(true)
  }

  const buildDiagram = async () => {
    try {
      setError(null)
      const res = await flowchartGenerate({ text: diagramText })
      setDiagramMermaid(res.mermaid)
      setChatMessages((prev) => [
        ...prev,
        {
          id: `assistant_${Date.now()}`,
          role: "assistant",
          content: res.mermaid,
          status: "done",
          citations: [],
          created_at: "",
        },
      ])
    } catch (e: any) {
      setError(e.message ?? "Failed to generate diagram")
    }
  }

  const openChart = () => {
    setChartFile(null)
    setChartColumns([])
    setChartNumeric([])
    setChartX("")
    setChartY([])
    setChartUrl(null)
    setChartRows([])
    setIsChartOpen(true)
  }

  const parseCsvQuick = async (file: File) => {
    const text = await file.text()
    const lines = text.split(/\r?\n/).filter((l) => l.trim())
    if (lines.length < 2) return []
    const headers = lines[0].split(",").map((h) => h.trim())
    const rows: any[] = []
    for (const line of lines.slice(1, 201)) {
      const parts = line.split(",")
      const row: any = {}
      headers.forEach((h, i) => (row[h] = (parts[i] ?? "").trim()))
      rows.push(row)
    }
    return rows
  }

  const onChartFile = async (f: File) => {
    setChartFile(f)
    setChartUrl(null)
    try {
      const [meta, rows] = await Promise.all([chartsAnalyze(f), parseCsvQuick(f)])
      setChartColumns(meta.columns || [])
      setChartNumeric(meta.numeric_columns || [])
      setChartRows(rows || [])
      const suggestedX = (meta.columns || []).find((c) => !(meta.numeric_columns || []).includes(c)) || (meta.columns || [])[0] || ""
      const suggestedY = (meta.numeric_columns || []).slice(0, 2)
      setChartX(suggestedX)
      setChartY(suggestedY)
    } catch (e: any) {
      setError(e.message ?? "Failed to analyze CSV")
    }
  }

  const buildChart = async () => {
    if (!sessionId) {
      setError("No active conversation. Start a conversation first.")
      return
    }
    if (!chartX || chartY.length === 0 || chartRows.length === 0) {
      setError("Select X and at least one Y series.")
      return
    }
    try {
      setError(null)
      const res = await chartsBuild({
        session_id: sessionId,
        chart_type: chartType,
        title: `${chartType.toUpperCase()} chart`,
        x: chartX,
        y: chartY,
        data: chartRows,
      })
      setChartUrl(res.url)
      setChatMessages((prev) => [
        ...prev,
        {
          id: `assistant_${Date.now()}`,
          role: "assistant",
          content: `Chart generated: ${res.url}`,
          status: "done",
          citations: [],
          created_at: "",
        },
      ])
    } catch (e: any) {
      setError(e.message ?? "Failed to build chart")
    }
  }

  useEffect(() => {
    if (!isAuthenticated) return
    const loadModels = async () => {
      try {
        const res = await getAvailableModels()
        const models = (res.available ?? res.models ?? []) as string[]
        const installed = (res.installed ?? []) as string[]
        setAvailableModels(models)
        setInstalledModels(installed)
        const offline = Boolean(res.offline)
        setModelsOffline(offline)
        const stored =
          typeof window !== "undefined"
            ? window.localStorage.getItem("docintel_model_preference")
            : null
        const fallback = res.default_model || models[0] || ""
        const allowed = offline ? installed : models
        const selected =
          stored && allowed.includes(stored)
            ? stored
            : allowed.includes(fallback)
              ? fallback
              : allowed[0] || fallback
        setSelectedModel(selected)
        if (selected && typeof window !== "undefined") {
          window.localStorage.setItem("docintel_model_preference", selected)
        }
      } catch (e: any) {
        setChatInfo(e.message ?? "Failed to load model list")
      }
    }
    loadModels()
  }, [isAuthenticated, authEpoch])

  useEffect(() => {
    if (!isAuthenticated) return
    const loadUi = async () => {
      try {
        const ui = await getUiSettings()
        const ingest = Number(ui?.poll?.ingest_ms)
        const pull = Number(ui?.poll?.pull_ms)
        if (Number.isFinite(ingest) && ingest > 200) setPollIngestMs(ingest)
        if (Number.isFinite(pull) && pull > 200) setPollPullMs(pull)
        if (typeof ui?.clear_input_on_send === "boolean") setClearOnSend(ui.clear_input_on_send)
      } catch {
      }
    }
    loadUi()
  }, [isAuthenticated, authEpoch])

  useEffect(() => {
    if (!isAuthenticated) return
    let timer: number | null = null
    let cancelled = false
    const poll = async () => {
      try {
        const s = await getBootstrapStatus()
        if (cancelled) return
        setBootstrapRunning(Boolean(s.running))
        setBootstrapPercent(Number.isFinite(s.percent) ? s.percent : 0)
        if (s.running && timer == null) {
          timer = window.setInterval(poll, 2000)
        }
        if (!s.running && timer != null) {
          window.clearInterval(timer)
          timer = null
        }
      } catch {
      }
    }
    poll()
    return () => {
      cancelled = true
      if (timer != null) window.clearInterval(timer)
    }
  }, [isAuthenticated, authEpoch])

  useEffect(() => {
    const loadChat = async () => {
      if (!isAuthenticated) return
      try {
        setChatInfo(null)
        let sid = sessionId
        if (!sid) {
          if (!activeDocumentId) return
          const created = await createChatSession(activeDocumentId, "document")
          sid = created.session_id
          setSessionId(sid)
          if (typeof window !== "undefined") {
            window.localStorage.setItem(sessionStorageKey, sid)
          }
        }
        const history = await getChatMessages(sid, 100)
        setChatMessages(history.messages)
      } catch (e: any) {
        setChatInfo(e.message ?? "Failed to load chat history")
      }
    }
    loadChat()
  }, [activeDocumentId, sessionId, isAuthenticated, authEpoch, sessionStorageKey])

  useEffect(() => {
    const onRestored = async () => {
      try {
        const pending = pendingAskRef.current
        if (pending && pending.documentId === activeDocumentId) {
          pendingAskRef.current = null
          await handleAsk(pending.text)
        }
        if (sessionId) {
          const history = await getChatMessages(sessionId, 100)
          setChatMessages(history.messages)
        }
        const models = await getAvailableModels()
        setAvailableModels((models.available ?? models.models ?? []) as string[])
        setInstalledModels((models.installed ?? []) as string[])
        setModelsOffline(Boolean(models.offline))
      } catch {
      }
    }
    window.addEventListener("docintel_auth_restored", onRestored as any)

    const onLogout = () => {
      setChatMessages([])
      setSessionId(null)
      setAnalysis(null)
      setSummaryHistory([])
      setPrompts([])
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(sessionStorageKey)
      }
    }
    window.addEventListener("docintel_logout", onLogout as any)

    return () => {
      window.removeEventListener("docintel_auth_restored", onRestored as any)
      window.removeEventListener("docintel_logout", onLogout as any)
    }
  }, [sessionId, activeDocumentId, sessionStorageKey])

  useEffect(() => {
    const load = async () => {
      try {
        if (!isAuthenticated || !activeDocumentId) return
        setLoadingAnalysis(true)
        setError(null)
        const [analysisRes, promptsRes, summaryRes] = await Promise.all([
          getDocumentAnalysis(activeDocumentId),
          suggestPrompts(activeDocumentId).catch(() => getDocumentPrompts(activeDocumentId)),
          getSummaryHistory(),
        ])
        setAnalysis(analysisRes)
        const rawPrompts: string[] = (promptsRes as any).prompts || []
        setPrompts(rawPrompts.length > 0 ? rawPrompts : [
          "Summarize this document in 10 sentences or less.",
          "List the key topics and entities mentioned in this document.",
          "List all action items and decisions mentioned in this document.",
          "Generate a process flow diagram (Mermaid) based on this document.",
          "What are the key requirements, deadlines, and responsibilities mentioned?",
        ])
        setSummaryHistory(summaryRes.history)
        if (analysisRes.status !== "READY") {
          try {
            const s = await getIngestStatus(activeDocumentId)
          if (s.status === "completed" || s.analysis_ready || s.ingestion_completed) {
            setIngestStatus(null)
          } else if (s.status === "failed") {
            setIngestStatus(s)
          } else {
            setIngestStatus(s)
          }
          } catch {
            setIngestStatus(null)
          }
        } else {
          setIngestStatus(null)
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to load document")
      } finally {
        setLoadingAnalysis(false)
      }
    }
    load()

    const onResize = () => {
      if (typeof window === "undefined") return
      setIsMobile(window.innerWidth <= 768)
    }

    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [activeDocumentId, isAuthenticated, authEpoch])

  useEffect(() => {
    if (!activeDocumentId) return
    if (!analysis) return
    if (analysis.status === "READY") return
    if (!isAuthenticated) return

    let cancelled = false
    let pollInterval: number | null = null
    let es: EventSource | null = null

    const stopAll = () => {
      if (pollInterval) {
        window.clearInterval(pollInterval)
        pollInterval = null
      }
      if (es) {
        es.close()
        es = null
      }
    }

    const refreshAnalysis = async () => {
      const [analysisRes, promptsRes] = await Promise.all([
        getDocumentAnalysis(activeDocumentId),
        suggestPrompts(activeDocumentId).catch(() => getDocumentPrompts(activeDocumentId)),
      ])
      if (cancelled) return
      setAnalysis(analysisRes)
      const refreshedPrompts: string[] = (promptsRes as any).prompts || []
      setPrompts(refreshedPrompts.length > 0 ? refreshedPrompts : [
        "Summarize this document in 10 sentences or less.",
        "List the key topics and entities mentioned in this document.",
        "List all action items and decisions mentioned in this document.",
        "Generate a process flow diagram (Mermaid) based on this document.",
        "What are the key requirements, deadlines, and responsibilities mentioned?",
      ])
      setIngestStatus(null)
    }

    const startPolling = () => {
      if (pollInterval) return
      const startedAt = Date.now()
      pollInterval = window.setInterval(async () => {
        try {
          if (Date.now() - startedAt > 60_000) {
            setChatInfo("Ingestion is taking longer than expected. You can retry ingestion.")
            stopAll()
            return
          }
          const s = await getIngestStatus(activeDocumentId)
          if (cancelled) return
          setIngestStatus(s)
          if (s.status === "completed" || s.analysis_ready || s.ingestion_completed) {
            await refreshAnalysis()
            stopAll()
          } else if (s.status === "failed") {
            setError(s.error_message || "Ingestion failed")
            setChatMessages([])
            setSessionId(null)
            setLoadingChat(false)
            if (typeof window !== "undefined") {
              window.localStorage.removeItem(`docintel_chat_session_${activeDocumentId}`)
            }
            stopAll()
          } else if (s.status === "uploaded" && s.ingestion_started === false) {
            setChatInfo("Ingestion has not started yet. You can retry ingestion.")
            stopAll()
          }
        } catch {
          if (cancelled) return
        }
      }, pollIngestMs)
    }

    try {
      es = new EventSource(
        `${apiBaseUrl}/api/ingest/stream?document_id=${encodeURIComponent(
          activeDocumentId,
        )}`,
      )
      es.onmessage = async (ev) => {
        if (cancelled) return
        try {
          const s = JSON.parse(ev.data)
          setIngestStatus(s)
          if (s.status === "completed" || s.analysis_ready || s.ingestion_completed) {
            await refreshAnalysis()
            stopAll()
          } else if (s.status === "failed") {
            setError(s.error_message || "Ingestion failed")
            setChatMessages([])
            setSessionId(null)
            setLoadingChat(false)
            if (typeof window !== "undefined") {
              window.localStorage.removeItem(`docintel_chat_session_${activeDocumentId}`)
            }
            stopAll()
          }
        } catch {
          startPolling()
        }
      }
      es.onerror = () => {
        startPolling()
      }
    } catch {
      startPolling()
    }

    return () => {
      cancelled = true
      stopAll()
    }
  }, [activeDocumentId, analysis?.status, apiBaseUrl, pollIngestMs, isAuthenticated, authEpoch])

  // Inject CSS animation for typing indicator once
  useEffect(() => {
    const id = "doctel-chat-animations"
    if (!document.getElementById(id)) {
      const style = document.createElement("style")
      style.id = id
      style.textContent = [
        "@keyframes thinking-dot-bounce {",
        "  0%, 80%, 100% { transform: scale(0.3); opacity: 0.4; }",
        "  40% { transform: scale(1); opacity: 1; }",
        "}",
        ".chat-thinking-dot {",
        "  display: inline-block; width: 8px; height: 8px; border-radius: 50%;",
        "  background-color: #94a3b8; margin: 0 3px;",
        "  animation: thinking-dot-bounce 1.4s infinite ease-in-out both;",
        "}",
        ".chat-thinking-dot:nth-child(1) { animation-delay: 0s; }",
        ".chat-thinking-dot:nth-child(2) { animation-delay: 0.2s; }",
        ".chat-thinking-dot:nth-child(3) { animation-delay: 0.4s; }",
      ].join("\n")
      document.head.appendChild(style)
    }
    return () => { document.getElementById(id)?.remove() }
  }, [])

  // Auto-scroll chat to bottom on new messages
  useEffect(() => {
    if (!chatScrollRef.current) return
    chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
  }, [chatMessages])

  const handleRetry = async () => {
    if (!activeDocumentId) return
    try {
      setError(null)
      await retryIngest(activeDocumentId)
      const s = await getIngestStatus(activeDocumentId)
      setIngestStatus(s)
      const analysisRes = await getDocumentAnalysis(activeDocumentId)
      setAnalysis(analysisRes)
    } catch (e: any) {
      setError(e.message ?? "Failed to retry ingestion")
    }
  }

  useEffect(() => {
    if (!isMetadataOpen) return
    const loadProjects = async () => {
      try {
        const res = await getProjects()
        setProjects(res.projects)
      } catch (e: any) {
        setError(e.message ?? "Failed to load projects")
      }
    }
    loadProjects()
  }, [isMetadataOpen])

  const GEMINI_MODEL_ID = "gemini-api"

  const modelLabel = (m: string) => {
    const key = (m || "").toLowerCase()
    if (key === GEMINI_MODEL_ID) return "Gemini 2.5 Flash (API)"
    if (key === "llama3.2:8b-instruct") return "Llama 3.2 — 8B Instruct"
    if (key === "llama3.2:3b-instruct") return "Llama 3.2 — 3B Instruct"
    if (key === "qwen3.5:9b") return "Qwen 3.5 — 9B"
    if (key === "mistral:7b-instruct") return "Mistral 7B Instruct"
    if (key === "llava:7b") return "LLaVA 7B (vision)"
    return m
  }

  const handleModelChange = async (nextModel: string) => {
    if (!nextModel || nextModel === selectedModel) {
      setIsModelMenuOpen(false)
      return
    }
    setSelectedModel(nextModel)
    if (typeof window !== "undefined") {
      window.localStorage.setItem("docintel_model_preference", nextModel)
    }
    setIsModelMenuOpen(false)
    if (!sessionId) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: `sys_model_${Date.now()}`,
          role: "system",
          content: `Model switched to ${nextModel}`,
          status: "done",
          citations: [],
          created_at: "",
        },
      ])
      return
    }
    try {
      await setChatSessionModel(sessionId, nextModel)
      const history = await getChatMessages(sessionId, 100)
      setChatMessages(history.messages)
    } catch (e: any) {
      setChatInfo(e.message ?? "Failed to set model")
    }
  }

  const openPullModal = (model: string) => {
    setPullModel(model)
    setPullLogs([])
    setPullStatus("pending")
    setPullError(null)
    setPullAttempts(0)
    setPullPercent(0)
    setPullEta(null)
    setIsPullOpen(true)
    setIsModelMenuOpen(false)
    window.setTimeout(() => runPull(model), 0)
  }

  const runPull = async (model: string) => {
    if (!model) return
    if (modelsOffline) {
      setPullError("Offline (using installed models only).")
      return
    }
    try {
      const st = await startModelPull(model, true)
      setPullStates((prev) => ({ ...prev, [model]: st }))
      setPullStatus(st.state)
      setPullAttempts(st.attempt || 0)
      setPullPercent(st.percent || 0)
      setPullEta(st.eta_seconds ?? null)
      if (st.last_event) setPullLogs((prev) => (prev.length ? prev : [st.last_event]))
    } catch (e: any) {
      setPullError(e.message ?? String(e))
    }
  }

  useEffect(() => {
    if (!isAuthenticated) return
    const active = Object.entries(pullStates).filter(
      ([, s]) => s && s.state && !["success", "failed"].includes(String(s.state)),
    )
    if (active.length === 0) return
    const interval = window.setInterval(async () => {
      try {
        const updates = await Promise.all(
          active.map(async ([m]) => {
            try {
              return await getModelPullStatus(m)
            } catch {
              return null
            }
          }),
        )
        const next: Record<string, any> = {}
        const anySuccess = updates.some((u) => u && u.state === "success")
        for (let i = 0; i < active.length; i++) {
          const model = active[i][0]
          const st = updates[i]
          if (st) next[model] = st
        }
        if (Object.keys(next).length) {
          setPullStates((prev) => ({ ...prev, ...next }))
        }
        if (anySuccess) {
          const updated = await getAvailableModels()
          const models = (updated.available ?? updated.models ?? []) as string[]
          const installed = (updated.installed ?? []) as string[]
          setAvailableModels(models)
          setInstalledModels(installed)
          setChatInfo("Model installed successfully.")
        }
        const current = pullModel ? next[pullModel] ?? pullStates[pullModel] : null
        if (isPullOpen && pullModel && current) {
          setPullStatus(current.state)
          setPullAttempts(current.attempt || 0)
          setPullPercent(current.percent || 0)
          setPullEta(current.eta_seconds ?? null)
          if (current.error) setPullError(current.error)
          if (current.last_event) {
            setPullLogs((prev) => {
              const last = prev[prev.length - 1]
              if (last === current.last_event) return prev
              return [...prev.slice(-200), current.last_event]
            })
          }
        }
      } catch {
      }
    }, pollPullMs)
    return () => window.clearInterval(interval)
  }, [pullStates, pullModel, isPullOpen, pollPullMs, isAuthenticated, authEpoch])

  // True whenever we are waiting for the backend (blocks new submissions & form controls)
  const isWaiting = loadingChat || chatMessages.some((m) => m.uiStatus === "waiting")

  const handleAsk = async (q: string) => {
    const text = q.trim()
    if (!text || isWaiting || !isAuthenticated) return

    const ts = Date.now()
    const userMsgId = `user_opt_${ts}`
    const thinkingId = `thinking_${ts}`

    // ── Optimistic update: show user bubble + typing indicator immediately ──
    setQuestion("")
    setError(null)
    setChatInfo(null)
    setLoadingChat(true)
    setChatMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user" as const,
        content: text,
        status: "pending" as const,
        uiStatus: "sending" as UIMessageStatus,
        citations: [],
        created_at: "",
      },
      {
        id: thinkingId,
        role: "assistant" as const,
        content: "",
        status: "pending" as const,
        uiStatus: "waiting" as UIMessageStatus,
        citations: [],
        created_at: "",
      },
    ])

    const replaceWithError = (errMsg: string) => {
      setChatMessages((prev) => [
        ...prev
          .filter((m) => m.id !== thinkingId)
          .map((m) =>
            m.id === userMsgId
              ? ({ ...m, uiStatus: "error" as UIMessageStatus } as UIChatMessage)
              : m,
          ),
        {
          id: `err_${ts}`,
          role: "system" as const,
          content: `❌ ${errMsg}`,
          status: "failed" as const,
          uiStatus: "error" as UIMessageStatus,
          citations: [],
          created_at: "",
          retryText: text,
        },
      ])
    }

    try {
      let sid = sessionId
      if (!sid) {
        const created = activeDocumentId
          ? await createChatSession(activeDocumentId, "document")
          : await createChatSession(null, "global")
        sid = created.session_id
        setSessionId(sid)
        if (typeof window !== "undefined") {
          window.localStorage.setItem(sessionStorageKey, sid)
        }
      }

      const askPayload = {
        question: text,
        session_id: sid,
        model: selectedModel,
        scope: effectiveSearchScope,
      }
      const res = activeDocumentId
        ? await chatWithDocument(activeDocumentId, askPayload)
        : await chatGlobally(askPayload)

      if ("status" in res && (res.status === "queued" || res.status === "pending_analysis")) {
        // Thinking indicator stays visible — polling removes it on resolve
        let attempts = 0
        const checkStatus = async () => {
          try {
            if (!activeDocumentId) {
              replaceWithError("Global chat could not complete. Try asking again.")
              setLoadingChat(false)
              return
            }
            const status = await getIngestStatus(activeDocumentId)
            if (status.status === "completed" || status.analysis_ready || status.ingestion_completed) {
              const answer = await chatWithDocument(activeDocumentId, {
                question: text,
                session_id: sid!,
                pending_message_id: (res as any).pending_message_id,
                model: selectedModel,
                scope: effectiveSearchScope,
              } as any)
              if (!("status" in answer)) {
                const historyFull = await getChatMessages(sid!, 100)
                setChatMessages(historyFull.messages)
              }
              setLoadingChat(false)
            } else if (status.status === "failed") {
              replaceWithError("Ingestion failed. The document could not be processed.")
              setSessionId(null)
              if (typeof window !== "undefined") {
                window.localStorage.removeItem(sessionStorageKey)
              }
              setLoadingChat(false)
            } else {
              if (attempts < 60) {
                attempts++
                window.setTimeout(checkStatus, 2000)
              } else {
                replaceWithError("Ingestion timed out. Try re-sending the question.")
                setLoadingChat(false)
              }
            }
          } catch (pollErr: any) {
            replaceWithError(pollErr?.message ?? "Failed while waiting for document analysis.")
            setLoadingChat(false)
          }
        }
        window.setTimeout(checkStatus, (res as any).retry_after_ms ?? 2000)
        // finally runs here (sets loadingChat=false) but isWaiting stays true
        // while the thinking bubble is present, blocking new submissions
        return
      }

      // Success: replace optimistic messages with real history from backend
      const history = await getChatMessages(sid, 100)
      setChatMessages(history.messages)
    } catch (e: any) {
      const errStatus = e instanceof ApiError ? e.status : null
      const errCode = e instanceof ApiError ? e.data?.error : null
      if (errStatus === 401 || errCode === "token_expired") {
        pendingAskRef.current = { documentId: activeDocumentId, text }
        setChatMessages((prev) => prev.filter((m) => m.id !== thinkingId))
        setChatInfo("Session expired. Please sign in again. Your message is saved.")
      } else {
        replaceWithError(e?.message ?? "Failed to get a response. Try again.")
      }
    } finally {
      setLoadingChat(false)
    }
  }

  const handleRetryMessage = (retryText: string, errMsgId: string | number) => {
    setChatMessages((prev) => {
      const errIdx = prev.findIndex((m) => m.id === errMsgId)
      if (errIdx < 0) return prev
      return prev.filter((m, i) => {
        if (m.id === errMsgId) return false
        // Also remove the failed user bubble right before the error
        if (i === errIdx - 1 && m.uiStatus === "error" && m.role === "user") return false
        return true
      })
    })
    void handleAsk(retryText)
  }

  const handleViewOriginal = async () => {
    try {
      setError(null)
      const blob = await downloadDocumentFile(activeDocumentId)
      const url = window.URL.createObjectURL(blob)
      window.open(url, "_blank", "noopener,noreferrer")
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000)
    } catch (e: any) {
      setError(e.message ?? "Failed to open document")
    }
  }

  const handleUpload = async (
    fileOverride?: File | null,
    metadataOverride?: {
      project_name?: string
      document_type?: string
      document_date?: string
    },
  ) => {
    const fileToUpload = fileOverride ?? metadataFile
    if (!fileToUpload) return
    try {
      setUploading(true)
      setError(null)
      const resolvedProjectName =
        metadataOverride?.project_name ??
        (selectedProjectId === "new"
          ? newProjectName.trim() || undefined
          : selectedProjectId
            ? projects.find((project) => project.id === selectedProjectId)?.name
            : undefined)

      if (selectedProjectId === "new" && !resolvedProjectName) {
        setError("Project name is required")
        setUploading(false)
        return
      }

      const uploaded = await uploadDocument(fileToUpload, {
        project_name: resolvedProjectName,
        document_type:
          metadataOverride?.document_type ??
          (metadataDocumentType.trim() || undefined),
        document_date:
          metadataOverride?.document_date ??
          (metadataDocumentDate || undefined),
      })
      setActiveDocumentId(uploaded.id)
      setChatMessages([])
      setSessionId(null)
      setQuestion("")
      setMetadataFile(null)
      setSelectedProjectId("")
      setNewProjectName("")
      setMetadataDocumentType("")
      setMetadataDocumentDate("")
      setIsMetadataOpen(false)
    } catch (e: any) {
      setError(e.message ?? "Failed to upload document")
    } finally {
      setUploading(false)
    }
  }

  const analysisPanel = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        overflowY: isMobile ? "visible" : "auto",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ fontWeight: 700, color: colors.textPrimary }}>
          Analysis Dashboard
        </div>
        <div style={{ fontSize: 12, color: colors.textMuted }}>
            {activeDocumentId || "No document selected"}
        </div>
      </div>

        {!activeDocumentId && (
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <span>Get Started</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <p style={{ ...bodyTextStyle, margin: 0 }}>
                No document is selected for this account yet. Open one of your documents from My Work or upload a new document with the + button in the chat bar.
              </p>
              <div style={{ fontSize: 13, color: colors.textMuted }}>
                Your workspace is user-specific, so documents uploaded by other users will not appear here.
              </div>
            </div>
          </div>
        )}

      {/* Document Info card — always visible as soon as analysis is loaded */}
      {analysis && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span>Document Info</span>
            {analysis.status === "READY" && (
              <span style={{ ...pillStyle, backgroundColor: "#16A34A" }}>Ready</span>
            )}
            {analysis.status !== "READY" && (
              <span style={{ ...pillStyle, backgroundColor: colors.primary }}>{analysis.status}</span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {analysis.project_name && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>Project</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary }}>
                  {analysis.project_name}
                </span>
              </div>
            )}
            {analysis.filename && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>File</span>
                <span style={{ fontSize: 13, color: colors.textPrimary, wordBreak: "break-all" }}>
                  {analysis.filename}
                </span>
              </div>
            )}
            {analysis.document_type && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>Type</span>
                <span style={{ fontSize: 13, color: colors.textPrimary }}>{analysis.document_type}</span>
              </div>
            )}
            {analysis.document_date && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>Date</span>
                <span style={{ fontSize: 13, color: colors.textPrimary }}>{analysis.document_date}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {loadingAnalysis && (
        <div style={{ color: colors.textMuted }}>Loading analysis…</div>
      )}
      {error && (
        <div style={{ color: colors.danger, fontSize: 13, padding: "8px 12px", borderRadius: 8, backgroundColor: "#FFF0F0", border: "1px solid #FECACA" }}>
          {/* Show a friendly message instead of raw JSON from exceptions */}
          {error.startsWith("{") || error.includes("Server error")
            ? "Analysis could not complete — the AI model returned an error. The document was still ingested and you can use the chat. Retry ingestion to attempt AI analysis again."
            : error}
        </div>
      )}
      {analysis && analysis.status !== "READY" && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span>Processing</span>
            <span style={pillStyle}>{analysis.status}</span>
          </div>
          <div style={{ ...bodyTextStyle, marginBottom: 8 }}>
            {ingestStatus?.message || "Processing document…"}
          </div>
          <div
            style={{
              height: 10,
              borderRadius: 999,
              backgroundColor: colors.border,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.min(100, Math.max(0, ingestStatus?.percent ?? 0))}%`,
                height: "100%",
                backgroundColor: colors.primary,
              }}
            />
          </div>
          {ingestStatus?.error_message && (
            <div style={{ marginTop: 10, color: colors.danger, fontSize: 13 }}>
              {ingestStatus.error_message.startsWith("{") || ingestStatus.error_message.includes("Server error")
                ? "AI model returned an error during analysis. Click Retry Ingestion to try again."
                : ingestStatus.error_message}
            </div>
          )}
          {ingestStatus?.status === "failed" && (
            <button
              type="button"
              onClick={handleRetry}
              style={{
                marginTop: 12,
                padding: "8px 12px",
                borderRadius: 999,
                border: `1px solid ${colors.border}`,
                backgroundColor: "#FFFFFF",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              Retry Ingestion
            </button>
          )}
        </div>
      )}
      {analysis && (
        <>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <span>Quick Actions</span>
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={handleViewOriginal}
                style={{
                  padding: "8px 12px",
                  borderRadius: 999,
                  border: `1px solid ${colors.border}`,
                  backgroundColor: "#FFFFFF",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                View Original Document
              </button>
              {ingestStatus?.status === "failed" && (
                <button
                  type="button"
                  onClick={handleRetry}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 999,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  Retry Ingestion
                </button>
              )}
            </div>
          </div>
          {summaryHistory.length > 0 && (
            <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <span>Summary History</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {summaryHistory.map((entry, idx) => (
                  <div
                    key={`${entry.document_id}-${idx}`}
                    style={{
                      border: `1px solid ${colors.border}`,
                      borderRadius: 10,
                      padding: 10,
                      backgroundColor: "#FFFFFF",
                    }}
                  >
                    <div style={{ fontSize: 12, color: colors.textMuted }}>
                      {entry.document_id} • {new Date(entry.created_at).toLocaleString()}
                    </div>
                    <div style={{ marginTop: 6, ...bodyTextStyle }}>
                      {entry.executive_summary}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {analysis.status === "READY" && <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <span>Executive Summary</span>
                <span style={pillStyle}>AI generated</span>
              </div>
            <p style={bodyTextStyle}>{analysis.executive_summary}</p>
          </div>}

          {analysis.status === "READY" && <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <span>Detailed Summary</span>
            </div>
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {analysis.detailed_summary.map((item, idx) => (
                <li key={idx} style={bodyTextStyle}>
                  {item}
                </li>
              ))}
            </ul>
          </div>}

          {analysis.status === "READY" && <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <span>Key Insights</span>
            </div>
            <div style={{ marginBottom: 8 }}>
              <div style={sectionLabelStyle}>Topics</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {analysis.topics.map((topic) => (
                  <span key={topic} style={chipStyle}>
                    {topic}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ marginBottom: 8 }}>
              <div style={sectionLabelStyle}>Entities</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {analysis.entities.map((entity) => (
                  <span key={entity} style={chipOutlineStyle}>
                    {entity}
                  </span>
                ))}
              </div>
            </div>
            {(analysis.key_entities?.dates?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={sectionLabelStyle}>Dates</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {analysis.key_entities?.dates?.map((date) => (
                    <span key={date} style={chipOutlineStyle}>
                      {date}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {(analysis.key_entities?.locations?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={sectionLabelStyle}>Locations</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {analysis.key_entities?.locations?.map((loc) => (
                    <span key={loc} style={chipOutlineStyle}>
                      {loc}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {(analysis.action_items?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={sectionLabelStyle}>Action Items</div>
                <ul style={{ paddingLeft: 18, margin: 0 }}>
                  {analysis.action_items?.slice(0, 6).map((item, idx) => (
                    <li key={idx} style={bodyTextStyle}>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {(analysis.decisions?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={sectionLabelStyle}>Decisions</div>
                <ul style={{ paddingLeft: 18, margin: 0 }}>
                  {analysis.decisions?.slice(0, 6).map((item, idx) => (
                    <li key={idx} style={bodyTextStyle}>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <div style={sectionLabelStyle}>Sentiment</div>
                <span
                  style={{
                    ...pillStyle,
                    backgroundColor:
                      analysis.sentiment.toLowerCase() === "negative" ||
                      analysis.sentiment.toLowerCase() === "urgent"
                        ? colors.danger
                        : colors.primary,
                  }}
                >
                  {analysis.sentiment}
                </span>
            </div>
          </div>}
        </>
      )}
    </div>
  )

  const copilotPanel = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        height: isMobile ? "auto" : "100%",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ fontWeight: 700, color: colors.textPrimary }}>Copilot</div>
        <div style={{ fontSize: 12, color: colors.textMuted }}>
          Suggested prompts and chat
        </div>
      </div>
        <div style={cardStyle}>
          <div style={{ ...cardHeaderStyle, display: "flex", justifyContent: "space-between", gap: 10 }}>
            <span>Suggested Prompts</span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={openDiagram}
                disabled={!isAuthenticated}
                style={{
                  padding: "6px 10px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                  backgroundColor: "#FFFFFF",
                  cursor: !isAuthenticated ? "default" : "pointer",
                  opacity: !isAuthenticated ? 0.6 : 1,
                  fontSize: 12,
                }}
              >
                Draw diagram
              </button>
              <button
                type="button"
                onClick={openChart}
                disabled={!isAuthenticated}
                style={{
                  padding: "6px 10px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                  backgroundColor: "#FFFFFF",
                  cursor: !isAuthenticated ? "default" : "pointer",
                  opacity: !isAuthenticated ? 0.6 : 1,
                  fontSize: 12,
                }}
              >
                Chart builder
              </button>
            </div>
          </div>
          <p style={{ ...bodyTextStyle, marginBottom: 12 }}>
            {activeDocumentId
              ? "Click a prompt or ask a question about this document. Answers are grounded in this document only."
              : "Ask general questions here. The assistant can use shared organizational knowledge, transferred learning, and web search fallback when needed."}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {(prompts.length > 0 ? prompts : GLOBAL_SUGGESTED_PROMPTS).map((p) => (
              <button
                key={p}
                type="button"
                style={promptChipButtonStyle}
                onClick={() => handleAsk(p)}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

      <div
        style={{
          ...cardStyle,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <div style={cardHeaderStyle}>
          <span>Chat History</span>
        </div>
        <div
          ref={chatScrollRef}
          style={{
            flex: 1,
            overflowY: isMobile ? "visible" : "auto",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            scrollBehavior: "smooth",
          }}
        >
          {chatMessages.length === 0 && (
            <div style={{ color: colors.textMuted, fontSize: 13 }}>
              {activeDocumentId
                ? "No messages yet. Ask a question to start the chat."
                : "No document selected yet. Ask a general question, or open one of your documents for document-grounded chat."}
            </div>
          )}
          {chatMessages.map((m) => {
            const isUser = m.role === "user"
            const isSystem = m.role === "system"
            const isError = m.uiStatus === "error"
            const align = isSystem ? "center" : isUser ? "flex-end" : "flex-start"
            const maxWidth = isSystem ? "100%" : "80%"
            const bg = isError && isSystem
              ? "rgba(254,226,226,0.85)"
              : isSystem
                ? "rgba(148,163,184,0.14)"
                : isError && isUser
                  ? "linear-gradient(135deg, rgba(107,114,128,1), rgba(156,163,175,1))"
                  : isUser
                    ? "linear-gradient(135deg, rgba(37,99,235,1), rgba(56,189,248,1))"
                    : "#FFFFFF"
            const color = isSystem ? colors.textPrimary : isUser ? "#FFFFFF" : colors.textPrimary
            const border = isError && isSystem
              ? "1px solid rgba(239,68,68,0.35)"
              : isSystem ? `1px solid rgba(148,163,184,0.25)` : isUser ? "none" : `1px solid ${colors.border}`
            const opacity = m.uiStatus === "waiting" ? 1 : m.status === "pending" ? 0.85 : 1
            return (
              <div key={String(m.id)} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div
                  style={{
                    alignSelf: align as any,
                    maxWidth,
                    background: bg,
                    color,
                    border,
                    padding: "8px 12px",
                    borderRadius: 16,
                    fontSize: 14,
                    opacity,
                    boxShadow: isSystem ? "none" : "0 8px 24px rgba(15,23,42,0.10)",
                  }}
                >
                  {m.uiStatus === "waiting" ? (
                    <div style={{ padding: "4px 2px", display: "flex", alignItems: "center" }}>
                      <span className="chat-thinking-dot" />
                      <span className="chat-thinking-dot" />
                      <span className="chat-thinking-dot" />
                    </div>
                  ) : (
                    renderRichContent(apiBaseUrl, m.content)
                  )}
                  {m.uiStatus === "sending" && (
                    <div style={{ marginTop: 4, fontSize: 11, opacity: 0.7 }}>Sending…</div>
                  )}
                  {m.uiStatus === "error" && isUser && (
                    <div style={{ marginTop: 4, fontSize: 11, color: "rgba(255,200,200,0.9)" }}>⚠ Not sent</div>
                  )}
                  {m.retryText && (
                    <button
                      type="button"
                      onClick={() => handleRetryMessage(m.retryText!, m.id)}
                      style={{
                        marginTop: 8,
                        display: "block",
                        fontSize: 12,
                        padding: "4px 12px",
                        borderRadius: 999,
                        border: "1px solid rgba(239,68,68,0.5)",
                        backgroundColor: "transparent",
                        color: "#dc2626",
                        cursor: "pointer",
                      }}
                    >
                      ↩ Retry
                    </button>
                  )}
                </div>
                {m.created_at && (
                  <div
                    style={{
                      alignSelf: align as any,
                      maxWidth,
                      fontSize: 11,
                      color: colors.textMuted,
                      opacity: 0.75,
                      padding: isSystem ? "0" : "0 10px",
                      textAlign: isSystem ? "center" : isUser ? "right" : "left",
                    }}
                  >
                    {m.created_at}
                  </div>
                )}
                {!isUser && !isSystem && (m.citations?.length ?? 0) > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {m.citations.map((c, cidx) => (
                      <span
                        key={`${c.filename}-${c.chunk_index}-${cidx}`}
                        title={c.text}
                        style={{
                          fontSize: 11,
                          padding: "2px 6px",
                          borderRadius: 10,
                          border: `1px solid ${colors.secondary}`,
                          backgroundColor: "#FFF5D6",
                        }}
                      >
                        Doc: {c.filename}, chunk {c.chunk_index}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {chatInfo && (
          <div style={{ marginTop: 10, fontSize: 12, color: colors.textMuted }}>
            {chatInfo}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleAsk(question)
          }}
          style={{
            display: "flex",
            gap: 10,
            marginTop: 8,
            alignItems: "center",
            backgroundColor: "#1F1F1F",
            borderRadius: 999,
            padding: "8px 10px",
            border: "1px solid rgba(255,255,255,0.08)",
            width: "100%",
            boxSizing: "border-box",
            overflow: "visible",
          }}
        >
          <button
            type="button"
            onClick={() => setIsMetadataOpen(true)}
            disabled={uploading}
            style={{
              position: "relative",
              width: 36,
              height: 36,
              borderRadius: "50%",
              border: "1px solid rgba(255,255,255,0.12)",
              backgroundColor: "#2A2A2A",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              fontWeight: 600,
              lineHeight: "20px",
              color: "#FFFFFF",
              cursor: uploading ? "default" : "pointer",
              opacity: uploading ? 0.6 : 1,
              flexShrink: 0,
              padding: 0,
            }}
          >
            +
          </button>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={activeDocumentId ? "Ask a question about this document…" : "Ask anything about the organization, prior learning, or the web…"}
            disabled={isWaiting || !isAuthenticated}
            style={{
              flex: 1,
              minWidth: 0,
              padding: "8px 6px",
              borderRadius: 999,
              border: "none",
              fontSize: 14,
              backgroundColor: "transparent",
              color: "#FFFFFF",
              outline: "none",
            }}
          />
          <div style={{ position: "relative", flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => setIsScopeMenuOpen((v) => !v)}
              disabled={isWaiting}
              title="Search scope"
              style={{
                height: 38,
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.12)",
                backgroundColor: "#2A2A2A",
                color: "#FFFFFF",
                fontSize: 12,
                padding: "0 12px",
                cursor: loadingChat ? "default" : "pointer",
                opacity: loadingChat ? 0.7 : 1,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>
                {!activeDocumentId
                  ? "Scope: Org knowledge"
                  : effectiveSearchScope === "all"
                    ? "Scope: All projects"
                    : "Scope: This project"}
              </span>
              <span style={{ opacity: 0.8 }}>▾</span>
            </button>
            {isScopeMenuOpen && (
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  bottom: 46,
                  width: 220,
                  backgroundColor: "#FFFFFF",
                  borderRadius: 12,
                  border: `1px solid ${colors.border}`,
                  boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
                  padding: 8,
                  zIndex: 80,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    setSearchScope("project")
                    setIsScopeMenuOpen(false)
                  }}
                  disabled={!activeDocumentId}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "10px 10px",
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: effectiveSearchScope === "project" ? "#E7F0FF" : "#FFFFFF",
                    cursor: !activeDocumentId ? "default" : "pointer",
                    opacity: !activeDocumentId ? 0.55 : 1,
                    fontSize: 13,
                  }}
                >
                  This project
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSearchScope("all")
                    setIsScopeMenuOpen(false)
                  }}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "10px 10px",
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: effectiveSearchScope === "all" ? "#E7F0FF" : "#FFFFFF",
                    cursor: "pointer",
                    fontSize: 13,
                  }}
                >
                  {activeDocumentId ? "All projects" : "Organization knowledge + web"}
                </button>
              </div>
            )}
          </div>
          <div style={{ position: "relative", flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => {
                if (!isHistoryOpen) openHistory()
                else setIsHistoryOpen(false)
              }}
              disabled={isWaiting || !isAuthenticated}
              title="Past conversations"
              style={{
                height: 38,
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.12)",
                backgroundColor: "#2A2A2A",
                color: "#FFFFFF",
                fontSize: 12,
                padding: "0 12px",
                cursor: isWaiting || !isAuthenticated ? "default" : "pointer",
                opacity: isWaiting || !isAuthenticated ? 0.7 : 1,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>Past</span>
              <span style={{ opacity: 0.8 }}>▾</span>
            </button>
            {isHistoryOpen && (
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  bottom: 46,
                  width: 360,
                  maxHeight: 340,
                  overflowY: "auto",
                  backgroundColor: "#FFFFFF",
                  borderRadius: 12,
                  border: `1px solid ${colors.border}`,
                  boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
                  padding: 10,
                  zIndex: 80,
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                }}
              >
                <input
                  type="text"
                  value={historyQuery}
                  onChange={(e) => setHistoryQuery(e.target.value)}
                  placeholder="Search conversations…"
                  style={{
                    width: "100%",
                    padding: "10px 10px",
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    fontSize: 13,
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                />
                {historyLoading ? (
                  <div style={{ fontSize: 12, color: colors.textMuted }}>Loading…</div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {historySessions
                      .filter((s) => {
                        const q = historyQuery.trim().toLowerCase()
                        if (!q) return true
                        return (
                          (s.title || "").toLowerCase().includes(q) ||
                          (s.document_id || "").toLowerCase().includes(q) ||
                          (s.model || "").toLowerCase().includes(q) ||
                          (s.scope || "").toLowerCase().includes(q)
                        )
                      })
                      .slice(0, 50)
                      .map((s) => (
                        <button
                          key={s.session_id}
                          type="button"
                          onClick={() => selectConversation(s.session_id)}
                          style={{
                            width: "100%",
                            textAlign: "left",
                            padding: "10px 10px",
                            borderRadius: 10,
                            border: `1px solid ${colors.border}`,
                            backgroundColor: "#FFFFFF",
                            cursor: "pointer",
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          <div style={{ fontSize: 13, color: colors.textPrimary, fontWeight: 700 }}>
                            {s.title || s.document_id || "Conversation"}
                          </div>
                          <div style={{ fontSize: 12, color: colors.textMuted }}>
                            {(s.scope || "document").toUpperCase()} • {s.model || "model"} • {s.updated_at || ""}
                          </div>
                        </button>
                      ))}
                    {historySessions.length === 0 && (
                      <div style={{ fontSize: 12, color: colors.textMuted }}>No conversations yet.</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          <div style={{ position: "relative", flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => setIsModelMenuOpen((v) => !v)}
              disabled={isWaiting || (modelsOffline && installedModels.length === 0)}
              title="Select model"
              style={{
                height: 38,
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.12)",
                backgroundColor: "#2A2A2A",
                color: "#FFFFFF",
                fontSize: 12,
                padding: "0 12px",
                cursor: isWaiting ? "default" : "pointer",
                opacity: isWaiting ? 0.7 : 1,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                maxWidth: 260,
              }}
            >
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {selectedModel ? `Model: ${modelLabel(selectedModel)}` : "Model"}
              </span>
              <span style={{ opacity: 0.8 }}>▾</span>
            </button>
            {isModelMenuOpen && (
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  bottom: 46,
                  width: 320,
                  maxHeight: 320,
                  overflowY: "auto",
                  backgroundColor: "#FFFFFF",
                  borderRadius: 12,
                  border: `1px solid ${colors.border}`,
                  boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
                  padding: 10,
                  zIndex: 80,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {modelsOffline && (
                  <div style={{ fontSize: 12, color: colors.textMuted }}>
                    Offline (installed models only)
                  </div>
                )}
                {(modelsOffline
                  ? [...installedModels, ...(installedModels.includes(GEMINI_MODEL_ID) ? [] : availableModels.filter(a => a === GEMINI_MODEL_ID))]
                  : availableModels
                ).map((m) => {
                  const isGemini = m === GEMINI_MODEL_ID
                  const installed = installedModels.includes(m)
                  const ps = pullStates[m]
                  const isPulling =
                    ps && ps.state && !["success", "failed", "idle"].includes(String(ps.state)) && !installed
                  const percent = isPulling ? Number(ps.percent || 0) : 0
                  const badge =
                    isGemini
                      ? "API"
                      : installed
                        ? "Installed"
                        : ps && ps.state === "pending"
                          ? "Pending…"
                          : ps && ps.state === "verifying"
                            ? "Verifying…"
                            : isPulling
                              ? `Downloading… ${percent}%`
                              : "Pull"
                  return (
                    <button
                      key={m}
                      type="button"
                      onClick={() => {
                        if (!isGemini && !installed) {
                          openPullModal(m)
                          return
                        }
                        handleModelChange(m)
                      }}
                      style={{
                        width: "100%",
                        textAlign: "left",
                        padding: "10px 10px",
                        borderRadius: 10,
                        border: `1px solid ${colors.border}`,
                        backgroundColor: m === selectedModel ? "#E7F0FF" : "#FFFFFF",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 10,
                      }}
                    >
                      <span style={{ fontSize: 13, color: colors.textPrimary }}>
                        {modelLabel(m)}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          borderRadius: 999,
                          border: `1px solid ${isGemini ? "#1a73e8" : installed ? colors.primary : colors.border}`,
                          backgroundColor: isGemini ? "#e8f0fe" : installed ? "#E7F0FF" : "#F4F6F8",
                          color: isGemini ? "#1a73e8" : installed ? colors.primaryDark : colors.textMuted,
                        }}
                      >
                        {badge}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
          <button
            type="submit"
            disabled={isWaiting || !isAuthenticated}
            style={{
              width: 38,
              height: 38,
              borderRadius: "50%",
              border: "none",
              backgroundColor: "#2A2A2A",
              color: "#FFFFFF",
              fontSize: 16,
              cursor: isWaiting || !isAuthenticated ? "default" : "pointer",
              opacity: isWaiting || !isAuthenticated ? 0.7 : 1,
            }}
          >
            {isWaiting ? "…" : "➤"}
          </button>
        </form>
        {isPullOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 90,
            }}
          >
            <div
              style={{
                backgroundColor: "#FFFFFF",
                borderRadius: 12,
                padding: 16,
                width: "100%",
                maxWidth: 640,
                boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div style={{ fontWeight: 700 }}>
                  Pull model: {pullModel}
                </div>
                <button
                  type="button"
                  onClick={() => setIsPullOpen(false)}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    borderRadius: 10,
                    padding: "6px 10px",
                    cursor: "pointer",
                  }}
                >
                  Close
                </button>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <span
                  style={{
                    fontSize: 12,
                    padding: "2px 10px",
                    borderRadius: 999,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#F4F6F8",
                    color: colors.textPrimary,
                  }}
                >
                  {pullStatus || "idle"} {pullAttempts ? `(attempt ${pullAttempts})` : ""}
                </span>
                <span style={{ fontSize: 12, color: colors.textMuted }}>
                  {pullEta != null ? `ETA ~${pullEta}s` : "Pulls can be large (10–20GB)."}
                </span>
                {pullStates[pullModel]?.resume_supported && (
                  <span style={{ fontSize: 12, color: colors.textMuted }}>
                    Resume supported
                  </span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: colors.textPrimary }}>
                  {Math.max(0, Math.min(100, pullPercent))}%
                </div>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      height: 10,
                      borderRadius: 999,
                      backgroundColor: "#EEF2F7",
                      overflow: "hidden",
                      border: `1px solid ${colors.border}`,
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.max(0, Math.min(100, pullPercent))}%`,
                        backgroundColor: pullError ? colors.danger : colors.primary,
                        transition: "width 200ms linear",
                      }}
                    />
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: colors.textMuted }}>
                    {pullStatus === "verifying"
                      ? "Verifying / extracting…"
                      : pullStatus === "retrying"
                        ? "Retrying…"
                        : pullStatus === "pending"
                          ? "Pending…"
                          : pullStatus === "downloading"
                            ? "Downloading…"
                            : pullStatus}
                  </div>
                </div>
              </div>
              {pullError && (
                <div style={{ color: colors.danger, fontSize: 13 }}>{pullError}</div>
              )}
              <div
                style={{
                  backgroundColor: "#0F172A",
                  color: "#E2E8F0",
                  borderRadius: 12,
                  padding: 12,
                  height: 260,
                  overflowY: "auto",
                  fontSize: 12,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  whiteSpace: "pre-wrap",
                }}
              >
                {pullLogs.length === 0 ? "No logs yet." : pullLogs.join("\n")}
              </div>
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => runPull(pullModel)}
                  disabled={modelsOffline || (pullStatus !== "failed" && pullStatus !== "idle")}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    cursor: modelsOffline ? "default" : "pointer",
                    opacity: modelsOffline || (pullStatus !== "failed" && pullStatus !== "idle") ? 0.6 : 1,
                  }}
                >
                  {modelsOffline ? "Offline" : pullStatus === "failed" ? "Retry" : "Start"}
                </button>
              </div>
            </div>
          </div>
        )}
        {isDiagramOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 91,
            }}
          >
            <div
              style={{
                backgroundColor: "#FFFFFF",
                borderRadius: 12,
                padding: 16,
                width: "100%",
                maxWidth: 720,
                boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div style={{ fontWeight: 800 }}>Diagram Builder</div>
                <button
                  type="button"
                  onClick={() => setIsDiagramOpen(false)}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    borderRadius: 10,
                    padding: "6px 10px",
                    cursor: "pointer",
                  }}
                >
                  Close
                </button>
              </div>
              <textarea
                value={diagramText}
                onChange={(e) => setDiagramText(e.target.value)}
                spellCheck={false}
                style={{
                  width: "100%",
                  height: 180,
                  borderRadius: 12,
                  border: `1px solid ${colors.border}`,
                  padding: 12,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: 12,
                  outline: "none",
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button
                  type="button"
                  onClick={buildDiagram}
                  disabled={loadingChat || !diagramText.trim()}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "none",
                    backgroundColor: colors.primary,
                    color: "#FFFFFF",
                    cursor: loadingChat || !diagramText.trim() ? "default" : "pointer",
                    opacity: loadingChat || !diagramText.trim() ? 0.6 : 1,
                  }}
                >
                  Generate Mermaid
                </button>
              </div>
              {diagramMermaid && (
                <pre
                  style={{
                    margin: 0,
                    backgroundColor: "#0F172A",
                    color: "#E2E8F0",
                    borderRadius: 12,
                    padding: 12,
                    maxHeight: 240,
                    overflowY: "auto",
                    fontSize: 12,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {diagramMermaid}
                </pre>
              )}
            </div>
          </div>
        )}
        {isChartOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 91,
            }}
          >
            <div
              style={{
                backgroundColor: "#FFFFFF",
                borderRadius: 12,
                padding: 16,
                width: "100%",
                maxWidth: 760,
                boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div style={{ fontWeight: 800 }}>Chart Builder (CSV)</div>
                <button
                  type="button"
                  onClick={() => setIsChartOpen(false)}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    borderRadius: 10,
                    padding: "6px 10px",
                    cursor: "pointer",
                  }}
                >
                  Close
                </button>
              </div>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) onChartFile(f)
                }}
              />
              {chartColumns.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                  <div>
                    <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 4 }}>Chart type</div>
                    <select
                      value={chartType}
                      onChange={(e) => setChartType(e.target.value)}
                      style={{ width: "100%", padding: 8, borderRadius: 10, border: `1px solid ${colors.border}` }}
                    >
                      <option value="bar">Bar</option>
                      <option value="line">Line</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 4 }}>X axis</div>
                    <select
                      value={chartX}
                      onChange={(e) => setChartX(e.target.value)}
                      style={{ width: "100%", padding: 8, borderRadius: 10, border: `1px solid ${colors.border}` }}
                    >
                      {chartColumns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 4 }}>Y series</div>
                    <select
                      multiple
                      value={chartY}
                      onChange={(e) => {
                        const selected = Array.from(e.target.selectedOptions).map((o) => o.value)
                        setChartY(selected)
                      }}
                      style={{ width: "100%", padding: 8, borderRadius: 10, border: `1px solid ${colors.border}`, height: 90 }}
                    >
                      {(chartNumeric.length ? chartNumeric : chartColumns).map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
                <button
                  type="button"
                  onClick={buildChart}
                  disabled={!chartFile || chartRows.length === 0}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "none",
                    backgroundColor: colors.primary,
                    color: "#FFFFFF",
                    cursor: !chartFile || chartRows.length === 0 ? "default" : "pointer",
                    opacity: !chartFile || chartRows.length === 0 ? 0.6 : 1,
                  }}
                >
                  Build chart
                </button>
              </div>
              {chartUrl && (
                <div style={{ fontSize: 13 }}>
                  Chart URL:{" "}
                  <a href={`${apiBaseUrl}${chartUrl}`} target="_blank" rel="noreferrer">
                    {chartUrl}
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
        {isMetadataOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
              zIndex: 50,
            }}
          >
            <div
              style={{
                backgroundColor: "#FFFFFF",
                borderRadius: 12,
                padding: 16,
                width: "100%",
                maxWidth: 420,
                boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div style={{ fontWeight: 600 }}>Upload document</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <select
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  style={{
                    flex: 1,
                    minWidth: 200,
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: `1px solid ${colors.border}`,
                    fontSize: 14,
                    backgroundColor: "#FFFFFF",
                  }}
                >
                  <option value="">No project</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                  <option value="new">New project…</option>
                </select>
                {selectedProjectId === "new" && (
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="New project name"
                    style={{
                      flex: 1,
                      minWidth: 200,
                      padding: "10px 12px",
                      borderRadius: 10,
                      border: `1px solid ${colors.border}`,
                      fontSize: 14,
                    }}
                  />
                )}
              </div>
              <input
                type="text"
                value={metadataDocumentType}
                onChange={(e) => setMetadataDocumentType(e.target.value)}
                placeholder="Document type"
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                  fontSize: 14,
                }}
              />
              <input
                type="date"
                value={metadataDocumentDate}
                onChange={(e) => setMetadataDocumentDate(e.target.value)}
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  border: `1px solid ${colors.border}`,
                  fontSize: 14,
                }}
              />
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) =>
                  setMetadataFile(e.target.files?.[0] ?? null)
                }
                style={{
                  padding: "6px 0",
                  fontSize: 14,
                }}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 8,
                  marginTop: 4,
                }}
              >
                <button
                  type="button"
                  onClick={() => setIsMetadataOpen(false)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 999,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: "#FFFFFF",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleUpload(metadataFile)}
                  disabled={!metadataFile || uploading}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 999,
                    border: "none",
                    backgroundColor: colors.primary,
                    color: "#FFFFFF",
                    fontSize: 13,
                    cursor:
                      !metadataFile || uploading ? "default" : "pointer",
                    opacity: !metadataFile || uploading ? 0.6 : 1,
                  }}
                >
                  {uploading ? "Uploading..." : "Upload"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div style={{ position: "relative" }}>
      {bootstrapRunning && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.25)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            padding: 16,
            zIndex: 70,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              backgroundColor: "#FFFFFF",
              borderRadius: 12,
              padding: 12,
              border: `1px solid ${colors.border}`,
              boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
              width: "100%",
              maxWidth: 520,
            }}
          >
            <div style={{ fontWeight: 800, color: colors.textPrimary }}>
              Preparing knowledge base
            </div>
            <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
              {bootstrapPercent}% • You can keep using the app while indexing runs.
            </div>
            <div
              style={{
                height: 8,
                borderRadius: 999,
                backgroundColor: "#EEF2F7",
                overflow: "hidden",
                marginTop: 10,
              }}
            >
              <div
                style={{
                  width: `${Math.max(0, Math.min(100, bootstrapPercent))}%`,
                  height: "100%",
                  backgroundColor: colors.primary,
                }}
              />
            </div>
          </div>
        </div>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isMobile
            ? "minmax(0, 1fr)"
            : "minmax(0, 2fr) minmax(0, 3fr)",
          gap: 20,
          height: isMobile ? "auto" : "calc(100vh - 64px - 48px)",
        }}
      >
        {isMobile ? (
          <>
            {copilotPanel}
            {analysisPanel}
          </>
        ) : (
          <>
            {analysisPanel}
            {copilotPanel}
          </>
        )}
      </div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  backgroundColor: colors.surface,
  borderRadius: 12,
  padding: 16,
  border: `1px solid ${colors.border}`,
  boxShadow: "0 4px 14px rgba(11,78,162,0.08)",
}

const cardHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 8,
  fontWeight: 600,
  color: colors.textPrimary,
}

const bodyTextStyle: React.CSSProperties = {
  fontSize: 14,
  color: colors.textPrimary,
}

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  textTransform: "uppercase",
  color: colors.textMuted,
  marginBottom: 4,
}

const chipStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: 16,
  backgroundColor: "#E7F0FF",
  color: colors.primaryDark,
  fontSize: 12,
}

const chipOutlineStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: 16,
  border: `1px solid ${colors.primary}`,
  color: colors.primaryDark,
  fontSize: 12,
  backgroundColor: colors.surface,
}

const pillStyle: React.CSSProperties = {
  fontSize: 11,
  padding: "2px 8px",
  borderRadius: 999,
  backgroundColor: "#FFE6B7",
  color: colors.primaryDark,
}

const promptChipButtonStyle: React.CSSProperties = {
  padding: "6px 10px",
  borderRadius: 999,
  border: "none",
  backgroundColor: "#FFE6B7",
  color: colors.primaryDark,
  fontSize: 13,
  cursor: "pointer",
}
