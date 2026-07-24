import React, { useEffect, useRef, useState } from "react"
import { MermaidView } from "../components/MermaidView"
import {
  DocumentAnalysisResponse,
  EnterpriseSummary,
  ChatMessage,
  SummaryHistoryEntry,
  OllamaModelDetail,
} from "../types/api"
import {
  getDocumentAnalysis,
  getEnterpriseSummary,
  getDocumentChunks,
  getDocumentPrompts,
  suggestPrompts,
  chatWithDocument,
  chatWithDocumentStream,
  chatGlobally,
  chatGloballyStream,
  getSummaryHistory,
  uploadDocument,
  getProjects,
  getMyDocuments,
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
  transcribeAudio,
} from "../api/client"
import { isCloudModel } from "../utils/modelUtils"
import { colors } from "../theme/colors"
import { useTheme } from "../context/ThemeContext"
import { useModel } from "../context/ModelContext"
import { getTokens } from "../theme/themeTokens"
import { RobotSearching } from "../components/RobotSearching"
import { UserIcon } from "../components/UserIcon"
import { ModelSelector } from "../components/ModelSelector"

interface DocumentViewPageProps {
  documentId: string | null
  isAuthenticated: boolean
  authEpoch: number
}

type UIMessageStatus = "idle" | "sending" | "waiting" | "streaming" | "success" | "done" | "error"
type UIChatMessage = Omit<ChatMessage, "id"> & {
  id: string | number
  uiStatus?: UIMessageStatus
  retryText?: string
}

const GLOBAL_CHAT_SESSION_KEY = "docintel_chat_session_global"
const GLOBAL_SUGGESTED_PROMPTS = [
  "What knowledge and documents are available in my workspace?",
  "Summarise my recent documents and highlight key topics.",
  "What are the main business systems, processes, and workflows across my documents?",
  "Identify any risks, compliance requirements, or action items across my knowledge base.",
]

/**
 * Generate context-aware fallback prompts based on a document analysis response.
 * Uses topics, entities, sentiment, and actions to produce specific, actionable prompts.
 */
function generateFallbackPrompts(analysis: DocumentAnalysisResponse | null): string[] {
  const topics = analysis?.topics || []
  const entities = analysis?.entities || []
  const hasActions = (analysis?.action_items?.length ?? 0) > 0
  const hasDecisions = (analysis?.decisions?.length ?? 0) > 0

  const topicLower = topics.map(t => t.toLowerCase())

  // Detect document domain from topics and entities
  const isBilling = topicLower.some(t => t.includes('bill') || t.includes('payment') || t.includes('tariff') || t.includes('meter'))
  const isOMS = topicLower.some(t => t.includes('oms') || t.includes('outage') || t.includes('fault') || t.includes('incident'))
  const isCRM = topicLower.some(t => t.includes('crm') || t.includes('customer') || t.includes('service') || t.includes('case'))
  const isNDPM = topicLower.some(t => t.includes('ndpm') || t.includes('connection') || t.includes('commission') || t.includes('workflow'))
  const isHR = topicLower.some(t => t.includes('hr') || t.includes('employee') || t.includes('staff') || t.includes('personnel'))
  const isPolicy = topicLower.some(t => t.includes('policy') || t.includes('compliance') || t.includes('regulation') || t.includes('governance'))

  // Build domain-specific prompt suggestions
  const prompts: string[] = []

  if (isBilling) {
    prompts.push(
      "Explain the billing lifecycle described in this document, including key steps and systems.",
      "What payment methods, collection processes, and account adjustments are documented?",
    )
  } else if (isOMS) {
    prompts.push(
      "Describe the outage management workflow, including fault detection, dispatch, and restoration.",
      "How is the OMS integrated with the CRM, billing, and notification systems?",
    )
  } else if (isCRM) {
    prompts.push(
      "Explain the customer journey as described in this document, from enquiry through resolution.",
      "What CRM integrations with other enterprise systems are documented?",
    )
  } else if (isNDPM) {
    prompts.push(
      "Walk through the new connection process from application to commissioning.",
      "What roles and responsibilities are involved in each stage of the NDPM workflow?",
    )
  } else if (isHR) {
    prompts.push(
      "Summarise the HR policies, employee lifecycle, and organisational structure described.",
      "What staff roles, responsibilities, and performance criteria are documented?",
    )
  } else if (isPolicy) {
    prompts.push(
      "Summarise the key policy requirements, compliance obligations, and governance rules.",
      "What are the enforcement mechanisms and escalation procedures described?",
    )
  } else {
    prompts.push(
      "Summarise this document in 10 sentences or less, focusing on the key purpose and scope.",
      "List the main systems, processes, and entities referenced in this document.",
    )
  }

  if (hasActions) {
    prompts.push("List all action items and decisions mentioned in this document with ownership details.")
  } else {
    prompts.push("What key requirements, deadlines, and responsibilities are mentioned?")
  }

  prompts.push("Generate a Mermaid process flow diagram based on the key steps in this document.")

  if (entities.length > 0) {
    prompts.push(`Analyse the relationships between key entities: ${entities.slice(0, 5).join(', ')}.`)
  } else {
    prompts.push("Extract all key entities: systems, departments, roles, locations, and dates.")
  }

  if (hasDecisions) {
    prompts.push("What decisions were made and what are their business implications?")
  }

  return prompts.slice(0, 6)
}

/**
 * Compute top N related documents by comparing entity + topic overlap with the current document.
 * Uses Jaccard similarity (intersection / union) on topics, then entity overlap as tiebreaker.
 */
interface RelatedDocResult {
  id: string
  filename: string
  project_name?: string
  score: number
  match_reasons: string[]
  matched_topics: string[]
  matched_entities: string[]
}

async function computeRelatedDocuments(
  currentAnalysis: DocumentAnalysisResponse,
  maxDocs: number = 50,
): Promise<RelatedDocResult[]> {
  const currentTopics = (currentAnalysis.topics || []).map(t => t.toLowerCase())
  const currentEntities = (currentAnalysis.entities || []).map(e => e.toLowerCase())

  if (currentTopics.length === 0 && currentEntities.length === 0) {
    return []
  }

  let allDocs: any[]
  try {
    const res = await getMyDocuments(1, maxDocs)
    allDocs = res?.documents || []
  } catch {
    return []
  }

  if (allDocs.length === 0) return []

  const results: RelatedDocResult[] = []

  // Fetch analysis for all documents in parallel (tolerate failures)
  const analysisResults = await Promise.allSettled(
    allDocs.map(doc =>
      getDocumentAnalysis(doc.id).then(analysis => ({ doc, analysis }))
    ),
  )

  for (const result of analysisResults) {
    if (result.status !== "fulfilled") continue
    const { doc, analysis } = result.value
    if (!analysis || analysis.status !== "READY") continue

    // Skip the current document itself
    if (doc.id === currentAnalysis.id) continue

    const docTopics = (analysis.topics || []).map(t => t.toLowerCase())
    const docEntities = (analysis.entities || []).map(e => e.toLowerCase())

    // Jaccard similarity on topics
    const topicSet = new Set(currentTopics)
    const docTopicSet = new Set(docTopics)
    const topicIntersection = currentTopics.filter(t => docTopicSet.has(t)).length
    const topicUnion = new Set([...topicSet, ...docTopicSet]).size
    const topicScore = topicUnion > 0 ? topicIntersection / topicUnion : 0

    // Entity overlap (fraction of current entities found in the other doc)
    const entityMatchCount = currentEntities.filter(e => docEntities.includes(e)).length
    const entityScore = currentEntities.length > 0 ? entityMatchCount / currentEntities.length : 0

    // Combined score: 60% topic + 40% entity
    const score = topicScore * 0.6 + entityScore * 0.4

    if (score <= 0) continue

    // Build match reasons
    const matchReasons: string[] = []
    const matchedTopics = docTopics.filter(t => currentTopics.includes(t))
    const matchedEntities = docEntities.filter(e => currentEntities.includes(e))

    if (matchedTopics.length > 0) {
      matchReasons.push(`Shared topics: ${matchedTopics.slice(0, 3).join(", ")}`)
    }
    if (matchedEntities.length > 0) {
      matchReasons.push(`Shared entities: ${matchedEntities.slice(0, 3).join(", ")}`)
    }

    results.push({
      id: doc.id || analysis.id,
      filename: doc.filename || analysis.filename || "Unknown",
      project_name: doc.project_name || analysis.project_name,
      score: Math.round(score * 100) / 100,
      match_reasons: matchReasons,
      matched_topics: matchedTopics.slice(0, 5),
      matched_entities: matchedEntities.slice(0, 5),
    })
  }

  // Sort by score descending, return top 5
  return results.sort((a, b) => b.score - a.score).slice(0, 5)
}

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
  const apiBaseUrl = (() => {
    const raw = (import.meta as any).env.VITE_API_BASE_URL
    if (typeof raw === "string" && raw.trim()) return raw.trim().replace(/\/+$/, "")
    return ""
  })()
  const { isDark, theme: themeName } = useTheme()
  const t = getTokens(themeName)
  const c = t.colors
  
  // Refs for click-outside detection
  const scopeMenuRef = useRef<HTMLDivElement>(null)
  const historyMenuRef = useRef<HTMLDivElement>(null)
  const diagramMenuRef = useRef<HTMLDivElement>(null)
  const chartMenuRef = useRef<HTMLDivElement>(null)
  const pullMenuRef = useRef<HTMLDivElement>(null)
  const refDocMenuRef = useRef<HTMLDivElement>(null)
  
  const [activeDocumentId, setActiveDocumentId] = useState(documentId)
  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null)
  const [enterpriseSummary, setEnterpriseSummary] = useState<EnterpriseSummary | null>(null)
  const [relatedDocuments, setRelatedDocuments] = useState<RelatedDocResult[]>([])
  const [loadingRelated, setLoadingRelated] = useState(false)
  const [prompts, setPrompts] = useState<string[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chatMessages, setChatMessages] = useState<UIChatMessage[]>([])
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const [summaryHistory, setSummaryHistory] = useState<SummaryHistoryEntry[]>([])
  const [question, setQuestion] = useState("")
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [loadingChat, setLoadingChat] = useState(false)
  const [chatInfo, setChatInfo] = useState<string | null>(null)
  const [installedModels, setInstalledModels] = useState<string[]>([])
  const [searchScope, setSearchScope] = useState<"project" | "all">("project")

  const {
    selectedModel, setSelectedModel,
    availableModels,
    modelLabels,
    modelCapabilities: capabilityMap,
    modelDetails,
    offline: modelsOffline,
    loading: modelsLoading,
    reloadModels,
    setModelForTask,
    v2ModelIds,
    v2Providers,
    taskDefaults,
  } = useModel()
  const [isScopeMenuOpen, setIsScopeMenuOpen] = useState(false)

  // On mount, apply Task Mapping for RAG — wait until taskDefaults are populated
  useEffect(() => {
    if (!modelsLoading && Object.keys(taskDefaults).length > 0) {
      setModelForTask("rag")
    }
  }, [modelsLoading, taskDefaults])
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
  const [isRefDocOpen, setIsRefDocOpen] = useState(false)
  const [selectedRefDocuments, setSelectedRefDocuments] = useState<string[]>([])
  const [pullStates, setPullStates] = useState<Record<string, any>>({})
  const [pollIngestMs, setPollIngestMs] = useState(1500)
  const [pollPullMs, setPollPullMs] = useState(800)
  const [clearOnSend, setClearOnSend] = useState(true)
  const [docChunks, setDocChunks] = useState<{ chunk_index: number; text: string }[] | null>(null)
  const [showDocContent, setShowDocContent] = useState(false)
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
  const [documents, setDocuments] = useState<
    {
      id: string
      filename: string
      project_id: string | null
      project_name: string
      status: string
      created_at: string
      download_url: string
      view_url: string
    }[]
  >([])
  const [recentDocuments, setRecentDocuments] = useState<
    {
      id: string
      filename: string
      created_at: string
      status: string
    }[]
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

  // Auto-load and auto-select the most recent document when authenticated
  useEffect(() => {
    const autoLoadRecentDocs = async () => {
      if (!isAuthenticated) return
      try {
        const res = await getMyDocuments()
        const docs = res.documents || []
        const sorted = docs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        setRecentDocuments(sorted.slice(0, 5))
        // Auto-select the most recent document if no document is currently selected
        // and no activeDocumentId is set yet (only on first load)
        if (!documentId && sorted.length > 0) {
          setActiveDocumentId(sorted[0].id)
        }
      } catch (e: any) {
        console.warn("Failed to load recent documents:", e.message)
      }
    }
    autoLoadRecentDocs()
  }, [isAuthenticated, authEpoch])

  useEffect(() => {
    // Only update if documentId explicitly changes from parent
    if (documentId) {
      setActiveDocumentId(documentId)
    } else if (documentId === null && activeDocumentId) {
      // Parent explicitly cleared the document (e.g., on navigation)
      // But don't immediately clear - let auto-select work first
      return
    }
  }, [documentId])

  useEffect(() => {
    // When activeDocumentId changes, handle analysis/prompts/chat reset
    if (!activeDocumentId) {
      setAnalysis(null)
      setEnterpriseSummary(null)
      setRelatedDocuments([])
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
  }, [activeDocumentId])

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
    setChatInfo(null)
    setError(null)
    setSessionId(sid)
    try {
      window.localStorage.setItem(sessionStorageKey, sid)
    } catch {
    }
    try {
      const history = await getChatMessages(sid, 1000)
      if (history && history.messages) {
        setChatMessages(history.messages)
        if (history.messages.length === 0) {
          setChatInfo("No messages in this conversation yet.")
        }
      } else {
        setChatInfo("No conversation data received from server.")
        console.warn("Unexpected response format:", history)
      }
    } catch (e: any) {
      const errMsg = e instanceof ApiError ? `Error ${e.status}: ${e.message}` : (e?.message ?? "Failed to load conversation")
      setChatInfo(errMsg)
      console.error("Failed to load conversation:", e)
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
      setLoadingChat(true)
      const res = await flowchartGenerate({ 
        text: diagramText,
        model: selectedModel || undefined,
        diagram_type: "flowchart"
      })
      setDiagramMermaid(res.mermaid)
      setChatMessages((prev) => [
        ...prev,
        {
          id: `assistant_${Date.now()}`,
          role: "assistant",
          content: `\`\`\`mermaid\n${res.mermaid}\n\`\`\``,
          status: "done",
          citations: [],
          created_at: "",
        },
      ])
    } catch (e: any) {
      setError(e.message ?? "Failed to generate diagram")
    } finally {
      setLoadingChat(false)
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
    const loadInstalled = async () => {
      try {
        const res = await getAvailableModels()
        setInstalledModels(res.installed ?? [])
      } catch (e: any) {
        console.warn("Failed to fetch installed models:", e)
      }
    }
    loadInstalled()
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
        reloadModels()
        const models = await getAvailableModels()
        setInstalledModels((models.installed ?? []) as string[])
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
        setPrompts(rawPrompts.length > 0 ? rawPrompts : generateFallbackPrompts(analysisRes))
        // Fetch enterprise summary
        try {
          const esRes = await getEnterpriseSummary(activeDocumentId)
          if (esRes.summary && Object.keys(esRes.summary).length > 0) {
            setEnterpriseSummary(esRes.summary as EnterpriseSummary)
          }
        } catch {
          // Enterprise summary not available — fine, use legacy analysis
        }
        // Fetch related documents by comparing entities and topics
        if (analysisRes && analysisRes.status === "READY") {
          setLoadingRelated(true)
          computeRelatedDocuments(analysisRes).then(related => {
            setRelatedDocuments(related)
          }).catch(() => {}).finally(() => {
            setLoadingRelated(false)
          })
        }
        // Fetch document chunks for content preview
        try {
          const chunkRes = await getDocumentChunks(activeDocumentId)
          if (chunkRes?.chunks && chunkRes.chunks.length > 0) {
            setDocChunks(chunkRes.chunks)
          }
        } catch {
          // Chunks not available yet
          setDocChunks(null)
        }
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
        const errStatus = e instanceof ApiError ? e.status : null
        const errCode = e instanceof ApiError ? e.data?.error : null
        if (errStatus === 404 || errCode === "document_not_found" || (e?.message ?? "").toLowerCase().includes("document not found")) {
          // Stale document ID – clear everything and let auto-select pick a valid doc
          try {
            if (typeof window !== "undefined" && sessionStorageKey) {
              window.localStorage.removeItem(sessionStorageKey)
            }
          } catch {}
          setSessionId(null)
          setActiveDocumentId(null)
          setAnalysis(null)
          setIngestStatus(null)
        } else {
          setError(e.message ?? "Failed to load document")
        }
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
      // Also refresh enterprise summary
      try {
        const esRes = await getEnterpriseSummary(activeDocumentId)
        if (esRes.summary && Object.keys(esRes.summary).length > 0) {
          setEnterpriseSummary(esRes.summary as EnterpriseSummary)
        }
      } catch {
        // Enterprise summary not available yet
      }
      const refreshedPrompts: string[] = (promptsRes as any).prompts || []
      setPrompts(refreshedPrompts.length > 0 ? refreshedPrompts : generateFallbackPrompts(analysisRes))
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
        "@keyframes pulse {",
        "  0%, 100% { transform: scale(1); opacity: 1; }",
        "  50% { transform: scale(1.05); opacity: 0.7; }",
        "}",
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

  useEffect(() => {
    if (!isRefDocOpen) return
    const loadDocuments = async () => {
      try {
        const res = await getMyDocuments()
        setDocuments(res.documents || [])
      } catch (e: any) {
        setError(e.message ?? "Failed to load documents")
      }
    }
    loadDocuments()
  }, [isRefDocOpen])

  const modelLabel = (m: string): string => {
    return modelLabels[m] || m
  }

  const handleModelChange = async (nextModel: string) => {
    if (!nextModel || nextModel === selectedModel) {
      return
    }
    setSelectedModel(nextModel)
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
          reloadModels()
          const updated = await getAvailableModels()
          setInstalledModels((updated.installed ?? []) as string[])
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

      const cloudModel = isCloudModel(selectedModel, modelDetails, v2Providers)

      if (cloudModel) {
        const streamCallbacks = {
          onChunk: (chunk: string, _model: string, streamSid: string) => {
            setChatMessages((prev) =>
              prev.map((m) =>
                m.id === thinkingId
                  ? { ...m, content: (m.content || "") + chunk, uiStatus: "streaming" as UIMessageStatus }
                  : m,
              ),
            )
            if (streamSid && !sessionId) {
              setSessionId(streamSid)
              if (typeof window !== "undefined") {
                window.localStorage.setItem(sessionStorageKey, streamSid)
              }
            }
          },
          onReasoning: (reasoning: string) => {
            setChatMessages((prev) =>
              prev.map((m) =>
                m.id === thinkingId
                  ? { ...m, reasoning: (m.reasoning || "") + reasoning }
                  : m,
              ),
            )
          },
          onDone: (_fullText: string, _model: string, _streamSid: string) => {
            setChatMessages((prev) =>
              prev.map((m) =>
                m.id === thinkingId
                  ? { ...m, uiStatus: "done" as UIMessageStatus }
                  : m,
              ),
            )
            setLoadingChat(false)
          },
          onError: (error: string) => {
            setChatMessages((prev) =>
              prev.map((m) =>
                m.id === thinkingId
                  ? { ...m, content: `Error: ${error}`, uiStatus: "error" as UIMessageStatus }
                  : m,
              ),
            )
            setLoadingChat(false)
          },
        }

        if (activeDocumentId) {
          await chatWithDocumentStream(activeDocumentId, askPayload, streamCallbacks)
        } else {
          await chatGloballyStream(askPayload, streamCallbacks)
        }
        return
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
        pendingAskRef.current = { documentId: activeDocumentId ?? "", text }
        setChatMessages((prev) => prev.filter((m) => m.id !== thinkingId))
        setChatInfo("Session expired. Please sign in again. Your message is saved.")
      } else if (errStatus === 404 || errCode === "document_not_found" || (e?.message ?? "").toLowerCase().includes("document not found")) {
        // Stale document ID in localStorage — clear it and prompt user to reselect
        try {
          if (typeof window !== "undefined" && sessionStorageKey) {
            window.localStorage.removeItem(sessionStorageKey)
          }
        } catch {}
        setSessionId(null)
        setActiveDocumentId(null)
        setChatMessages([])
        replaceWithError(
          "The document could not be found — it may have been deleted or re-uploaded. " +
          "Please select the document again from the sidebar to continue."
        )
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
      const blob = await downloadDocumentFile(activeDocumentId!)
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

  // Click-outside handlers for all menus and modals
  useEffect(() => {
    if (!isScopeMenuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (scopeMenuRef.current && !scopeMenuRef.current.contains(e.target as Node)) {
        setIsScopeMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isScopeMenuOpen])

  useEffect(() => {
    if (!isHistoryOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (historyMenuRef.current && !historyMenuRef.current.contains(e.target as Node)) {
        setIsHistoryOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isHistoryOpen])

  useEffect(() => {
    if (!isDiagramOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (diagramMenuRef.current && !diagramMenuRef.current.contains(e.target as Node)) {
        setIsDiagramOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isDiagramOpen])

  useEffect(() => {
    if (!isChartOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (chartMenuRef.current && !chartMenuRef.current.contains(e.target as Node)) {
        setIsChartOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isChartOpen])

  useEffect(() => {
    if (!isPullOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (pullMenuRef.current && !pullMenuRef.current.contains(e.target as Node)) {
        setIsPullOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isPullOpen])

  useEffect(() => {
    if (!isRefDocOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (refDocMenuRef.current && !refDocMenuRef.current.contains(e.target as Node)) {
        setIsRefDocOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isRefDocOpen])

  const [showAnalysisDrawer, setShowAnalysisDrawer] = React.useState(false)

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
        <div style={{ fontWeight: 700, color: c.textPrimary }}>
          Analysis Dashboard
        </div>
        <div style={{ fontSize: 12, color: c.textMuted }}>
            {analysis?.filename ? `Document: ${analysis.filename}` : activeDocumentId ? "Selected" : "No document selected"}
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
              <div style={{ fontSize: 13, color: c.textMuted }}>
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
              <span style={{ ...pillStyle, backgroundColor: c.primary }}>{analysis.status}</span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {analysis.project_name && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>Repository</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: c.textPrimary }}>
                  {analysis.project_name}
                </span>
              </div>
            )}
            {analysis.filename && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>File</span>
                <span style={{ fontSize: 13, color: c.textPrimary, wordBreak: "break-all" }}>
                  {analysis.filename}
                </span>
              </div>
            )}
            {analysis.document_type && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>Type</span>
                <span style={{ fontSize: 13, color: c.textPrimary }}>{analysis.document_type}</span>
              </div>
            )}
            {analysis.document_date && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ ...sectionLabelStyle, minWidth: 90 }}>Date</span>
                <span style={{ fontSize: 13, color: c.textPrimary }}>{analysis.document_date}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {loadingAnalysis && (
        <div style={{ color: c.textMuted }}>Loading analysis…</div>
      )}
      {error && (
        <div style={{ color: c.danger, fontSize: 13, padding: "8px 12px", borderRadius: 8, backgroundColor: "#FFF0F0", border: "1px solid #FECACA" }}>
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
              backgroundColor: c.border,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.min(100, Math.max(0, ingestStatus?.percent ?? 0))}%`,
                height: "100%",
                backgroundColor: c.primary,
              }}
            />
          </div>
          {ingestStatus?.error_message && (
            <div style={{ marginTop: 10, color: c.danger, fontSize: 13 }}>
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
                border: `1px solid ${c.border}`,
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
      {/* ── Document Intelligence Card ── */}
      {analysis && analysis.status === "READY" && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span>📊 Document Intelligence</span>
            {analysis.sentiment && (
              <span style={{
                ...pillStyle,
                backgroundColor: analysis.sentiment === 'Positive' ? 'rgba(22,163,74,0.15)' :
                  analysis.sentiment === 'Urgent' ? 'rgba(239,68,68,0.15)' :
                  analysis.sentiment === 'Negative' ? 'rgba(245,158,11,0.15)' :
                  'rgba(107,114,128,0.15)',
                borderColor: analysis.sentiment === 'Positive' ? 'rgba(22,163,74,0.25)' :
                  analysis.sentiment === 'Urgent' ? 'rgba(239,68,68,0.25)' :
                  analysis.sentiment === 'Negative' ? 'rgba(245,158,11,0.25)' :
                  'rgba(107,114,128,0.25)',
                color: analysis.sentiment === 'Positive' ? '#4ADE80' :
                  analysis.sentiment === 'Urgent' ? '#F87171' :
                  analysis.sentiment === 'Negative' ? '#FBBF24' :
                  '#9CA3AF',
              }}>
                {analysis.sentiment}
              </span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {analysis.topics && analysis.topics.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Business Areas</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {analysis.topics.slice(0, 6).map(topic => (
                    <span key={topic} style={chipStyle}>{topic}</span>
                  ))}
                </div>
              </div>
            )}
            {analysis.entities && analysis.entities.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Systems & Entities</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {analysis.entities.slice(0, 8).map(entity => (
                    <span key={entity} style={chipOutlineStyle}>{entity}</span>
                  ))}
                </div>
              </div>
            )}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {(analysis.action_items?.length ?? 0) > 0 && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.2)", color: "#FCD34D",
                }}>
                  ⚡ {(analysis.action_items?.length ?? 0)} Action{(analysis.action_items?.length ?? 0) !== 1 ? 's' : ''}
                </span>
              )}
              {(analysis.decisions?.length ?? 0) > 0 && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: "rgba(59,130,246,0.12)", border: "1px solid rgba(59,130,246,0.2)", color: "#60A5FA",
                }}>
                  ✓ {(analysis.decisions?.length ?? 0)} Decision{(analysis.decisions?.length ?? 0) !== 1 ? 's' : ''}
                </span>
              )}
              {analysis.document_type && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.2)", color: "#A78BFA",
                }}>
                  📄 {analysis.document_type}
                </span>
              )}
              {enterpriseSummary && enterpriseSummary.doc_type && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700,
                  background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)", color: "#34D399",
                  textTransform: "uppercase", letterSpacing: "0.5px",
                }}>
                  🏷 {enterpriseSummary.doc_type}
                </span>
              )}
              {enterpriseSummary && enterpriseSummary.key_findings && enterpriseSummary.key_findings.length > 0 && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: "rgba(59,130,246,0.12)", border: "1px solid rgba(59,130,246,0.2)", color: "#60A5FA",
                }}>
                  🔍 {enterpriseSummary.key_findings.length} Finding{enterpriseSummary.key_findings.length !== 1 ? 's' : ''}
                </span>
              )}
              {enterpriseSummary && enterpriseSummary.risks && enterpriseSummary.risks.length > 0 && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.2)", color: "#F87171",
                }}>
                  ⚠ {enterpriseSummary.risks.length} Risk{enterpriseSummary.risks.length !== 1 ? 's' : ''}
                </span>
              )}
              {enterpriseSummary && enterpriseSummary.actions && enterpriseSummary.actions.length > 0 && (
                <span style={{
                  padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
                  background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.2)", color: "#FCD34D",
                }}>
                  ✓ {enterpriseSummary.actions.length} Action{enterpriseSummary.actions.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
      {/* ── Enterprise Summary Card ── */}
      {analysis && analysis.status === "READY" && enterpriseSummary && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span>🏢 Enterprise Summary</span>
            {enterpriseSummary.doc_type && (
              <span style={{ ...pillStyle, backgroundColor: "rgba(99,102,241,0.15)", borderColor: "rgba(99,102,241,0.25)", color: "#818CF8" }}>
                {enterpriseSummary.doc_type.toUpperCase()}
              </span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {enterpriseSummary.executive_summary && (
              <div>
                <div style={sectionLabelStyle}>Executive Summary</div>
                <p style={{ fontSize: 13, lineHeight: 1.6, color: c.textSecondary, margin: "4px 0 0" }}>
                  {enterpriseSummary.executive_summary}
                </p>
              </div>
            )}
            {enterpriseSummary.key_findings && enterpriseSummary.key_findings.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Key Findings ({enterpriseSummary.key_findings.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.key_findings.slice(0, 5).map((f, i) => (
                    <div key={i} style={{ fontSize: 13, color: c.textSecondary, paddingLeft: 12, borderLeft: `2px solid ${c.border}` }}>
                      {f}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.systems_entities && enterpriseSummary.systems_entities.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Systems & Entities</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                  {enterpriseSummary.systems_entities.slice(0, 8).map((e, i) => (
                    <span key={i} style={{
                      padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 500,
                      backgroundColor: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.2)", color: "#A78BFA",
                    }}>
                      {e.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.risks && enterpriseSummary.risks.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Risks ({enterpriseSummary.risks.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.risks.slice(0, 4).map((r, i) => (
                    <div key={i} style={{
                      fontSize: 12, color: c.textSecondary, padding: "6px 10px",
                      borderRadius: 8, backgroundColor: "rgba(239,68,68,0.08)",
                      border: "1px solid rgba(239,68,68,0.15)",
                    }}>
                      <span style={{ fontWeight: 600, color: "#F87171" }}>⚠ </span>
                      {r.risk}
                      {r.mitigation && <div style={{ marginTop: 2, fontSize: 11, color: c.textMuted }}>Mitigation: {r.mitigation}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.actions && enterpriseSummary.actions.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Actions ({enterpriseSummary.actions.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.actions.slice(0, 4).map((a, i) => (
                    <div key={i} style={{ fontSize: 13, color: c.textSecondary, paddingLeft: 12, borderLeft: `2px solid ${c.border}` }}>
                      {a}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.responsibilities && enterpriseSummary.responsibilities.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Responsibilities</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.responsibilities.slice(0, 4).map((r, i) => (
                    <div key={i} style={{
                      fontSize: 12, color: c.textSecondary, padding: "6px 10px",
                      borderRadius: 8, backgroundColor: "rgba(59,130,246,0.06)",
                      border: "1px solid rgba(59,130,246,0.12)",
                    }}>
                      <span style={{ fontWeight: 600 }}>{r.role}</span>
                      {r.department && <span style={{ color: c.textMuted }}> · {r.department}</span>}
                      <div style={{ marginTop: 2, fontSize: 11 }}>{r.responsibility}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.functional_requirements && enterpriseSummary.functional_requirements.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Requirements ({enterpriseSummary.functional_requirements.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.functional_requirements.slice(0, 5).map((r, i) => (
                    <div key={i} style={{ fontSize: 13, color: c.textSecondary, paddingLeft: 12, borderLeft: `2px solid ${c.border}` }}>
                      {r}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.decisions && enterpriseSummary.decisions.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Decisions ({enterpriseSummary.decisions.length})</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.decisions.slice(0, 4).map((d, i) => (
                    <div key={i} style={{ fontSize: 13, color: c.textSecondary, paddingLeft: 12, borderLeft: `2px solid ${c.border}` }}>
                      {d}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.compliance_requirements && enterpriseSummary.compliance_requirements.length > 0 && (
              <div>
                <div style={sectionLabelStyle}>Compliance Requirements</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                  {enterpriseSummary.compliance_requirements.slice(0, 4).map((c, i) => (
                    <div key={i} style={{ fontSize: 13, color: c.textSecondary, paddingLeft: 12, borderLeft: `2px solid ${c.border}` }}>
                      {c}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {enterpriseSummary.business_impact && (
              <div>
                <div style={sectionLabelStyle}>Business Impact</div>
                <p style={{ fontSize: 13, lineHeight: 1.6, color: c.textSecondary, margin: "4px 0 0" }}>
                  {enterpriseSummary.business_impact}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
      {analysis && analysis.status === "READY" && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span>Related Documents</span>
            {loadingRelated && (
              <span style={{ fontSize: 11, color: c.textMuted }}>Computing similarity…</span>
            )}
            {!loadingRelated && relatedDocuments.length > 0 && (
              <span style={{ fontSize: 11, color: c.textMuted }}>Top {relatedDocuments.length}</span>
            )}
          </div>
          {!loadingRelated && relatedDocuments.length === 0 && (
            <div style={{ fontSize: 13, color: c.textMuted }}>
              No related documents found. Add more documents to surface related content.
            </div>
          )}
          {relatedDocuments.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {relatedDocuments.map((rd) => (
                <div
                  key={rd.id}
                  onClick={() => {
                    setActiveDocumentId(rd.id);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    background: "rgba(59,130,246,0.04)",
                    border: "1px solid rgba(59,130,246,0.1)",
                    cursor: "pointer",
                    transition: "background 0.15s, border-color 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.background = "rgba(59,130,246,0.1)";
                    (e.currentTarget as HTMLElement).style.borderColor = "rgba(59,130,246,0.25)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.background = "rgba(59,130,246,0.04)";
                    (e.currentTarget as HTMLElement).style.borderColor = "rgba(59,130,246,0.1)";
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: c.textPrimary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                      {rd.filename}
                    </span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 999,
                      background: "rgba(59,130,246,0.12)", color: "#60A5FA", marginLeft: 8, whiteSpace: "nowrap",
                    }}>
                      {Math.round(rd.score * 100)}%
                    </span>
                  </div>
                  {rd.matched_topics.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 4 }}>
                      {rd.matched_topics.map((t) => (
                        <span key={t} style={{
                          padding: "1px 6px", borderRadius: 999, fontSize: 10,
                          background: "rgba(16,185,129,0.1)", color: "#34D399",
                        }}>
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {rd.match_reasons.length > 0 && (
                    <div style={{ fontSize: 11, color: c.textMuted, lineHeight: 1.5 }}>
                      {rd.match_reasons.map((r, i) => (
                        <div key={i}>{r}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
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
                  border: `1px solid ${c.border}`,
                  backgroundColor: "#FFFFFF",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                View Original Document
              </button>
              <button
                type="button"
                onClick={() => {
                  const el = document.getElementById("doc-content-preview")
                  if (el) el.scrollIntoView({ behavior: "smooth" })
                }}
                style={{
                  padding: "8px 12px",
                  borderRadius: 999,
                  border: `1px solid ${c.border}`,
                  backgroundColor: "#FFFFFF",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                📄 View Content
              </button>
              {ingestStatus?.status === "failed" && (
                <button
                  type="button"
                  onClick={handleRetry}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 999,
                    border: `1px solid ${c.border}`,
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

          {/* ── Document Content Preview ── */}
          {docChunks && docChunks.length > 0 && (
            <div id="doc-content-preview" style={{
              ...cardStyle,
              overflow: "hidden",
            }}>
              <div
                onClick={() => setShowDocContent(!showDocContent)}
                style={{
                  ...cardHeaderStyle,
                  cursor: "pointer",
                  userSelect: "none",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span>📖 Document Content</span>
                  <span style={{
                    fontSize: 10,
                    color: c.textMuted,
                    fontWeight: 400,
                    background: c.surfaceActive,
                    borderRadius: 8,
                    padding: "2px 8px",
                  }}>
                    {docChunks.length} section{docChunks.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <span style={{
                  fontSize: 11,
                  color: c.textMuted,
                  transition: "transform 0.2s",
                }}>
                  {showDocContent ? "▲ Hide" : "▼ Show"}
                </span>
              </div>
              {showDocContent && (
                <div style={{ maxHeight: 500, overflowY: "auto", padding: "4px 0" }}>
                  {docChunks.map((chunk, idx) => (
                    <details key={idx} style={{
                      marginBottom: idx < docChunks.length - 1 ? 10 : 0,
                      fontSize: 13,
                    }}>
                      <summary style={{
                        cursor: "pointer",
                        fontSize: 11,
                        fontWeight: 600,
                        color: c.primary,
                        padding: "6px 10px",
                        background: c.surfaceActive,
                        borderRadius: 6,
                        outline: "none",
                      }}>
                        Section {chunk.chunk_index + 1}
                      </summary>
                      <div style={{
                        padding: "10px 12px",
                        fontSize: 12.5,
                        lineHeight: 1.7,
                        color: c.textSecondary,
                        whiteSpace: "pre-wrap",
                      }}>
                        {chunk.text}
                      </div>
                    </details>
                  ))}
                </div>
              )}
            </div>
          )}

          {analysis.status === "READY" && analysis.executive_summary && (
            <div style={{
              ...cardStyle,
              borderLeft: `4px solid ${c.primary}`,
            }}>
              <div style={cardHeaderStyle}>
                <span>📋 Executive Summary</span>
                <span style={{...pillStyle, backgroundColor: "rgba(91,136,255,0.15)", borderColor: "rgba(91,136,255,0.25)", color: "#93B4FF"}}>
                  AI generated
                </span>
              </div>
              <p style={{...bodyTextStyle, fontSize: 14, lineHeight: 1.7}}>{analysis.executive_summary}</p>
            </div>
          )}

          {analysis.status === "READY" && (
            <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <span>🏷️ Topics & Business Areas</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {analysis.topics.map((topic) => (
                  <span key={topic} style={chipStyle}>
                    {topic}
                  </span>
                ))}
                {analysis.topics.length === 0 && (
                  <span style={{ fontSize: 13, color: c.textMuted }}>No topics extracted</span>
                )}
              </div>
            </div>
          )}

          {analysis.status === "READY" && (
            <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <span>🔧 Systems & Entities</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {analysis.entities.map((entity) => (
                  <span key={entity} style={chipOutlineStyle}>
                    {entity}
                  </span>
                ))}
                {analysis.entities.length === 0 && (
                  <span style={{ fontSize: 13, color: c.textMuted }}>No entities extracted</span>
                )}
              </div>
            </div>
          )}

          {analysis.status === "READY" && analysis.detailed_summary && analysis.detailed_summary.length > 0 && (
            <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <span>📄 Detailed Summary</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {analysis.detailed_summary.map((item, idx) => (
                  <p key={idx} style={{...bodyTextStyle, margin: 0, paddingLeft: 12, borderLeft: `2px solid ${c.border}`}}>
                    {item}
                  </p>
                ))}
              </div>
            </div>
          )}

          {analysis.status === "READY" && ((analysis.action_items?.length ?? 0) > 0 || (analysis.decisions?.length ?? 0) > 0) && (
            <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <span>⚡ Actions & Decisions</span>
              </div>
              {(analysis.action_items?.length ?? 0) > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={sectionLabelStyle}>Action Items</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {analysis.action_items?.slice(0, 6).map((item, idx) => (
                      <div key={idx} style={{...bodyTextStyle, margin: 0, padding: '8px 12px', background: 'rgba(245,158,11,0.06)', borderRadius: 8, borderLeft: '3px solid rgba(245,158,11,0.3)'}}>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(analysis.decisions?.length ?? 0) > 0 && (
                <div>
                  <div style={sectionLabelStyle}>Decisions</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {analysis.decisions?.slice(0, 6).map((item, idx) => (
                      <div key={idx} style={{...bodyTextStyle, margin: 0, padding: '8px 12px', background: 'rgba(59,130,246,0.06)', borderRadius: 8, borderLeft: '3px solid rgba(59,130,246,0.3)'}}>
                        ✓ {item}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
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
        <div style={{ fontWeight: 700, color: c.textPrimary }}>Copilot</div>
        <div style={{ fontSize: 12, color: c.textMuted }}>
          Suggested prompts and chat
        </div>
      </div>
        <div style={cardStyle}>
          <details style={{ marginBottom: 0 }}>
            <summary style={{
              cursor: "pointer",
              color: c.textPrimary,
              fontWeight: 700,
              fontSize: 14,
              padding: "6px 0",
              outline: "none",
              userSelect: "none",
              ...cardHeaderStyle,
              display: "flex",
              justifyContent: "space-between",
              gap: 10,
            }}>
              <span>Suggested Prompts</span>
            </summary>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button
                type="button"
                onClick={openDiagram}
                disabled={!isAuthenticated}
                style={{
                  padding: "6px 10px",
                  borderRadius: 10,
                  border: `1px solid ${c.border}`,
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
                  border: `1px solid ${c.border}`,
                  backgroundColor: "#FFFFFF",
                  cursor: !isAuthenticated ? "default" : "pointer",
                  opacity: !isAuthenticated ? 0.6 : 1,
                  fontSize: 12,
                }}
              >
                Chart builder
              </button>
            </div>
          </details>
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

      {analysis && analysis.status === "READY" && (enterpriseSummary?.executive_summary || analysis.executive_summary) && (
        <div style={{
          ...cardStyle,
          borderLeft: `4px solid ${c.primary}`,
          marginBottom: 0,
        }}>
          <div style={cardHeaderStyle}>
            <span>Executive Summary</span>
            {enterpriseSummary && enterpriseSummary.doc_type && (
              <span style={{
                padding: "2px 8px", borderRadius: 999, fontSize: 10, fontWeight: 700,
                background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)", color: "#34D399",
                textTransform: "uppercase", letterSpacing: "0.5px",
              }}>
                {enterpriseSummary.doc_type}
              </span>
            )}
          </div>
          <p style={{...bodyTextStyle, fontSize: 14, lineHeight: 1.7, margin: 0}}>
            {enterpriseSummary?.executive_summary || analysis.executive_summary}
          </p>
        </div>
      )}

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
            height: "100%",
            maxHeight: "calc(100vh - 360px)",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            scrollBehavior: "smooth",
            paddingRight: "8px",
          }}
        >
          {/* Recently Uploaded Documents Summary */}
          {activeDocumentId && recentDocuments.length > 0 && chatMessages.length === 0 && (
            <div
              style={{
                backgroundColor: "rgba(59, 130, 246, 0.08)",
                border: "1px solid rgba(59, 130, 246, 0.2)",
                borderRadius: 12,
                padding: 12,
                marginBottom: 8,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: c.textPrimary, marginBottom: 8 }}>
                📄 Recently Uploaded Document
              </div>
              <div style={{ fontSize: 13, color: c.textPrimary, marginBottom: 6 }}>
                <strong>{recentDocuments[0]?.filename}</strong>
              </div>
              <div style={{ fontSize: 12, color: c.textMuted }}>
                Uploaded: {new Date(recentDocuments[0]?.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </div>
              {recentDocuments[0]?.status !== 'completed' && (
                <div style={{ fontSize: 11, color: c.textMuted, marginTop: 6, fontStyle: 'italic' }}>
                  Status: {recentDocuments[0]?.status}
                </div>
              )}
            </div>
          )}

          {chatMessages.length === 0 && (
            <div style={{ color: c.textMuted, fontSize: 13 }}>
              {activeDocumentId
                ? "No messages yet. Ask a question about this document using the suggested prompts or ask your own question."
                : "No document selected yet. Ask a general question, or open one of your documents for document-grounded chat."}
            </div>
          )}
          {chatMessages.map((m) => {
            const isUser = m.role === "user"
            const isSystem = m.role === "system"
            const isError = m.uiStatus === "error"
            const opacity = m.uiStatus === "waiting" ? 1 : m.status === "pending" ? 0.88 : 1
            return (
              <div
                key={String(m.id)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  alignItems: isSystem ? "center" : isUser ? "flex-end" : "flex-start",
                  opacity,
                }}
              >
                {/* Avatar + bubble row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-end",
                    gap: 8,
                    flexDirection: isUser ? "row-reverse" : "row",
                    maxWidth: isSystem ? "90%" : "82%",
                  }}
                >
                  {/* Avatar */}
                  {!isSystem && (
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        background: isUser
                          ? "linear-gradient(135deg, #5B88FF, #1FE7FF)"
                          : "linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06))",
                        border: isUser ? "none" : "1px solid rgba(255,255,255,0.12)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 13,
                        flexShrink: 0,
                        color: isUser ? "#fff" : "rgba(255,255,255,0.7)",
                        fontWeight: 700,
                        boxShadow: isUser ? "0 2px 8px rgba(91,136,255,0.3)" : "none",
                      }}
                    >
                      {isUser ? <UserIcon /> : "AI"[0]}
                    </div>
                  )}

                  {/* Bubble */}
                  <div
                    style={{
                      padding: isSystem ? "8px 14px" : "12px 16px",
                      borderRadius: isUser ? "18px 18px 4px 18px" : isSystem ? 10 : "4px 18px 18px 18px",
                      background: isError && isSystem
                        ? "rgba(239,68,68,0.12)"
                        : isSystem
                          ? "rgba(255,255,255,0.05)"
                          : isError && isUser
                            ? "rgba(107,114,128,0.5)"
                            : isUser
                              ? "linear-gradient(135deg, #3B6FE8 0%, #5B88FF 100%)"
                              : "rgba(255,255,255,0.07)",
                      border: isError && isSystem
                        ? "1px solid rgba(239,68,68,0.25)"
                        : isSystem
                          ? "1px solid rgba(255,255,255,0.08)"
                          : isUser
                            ? "none"
                            : "1px solid rgba(255,255,255,0.1)",
                      color: isSystem ? "rgba(255,255,255,0.55)" : isUser ? "#FFFFFF" : "#E5E7EB",
                      fontSize: isSystem ? 12 : 14,
                      lineHeight: 1.6,
                      backdropFilter: isUser ? "none" : "blur(8px)",
                      boxShadow: isUser
                        ? "0 4px 16px rgba(59,111,232,0.35)"
                        : isSystem
                          ? "none"
                          : "0 2px 12px rgba(0,0,0,0.25)",
                      maxWidth: "100%",
                      wordBreak: "break-word" as const,
                    }}
                  >
                    {m.uiStatus === "waiting" ? (
                      <RobotSearching />
                    ) : m.uiStatus === "streaming" ? (
                      <>
                        {renderRichContent(apiBaseUrl, m.content)}
                        <span style={{ display: "inline-block", width: 2, height: "1em", backgroundColor: c.primary, marginLeft: 2, animation: "streaming-blink 1s step-end infinite", verticalAlign: "text-bottom" }} />
                      </>
                    ) : (
                      renderRichContent(apiBaseUrl, m.content)
                    )}
                    {m.uiStatus === "sending" && (
                      <div style={{ marginTop: 4, fontSize: 11, opacity: 0.6 }}>Sending…</div>
                    )}
                    {m.uiStatus === "error" && isUser && (
                      <div style={{ marginTop: 4, fontSize: 11, color: "rgba(255,200,200,0.8)" }}>⚠ Not sent</div>
                    )}
                    {m.retryText && (
                      <button
                        type="button"
                        onClick={() => handleRetryMessage(m.retryText!, m.id)}
                        style={{
                          marginTop: 8,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: 12,
                          padding: "4px 12px",
                          borderRadius: 999,
                          border: "1px solid rgba(239,68,68,0.4)",
                          background: "rgba(239,68,68,0.08)",
                          color: "#F87171",
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        ↩ Retry
                      </button>
                    )}
                  </div>
                </div>

                {/* Citations */}
                {!isUser && !isSystem && (m.citations?.length ?? 0) > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 5, paddingLeft: 36 }}>
                    {m.citations.map((c, cidx) => (
                      <span
                        key={`${c.filename}-${c.chunk_index}-${cidx}`}
                        title={c.text}
                        style={{
                          fontSize: 11,
                          padding: "3px 8px",
                          borderRadius: 8,
                          border: "1px solid rgba(91,136,255,0.25)",
                          background: "rgba(91,136,255,0.08)",
                          color: "rgba(91,136,255,0.9)",
                          cursor: "default",
                        }}
                      >
                        📄 {c.filename.length > 22 ? c.filename.slice(0, 22) + "…" : c.filename}
                      </span>
                    ))}
                  </div>
                )}

                {/* Reasoning / Thinking */}
                {!isUser && !isSystem && m.reasoning && (
                  <details style={{ paddingLeft: 36, marginTop: 8 }}>
                    <summary style={{
                      cursor: "pointer",
                      color: "rgba(255,255,255,0.35)",
                      fontWeight: 600,
                      fontSize: 10.5,
                      letterSpacing: "0.3px",
                      textTransform: "uppercase" as const,
                      userSelect: "none",
                      outline: "none",
                    }}>
                      💭 Show reasoning
                    </summary>
                    <div style={{
                      marginTop: 6,
                      padding: "10px 14px",
                      background: "rgba(255,255,255,0.04)",
                      borderRadius: 8,
                      color: "rgba(255,255,255,0.5)",
                      fontSize: 12,
                      lineHeight: 1.65,
                      fontStyle: "italic",
                      whiteSpace: "pre-wrap",
                      borderLeft: "3px solid rgba(91,136,255,0.3)",
                    }}>
                      {m.reasoning}
                    </div>
                  </details>
                )}

                {/* Timestamp */}
                {m.created_at && (
                  <div
                    style={{
                      fontSize: 10,
                      color: "rgba(255,255,255,0.2)",
                      paddingLeft: isUser ? 0 : 36,
                      paddingRight: isUser ? 36 : 0,
                      textAlign: isSystem ? "center" : isUser ? "right" : "left",
                    }}
                  >
                    {m.created_at}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {chatInfo && (
          <div style={{ marginTop: 10, fontSize: 12, color: c.textMuted }}>
            {chatInfo}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            onClick={() => setIsRefDocOpen(!isRefDocOpen)}
            title="Reference documents from projects"
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              border: `1px solid ${selectedRefDocuments.length > 0 ? c.accent : "rgba(255,255,255,0.12)"}`,
              backgroundColor: selectedRefDocuments.length > 0 ? "rgba(37,99,235,0.15)" : "transparent",
              color: selectedRefDocuments.length > 0 ? c.accent : "#999999",
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              whiteSpace: "nowrap",
            }}
          >
            <span>📎 Refs</span>
            {selectedRefDocuments.length > 0 && (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 18,
                  height: 18,
                  borderRadius: "50%",
                  backgroundColor: c.accent,
                  color: "#FFFFFF",
                  fontSize: 10,
                  fontWeight: "600",
                }}
              >
                {selectedRefDocuments.length}
              </span>
            )}
          </button>
          {selectedRefDocuments.length > 0 && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", flex: 1 }}>
              {selectedRefDocuments.map((doc) => (
                <div
                  key={doc}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 8px",
                    borderRadius: 6,
                    backgroundColor: "rgba(37,99,235,0.1)",
                    border: `1px solid ${c.accent}`,
                    fontSize: 11,
                    color: c.accent,
                  }}
                >
                  <span>{doc.length > 20 ? doc.substring(0, 20) + "…" : doc}</span>
                  <button
                    type="button"
                    onClick={() => setSelectedRefDocuments(selectedRefDocuments.filter((d) => d !== doc))}
                    style={{
                      background: "none",
                      border: "none",
                      color: c.accent,
                      cursor: "pointer",
                      fontSize: 12,
                      padding: 0,
                      height: 16,
                      width: 16,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {isRefDocOpen && (
          <div
            ref={refDocMenuRef}
            style={{
              marginBottom: 8,
              padding: 12,
              borderRadius: 8,
              border: `2px solid ${c.accent}`,
              backgroundColor: isDark ? c.bgSecondary : "#FFFFFF",
              maxHeight: "380px",
              overflowY: "auto",
              boxShadow: isDark ? "0 4px 12px rgba(0,0,0,0.4)" : "0 4px 12px rgba(0,0,0,0.15)",
            }}
          >
            <div style={{ fontSize: 13, color: c.text, marginBottom: 12, fontWeight: 700 }}>
              {documents && documents.length > 0
                ? `📁 Repositories & Documents (${documents.length} available)`
                : "No repositories or documents available. Upload a document first."}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {documents && documents.length > 0 ? (
                Array.from(
                  documents.reduce((acc, doc) => {
                    const projName = doc.project_name || "📁 Uncategorized"
                    if (!acc.has(projName)) {
                      acc.set(projName, [])
                    }
                    acc.get(projName)!.push(doc)
                    return acc
                  }, new Map<string, typeof documents>())
                )
                  .sort((a, b) => a[0].localeCompare(b[0]))
                  .map(([projectName, projectDocs]) => {
                    const projectSelected = projectDocs.every((d) =>
                      selectedRefDocuments.includes(d.filename)
                    )
                    const projectIndeterminate =
                      projectDocs.some((d) => selectedRefDocuments.includes(d.filename)) &&
                      !projectSelected
                    return (
                      <div key={projectName} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "10px 8px",
                            borderRadius: 6,
                            cursor: "pointer",
                            backgroundColor:
                              projectSelected || projectIndeterminate
                                ? c.surfaceActive
                                : "transparent",
                            fontWeight: 700,
                            fontSize: 13,
                            color: c.text,
                            border: projectSelected || projectIndeterminate ? `1px solid ${c.accent}` : "1px solid transparent",
                            transition: "all 0.15s ease",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={projectSelected}
                            ref={(el) => {
                              if (el) el.indeterminate = projectIndeterminate
                            }}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedRefDocuments([
                                  ...selectedRefDocuments,
                                  ...projectDocs
                                    .map((d) => d.filename)
                                    .filter((f) => !selectedRefDocuments.includes(f)),
                                ])
                              } else {
                                setSelectedRefDocuments(
                                  selectedRefDocuments.filter(
                                    (f) => !projectDocs.map((d) => d.filename).includes(f)
                                  )
                                )
                              }
                            }}
                            style={{
                              width: 14,
                              height: 14,
                              cursor: "pointer",
                              accentColor: c.accent,
                            }}
                          />
                          <span style={{ fontWeight: 600 }}>{projectName}</span>
                          <span style={{ fontSize: 11, opacity: 0.7, marginLeft: "auto", color: c.textMuted, fontWeight: 500 }}>
                            {projectDocs.length} doc{projectDocs.length !== 1 ? "s" : ""}
                          </span>
                        </label>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginLeft: 24 }}>
                          {projectDocs
                            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                            .map((doc) => {
                              const docDate = new Date(doc.created_at)
                              const dateStr = docDate.toLocaleDateString()
                              return (
                                <label
                                  key={doc.id}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                    padding: "7px 8px",
                                    borderRadius: 4,
                                    cursor: "pointer",
                                    backgroundColor: selectedRefDocuments.includes(doc.filename)
                                      ? c.surfaceActive
                                      : (isDark ? "transparent" : "#F9F9F9"),
                                    fontSize: 12,
                                    color: c.text,
                                    border: selectedRefDocuments.includes(doc.filename)
                                      ? `1px solid ${c.accent}`
                                      : `1px solid ${c.border}`,
                                    transition: "all 0.15s ease",
                                  }}
                                >
                                  <input
                                    type="checkbox"
                                    checked={selectedRefDocuments.includes(doc.filename)}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedRefDocuments([
                                          ...selectedRefDocuments,
                                          doc.filename,
                                        ])
                                      } else {
                                        setSelectedRefDocuments(
                                          selectedRefDocuments.filter(
                                            (d) => d !== doc.filename
                                          )
                                        )
                                      }
                                    }}
                                    style={{
                                      width: 16,
                                      height: 16,
                                      cursor: "pointer",
                                      accentColor: c.accent,
                                      flexShrink: 0,
                                    }}
                                  />
                                  <span
                                    style={{
                                      flex: 1,
                                      minWidth: 0,
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                      fontWeight: 500,
                                    }}
                                  >
                                    📄 {doc.filename}
                                  </span>
                                  <span
                                    style={{
                                      opacity: 0.75,
                                      whiteSpace: "nowrap",
                                      fontSize: 11,
                                      color: c.textMuted,
                                      fontWeight: 400,
                                    }}
                                  >
                                    {dateStr}
                                  </span>
                                </label>
                              )
                            })}
                        </div>
                      </div>
                    )
                  })
              ) : (
                <div style={{ fontSize: 13, color: "#666666", padding: "12px", textAlign: "center", fontWeight: 500 }}>
                  ℹ️ No projects or documents found. Create a project and upload documents to get started.
                </div>
              )}
            </div>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            let questionWithRefs = question
            if (selectedRefDocuments.length > 0) {
              questionWithRefs = `[Referencing: ${selectedRefDocuments.join(", ")}]\n\n${question}`
            }
            handleAsk(questionWithRefs)
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
            flexShrink: 0,
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
            placeholder={
              selectedRefDocuments.length > 0
                ? `Ask about the referenced document${selectedRefDocuments.length > 1 ? "s" : ""}…`
                : activeDocumentId
                  ? "Ask a question about this document…"
                  : "Ask anything about the organization, prior learning, or the web…"
            }
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
          <div style={{ position: "relative", flexShrink: 0 }} ref={scopeMenuRef}>
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
                    ? "Scope: All repositories"
                    : "Scope: This repository"}
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
                  border: `1px solid ${c.border}`,
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
                    border: `1px solid ${c.border}`,
                    backgroundColor: effectiveSearchScope === "project" ? "#E7F0FF" : "#FFFFFF",
                    cursor: !activeDocumentId ? "default" : "pointer",
                    opacity: !activeDocumentId ? 0.55 : 1,
                    fontSize: 13,
                  }}
                >
                  This repository
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
                    border: `1px solid ${c.border}`,
                    backgroundColor: effectiveSearchScope === "all" ? "#E7F0FF" : "#FFFFFF",
                    cursor: "pointer",
                    fontSize: 13,
                  }}
                >
                  {activeDocumentId ? "All repositories" : "Organization knowledge + web"}
                </button>
              </div>
            )}
          </div>
          <div style={{ position: "relative", flexShrink: 0 }} ref={historyMenuRef}>
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
                  border: `1px solid ${c.border}`,
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
                    border: `1px solid ${c.border}`,
                    fontSize: 13,
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                />
                {historyLoading ? (
                  <div style={{ fontSize: 12, color: c.textMuted }}>Loading…</div>
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
                            border: `1px solid ${c.border}`,
                            backgroundColor: "#FFFFFF",
                            cursor: "pointer",
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          <div style={{ fontSize: 13, color: c.textPrimary, fontWeight: 700 }}>
                            {s.title || s.document_id || "Conversation"}
                          </div>
                <div style={{ fontSize: 12, color: c.textMuted }}>
                            {(s.scope || "document").toUpperCase()} • {s.model || "model"} • {s.updated_at || ""}
                          </div>
                        </button>
                      ))}
                    {historySessions.length === 0 && (
                      <div style={{ fontSize: 12, color: c.textMuted }}>No conversations yet.</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          <div style={{ flexShrink: 0, width: "280px" }}>
            <ModelSelector
              providers={v2Providers}
              value={selectedModel}
              onChange={(modelId) => handleModelChange(modelId)}
              placeholder="Select model"
              disabled={isWaiting || (modelsOffline && installedModels.length === 0)}
              selectableOnly={true}
              includeLocalModels={true}
            />
          </div>
          {isTranscribing && (
            <div style={{
              fontSize: 12, color: "#FFFFFF", whiteSpace: "nowrap",
              opacity: 0.8,
            }}>
              Transcribing...
            </div>
          )}
          <button
            type="button"
            onClick={toggleRecording}
            disabled={isTranscribing}
            title={isRecording ? "Stop recording" : "Record voice message"}
            style={{
              width: 38,
              height: 38,
              borderRadius: "50%",
              border: "none",
              backgroundColor: isRecording ? "#EF4444" : "#2A2A2A",
              color: "#FFFFFF",
              fontSize: 16,
              cursor: isTranscribing ? "default" : "pointer",
              opacity: isTranscribing ? 0.5 : 1,
              flexShrink: 0,
              transition: "all 0.2s ease",
            }}
          >
            {isRecording ? "⏹" : "🎙"}
          </button>
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
            ref={pullMenuRef}
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
                    border: `1px solid ${c.border}`,
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
                    border: `1px solid ${c.border}`,
                    backgroundColor: "#F4F6F8",
                    color: c.textPrimary,
                  }}
                >
                  {pullStatus || "idle"} {pullAttempts ? `(attempt ${pullAttempts})` : ""}
                </span>
                <span style={{ fontSize: 12, color: c.textMuted }}>
                  {pullEta != null ? `ETA ~${pullEta}s` : "Pulls can be large (10–20GB)."}
                </span>
                {pullStates[pullModel]?.resume_supported && (
                  <span style={{ fontSize: 12, color: c.textMuted }}>
                    Resume supported
                  </span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: c.textPrimary }}>
                  {Math.max(0, Math.min(100, pullPercent))}%
                </div>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      height: 10,
                      borderRadius: 999,
                      backgroundColor: "#EEF2F7",
                      overflow: "hidden",
                      border: `1px solid ${c.border}`,
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.max(0, Math.min(100, pullPercent))}%`,
                        backgroundColor: pullError ? c.danger : c.primary,
                        transition: "width 200ms linear",
                      }}
                    />
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: c.textMuted }}>
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
                <div style={{ color: c.danger, fontSize: 13 }}>{pullError}</div>
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
                    border: `1px solid ${c.border}`,
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
            ref={diagramMenuRef}
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
                    border: `1px solid ${c.border}`,
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
                  border: `1px solid ${c.border}`,
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
                    backgroundColor: c.primary,
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
            ref={chartMenuRef}
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
                    border: `1px solid ${c.border}`,
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
                    <div style={{ fontSize: 12, color: c.textMuted, marginBottom: 4 }}>Chart type</div>
                    <select
                      value={chartType}
                      onChange={(e) => setChartType(e.target.value)}
                      style={{ width: "100%", padding: 8, borderRadius: 10, border: `1px solid ${c.border}` }}
                    >
                      <option value="bar" style={{ backgroundColor: c.bgSecondary, color: c.text }}>Bar</option>
                      <option value="line" style={{ backgroundColor: c.bgSecondary, color: c.text }}>Line</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: c.textMuted, marginBottom: 4 }}>X axis</div>
                    <select
                      value={chartX}
                      onChange={(e) => setChartX(e.target.value)}
                      style={{ width: "100%", padding: 8, borderRadius: 10, border: `1px solid ${c.border}` }}
                    >
                      {chartColumns.map((col) => (
                        <option key={col} value={col} style={{ backgroundColor: c.bgSecondary, color: c.text }}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: c.textMuted, marginBottom: 4 }}>Y series</div>
                    <select
                      multiple
                      value={chartY}
                      onChange={(e) => {
                        const selected = Array.from(e.target.selectedOptions).map((o) => o.value)
                        setChartY(selected)
                      }}
                      style={{ width: "100%", padding: 8, borderRadius: 10, border: `1px solid ${c.border}`, height: 90 }}
                    >
                      {(chartNumeric.length ? chartNumeric : chartColumns).map((col) => (
                        <option key={col} value={col} style={{ backgroundColor: c.bgSecondary, color: c.text }}>
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
                    backgroundColor: c.primary,
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
                backgroundColor: isDark ? c.bgSecondary : "#FFFFFF",
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
              <div style={{ fontWeight: 700, fontSize: 16, color: c.text, marginBottom: 4 }}>Upload to Repository</div>
              <div style={{ fontSize: 13, color: c.textMuted, marginBottom: 8 }}>Select an existing repository or create a new one.</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <select
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  style={{
                    flex: 1,
                    minWidth: 200,
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: `1px solid ${c.border}`,
                    fontSize: 14,
                    color: c.text,
                    backgroundColor: isDark ? c.inputBg : "#FFFFFF",
                    WebkitAppearance: "none",
                    MozAppearance: "none",
                    appearance: "none",
                    backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%23${isDark ? 'ffffff' : '0a1628'}40' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                    backgroundPosition: "right 10px center",
                    backgroundRepeat: "no-repeat",
                    backgroundSize: "16px",
                    paddingRight: "32px",
                  }}
                >
                  <option value="">No repository</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                  <option value="new">New repository…</option>
                </select>
                {selectedProjectId === "new" && (
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="New repository name"
                    style={{
                      flex: 1,
                      minWidth: 200,
                      padding: "10px 12px",
                      borderRadius: 10,
                      border: `1px solid ${c.border}`,
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
                  border: `1px solid ${c.border}`,
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
                  border: `1px solid ${c.border}`,
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
                    border: `1px solid ${c.border}`,
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
                    backgroundColor: c.primary,
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
    <div style={{ position: "relative", height: isMobile ? "auto" : "calc(100vh - 64px - 48px)", display: "flex", flexDirection: "column" }}>
      {/* Bootstrap progress banner */}
      {bootstrapRunning && (
        <div
          style={{
            position: "fixed",
            top: 72,
            left: "50%",
            transform: "translateX(-50%)",
            width: "90%",
            maxWidth: 520,
            padding: "12px 16px",
            borderRadius: 12,
            background: "rgba(15,17,23,0.95)",
            border: "1px solid rgba(91,136,255,0.2)",
            backdropFilter: "blur(16px)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            zIndex: 70,
            pointerEvents: "none",
          }}
        >
          <div style={{ fontWeight: 700, color: "#E5E7EB", fontSize: 14, marginBottom: 4 }}>
            🧠 Preparing knowledge base — {bootstrapPercent}%
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", marginBottom: 8 }}>
            You can keep using the app while indexing runs.
          </div>
          <div style={{ height: 6, borderRadius: 999, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.max(0, Math.min(100, bootstrapPercent))}%`,
                height: "100%",
                background: "linear-gradient(90deg, #5B88FF, #1FE7FF)",
                transition: "width 0.5s ease",
              }}
            />
          </div>
        </div>
      )}

      {/* Analysis drawer toggle button */}
      {analysis && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8, flexShrink: 0 }}>
          <button
            type="button"
            onClick={() => setShowAnalysisDrawer((v) => !v)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 14px",
              borderRadius: 10,
              border: showAnalysisDrawer
                ? "1px solid rgba(91,136,255,0.4)"
                : "1px solid rgba(255,255,255,0.1)",
              background: showAnalysisDrawer
                ? "rgba(91,136,255,0.12)"
                : "rgba(255,255,255,0.04)",
              color: showAnalysisDrawer ? "#5B88FF" : "rgba(255,255,255,0.5)",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "all 0.2s ease",
            }}
          >
            <span>📊</span>
            <span>{showAnalysisDrawer ? "Hide Analysis" : "Show Analysis"}</span>
          </button>
        </div>
      )}

      {/* Main layout */}
      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns:
            isMobile || !showAnalysisDrawer
              ? "minmax(0, 1fr)"
              : "minmax(0, 1fr) minmax(0, 3fr)",
          gap: 20,
          minHeight: 0,
          transition: "grid-template-columns 0.3s ease",
        }}
      >
        {isMobile ? (
          <>
            {copilotPanel}
            {showAnalysisDrawer && analysisPanel}
          </>
        ) : (
          <>
            {showAnalysisDrawer && analysisPanel}
            {copilotPanel}
          </>
        )}
      </div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.05)",
  backdropFilter: "blur(12px)",
  borderRadius: 16,
  padding: 18,
  border: "1px solid rgba(255,255,255,0.08)",
  boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
}

const cardHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 12,
  fontWeight: 700,
  color: "#E5E7EB",
  fontSize: 14,
}

const bodyTextStyle: React.CSSProperties = {
  fontSize: 14,
  color: "rgba(255,255,255,0.7)",
  lineHeight: 1.6,
}

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "rgba(255,255,255,0.35)",
  marginBottom: 6,
}

const chipStyle: React.CSSProperties = {
  padding: "4px 10px",
  borderRadius: 99,
  background: "rgba(91,136,255,0.15)",
  border: "1px solid rgba(91,136,255,0.25)",
  color: "#93B4FF",
  fontSize: 12,
  fontWeight: 500,
}

const chipOutlineStyle: React.CSSProperties = {
  padding: "4px 10px",
  borderRadius: 99,
  border: "1px solid rgba(31,231,255,0.25)",
  background: "rgba(31,231,255,0.08)",
  color: "#67E8FF",
  fontSize: 12,
  fontWeight: 500,
}

const pillStyle: React.CSSProperties = {
  fontSize: 11,
  padding: "2px 10px",
  borderRadius: 999,
  background: "rgba(245,158,11,0.15)",
  border: "1px solid rgba(245,158,11,0.25)",
  color: "#FCD34D",
  fontWeight: 600,
}

const promptChipButtonStyle: React.CSSProperties = {
  padding: "8px 14px",
  borderRadius: 10,
  border: "1px solid rgba(245,158,11,0.2)",
  background: "rgba(245,158,11,0.08)",
  color: "rgba(252,211,77,0.9)",
  fontSize: 13,
  cursor: "pointer",
  textAlign: "left",
  lineHeight: 1.4,
  transition: "all 0.2s ease",
  fontFamily: "inherit",
}
