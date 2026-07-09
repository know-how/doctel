/**
 * AdminPromptSuggestionsPage.tsx - Manage New Chat Prompt Suggestions
 * 
 * Admin interface for managing the dynamic prompt suggestions
 * that appear on the New Chat page.
 */

import React, { useEffect, useState } from "react"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  getRandomPromptSuggestions,
  getPromptCategories,
  listPromptSuggestions,
  createPromptSuggestion,
  updatePromptSuggestion,
  deletePromptSuggestion,
  togglePromptSuggestion,
  PromptSuggestion,
} from "../api/client"

const PREDEFINED_ICONS = [
  { icon: "⚡", label: "Lightning" },
  { icon: "📋", label: "Document" },
  { icon: "🇿🇼", label: "Zimbabwe" },
  { icon: "🏗️", label: "Construction" },
  { icon: "🔌", label: "Plug" },
  { icon: "💰", label: "Money" },
  { icon: "🔒", label: "Lock" },
  { icon: "🦺", label: "Safety" },
  { icon: "📊", label: "Chart" },
  { icon: "📝", label: "Note" },
  { icon: "🔧", label: "Tools" },
  { icon: "💼", label: "Business" },
  { icon: "⚡", label: "Power" },
  { icon: "🔌", label: "Electric" },
  { icon: "🖼️", label: "Image" },
  { icon: "🎤", label: "Audio" },
  { icon: "💻", label: "Code" },
  { icon: "🧠", label: "AI" },
  { icon: "📄", label: "Text" },
  { icon: "🔍", label: "Search" },
]

const CATEGORIES = [
  { value: "procedures", label: "Procedures" },
  { value: "policy", label: "Policy" },
  { value: "safety", label: "Safety" },
  { value: "reports", label: "Reports" },
  { value: "languages", label: "Languages" },
  { value: "technical", label: "Technical" },
  { value: "general", label: "General" },
]

export const AdminPromptSuggestionsPage: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [suggestions, setSuggestions] = useState<PromptSuggestion[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState("")
  const [showEnabledOnly, setShowEnabledOnly] = useState(false)

  // Form state
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [formData, setFormData] = useState({
    title: "",
    prompt_text: "",
    category: "general",
    icon: "💬",
    requires_capability: "",
    display_order: 0,
    enabled: true,
  })
  const [saving, setSaving] = useState(false)

  const loadSuggestions = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await listPromptSuggestions(0, 1000, filterCategory || undefined, showEnabledOnly || undefined, searchQuery || undefined)
      setSuggestions(res.items)
    } catch (e: any) {
      setError(e.message ?? "Failed to load prompt suggestions")
    } finally {
      setLoading(false)
    }
  }

  const loadCategories = async () => {
    try {
      const res = await getPromptCategories()
      setCategories(res.categories)
    } catch (e) {
      console.warn("Failed to load categories:", e)
    }
  }

  useEffect(() => {
    loadSuggestions()
    loadCategories()
  }, [filterCategory, showEnabledOnly, searchQuery])

  const resetForm = () => {
    setFormData({
      title: "",
      prompt_text: "",
      category: "general",
      icon: "💬",
      requires_capability: "",
      display_order: 0,
      enabled: true,
    })
    setEditingId(null)
    setShowForm(false)
  }

  const startEdit = (suggestion: PromptSuggestion) => {
    setFormData({
      title: suggestion.title,
      prompt_text: suggestion.prompt_text,
      category: suggestion.category,
      icon: suggestion.icon,
      requires_capability: suggestion.requires_capability || "",
      display_order: suggestion.display_order,
      enabled: suggestion.enabled,
    })
    setEditingId(suggestion.id)
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!formData.title.trim() || !formData.prompt_text.trim()) {
      setError("Title and prompt text are required")
      return
    }

    try {
      setSaving(true)
      setError(null)

      const payload = {
        ...formData,
        requires_capability: formData.requires_capability || undefined,
      }

      if (editingId) {
        await updatePromptSuggestion(editingId, payload)
      } else {
        await createPromptSuggestion(payload)
      }

      await loadSuggestions()
      resetForm()
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this prompt suggestion?")) return

    try {
      await deletePromptSuggestion(id)
      await loadSuggestions()
    } catch (e: any) {
      setError(e.message ?? "Delete failed")
    }
  }

  const handleToggle = async (id: number) => {
    try {
      await togglePromptSuggestion(id)
      await loadSuggestions()
    } catch (e: any) {
      setError(e.message ?? "Toggle failed")
    }
  }

  return (
    <div style={{ padding: t.spacing.lg, maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: t.spacing.lg, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: c.text }}>Prompt Suggestions</h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: c.textSecondary }}>
            Manage the dynamic prompt suggestions displayed on the New Chat page.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{
            padding: "10px 20px",
            background: c.primary,
            color: "#fff",
            border: "none",
            borderRadius: t.radii.md,
            cursor: "pointer",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span>+</span> {showForm ? "Cancel" : "Add Prompt"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: 12,
          marginBottom: 16,
          borderRadius: t.radii.md,
          backgroundColor: c.error + "20",
          color: c.error,
          fontSize: 14,
        }}>
          {error}
        </div>
      )}

      {/* Form */}
      {showForm && (
        <div style={{
          padding: 20,
          marginBottom: 24,
          background: c.surface,
          borderRadius: t.radii.lg,
          border: `1px solid ${c.border}`,
        }}>
          <h3 style={{ margin: "0 0 16px", fontSize: 16, color: c.text }}>
            {editingId ? "Edit Prompt Suggestion" : "New Prompt Suggestion"}
          </h3>

          <div style={{ display: "grid", gap: 16 }}>
            {/* Title */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
                Title *
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., ZETDC outage reporting process"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: `1px solid ${c.border}`,
                  borderRadius: t.radii.md,
                  background: c.background,
                  color: c.text,
                  fontSize: 14,
                }}
              />
            </div>

            {/* Prompt Text */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
                Prompt Text *
              </label>
              <textarea
                value={formData.prompt_text}
                onChange={(e) => setFormData({ ...formData, prompt_text: e.target.value })}
                placeholder="e.g., Explain the ZETDC outage reporting process step by step"
                rows={3}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: `1px solid ${c.border}`,
                  borderRadius: t.radii.md,
                  background: c.background,
                  color: c.text,
                  fontSize: 14,
                  resize: "vertical",
                }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              {/* Category */}
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
                  Category
                </label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: `1px solid ${c.border}`,
                    borderRadius: t.radii.md,
                    background: c.background,
                    color: c.text,
                    fontSize: 14,
                  }}
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>

              {/* Icon */}
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
                  Icon
                </label>
                <select
                  value={formData.icon}
                  onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: `1px solid ${c.border}`,
                    borderRadius: t.radii.md,
                    background: c.background,
                    color: c.text,
                    fontSize: 14,
                  }}
                >
                  {PREDEFINED_ICONS.map((item) => (
                    <option key={item.icon + item.label} value={item.icon}>
                      {item.icon} {item.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Display Order */}
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
                  Display Order
                </label>
                <input
                  type="number"
                  value={formData.display_order}
                  onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) || 0 })}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: `1px solid ${c.border}`,
                    borderRadius: t.radii.md,
                    background: c.background,
                    color: c.text,
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            {/* Required Capability */}
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: c.text, marginBottom: 6 }}>
                Requires Capability (optional)
              </label>
              <select
                value={formData.requires_capability}
                onChange={(e) => setFormData({ ...formData, requires_capability: e.target.value })}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: `1px solid ${c.border}`,
                  borderRadius: t.radii.md,
                  background: c.background,
                  color: c.text,
                  fontSize: 14,
                }}
              >
                <option value="">None (available for all models)</option>
                <option value="vision">Vision (Image support)</option>
                <option value="audio">Audio (Voice support)</option>
                <option value="code">Code Generation</option>
                <option value="reasoning">Advanced Reasoning</option>
              </select>
            </div>

            {/* Enabled */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                id="enabled"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              />
              <label htmlFor="enabled" style={{ fontSize: 14, color: c.text }}>
                Enabled (visible on New Chat page)
              </label>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  padding: "10px 24px",
                  background: c.primary,
                  color: "#fff",
                  border: "none",
                  borderRadius: t.radii.md,
                  cursor: saving ? "not-allowed" : "pointer",
                  fontWeight: 600,
                  opacity: saving ? 0.6 : 1,
                }}
              >
                {saving ? "Saving..." : (editingId ? "Update" : "Create")}
              </button>
              <button
                onClick={resetForm}
                style={{
                  padding: "10px 24px",
                  background: "transparent",
                  color: c.text,
                  border: `1px solid ${c.border}`,
                  borderRadius: t.radii.md,
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        display: "flex",
        gap: 12,
        marginBottom: 20,
        flexWrap: "wrap",
        alignItems: "center",
      }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search prompts..."
          style={{
            padding: "8px 12px",
            border: `1px solid ${c.border}`,
            borderRadius: t.radii.md,
            background: c.background,
            color: c.text,
            fontSize: 14,
            minWidth: 200,
          }}
        />

        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{
            padding: "8px 12px",
            border: `1px solid ${c.border}`,
            borderRadius: t.radii.md,
            background: c.background,
            color: c.text,
            fontSize: 14,
          }}
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((cat) => (
            <option key={cat.value} value={cat.value}>{cat.label}</option>
          ))}
        </select>

        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, color: c.text }}>
          <input
            type="checkbox"
            checked={showEnabledOnly}
            onChange={(e) => setShowEnabledOnly(e.target.checked)}
          />
          Enabled only
        </label>
      </div>

      {/* List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: c.textSecondary }}>
          Loading prompt suggestions...
        </div>
      ) : suggestions.length === 0 ? (
        <div style={{
          textAlign: "center",
          padding: 60,
          background: c.surface,
          borderRadius: t.radii.lg,
          color: c.textSecondary,
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>💬</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: c.text, marginBottom: 8 }}>
            No prompt suggestions found
          </div>
          <div style={{ fontSize: 14 }}>
            Create your first prompt suggestion to get started
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.id}
              style={{
                padding: 16,
                background: c.surface,
                borderRadius: t.radii.lg,
                border: `1px solid ${suggestion.enabled ? c.border : c.error + "40"}`,
                opacity: suggestion.enabled ? 1 : 0.7,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flex: 1 }}>
                  <span style={{ fontSize: 24 }}>{suggestion.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 15, fontWeight: 600, color: c.text }}>
                        {suggestion.title}
                      </span>
                      {!suggestion.enabled && (
                        <span style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          background: c.error + "20",
                          color: c.error,
                          borderRadius: 4,
                        }}>
                          Disabled
                        </span>
                      )}
                      {suggestion.requires_capability && (
                        <span style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          background: c.primary + "20",
                          color: c.primary,
                          borderRadius: 4,
                        }}>
                          Requires: {suggestion.requires_capability}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 13, color: c.textSecondary, marginBottom: 6 }}>
                      {suggestion.prompt_text}
                    </div>
                    <div style={{ display: "flex", gap: 8, fontSize: 12, color: c.textMuted }}>
                      <span style={{
                        padding: "2px 8px",
                        background: c.background,
                        borderRadius: 4,
                        textTransform: "capitalize",
                      }}>
                        {suggestion.category}
                      </span>
                      <span>Order: {suggestion.display_order}</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => handleToggle(suggestion.id)}
                    style={{
                      padding: "6px 12px",
                      background: suggestion.enabled ? c.success + "20" : c.surface,
                      color: suggestion.enabled ? c.success : c.text,
                      border: `1px solid ${suggestion.enabled ? c.success : c.border}`,
                      borderRadius: t.radii.md,
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {suggestion.enabled ? "Enabled" : "Disabled"}
                  </button>
                  <button
                    onClick={() => startEdit(suggestion)}
                    style={{
                      padding: "6px 12px",
                      background: c.surface,
                      color: c.text,
                      border: `1px solid ${c.border}`,
                      borderRadius: t.radii.md,
                      cursor: "pointer",
                      fontSize: 12,
                    }}
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(suggestion.id)}
                    style={{
                      padding: "6px 12px",
                      background: c.error + "10",
                      color: c.error,
                      border: `1px solid ${c.error + "40"}`,
                      borderRadius: t.radii.md,
                      cursor: "pointer",
                      fontSize: 12,
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
