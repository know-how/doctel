/**
 * ProviderGroupedModelSelect.tsx
 * 
 * A model selector component that displays models grouped by provider.
 * Only shows models from the database (managed_models table) with status
 * ACTIVE or MAINTENANCE.
 * 
 * SOURCE OF TRUTH: Database-managed models ONLY
 * - A model appears only when:
 *   1. It exists on a provider
 *   2. It has been fetched from that provider
 *   3. It has been saved in the database
 *   4. Administrator has assigned status ACTIVE or MAINTENANCE
 */

import React, { useState, useMemo, useRef, useEffect } from "react"
import type { V2Provider, V2ModelMetadata } from "../types/api"

// Inline SVG icons (avoiding external dependency)
const ChevronDownIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>
)

const SearchIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"></circle>
    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
  </svg>
)

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>
)

const AlertCircleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="8" x2="12" y2="12"></line>
    <line x1="12" y1="16" x2="12.01" y2="16"></line>
  </svg>
)

const ServerIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
    <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
    <line x1="6" y1="6" x2="6.01" y2="6"></line>
    <line x1="6" y1="18" x2="6.01" y2="18"></line>
  </svg>
)

interface ProviderGroupedModelSelectProps {
  /** Array of providers with their models */
  providers: V2Provider[]
  /** Currently selected model ID */
  value: string
  /** Callback when selection changes */
  onChange: (modelId: string, model?: V2ModelMetadata, provider?: V2Provider) => void
  /** Placeholder text */
  placeholder?: string
  /** Whether the field is disabled */
  disabled?: boolean
  /** Additional CSS classes */
  className?: string
  /** Filter by capability (e.g., 'chat', 'vision', 'code') */
  capabilityFilter?: string
  /** Show only selectable models (ACTIVE status) - excludes MAINTENANCE */
  selectableOnly?: boolean
  /** Include Ollama/local models */
  includeLocalModels?: boolean
  /** Local models list (from Ollama) */
  localModels?: string[]
}

interface GroupedModel {
  provider: V2Provider
  models: V2ModelMetadata[]
}

export function ProviderGroupedModelSelect({
  providers,
  value,
  onChange,
  placeholder = "Select a model...",
  disabled = false,
  className = "",
  capabilityFilter,
  selectableOnly = false,
  includeLocalModels = true,
  localModels = [],
}: ProviderGroupedModelSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const containerRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Focus search input when opening
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [isOpen])

  // Group and filter models
  const groupedModels = useMemo((): GroupedModel[] => {
    const groups: GroupedModel[] = []

    // Add database-managed providers
    for (const provider of providers) {
      let models = provider.models || []

      // Filter by status: ACTIVE, INSTALLED, AVAILABLE, and MAINTENANCE are visible
      const visibleStates = ["active", "installed", "available", "maintenance"]
      const selectableStates = ["active", "installed", "available"]
      models = models.filter(m => visibleStates.includes(m.state))

      // Filter by selectableOnly (exclude MAINTENANCE and other non-selectable states)
      if (selectableOnly) {
        models = models.filter(m => selectableStates.includes(m.state))
      }

      // Filter by capability if specified
      if (capabilityFilter) {
        models = models.filter(m => {
          const caps = m.capabilities || m.forTasks || []
          return caps.includes(capabilityFilter)
        })
      }

      // Filter by search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        models = models.filter(m =>
          m.id.toLowerCase().includes(query) ||
          m.name.toLowerCase().includes(query) ||
          (m.description && m.description.toLowerCase().includes(query))
        )
      }

      if (models.length > 0) {
        groups.push({ provider, models })
      }
    }

    // Sort providers by order, then name
    groups.sort((a, b) => {
      if (a.provider.order !== b.provider.order) {
        return a.provider.order - b.provider.order
      }
      return a.provider.name.localeCompare(b.provider.name)
    })

    // Add Ollama/Local models group if applicable
    if (includeLocalModels && localModels.length > 0) {
      let filteredLocalModels = localModels

      // Filter by search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        filteredLocalModels = localModels.filter(m => m.toLowerCase().includes(query))
      }

      if (filteredLocalModels.length > 0) {
        const localProvider: V2Provider = {
          id: "ollama",
          name: "Local (Ollama)",
          vendor: "Ollama",
          base_url: "http://localhost:11434",
          api_key_env: "",
          status: "active",
          description: "Locally hosted models via Ollama",
          icon: "cpu",
          order: 999, // Put at the end
          models: filteredLocalModels.map(m => ({
            id: m,
            name: m.split(":").pop() || m,
            state: "active",
            contextWindow: 4096,
            pricingTier: "local",
            license: "Open Source",
          })),
        }
        groups.push({ provider: localProvider, models: localProvider.models })
      }
    }

    return groups
  }, [providers, searchQuery, capabilityFilter, selectableOnly, includeLocalModels, localModels])

  // Find selected model info
  const selectedModelInfo = useMemo(() => {
    for (const group of groupedModels) {
      const model = group.models.find(m => m.id === value)
      if (model) {
        return { model, provider: group.provider }
      }
    }
    return null
  }, [groupedModels, value])

  // Handle model selection
  const handleSelect = (model: V2ModelMetadata, provider: V2Provider) => {
    onChange(model.id, model, provider)
    setIsOpen(false)
    setSearchQuery("")
  }

  // Get provider icon
  const getProviderIcon = (provider: V2Provider) => {
    const iconMap: Record<string, React.ReactNode> = {
      "google": <span className="text-blue-500 font-bold text-xs">G</span>,
      "openai": <span className="text-green-500 font-bold text-xs">O</span>,
      "anthropic": <span className="text-purple-500 font-bold text-xs">A</span>,
      "ollama": <span style={{ color: '#6B7280' }}><ServerIcon /></span>,
      "deepseek": <span className="text-cyan-500 font-bold text-xs">D</span>,
      "opencode": <span className="text-orange-500 font-bold text-xs">OC</span>,
      "huggingface": <span className="text-yellow-500 font-bold text-xs">HF</span>,
    }
    return iconMap[provider.vendor?.toLowerCase()] || <span style={{ color: '#9CA3AF' }}><ServerIcon /></span>
  }

  // Get status indicator
  const getStatusIndicator = (model: V2ModelMetadata) => {
    if (model.state === "maintenance") {
      return (
        <span style={{ color: '#EAB308' }} title="Under Maintenance"><AlertCircleIcon /></span>
      )
    }
    if (model.state === "installed") {
      return (
        <span style={{ color: '#22C55E', fontSize: '10px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px', backgroundColor: 'rgba(34,197,94,0.15)' }}>
          Installed
        </span>
      )
    }
    if (model.state === "available") {
      return (
        <span style={{ color: '#3B82F6', fontSize: '10px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px', backgroundColor: 'rgba(59,130,246,0.15)' }}>
          Available
        </span>
      )
    }
    return null
  }

  // Count total visible models
  const totalModels = useMemo(() => {
    return groupedModels.reduce((sum, group) => sum + group.models.length, 0)
  }, [groupedModels])

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          w-full flex items-center justify-between px-3 py-2 text-sm
          border rounded-md shadow-sm transition-colors
          ${disabled 
            ? "bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed" 
            : "bg-white border-gray-300 hover:border-gray-400 text-gray-900 cursor-pointer"
          }
          ${isOpen ? "border-blue-500 ring-1 ring-blue-500" : ""}
        `}
      >
        <div className="flex items-center gap-2 min-w-0">
          {selectedModelInfo ? (
            <>
              <span className="flex-shrink-0">
                {getProviderIcon(selectedModelInfo.provider)}
              </span>
              <span className="truncate">
                {selectedModelInfo.model.name}
              </span>
              {selectedModelInfo.model.state === "maintenance" && (
                <span className="text-xs text-yellow-600 bg-yellow-50 px-1.5 py-0.5 rounded">
                  Maintenance
                </span>
              )}
            </>
          ) : (
            <span className="text-gray-400 truncate">{placeholder}</span>
          )}
        </div>
        <span style={{ 
          color: '#9CA3AF', 
          flexShrink: 0, 
          marginLeft: '8px',
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s'
        }}><ChevronDownIcon /></span>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-96 overflow-hidden">
          {/* Search Header */}
          <div className="sticky top-0 bg-white border-b border-gray-200 p-2">
            <div className="relative">
              <span style={{ 
                position: 'absolute', 
                left: '12px', 
                top: '50%', 
                transform: 'translateY(-50%)',
                color: '#9CA3AF'
              }}><SearchIcon /></span>
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search models..."
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="mt-1 text-xs text-gray-500 px-1">
              {totalModels} model{totalModels !== 1 ? "s" : ""} available
            </div>
          </div>

          {/* Model List */}
          <div className="overflow-y-auto max-h-80">
            {groupedModels.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-500 text-center">
                {searchQuery ? "No models match your search" : "No models available"}
              </div>
            ) : (
              groupedModels.map((group) => (
                <div key={group.provider.id} className="border-b border-gray-100 last:border-b-0">
                  {/* Provider Header */}
                  <div className="px-3 py-2 bg-gray-50 flex items-center gap-2">
                    <span className="flex-shrink-0">{getProviderIcon(group.provider)}</span>
                    <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                      {group.provider.name}
                    </span>
                    <span className="text-xs text-gray-400 ml-auto">
                      {group.models.length}
                    </span>
                  </div>

                  {/* Models */}
                  <div>
                    {group.models.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => handleSelect(model, group.provider)}
                        disabled={model.state === "maintenance" && selectableOnly}
                        className={`
                          w-full px-3 py-2 text-left text-sm flex items-center gap-2
                          hover:bg-gray-50 transition-colors
                          ${value === model.id ? "bg-blue-50 text-blue-700" : "text-gray-700"}
                          ${model.state === "maintenance" && selectableOnly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
                        `}
                      >
                        <span style={{ flexShrink: 0, width: '16px' }}>
                          {value === model.id && <span style={{ color: '#2563EB' }}><CheckIcon /></span>}
                        </span>
                        <span className="flex-1 truncate">
                          {model.name}
                        </span>
                        {getStatusIndicator(model)}
                        {model.pricingTier && model.pricingTier !== "local" && (
                          <span className="text-xs text-gray-400 flex-shrink-0">
                            {model.pricingTier}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ProviderGroupedModelSelect
