export interface NavItem {
  id: string
  label: string
  icon: string
  path: string
  roles?: string[]
  children?: NavItem[]
}

export const sidebarConfig: NavItem[] = [
  {
    id: "new-chat",
    label: "New Chat",
    icon: "💬",
    path: "/chat",
  },
  {
    id: "documents",
    label: "Documents",
    icon: "📄",
    path: "/documents",
    children: [
      { id: "documents-add", label: "Add Document", icon: "➕", path: "/documents/add" },
      { id: "documents-workspaces", label: "Workspaces", icon: "🗂️", path: "/documents/workspaces" },
      { id: "documents-library", label: "Library", icon: "📚", path: "/documents/library" },
      { id: "documents-status", label: "Processing Status", icon: "🔄", path: "/documents/status" },
    ],
  },
  {
    id: "analyze",
    label: "Analyze",
    icon: "🧠",
    path: "/analyze",
    children: [
      { id: "analyze-chat", label: "Ask Documents", icon: "💬", path: "/analyze/chat" },
      { id: "analyze-extraction", label: "Extraction", icon: "📋", path: "/analyze/extraction" },
      { id: "analyze-summaries", label: "Summaries", icon: "📝", path: "/analyze/summaries" },
      { id: "analyze-classification", label: "Classification", icon: "🏷️", path: "/analyze/classification" },
      { id: "analyze-compare", label: "Compare", icon: "⚖️", path: "/analyze/compare" },
    ],
  },
  {
    id: "outputs",
    label: "Outputs",
    icon: "📤",
    path: "/outputs",
    children: [
      { id: "outputs-history", label: "History", icon: "📋", path: "/outputs/history" },
      { id: "outputs-exports", label: "Exports", icon: "📥", path: "/outputs/exports" },
      { id: "outputs-reports", label: "Reports", icon: "📊", path: "/outputs/reports" },
    ],
  },
  {
    id: "admin",
    label: "Models & Config",
    icon: "⚙️",
    path: "/admin",
    roles: ["admin"],
    children: [
      { id: "admin-models", label: "Models", icon: "🤖", path: "/admin/models" },
      { id: "admin-providers", label: "Providers", icon: "🏢", path: "/admin/providers" },
      { id: "admin-marketplace", label: "Model Marketplace", icon: "🛒", path: "/admin/marketplace" },
      { id: "admin-prompts", label: "Prompts", icon: "💬", path: "/admin/prompts" },
      { id: "admin-context", label: "Context & Tokens", icon: "🔢", path: "/admin/context" },
      { id: "admin-integrations", label: "Integrations", icon: "🔌", path: "/admin/integrations" },
      { id: "admin-system", label: "System Status", icon: "📊", path: "/admin/system" },
      { id: "admin-settings-json", label: "Advanced Settings", icon: "📋", path: "/admin-settings" },
    ],
  },
  {
    id: "collaboration",
    label: "Collaboration",
    icon: "👥",
    path: "/team",
    children: [
      { id: "team-members", label: "Team", icon: "👤", path: "/team" },
      { id: "shared-workspaces", label: "Shared", icon: "🔗", path: "/shared" },
      { id: "activity", label: "Activity", icon: "📊", path: "/activity" },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    icon: "🔧",
    path: "/settings",
    children: [
      { id: "settings-profile", label: "Profile", icon: "👤", path: "/settings/profile" },
      { id: "settings-security", label: "Security", icon: "🔒", path: "/settings/security" },
      // Billing removed per enhancement spec
    ],
  },
]
