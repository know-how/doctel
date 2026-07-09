/**
 * ModelSelector.tsx
 * 
 * Unified model selector component - Single source of truth for model selection.
 * Used by: Task Mapping, New Chat, Documents, Analyze, Outputs
 * 
 * Features:
 * - Searchable dropdown with provider grouping
 * - Capability badges ([TEXT], [VISION], [CODE], [REASONING], etc.)
 * - Status indicators (Active, Installed, Available, Maintenance)
 * - Keyboard navigation
 * - Responsive design (desktop dropdown, mobile modal)
 * 
 * SOURCE OF TRUTH: Database-managed models ONLY via ModelRegistryService
 */

import React, { useState, useMemo, useRef, useEffect, useCallback } from "react"
import type { V2Provider, V2ModelMetadata } from "../types/api"
import { 
  CAPABILITY_CONFIG, 
  PROVIDER_ICONS,
  formatModelName,
  getCapabilityIcons 
} from "../services/ModelRegistryService"

// ═══════════════════════════════════════════════════════════════════════════════
// THEME COLORS (Dark Modern)
// ═══════════════════════════════════════════════════════════════════════════════

const THEME = {
  background: "#131A2E",
  card: "#1B2238",
  border: "rgba(255,255,255,0.08)",
  hover: "#2C3F74",
  selected: "#4F7CFF",
  text: "#FFFFFF",
  muted: "#9CA3AF",
  success: "#22C55E",
  warning: "#EAB308",
  error: "#EF4444",
  overlay: "rgba(0,0,0,0.5)",
} as const

// ═══════════════════════════════════════════════════════════════════════════════
// INLINE SVG ICONS
// ═══════════════════════════════════════════════════════════════════════════════

const Icons = {
  ChevronDown: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ),
  
  Search: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  
  Check: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={style}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  
  AlertCircle: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  
  Server: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <rect x="2" y="2" width="20" height="8" rx="2" />
      <rect x="2" y="14" width="20" height="8" rx="2" />
      <line x1="6" y1="6" x2="6.01" y2="6" />
      <line x1="6" y1="18" x2="6.01" y2="18" />
    </svg>
  ),
  
  Robot: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  ),
  
  Cloud: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
    </svg>
  ),
  
  Cpu: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  ),

  X: ({ style }: { style?: React.CSSProperties }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
}

// Re-export capability config from service for internal use
// This ensures consistency across all components

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface ModelSelectorProps {
  providers: V2Provider[]
  value: string
  onChange: (modelId: string, model?: V2ModelMetadata, provider?: V2Provider) => void
  placeholder?: string
  disabled?: boolean
  capabilityFilter?: string
  selectableOnly?: boolean
  includeLocalModels?: boolean
  localModels?: string[]
}

interface GroupedProvider {
  provider: V2Provider
  models: V2ModelMetadata[]
  isExpanded: boolean
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS - Using ModelRegistryService
// ═══════════════════════════════════════════════════════════════════════════════

function getProviderIcon(vendor: string): React.ReactNode {
  const v = vendor?.toLowerCase() || ""
  const iconStyle = { color: THEME.muted }
  
  // Use PROVIDER_ICONS from service for consistency
  const icon = PROVIDER_ICONS[v] || "🤖"
  
  // Return emoji for providers that have them
  if (icon !== "🤖") {
    return <span style={{ fontSize: "16px" }}>{icon}</span>
  }
  
  // Fallback to legacy SVG icons
  if (v.includes("ollama") || v.includes("local")) return <Icons.Cpu style={iconStyle} />
  if (v.includes("openai")) return <span style={{ color: "#10A37F", fontSize: "12px", fontWeight: 700 }}>OA</span>
  if (v.includes("anthropic")) return <span style={{ color: "#D97757", fontSize: "12px", fontWeight: 700 }}>A</span>
  if (v.includes("google") || v.includes("gemini")) return <span style={{ color: "#4285F4", fontSize: "12px", fontWeight: 700 }}>G</span>
  if (v.includes("deepseek")) return <span style={{ color: "#4F46E5", fontSize: "12px", fontWeight: 700 }}>D</span>
  if (v.includes("opencode")) return <span style={{ color: "#F97316", fontSize: "12px", fontWeight: 700 }}>OC</span>
  if (v.includes("huggingface")) return <span style={{ color: "#FFD21E", fontSize: "12px", fontWeight: 700 }}>HF</span>
  if (v.includes("azure")) return <span style={{ color: "#0078D4", fontSize: "12px", fontWeight: 700 }}>Az</span>
  
  return <Icons.Cloud style={iconStyle} />
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function ModelSelector({
  providers,
  value,
  onChange,
  placeholder = "Select a model...",
  disabled = false,
  capabilityFilter,
  selectableOnly = false,
  includeLocalModels = true,
  localModels = [],
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set())
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // ═══════════════════════════════════════════════════════════════════════════════
  // DATA PROCESSING
  // ═══════════════════════════════════════════════════════════════════════════════

  const { groupedProviders, flatModels, selectedModelInfo } = useMemo(() => {
    const groups: GroupedProvider[] = []
    let allModels: Array<{ model: V2ModelMetadata; provider: V2Provider; index: number }> = []
    let modelIndex = 0

    // Process database providers
    for (const provider of providers) {
      // Skip providers that are disabled
      if (provider.status === "disabled") {
        continue
      }

      let models = provider.models || []

      // Filter by model status: ACTIVE, INSTALLED, AVAILABLE are visible and selectable
      // MAINTENANCE is visible but disabled for selection
      const visibleStates = ["active", "installed", "available", "maintenance"]
      const selectableStates = ["active", "installed", "available"]
      models = models.filter(m => visibleStates.includes(m.state))
      
      // Filter selectable only (exclude MAINTENANCE)
      if (selectableOnly) {
        models = models.filter(m => selectableStates.includes(m.state))
      }

      // Filter by capability
      if (capabilityFilter) {
        models = models.filter(m => {
          const caps = m.capabilities || m.forTasks || []
          return caps.includes(capabilityFilter)
        })
      }

      // Filter by search (model name, ID, provider name)
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        models = models.filter(m =>
          m.id.toLowerCase().includes(query) ||
          m.name.toLowerCase().includes(query) ||
          provider.name.toLowerCase().includes(query) ||
          provider.vendor?.toLowerCase().includes(query)
        )
      }

      // Only include provider if it has visible models after filtering
      if (models.length > 0) {
        // Auto-expand if searching, otherwise use user preference
        const isExpanded = searchQuery.trim() ? true : expandedProviders.has(provider.id)
        
        groups.push({ provider, models, isExpanded })
        
        for (const model of models) {
          allModels.push({ model, provider, index: modelIndex++ })
        }
      }
    }

    // Add Ollama local models
    if (includeLocalModels && localModels.length > 0) {
      let filteredLocal = localModels
      
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        filteredLocal = localModels.filter(m => m.toLowerCase().includes(query))
      }

      if (filteredLocal.length > 0) {
        const localProvider: V2Provider = {
          id: "ollama",
          name: "Local (Ollama)",
          vendor: "Ollama",
          base_url: "http://localhost:11434",
          api_key_env: "",
          status: "active",
          description: "Locally hosted models",
          icon: "cpu",
          order: 999,
          models: filteredLocal.map(m => ({
            id: m,
            name: formatModelName(m),
            state: "active",
            contextWindow: 4096,
            pricingTier: "local",
            license: "Open Source",
          })),
        }
        
        const isExpanded = searchQuery.trim() ? true : expandedProviders.has("ollama")
        groups.push({ provider: localProvider, models: localProvider.models, isExpanded })
        
        for (const model of localProvider.models) {
          allModels.push({ model, provider: localProvider, index: modelIndex++ })
        }
      }
    }

    // Sort providers by order
    groups.sort((a, b) => (a.provider.order || 0) - (b.provider.order || 0))

    // Find selected model
    let selectedInfo = null
    for (const group of groups) {
      const model = group.models.find(m => m.id === value)
      if (model) {
        selectedInfo = { model, provider: group.provider }
        break
      }
    }

    return { groupedProviders: groups, flatModels: allModels, selectedModelInfo: selectedInfo }
  }, [providers, localModels, searchQuery, capabilityFilter, selectableOnly, includeLocalModels, expandedProviders, value])

  // ═══════════════════════════════════════════════════════════════════════════════
  // EVENT HANDLERS
  // ═══════════════════════════════════════════════════════════════════════════════

  const handleSelect = useCallback((model: V2ModelMetadata, provider: V2Provider) => {
    const selectableStates = ["active", "installed", "available"]
    if (!selectableStates.includes(model.state) && selectableOnly) return
    onChange(model.id, model, provider)
    setIsOpen(false)
    setSearchQuery("")
  }, [onChange, selectableOnly])

  const toggleProvider = useCallback((providerId: string) => {
    setExpandedProviders(prev => {
      const next = new Set(prev)
      if (next.has(providerId)) {
        next.delete(providerId)
      } else {
        next.add(providerId)
      }
      return next
    })
  }, [])

  const expandAll = useCallback(() => {
    setExpandedProviders(new Set(groupedProviders.map(g => g.provider.id)))
  }, [groupedProviders])

  // ═══════════════════════════════════════════════════════════════════════════════
  // KEYBOARD NAVIGATION
  // ═══════════════════════════════════════════════════════════════════════════════

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault()
          setHighlightedIndex(prev => Math.min(prev + 1, flatModels.length - 1))
          break
        case "ArrowUp":
          e.preventDefault()
          setHighlightedIndex(prev => Math.max(prev - 1, 0))
          break
        case "Enter":
          e.preventDefault()
          const item = flatModels[highlightedIndex]
          if (item) {
            handleSelect(item.model, item.provider)
          }
          break
        case "Escape":
          e.preventDefault()
          setIsOpen(false)
          break
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, flatModels, highlightedIndex, handleSelect])

  // Scroll highlighted into view
  useEffect(() => {
    if (!isOpen || !listRef.current) return
    const element = listRef.current.querySelector(`[data-index="${highlightedIndex}"]`)
    if (element) {
      element.scrollIntoView({ block: "nearest" })
    }
  }, [highlightedIndex, isOpen])

  // Focus search on open
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus()
      // Expand all when searching
      if (searchQuery.trim()) {
        expandAll()
      }
    }
  }, [isOpen, searchQuery, expandAll])

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // ═══════════════════════════════════════════════════════════════════════════════
  // RENDER HELPERS
  // ═══════════════════════════════════════════════════════════════════════════════

  const renderCapabilityBadges = (capabilities: string[] = []) => {
    const uniqueCaps = [...new Set(capabilities)].slice(0, 4)
    
    return (
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
        {uniqueCaps.map(cap => {
          const config = CAPABILITY_CONFIG[cap.toLowerCase()] || { 
            label: cap, 
            color: THEME.muted, 
            bgColor: "rgba(156,163,175,0.15)" 
          }
          return (
            <span
              key={cap}
              style={{
                fontSize: "10px",
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: "4px",
                color: config.color,
                backgroundColor: config.bgColor,
                textTransform: "uppercase",
                letterSpacing: "0.3px",
              }}
            >
              {config.label}
            </span>
          )
        })}
      </div>
    )
  }

  const renderStatusBadge = (state: string, providerStatus?: string) => {
    // Provider offline takes precedence
    if (providerStatus === "disconnected" || providerStatus === "error") {
      return (
        <span
          style={{
            fontSize: "10px",
            fontWeight: 600,
            padding: "2px 8px",
            borderRadius: "4px",
            color: THEME.error,
            backgroundColor: "rgba(239,68,68,0.15)",
            marginLeft: "auto",
          }}
        >
          Provider Offline
        </span>
      )
    }
    
    // State-based badges
    if (state === "maintenance") {
      return (
        <span
          style={{
            fontSize: "10px",
            fontWeight: 600,
            padding: "2px 8px",
            borderRadius: "4px",
            color: THEME.warning,
            backgroundColor: "rgba(234,179,8,0.15)",
            marginLeft: "auto",
          }}
        >
          Maintenance
        </span>
      )
    }
    
    if (state === "installed") {
      return (
        <span
          style={{
            fontSize: "10px",
            fontWeight: 600,
            padding: "2px 8px",
            borderRadius: "4px",
            color: THEME.success,
            backgroundColor: "rgba(34,197,94,0.15)",
            marginLeft: "auto",
          }}
        >
          Installed
        </span>
      )
    }
    
    if (state === "available") {
      return (
        <span
          style={{
            fontSize: "10px",
            fontWeight: 600,
            padding: "2px 8px",
            borderRadius: "4px",
            color: THEME.selected,
            backgroundColor: "rgba(79,124,255,0.15)",
            marginLeft: "auto",
          }}
        >
          Available
        </span>
      )
    }
    
    return null
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // RENDER: SELECTED MODEL DISPLAY
  // ═══════════════════════════════════════════════════════════════════════════════

  const renderTrigger = () => {
    const isActive = ["active", "installed", "available"].includes(selectedModelInfo?.model.state || "")
    
    return (
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        style={{
          width: "100%",
          minWidth: "280px",
          padding: "12px 16px",
          backgroundColor: THEME.card,
          border: `1px solid ${isOpen ? THEME.selected : THEME.border}`,
          borderRadius: "10px",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          transition: "all 0.2s ease",
          display: "flex",
          alignItems: "center",
          gap: "12px",
        }}
      >
        {selectedModelInfo ? (
          <>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                backgroundColor: THEME.background,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              {getProviderIcon(selectedModelInfo.provider.vendor)}
            </div>
            <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: THEME.text,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {selectedModelInfo.model.name}
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: THEME.muted,
                  marginTop: "2px",
                }}
              >
                {selectedModelInfo.provider.name}
                {(selectedModelInfo.model.capabilities || selectedModelInfo.model.forTasks)?.length > 0 && (
                  <span style={{ marginLeft: "8px" }}>
                    • {(selectedModelInfo.model.capabilities || selectedModelInfo.model.forTasks)?.slice(0, 2).join(" • ")}
                  </span>
                )}
              </div>
            </div>
            {!isActive && (
              <span
                style={{
                  fontSize: "10px",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  backgroundColor: "rgba(234,179,8,0.15)",
                  color: THEME.warning,
                }}
              >
                {selectedModelInfo.model.state}
              </span>
            )}
          </>
        ) : (
          <div style={{ flex: 1, textAlign: "left" }}>
            <span style={{ color: THEME.muted, fontSize: "14px" }}>{placeholder}</span>
          </div>
        )}
        <Icons.ChevronDown
          style={{
            color: THEME.muted,
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease",
            flexShrink: 0,
          }}
        />
      </button>
    )
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // RENDER: DROPDOWN
  // ═══════════════════════════════════════════════════════════════════════════════

  const renderDropdown = () => {
    if (!isOpen) return null

    const totalModels = groupedProviders.reduce((sum, g) => sum + g.models.length, 0)

    return (
      <div
        style={{
          position: "absolute",
          top: "calc(100% + 8px)",
          left: 0,
          minWidth: "450px",
          maxWidth: "650px",
          width: "100%",
          maxHeight: "500px",
          backgroundColor: THEME.background,
          border: `1px solid ${THEME.border}`,
          borderRadius: "12px",
          boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)",
          zIndex: 9999,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          animation: "dropdownSlideIn 0.15s ease-out",
        }}
      >
        {/* Search Header */}
        <div
          style={{
            padding: "16px",
            borderBottom: `1px solid ${THEME.border}`,
            backgroundColor: THEME.card,
          }}
        >
          <div style={{ position: "relative" }}>
            <Icons.Search
              style={{
                position: "absolute",
                left: "14px",
                top: "50%",
                transform: "translateY(-50%)",
                color: THEME.muted,
              }}
            />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search models..."
              style={{
                width: "100%",
                padding: "10px 14px 10px 42px",
                backgroundColor: THEME.background,
                border: `1px solid ${THEME.border}`,
                borderRadius: "8px",
                color: THEME.text,
                fontSize: "14px",
                outline: "none",
                transition: "all 0.2s",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = THEME.selected
              }}
              onBlur={(e) => {
                e.target.style.borderColor = THEME.border
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  right: "10px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  color: THEME.muted,
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                <Icons.X />
              </button>
            )}
          </div>
          <div
            style={{
              fontSize: "12px",
              color: THEME.muted,
              marginTop: "8px",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>{totalModels} model{totalModels !== 1 ? "s" : ""} available</span>
            {groupedProviders.length > 0 && (
              <button
                onClick={expandAll}
                style={{
                  background: "none",
                  border: "none",
                  color: THEME.selected,
                  fontSize: "11px",
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                Expand All
              </button>
            )}
          </div>
        </div>

        {/* Model List */}
        <div
          ref={listRef}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "8px",
          }}
        >
          {groupedProviders.length === 0 ? (
            <div
              style={{
                padding: "40px 20px",
                textAlign: "center",
                color: THEME.muted,
              }}
            >
              <Icons.Robot style={{ marginBottom: "12px", opacity: 0.5 }} />
              <div style={{ fontSize: "14px", fontWeight: 500 }}>
                {searchQuery ? "No models match your search" : "No Active Models Available"}
              </div>
              <div style={{ fontSize: "12px", marginTop: "4px", opacity: 0.7 }}>
                {searchQuery ? "Try a different search term" : "Add models from the Providers page"}
              </div>
            </div>
          ) : (
            groupedProviders.map((group) => (
              <div
                key={group.provider.id}
                style={{
                  marginBottom: "8px",
                  borderRadius: "8px",
                  overflow: "hidden",
                }}
              >
                {/* Provider Header */}
                <button
                  onClick={() => toggleProvider(group.provider.id)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    backgroundColor: THEME.card,
                    border: "none",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    cursor: "pointer",
                    color: THEME.text,
                    textAlign: "left",
                  }}
                >
                  <span
                    style={{
                      transform: group.isExpanded ? "rotate(0deg)" : "rotate(-90deg)",
                      transition: "transform 0.2s",
                      color: THEME.muted,
                    }}
                  >
                    <Icons.ChevronDown />
                  </span>
                  {getProviderIcon(group.provider.vendor)}
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                      flex: 1,
                    }}
                  >
                    {group.provider.name}
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      color: THEME.muted,
                      backgroundColor: THEME.background,
                      padding: "2px 8px",
                      borderRadius: "12px",
                    }}
                  >
                    {group.models.length}
                  </span>
                </button>

                {/* Models */}
                {group.isExpanded && (
                  <div>
                    {group.models.map((model, idx) => {
                      const isSelected = value === model.id
                      const isHighlighted = flatModels.find(m => m.model.id === model.id)?.index === highlightedIndex
                      // Disable if: 1) Not in selectable states and selectableOnly, 2) Provider disconnected/error
                      const isProviderOffline = group.provider.status === "disconnected" || group.provider.status === "error"
                      const selectableStates = ["active", "installed", "available"]
                      const isNotSelectable = !selectableStates.includes(model.state) && selectableOnly
                      const isDisabled = isNotSelectable || isProviderOffline
                      const capabilities = model.capabilities || model.forTasks || []
                      
                      return (
                        <button
                          key={model.id}
                          data-index={flatModels.find(m => m.model.id === model.id)?.index}
                          onClick={() => handleSelect(model, group.provider)}
                          disabled={isDisabled}
                          style={{
                            width: "100%",
                            padding: "12px 16px",
                            backgroundColor: isSelected
                              ? "rgba(79,124,255,0.15)"
                              : isHighlighted
                              ? THEME.hover
                              : "transparent",
                            border: "none",
                            borderLeft: isSelected ? `3px solid ${THEME.selected}` : "3px solid transparent",
                            cursor: isDisabled ? "not-allowed" : "pointer",
                            opacity: isDisabled ? 0.5 : 1,
                            textAlign: "left",
                            transition: "all 0.15s ease",
                          }}
                          onMouseEnter={(e) => {
                            if (!isDisabled) {
                              const index = flatModels.find(m => m.model.id === model.id)?.index
                              if (index !== undefined) setHighlightedIndex(index)
                            }
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                            {/* Checkmark */}
                            <div
                              style={{
                                width: "20px",
                                flexShrink: 0,
                                paddingTop: "2px",
                              }}
                            >
                              {isSelected && (
                                <Icons.Check style={{ color: THEME.selected }} />
                              )}
                            </div>

                            {/* Model Info */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: "14px",
                                    fontWeight: 500,
                                    color: THEME.text,
                                  }}
                                >
                                  {model.name}
                                </span>
                                {renderStatusBadge(model.state, group.provider.status)}
                              </div>
                              
                              <div
                                style={{
                                  fontSize: "12px",
                                  color: THEME.muted,
                                  marginTop: "2px",
                                }}
                              >
                                {group.provider.name}
                              </div>
                              
                              {renderCapabilityBadges(capabilities)}
                            </div>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    )
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // MAIN RENDER
  // ═══════════════════════════════════════════════════════════════════════════════

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        display: "inline-block",
        width: "100%",
      }}
    >
      {renderTrigger()}
      {renderDropdown()}
      
      {/* CSS Animation */}
      <style>{`
        @keyframes dropdownSlideIn {
          from {
            opacity: 0;
            transform: translateY(-8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  )
}

export default ModelSelector
