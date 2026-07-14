/**
 * AdminPromptManagementPage.tsx - Unified Prompt Management
 *
 * Combines System Prompts (task-type templates) and Chat Suggestions
 * (new-chat page prompts) into a single tabbed interface.
 */

import React, { useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { SystemPromptsTab } from "./prompts/SystemPromptsTab"
import { ChatSuggestionsTab } from "./prompts/ChatSuggestionsTab"

type TabId = "system" | "chat"

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "system", label: "System Prompts", icon: "⚙️" },
  { id: "chat", label: "Chat Suggestions", icon: "💬" },
]

export const AdminPromptManagementPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const [activeTab, setActiveTab] = useState<TabId>("system")

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ marginBottom: 20 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 700, color: c.text, margin: 0 }}
        >
          🧠 Prompt Management
        </h1>
        <p style={{ fontSize: 13, color: c.textMuted, margin: "4px 0 0 0" }}>
          Manage system prompts used per task type and chat suggestion cards
        </p>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          borderBottom: `1px solid ${c.border}`,
          marginBottom: 20,
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "10px 18px",
              border: "none",
              borderBottom:
                activeTab === tab.id
                  ? `2px solid ${c.primary}`
                  : "2px solid transparent",
              background: "transparent",
              color: activeTab === tab.id ? c.primary : c.textMuted,
              fontWeight: activeTab === tab.id ? 700 : 500,
              fontSize: 14,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "system" ? <SystemPromptsTab /> : <ChatSuggestionsTab />}
    </div>
  )
}
