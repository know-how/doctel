import React, { useState, useEffect, useCallback } from "react"
import { Sidebar } from "./Sidebar"
import { IntroOverlay } from "../IntroOverlay"
import { useTheme } from "../../context/ThemeContext"
import { getTokens } from "../../theme/themeTokens"
import { getUiSettings } from "../../api/client"

import { DocumentLibraryPage } from "../../pages/DocumentLibraryPage"
import { DocumentAddPage } from "../../pages/DocumentAddPage"
import { WorkspacesPage } from "../../pages/WorkspacesPage"
import { ProcessingStatusPage } from "../../pages/ProcessingStatusPage"
import { AnalyzeChatPage } from "../../pages/AnalyzeChatPage"
import { AnalyzeExtractionPage } from "../../pages/AnalyzeExtractionPage"
import { AnalyzeSummariesPage } from "../../pages/AnalyzeSummariesPage"
import { AnalyzeComparePage } from "../../pages/AnalyzeComparePage"
import { AnalyzeClassificationPage } from "../../pages/AnalyzeClassificationPage"
import { OutputsHistoryPage } from "../../pages/OutputsHistoryPage"
import { OutputsExportsPage } from "../../pages/OutputsExportsPage"
import { OutputsReportsPage } from "../../pages/OutputsReportsPage"
import { AdminModelsPage } from "../../pages/AdminModelsPage"
import { AdminModelManagementPage } from "../../pages/AdminModelManagementPage"
import { AdminProvidersPage } from "../../pages/AdminProvidersPage"
import { AdminAppConfigPage } from "../../pages/AdminAppConfigPage"
import { AdminModelMarketplacePage } from "../../pages/AdminModelMarketplacePage"
import { AdminPromptsPage } from "../../pages/AdminPromptsPage"
import { AdminPromptSuggestionsPage } from "../../pages/AdminPromptSuggestionsPage"
import { AdminContextTokensPage } from "../../pages/AdminContextTokensPage"
import { AdminIntegrationsPage } from "../../pages/AdminIntegrationsPage"
import { SystemStatusPage } from "../../pages/SystemStatusPage"
import { CollaborationTeamPage } from "../../pages/CollaborationTeamPage"
import { CollaborationActivityPage } from "../../pages/CollaborationActivityPage"
import { SharedDocumentsPage } from "../../pages/SharedDocumentsPage"
import { SettingsProfilePage } from "../../pages/SettingsProfilePage"
import { SettingsSecurityPage } from "../../pages/SettingsSecurityPage"
import { DocumentViewPage } from "../../pages/DocumentViewPage"
import { MyWorkPage } from "../../pages/MyWorkPage"
import { AdminSettingsPage } from "../../pages/AdminSettingsPage"
import { TrainingRoomPage } from "../../pages/TrainingRoomPage"
import { NewChatPage } from "../../pages/NewChatPage"

interface AuthenticatedLayoutProps {
  onLogout: () => void
  userRole: string
  displayName: string
  isAuthenticated: boolean
}

const COLLAPSED_KEY = "docintel_sidebar_collapsed"

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === "true"
  } catch {
    return false
  }
}

export const AuthenticatedLayout: React.FC<AuthenticatedLayoutProps> = ({
  onLogout,
  userRole,
  displayName,
  isAuthenticated,
}) => {
  const { theme: themeName } = useTheme()
  const t = getTokens(themeName)

  const [currentPath, setCurrentPath] = useState(() => {
    // Read initial path from URL on mount
    if (typeof window !== "undefined") {
      return window.location.pathname || "/chat"
    }
    return "/chat"
  })
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [workspaceProjectId, setWorkspaceProjectId] = useState<string | null>(null)
  const [introVisible, setIntroVisible] = useState(false)
  const [collapsed, setCollapsed] = useState(loadCollapsed)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [uiCfg, setUiCfg] = useState<any>({
    show_intro_animation: true,
    show_greeting_message: true,
    intro_duration_ms: 2400,
    greeting_messages: [],
  })

  useEffect(() => {
    const loadUi = async () => {
      try {
        const ui = await getUiSettings()
        setUiCfg(ui || {})
        const showIntro =
          Boolean(ui?.show_intro_animation) ||
          Boolean(ui?.show_greeting_message)
        if (showIntro) setIntroVisible(true)
      } catch {}
    }
    loadUi()
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, String(collapsed))
    } catch {}
  }, [collapsed])

  useEffect(() => {
    if (currentPath.startsWith("/admin") && userRole !== "admin") {
      setCurrentPath("/documents/library")
    }
  }, [currentPath, userRole])

  const handleOpenDocument = useCallback((id: string) => {
    setDocumentId(id)
    setCurrentPath("/copilot")
  }, [])

  const handleNavigate = useCallback((path: string) => {
    const qIdx = path.indexOf("?")
    if (qIdx >= 0) {
      const qs = path.slice(qIdx + 1)
      const params = new URLSearchParams(qs)
      const pid = params.get("project_id")
      if (pid) setWorkspaceProjectId(pid)
      setCurrentPath(path.slice(0, qIdx))
    } else {
      setCurrentPath(path)
    }
    // Close mobile sidebar when navigating
    setMobileMenuOpen(false)
  }, [])

  const handleToggleSidebar = useCallback(() => {
    setCollapsed((v) => !v)
  }, [])

  const toggleMobileMenu = useCallback(() => {
    setMobileMenuOpen((v) => !v)
  }, [])

  const renderPage = () => {
    switch (currentPath) {
      case "/documents":
      case "/documents/library":
        return <DocumentLibraryPage key={workspaceProjectId || "all"} onOpenDocument={handleOpenDocument} initialProjectId={workspaceProjectId} />
      case "/documents/add":
        return <DocumentAddPage onOpenDocument={handleOpenDocument} />
      case "/documents/workspaces":
        return <WorkspacesPage onNavigate={handleNavigate} onOpenDocument={handleOpenDocument} />
      case "/documents/status":
        return <ProcessingStatusPage />
      case "/analyze/chat":
        return <AnalyzeChatPage />
      case "/analyze/extraction":
        return <AnalyzeExtractionPage />
      case "/analyze/summaries":
        return <AnalyzeSummariesPage />
      case "/analyze/compare":
        return <AnalyzeComparePage />
      case "/analyze/classification":
        return <AnalyzeClassificationPage />
      case "/outputs/history":
        return <OutputsHistoryPage />
      case "/outputs/exports":
        return <OutputsExportsPage />
      case "/outputs/reports":
        return <OutputsReportsPage />
      case "/admin/app-config":
        return <AdminAppConfigPage />
      case "/admin/models":
        return <AdminModelManagementPage />
      case "/admin/providers":
        return <AdminProvidersPage />
      case "/admin/marketplace":
        return <AdminModelMarketplacePage />
      case "/admin/prompts":
        return <AdminPromptsPage />
      case "/admin/prompt-suggestions":
        return <AdminPromptSuggestionsPage />
      case "/admin/context":
        return <AdminContextTokensPage />
      case "/admin/integrations":
        return <AdminIntegrationsPage />
      case "/team":
        return <CollaborationTeamPage />
      case "/shared":
        return <SharedDocumentsPage />
      case "/activity":
        return <CollaborationActivityPage />
      case "/settings/profile":
        return <SettingsProfilePage />
      case "/settings/security":
        return <SettingsSecurityPage />
      case "/copilot":
        return (
          <DocumentViewPage
            documentId={documentId}
            isAuthenticated={isAuthenticated}
            authEpoch={0}
          />
        )
      case "/mywork":
        return <MyWorkPage onOpenDocument={handleOpenDocument} />
      case "/admin/system":
        return <SystemStatusPage />
      case "/admin-settings":
        return <AdminSettingsPage />
      case "/training":
        return <TrainingRoomPage />
      case "/chat":
        return <NewChatPage />
      default:
        return <DocumentLibraryPage onOpenDocument={handleOpenDocument} />
    }
  }

  return (
    <div
      className="docintel-layout-root"
      style={{
        display: "flex",
        height: "100vh",
        overflow: "hidden",
        background: t.gradients.bg,
        color: t.colors.text,
        fontFamily: t.font.sans,
      }}
    >
      <style>{`
        @media (max-width: 768px) {
          .docintel-layout-content {
            padding-left: 52px !important;
          }
        }
      `}</style>
      <Sidebar
        currentPath={currentPath}
        onNavigate={handleNavigate}
        onLogout={onLogout}
        userRole={userRole}
        displayName={displayName}
        isAuthenticated={isAuthenticated}
        collapsed={collapsed}
        onToggleCollapse={handleToggleSidebar}
        mobileMenuOpen={mobileMenuOpen}
        onToggleMobileMenu={toggleMobileMenu}
      />

      <div
        className="docintel-layout-content"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          overflowY: "auto",
          overflowX: "hidden",
        }}
      >
        {renderPage()}
      </div>

      <IntroOverlay
        visible={introVisible}
        durationMs={Number(uiCfg?.intro_duration_ms) || 2400}
        showGreeting={Boolean(uiCfg?.show_greeting_message)}
        greetingMessages={(uiCfg?.greeting_messages || []) as string[]}
        displayName={displayName}
        onDone={() => setIntroVisible(false)}
      />
    </div>
  )
}
