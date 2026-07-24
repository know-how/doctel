import React, { useCallback, useEffect, useState } from "react"
import { View, Text, Pressable, Modal, TextInput, Image, ScrollView, useWindowDimensions, ActivityIndicator } from "react-native"
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { DashboardScreen } from "./src/screens/DashboardScreen"
import { DocumentUploadScreen } from "./src/screens/DocumentUploadScreen"
import { ChatScreen } from "./src/screens/ChatScreen"
import { GlobalChatScreen } from "./src/screens/GlobalChatScreen"
import { ModelSelectorScreen } from "./src/screens/ModelSelectorScreen"
import { ProjectsScreen } from "./src/screens/ProjectsScreen"
import { ChatSessionsScreen } from "./src/screens/ChatSessionsScreen"
import { SystemStatusScreen } from "./src/screens/SystemStatusScreen"
import { useEcNumber } from "./src/hooks/useEcNumber"
import { useSyncEvents } from "./src/hooks/useSyncEvents"
import { useConnectionMonitor } from "./src/hooks/useConnectionMonitor"
import ConnectionToast from "./src/components/ConnectionToast"
import { login, setAuthToken, requestEmailOtp, verifyEmailOtp, logout } from "./src/api/client"
import zetdcLogo from "./src/assets/zetdc-logo.png"
import { DocChatAnimation } from "./src/components/DocChatAnimation"
import { ThemeProvider, useTheme } from "./src/context/ThemeContext"
import { ModelProvider, useModel } from "./src/context/ModelContext"
import { SidebarDrawer } from "./src/navigation/SidebarDrawer"
import { InlineSidebar } from "./src/navigation/InlineSidebar"
import { DocumentLibraryScreen } from "./src/screens/DocumentLibraryScreen"
import { DocumentAddScreen } from "./src/screens/DocumentAddScreen"
import { WorkspacesScreen } from "./src/screens/WorkspacesScreen"
import { ProcessingStatusScreen } from "./src/screens/ProcessingStatusScreen"
import { AnalyzeChatScreen } from "./src/screens/AnalyzeChatScreen"
import { AnalyzeExtractionScreen } from "./src/screens/AnalyzeExtractionScreen"
import { AnalyzeSummariesScreen } from "./src/screens/AnalyzeSummariesScreen"
import { AnalyzeCompareScreen } from "./src/screens/AnalyzeCompareScreen"
import { AnalyzeClassificationScreen } from "./src/screens/AnalyzeClassificationScreen"
import { OutputsHistoryScreen } from "./src/screens/OutputsHistoryScreen"
import { AdminModelsScreen } from "./src/screens/AdminModelsScreen"
import { AdminPromptsScreen } from "./src/screens/AdminPromptsScreen"
import { V2AdminScreen } from "./src/screens/V2AdminScreen"
import { ProvidersScreen } from "./src/screens/ProvidersScreen"
import { ProviderDetailScreen } from "./src/screens/ProviderDetailScreen"
import { ModelManagementScreen } from "./src/screens/ModelManagementScreen"
import { TaskMappingScreen } from "./src/screens/TaskMappingScreen"
import { SettingsProfileScreen } from "./src/screens/SettingsProfileScreen"
import { CollaborationTeamScreen } from "./src/screens/CollaborationTeamScreen"
import { NewChatScreen } from "./src/screens/NewChatScreen"
// ── New admin & feature screens (frontend alignment) ──────────
import { AdminEmbeddingsScreen } from "./src/screens/AdminEmbeddingsScreen"
import { AdminAutoRoutingScreen } from "./src/screens/AdminAutoRoutingScreen"
import { AdminStorageScreen } from "./src/screens/AdminStorageScreen"
import { AdminSecurityScreen } from "./src/screens/AdminSecurityScreen"
import { AdminRBACScreen } from "./src/screens/AdminRBACScreen"
import { AdminDepartmentsScreen } from "./src/screens/AdminDepartmentsScreen"
import { AdminDiagnosticsScreen } from "./src/screens/AdminDiagnosticsScreen"
import { AdminAuditScreen } from "./src/screens/AdminAuditScreen"
import { AdminIntegrationsScreen } from "./src/screens/AdminIntegrationsScreen"
import { DocumentViewScreen } from "./src/screens/DocumentViewScreen"
import { SettingsSecurityScreen } from "./src/screens/SettingsSecurityScreen"
import { OutputsExportsScreen } from "./src/screens/OutputsExportsScreen"
import { OutputsReportsScreen } from "./src/screens/OutputsReportsScreen"

type ScreenType = "main" | "chat" | "upload" | "global-chat" | "models" | "projects" | "sessions" | "status"

const navTabs: Array<{ id: ScreenType; label: string; icon: string }> = [
  { id: "main", label: "Home", icon: "🏠" },
  { id: "upload", label: "Upload", icon: "⬆️" },
  { id: "chat", label: "Copilot", icon: "✦" },
  { id: "global-chat", label: "Global", icon: "🌍" },
  { id: "projects", label: "Repos", icon: "🗂️" },
  { id: "sessions", label: "History", icon: "📋" },
  { id: "models", label: "Models", icon: "🤖" },
  { id: "status", label: "Status", icon: "🔧" },
]

function getPageTitle(path: string): string {
  const titles: Record<string, string> = {
    "/documents/library": "Document Library",
    "/documents/add": "Add Document",
    "/documents/workspaces": "Workspaces",
    "/documents/status": "Processing Status",
    "/documents/view": "Document View",
    "/chat": "New Chat",
    "/analyze/chat": "Ask Documents",
    "/analyze/extraction": "Extraction",
    "/analyze/summaries": "Summaries",
    "/analyze/compare": "Compare",
    "/analyze/classification": "Classification",
    "/outputs/history": "Output History",
    "/outputs/exports": "Exports",
    "/outputs/reports": "Reports",
    // ── AI PLATFORM ────────────────────────────────────
    "/admin/providers": "Providers",
    "/admin/models": "Model Catalog",
    "/admin/embeddings": "Embeddings",
    "/admin/prompts": "Prompt Management",
    "/admin/auto-routing": "Auto Routing",
    "/admin/system": "System Status",
    // ── ADMINISTRATION ─────────────────────────────────
    "/admin/storage": "Storage",
    "/admin/integrations": "Integrations",
    "/admin/security": "Security",
    "/admin/rbac": "RBAC",
    "/admin/departments": "Departments",
    "/admin/diagnostics": "Diagnostics",
    "/admin/audit": "Audit",
    // ── Settings ───────────────────────────────────────
    "/settings/profile": "Profile",
    "/settings/security": "Security",
    // ── Collaboration ──────────────────────────────────
    "/team": "Team",
    "/shared": "Shared Workspaces",
    "/activity": "Activity",
  }
  return titles[path] || "Documents"
}

function PlaceholderPage({ title, emoji }: { title: string; emoji?: string }) {
  const { tokens: t } = useTheme()
  return (
    <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: t.colors.bg, padding: t.spacing.lg }}>
      <Text style={{ fontSize: 48, marginBottom: t.spacing.md }}>{emoji || "🚧"}</Text>
      <Text style={{ fontSize: 18, fontWeight: "700", color: t.colors.text, marginBottom: t.spacing.xs, textAlign: "center" }}>{title}</Text>
      <Text style={{ fontSize: 13, color: t.colors.textMuted, textAlign: "center" }}>This page is under construction and will be available soon.</Text>
    </View>
  )
}

function AppContent() {
  const { tokens: t, isDark } = useTheme()
  const { width: windowWidth } = useWindowDimensions()
  const isTablet = windowWidth >= 768
  const [documentId, setDocumentId] = useState("doc_1")
  const [documentViewFilename, setDocumentViewFilename] = useState<string | undefined>(undefined)
  const { ecNumber, setEcNumber } = useEcNumber()
  const { reloadModels } = useModel()
  const [activeTab, setActiveTab] = useState<ScreenType>("main")
  const [inputValue, setInputValue] = useState(ecNumber)
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [emailCode, setEmailCode] = useState("")
  const [emailSent, setEmailSent] = useState(false)
  const [loginMode, setLoginMode] = useState<"ec" | "email">("email")
  const [touched, setTouched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState("")
  const [hasToken, setHasToken] = useState(false)
  const [checkingToken, setCheckingToken] = useState(true)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [currentPath, setCurrentPath] = useState("/chat")
  const [userRole, setUserRole] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [workspaceProjectId, setWorkspaceProjectId] = useState<string | null>(null)

  // ── Backend connection check (live monitor) ─────────────────
  const {
    checked: connectionChecked,
    ok: connectionOk,
    initialChecking: connectionChecking,
    liveChecking,
    error: connectionError,
    startupSteps,
    backendRunning,
    ollamaRunning,
    reconnectAttempt,
    recheck,
  } = useConnectionMonitor()

  const hasEc = !!ecNumber
  const showError = touched && !inputValue.trim()
  const showPasswordError = touched && !password.trim()
  const isAuthenticated = hasEc && hasToken
  const showEmailError = touched && !email.trim()
  const showEmailCodeError = touched && !emailCode.trim()
  const isValidZetdcEmail =
    !!email.trim() && email.trim().toLowerCase().endsWith("@zetdc.co.zw")

  useEffect(() => {
    const loadToken = async () => {
      const token = await AsyncStorage.getItem("docintel_auth_token")
      setHasToken(!!token)
      setCheckingToken(false)
    }
    loadToken()
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await logout()
    } catch {
    } finally {
      await setEcNumber("")
      setHasToken(false)
      setInputValue("")
      setPassword("")
      setEmail("")
      setEmailCode("")
      setEmailSent(false)
      setTouched(false)
      setAuthError("")
      setUserRole("")
      setDisplayName("")
    }
  }, [setEcNumber])

  useSyncEvents({
    enabled: isAuthenticated,
    onLogout: () => handleLogout(),
  })

  function renderPage() {
    const isAdmin = userRole === "admin"

    // ── Dynamic provider detail routes (support both old v2 and new paths) ──
    const providerDetailMatch = currentPath.match(/^\/(admin\/v2\/providers|admin\/providers)\/([^/]+)$/)
    if (providerDetailMatch) {
      const providerId = decodeURIComponent(providerDetailMatch[2])
      return isAdmin ? <ProviderDetailScreen providerId={providerId} onNavigate={handleNavigate} /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
    }
    const providerModelMatch = currentPath.match(/^\/(admin\/v2\/providers|admin\/providers)\/([^/]+)\/models\/([^/]+)$/)
    if (providerModelMatch) {
      const providerId = decodeURIComponent(providerModelMatch[2])
      const modelId = decodeURIComponent(providerModelMatch[3])
      return isAdmin ? <ModelManagementScreen providerId={providerId} modelId={modelId} onNavigate={handleNavigate} /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
    }

    switch (currentPath) {
      case "/chat":
        return <NewChatScreen onOpenDocument={(docId, filename) => { setDocumentId(docId); setDocumentViewFilename(filename); setCurrentPath("/documents/view"); }} />
      case "/documents/library":
        return <DocumentLibraryScreen key={workspaceProjectId || "all"} onSelectDocument={(doc) => { setDocumentId(doc.id); setCurrentPath("/analyze/chat"); }} initialProjectId={workspaceProjectId} />
      case "/documents/add":
        return <DocumentAddScreen onUploaded={(id) => { setDocumentId(id); setCurrentPath("/documents/library"); }} />
      case "/documents/workspaces":
        return <WorkspacesScreen onSelectProject={(proj) => { setWorkspaceProjectId(proj.id); setCurrentPath("/documents/library"); }} />
      case "/documents/status":
        return <ProcessingStatusScreen />
      case "/documents/view":
        return <DocumentViewScreen documentId={documentId} onNavigate={handleNavigate} filename={documentViewFilename} />
      case "/analyze/chat":
        return <AnalyzeChatScreen key={documentId} documentId={documentId} />
      case "/analyze/extraction":
        return <AnalyzeExtractionScreen />
      case "/analyze/summaries":
        return <AnalyzeSummariesScreen />
      case "/analyze/compare":
        return <AnalyzeCompareScreen />
      case "/analyze/classification":
        return <AnalyzeClassificationScreen />
      case "/outputs/history":
        return <OutputsHistoryScreen />
      case "/outputs/exports":
        return <OutputsExportsScreen />
      case "/outputs/reports":
        return <OutputsReportsScreen />
      // ── AI PLATFORM (admin) ──────────────────────────────────────
      case "/admin/providers":
        return isAdmin ? <ProvidersScreen onNavigate={handleNavigate} /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/models":
        return isAdmin ? <V2AdminScreen onNavigate={handleNavigate} /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/embeddings":
        return isAdmin ? <AdminEmbeddingsScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/prompts":
        return isAdmin ? <AdminPromptsScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/auto-routing":
        return isAdmin ? <AdminAutoRoutingScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/system":
        return isAdmin ? <SystemStatusScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      // ── ADMINISTRATION (admin) ──────────────────────────────────
      case "/admin/storage":
        return isAdmin ? <AdminStorageScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/integrations":
        return isAdmin ? <AdminIntegrationsScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/security":
        return isAdmin ? <AdminSecurityScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/rbac":
        return isAdmin ? <AdminRBACScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/departments":
        return isAdmin ? <AdminDepartmentsScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/diagnostics":
        return isAdmin ? <AdminDiagnosticsScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      case "/admin/audit":
        return isAdmin ? <AdminAuditScreen /> : <DocumentLibraryScreen onSelectDocument={() => {}} />
      // ── Settings ────────────────────────────────────────────────
      case "/settings/profile":
        return <SettingsProfileScreen />
      case "/settings/security":
        return <SettingsSecurityScreen />
      // ── Collaboration ───────────────────────────────────────────
      case "/team":
        return <CollaborationTeamScreen />
      case "/shared":
        return <WorkspacesScreen onSelectProject={(proj) => { setCurrentPath("/documents/library"); }} />
      case "/activity":
        return <CollaborationTeamScreen />
      default:
        return <DocumentLibraryScreen onSelectDocument={() => {}} />
    }
  }

  const handleNavigate = useCallback((path: string) => {
    setCurrentPath(path)
    setDrawerVisible(false)
  }, [])

  // ── Connection check gate screens ─────────────────────────────
  if (connectionChecking || !connectionOk) {
    const isError = !connectionChecking && !connectionOk

    const getStepIcon = (step: typeof startupSteps[0]) => {
      switch (step.status) {
        case "done": return "✅"
        case "error": return "❌"
        case "in-progress": return "⏳"
        case "skipped": return "⏭️"
        default: return "⬜"
      }
    }

    const getStepColor = (step: typeof startupSteps[0]) => {
      switch (step.status) {
        case "done": return "#34D399"
        case "error": return "#EF4444"
        case "in-progress": return "#5B88FF"
        case "skipped": return "#6B7280"
        default: return "#374151"
      }
    }

    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: "#070B14" }}>
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 32 }}>
          {/* Logo / Icon */}
          <Text style={{ fontSize: 48, lineHeight: 52, marginBottom: 12 }}>
            {isError ? "⚠️" : "🔄"}
          </Text>

          {/* Title */}
          <Text style={{ fontSize: 18, fontWeight: "700", color: "#FFFFFF", marginBottom: 8 }}>
            {isError ? "Unable to Connect" : "Starting Up…"}
          </Text>

          {/* Subtitle */}
          <Text style={{
            fontSize: 13, color: "rgba(255,255,255,0.55)",
            textAlign: "center", maxWidth: 400, lineHeight: 20,
            marginBottom: 28,
          }}>
            {isError
              ? connectionError || "The backend server is not reachable. Please ensure the server is running and try again."
              : "Initializing connection and verifying system components…"
            }
          </Text>

          {/* Startup Steps */}
          <View style={{ width: "100%", maxWidth: 360, gap: 12 }}>
            {startupSteps.map((step) => (
              <View
                key={step.id}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 12,
                  opacity: step.status === "pending" ? 0.4 : 1,
                }}
              >
                {/* Status indicator */}
                <View style={{
                  width: 28, height: 28,
                  borderRadius: 14,
                  backgroundColor: step.status === "in-progress" ? "rgba(91,136,255,0.15)" : "transparent",
                  alignItems: "center", justifyContent: "center",
                }}>
                  <Text style={{ fontSize: 14 }}>{getStepIcon(step)}</Text>
                </View>

                {/* Label + optional message */}
                <View style={{ flex: 1 }}>
                  <Text style={{
                    fontSize: 14,
                    fontWeight: step.status === "in-progress" ? "600" : "400",
                    color: step.status === "in-progress" ? "#FFFFFF" : "rgba(255,255,255,0.7)",
                  }}>
                    {step.label}
                  </Text>
                  {step.message ? (
                    <Text style={{
                      fontSize: 11, color: "rgba(255,255,255,0.4)",
                      marginTop: 1,
                    }}>
                      {step.message}
                    </Text>
                  ) : null}
                </View>
              </View>
            ))}
          </View>

          {/* Retry button for error state */}
          {isError ? (
            <Pressable
              onPress={recheck}
              style={{
                marginTop: 28,
                paddingVertical: 12,
                paddingHorizontal: 32,
                borderRadius: 10,
                backgroundColor: "#5B88FF",
              }}
            >
              <Text style={{ color: "#FFFFFF", fontSize: 14, fontWeight: "600" }}>
                Retry Connection
              </Text>
            </Pressable>
          ) : null}

          {/* Spinner at bottom while checking */}
          {connectionChecking ? (
            <ActivityIndicator
              size="small"
              color="#5B88FF"
              style={{ marginTop: 28 }}
            />
          ) : null}
        </View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: t.colors.bg }}>
      {isAuthenticated ? (
        <View style={{ flex: 1, flexDirection: isTablet ? "row" : "column", backgroundColor: t.colors.bg }}>
          {isTablet ? (
            <InlineSidebar
              collapsed={sidebarCollapsed}
              onToggleCollapse={() => setSidebarCollapsed((p) => !p)}
              onNavigate={handleNavigate}
              onLogout={handleLogout}
              currentPath={currentPath}
              userRole={userRole || ""}
              displayName={displayName}
            />
          ) : (
            <View
              style={{
                height: 56,
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                paddingHorizontal: 16,
            backgroundColor: isDark ? "#070B14" : t.colors.bg,
                borderBottomWidth: 1,
                borderBottomColor: t.colors.border,
              }}
            >
              <Pressable onPress={() => setDrawerVisible(true)}>
                <Text style={{ fontSize: 22, color: t.colors.text }}>☰</Text>
              </Pressable>
              <Text style={{ fontSize: 16, fontWeight: "700", color: t.colors.text }}>
                {getPageTitle(currentPath)}
              </Text>
              <View style={{ width: 40 }} />
            </View>
          )}
          <View style={{ flex: 1, minWidth: 0 }}>
            {renderPage()}
          </View>
          {!isTablet && (
            <SidebarDrawer
              visible={drawerVisible}
              onClose={() => setDrawerVisible(false)}
              onNavigate={handleNavigate}
              onLogout={handleLogout}
              userRole={userRole || ""}
              displayName={displayName}
            />
          )}
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, justifyContent: "center" }}>
          <View style={{ gap: 8 }}>
            <Text style={{ fontSize: 16, fontWeight: "600", color: t.colors.text }}>
              Sign in to access all features
            </Text>
            <Text style={{ fontSize: 13, color: t.colors.textMuted }}>
              Upload documents, chat, manage models, and more.
            </Text>
          </View>
        </ScrollView>
      )}

      <ConnectionToast connected={connectionOk} liveChecking={liveChecking} />

      <Modal visible={!isAuthenticated} transparent animationType="fade">
        <View
          style={{
            flex: 1,
            backgroundColor: t.colors.bg,
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
          }}
        >
          <View style={modalStyle(t)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 14, marginBottom: 20 }}>
              <View
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  backgroundColor: t.colors.surfaceActive,
                  borderWidth: 1,
                  borderColor: t.colors.borderFocus,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Image source={zetdcLogo} resizeMode="contain" style={{ width: 32, height: 32 }} />
              </View>
              <View>
                <Text style={{ fontSize: 10, color: t.colors.textMuted, fontWeight: "700", letterSpacing: 1.2 }}>
                  ZIMBABWE ELECTRICITY TRANSMISSION
                </Text>
                <Text
                  style={{
                    fontSize: 16,
                    fontWeight: "800",
                    color: t.colors.text,
                    letterSpacing: 0.3,
                  }}
                >
                  DOCTEL LARGE LANGUAGE MODEL
                </Text>
                <Text style={{ fontSize: 9, color: t.colors.primary, fontWeight: "700", letterSpacing: 1.5 }}>
                  & DISTRIBUTION COMPANY
                </Text>
              </View>
            </View>
            <DocChatAnimation />
            <Text style={{ fontSize: 16, fontWeight: "700", color: t.colors.text, marginBottom: 4 }}>
              Sign in to continue
            </Text>
            {checkingToken ? (
              <Text style={{ marginTop: 12, color: t.colors.textMuted }}>Checking session...</Text>
            ) : (
              <>
                {loginMode === "ec" ? (
                  <>
                    <TextInput
                      value={inputValue}
                      onChangeText={setInputValue}
                      onBlur={() => setTouched(true)}
                      placeholder="EC12345"
                      style={inputStyle(t)}
                    />
                    {showError ? (
                      <Text style={{ color: t.colors.error, marginBottom: 8 }}>
                        EC number is required.
                      </Text>
                    ) : null}
                    <TextInput
                      value={password}
                      onChangeText={setPassword}
                      onBlur={() => setTouched(true)}
                      placeholder="Password"
                      secureTextEntry
                      style={inputStyle(t)}
                    />
                    {showPasswordError ? (
                      <Text style={{ color: t.colors.error, marginBottom: 8 }}>
                        Password is required.
                      </Text>
                    ) : null}
                  </>
                ) : (
                  <>
                    <TextInput
                      value={email}
                      onChangeText={setEmail}
                      onBlur={() => setTouched(true)}
                      placeholder="name@zetdc.co.zw"
                      autoCapitalize="none"
                      style={inputStyle(t)}
                    />
                    {(showEmailError || (touched && !isValidZetdcEmail)) ? (
                      <Text style={{ color: t.colors.error, marginBottom: 8 }}>
                        Enter a valid ZETDC email.
                      </Text>
                    ) : null}
                    {emailSent ? (
                      <>
                        <TextInput
                          value={emailCode}
                          onChangeText={setEmailCode}
                          onBlur={() => setTouched(true)}
                          placeholder="6-digit code"
                          keyboardType="number-pad"
                          style={inputStyle(t)}
                        />
                        {showEmailCodeError ? (
                          <Text style={{ color: t.colors.error, marginBottom: 8 }}>
                            Code is required.
                          </Text>
                        ) : null}
                        <Pressable
                          onPress={async () => {
                            try {
                              setLoading(true)
                              await requestEmailOtp({ email: email.trim() })
                            } catch (e: any) {
                              setAuthError(e.message ?? "Failed to resend code.")
                            } finally {
                              setLoading(false)
                            }
                          }}
                          style={secondaryButtonStyle(t)}
                          disabled={loading}
                        >
                          <Text style={{ color: t.colors.primary }}>
                            Resend Code
                          </Text>
                        </Pressable>
                      </>
                    ) : null}
                  </>
                )}
                {authError ? (
                  <Text style={{ color: t.colors.error, marginBottom: 8 }}>{authError}</Text>
                ) : null}
                <Pressable
                  onPress={async () => {
                    setTouched(true)
                    setAuthError("")
                    try {
                      setLoading(true)
                      if (loginMode === "ec") {
                        if (!inputValue.trim() || !password.trim()) return
                        const res = await login({
                          ec_number: inputValue.trim(),
                          password: password,
                        })
                        await setEcNumber(res.ec_number)
                        await setAuthToken(res.access_token)
                        setHasToken(true)
                        setDisplayName(res.display_name || res.ec_number)
                        setUserRole(res.role || "")
                        setPassword("")
                        // Reload models with auth so task mappings are picked up
                        try { await reloadModels() } catch {}
                      } else {
                        if (!email.trim() || !isValidZetdcEmail) return
                        if (!emailSent) {
                          await requestEmailOtp({ email: email.trim() })
                          setEmailSent(true)
                        } else {
                          if (!emailCode.trim()) return
                          const res = await verifyEmailOtp({
                            email: email.trim(),
                            code: emailCode.trim(),
                          })
                          await setEcNumber(res.ec_number)
                          await setAuthToken(res.access_token)
                          setHasToken(true)
                          setDisplayName(res.display_name || res.ec_number)
                          setUserRole(res.role || "")
                          setEmailCode("")
                          // Reload models with auth so task mappings are picked up
                          try { await reloadModels() } catch {}
                        }
                      }
                    } catch (e: any) {
                      setAuthError(e.message ?? "Login failed.")
                    } finally {
                      setLoading(false)
                    }
                  }}
                  style={[
                    primaryButtonStyle(t),
                    loading ? { opacity: 0.8 } : null,
                  ]}
                  disabled={loading}
                >
                  <Text style={{ color: "#FFFFFF" }}>
                    {loading
                      ? loginMode === "email" && !emailSent
                        ? "Sending..."
                        : "Signing in..."
                      : loginMode === "email" && !emailSent
                        ? "Send Code"
                        : "Continue"}
                  </Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  )
}

export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <ModelProvider>
          <AppContent />
        </ModelProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  )
}



const modalStyle = (t: ReturnType<typeof useTheme>["tokens"]) => ({
  backgroundColor: t.colors.bgSecondary,
  borderRadius: 20,
  padding: 24,
  width: "100%",
  maxWidth: 420,
  borderWidth: 1,
  borderColor: t.colors.borderFocus,
  shadowColor: t.colors.primary,
  shadowOpacity: 0.25,
  shadowRadius: 24,
  shadowOffset: { width: 0, height: 8 },
  elevation: 10,
}) as const

const inputStyle = (t: ReturnType<typeof useTheme>["tokens"]) => ({
  borderWidth: 1,
  borderColor: t.colors.border,
  borderRadius: 12,
  paddingHorizontal: 14,
  paddingVertical: 12,
  marginTop: 10,
  marginBottom: 8,
  backgroundColor: t.colors.inputBg,
  color: t.colors.text,
  fontSize: 14,
}) as const

const primaryButtonStyle = (t: ReturnType<typeof useTheme>["tokens"]) => ({
  background: "transparent",
  backgroundColor: t.colors.primary,
  paddingVertical: 14,
  borderRadius: 14,
  alignItems: "center",
  marginTop: 4,
  shadowColor: t.colors.primary,
  shadowOpacity: 0.4,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 4 },
  elevation: 6,
}) as const

const secondaryButtonStyle = (t: ReturnType<typeof useTheme>["tokens"]) => ({
  marginTop: 8,
  borderWidth: 1,
  borderColor: t.colors.borderFocus,
  paddingVertical: 10,
  borderRadius: 12,
  alignItems: "center",
  backgroundColor: t.colors.surfaceActive,
}) as const
