/**
 * ChatSuggestionsTab.tsx - Chat Prompt Suggestions
 *
 * Extracted from AdminPromptSuggestionsPage for use in the merged PromptManagementPage.
 * Full CRUD + toggle management of chat prompt suggestions with filtering and search.
 */

import React, { useEffect, useState } from "react"
import {
  listPromptSuggestions,
  createPromptSuggestion,
  updatePromptSuggestion,
  deletePromptSuggestion,
  togglePromptSuggestion,
  getPromptCategories,
} from "../../api/client"
import type { PromptSuggestion } from "../../api/client"
import { useTheme } from "../../context/ThemeContext"
import { getTokens } from "../../theme/themeTokens"

const PREDEFINED_ICONS = [
  "💡", "📝", "🎯", "📊", "📚", "💬", "🔍", "🚀", "✅", "🧠",
  "🎨", "📈", "💼", "🌟", "📋", "⚡", "🛠️", "📌", "🎭", "🔬",
]

const CATEGORIES = [
  "general", "technical", "medical", "legal", "academic", "creative", "business",
]

export const ChatSuggestionsTab: React.FC = () => {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const [suggestions, setSuggestions] = useState<PromptSuggestion[]>([])
  const [categories, setCategories] = useState<string[]>(CATEGORIES)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [showEnabledOnly, setShowEnabledOnly] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    title: "",
    prompt_text: "",
    category: "general",
    icon: "💡",
    display_order: 0,
    requires_capability: "",
    enabled: true,
  })

  const loadSuggestions = async () => {
    try {
      setLoading(true)
      setError(null)
      const params: Record<string, any> = {}
      if (filterCategory) params.category = filterCategory
      if (searchQuery) params.search = searchQuery
      if (showEnabledOnly) params.is_enabled = true
      const res = await listPromptSuggestions(params)
      // Normalize response shape: { items, total, skip, limit } or array
      const items = res.items ?? res.suggestions ?? res.data ?? res
      setSuggestions(Array.isArray(items) ? items : [])
    } catch (e: any) {
      setError(e.message ?? "Failed to load suggestions")
    } finally {
      setLoading(false)
    }
  }

  const loadCategories = async () => {
    try {
      const res = await getPromptCategories()
      if (res?.categories) setCategories(res.categories)
    } catch {
      // Fallback to static list
    }
  }

  useEffect(() => {
    loadSuggestions()
    loadCategories()
  }, [])

  useEffect(() => {
    loadSuggestions()
  }, [filterCategory, searchQuery, showEnabledOnly])

  const resetForm = () => {
    setFormData({
      title: "",
      prompt_text: "",
      category: "general",
      icon: "💡",
      display_order: 0,
      requires_capability: "",
      enabled: true,
    })
    setEditingId(null)
    setShowForm(false)
  }

  const startCreate = () => {
    resetForm()
    setShowForm(true)
  }

  const startEdit = (s: PromptSuggestion) => {
    setEditingId(s.id!)
    setFormData({
      title: s.title,
      prompt_text: s.prompt_text,
      category: s.category,
      icon: s.icon || "💡",
      display_order: s.display_order ?? 0,
      requires_capability: s.requires_capability || "",
      enabled: s.enabled ?? true,
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!formData.title.trim() || !formData.prompt_text.trim()) {
      setError("Title and prompt text are required.")
      return
    }
    try {
      setSaving(true)
      setError(null)
      const payload = {
        ...formData,
        display_order: Number(formData.display_order) || 0,
        requires_capability: formData.requires_capability || undefined,
      }
      if (editingId) {
        await updatePromptSuggestion(editingId, payload)
      } else {
        await createPromptSuggestion(payload)
      }
      resetForm()
      await loadSuggestions()
    } catch (e: any) {
      setError(e.message ?? "Save failed")
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (id: number) => {
    try {
      setError(null)
      await togglePromptSuggestion(id)
      await loadSuggestions()
    } catch (e: any) {
      setError(e.message ?? "Toggle failed")
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this prompt suggestion?")) return
    try {
      setError(null)
      await deletePromptSuggestion(id)
      await loadSuggestions()
    } catch (e: any) {
      setError(e.message ?? "Delete failed")
    }
  }

  return (
    <div>
      {/* Error */}
      {error && (
        <div
          style={{
            padding: 10,
            marginBottom: 12,
            borderRadius: t.radii.md,
            backgroundColor: c.error + "18",
            color: c.error,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Filter bar */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: t.spacing.lg,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search suggestions..."
          style={{
            flex: 1,
            minWidth: 180,
            padding: "8px 12px",
            borderRadius: t.radii.sm,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
          }}
        />
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{
            padding: "8px 12px",
            borderRadius: t.radii.sm,
            border: `1px solid ${c.border}`,
            backgroundColor: c.inputBg,
            color: c.text,
            fontSize: 13,
          }}
        >
          <option value="" style={{ backgroundColor: c.inputBg, color: c.text }}>
            All categories
          </option>
          {categories.map((cat) => (
            <option
              key={cat}
              value={cat}
              style={{ backgroundColor: c.inputBg, color: c.text }}
            >
              {cat}
            </option>
          ))}
        </select>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 13,
            color: c.text,
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={showEnabledOnly}
            onChange={(e) => setShowEnabledOnly(e.target.checked)}
          />
          Enabled only
        </label>
        <button
          onClick={startCreate}
          style={{
            padding: "8px 16px",
            borderRadius: t.radii.sm,
            border: "none",
            backgroundColor: c.primary,
            color: "#FFFFFF",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          + New suggestion
        </button>
      </div>

      {/* Create / Edit form */}
      {showForm && (
        <div
          style={{
            borderRadius: t.radii.lg,
            border: `1px solid ${editingId ? c.primary : c.success}`,
            padding: t.spacing.lg,
            backgroundColor: c.cardBg,
            marginBottom: t.spacing.lg,
          }}
        >
          <h4
            style={{
              margin: "0 0 12px 0",
              fontSize: 14,
              fontWeight: 700,
              color: c.text,
            }}
          >
            {editingId ? "Edit suggestion" : "New suggestion"}
          </h4>

          {/* Icon selector */}
          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
              Icon
            </label>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {PREDEFINED_ICONS.map((ico) => (
                <button
                  key={ico}
                  onClick={() => setFormData({ ...formData, icon: ico })}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: t.radii.sm,
                    border: `1px solid ${formData.icon === ico ? c.primary : c.border}`,
                    backgroundColor: formData.icon === ico ? c.primary + "18" : c.surface,
                    cursor: "pointer",
                    fontSize: 16,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {ico}
                </button>
              ))}
            </div>
          </div>

          {/* Title */}
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
              Title
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="e.g., Summarize this document"
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* Prompt text */}
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
              Prompt text
            </label>
            <textarea
              value={formData.prompt_text}
              onChange={(e) => setFormData({ ...formData, prompt_text: e.target.value })}
              placeholder="Enter the prompt template text..."
              rows={4}
              style={{
                width: "100%",
                padding: 10,
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
                fontFamily: "monospace",
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* Row: Category + Order */}
          <div style={{ display: "flex", gap: 12, marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
                Category
              </label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: t.radii.sm,
                  border: `1px solid ${c.border}`,
                  backgroundColor: c.inputBg,
                  color: c.text,
                  fontSize: 13,
                }}
              >
                {categories.map((cat) => (
                  <option key={cat} value={cat} style={{ backgroundColor: c.inputBg, color: c.text }}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ width: 100 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
                Display order
              </label>
              <input
                type="number"
                value={formData.display_order}
                onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) || 0 })}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: t.radii.sm,
                  border: `1px solid ${c.border}`,
                  backgroundColor: c.inputBg,
                  color: c.text,
                  fontSize: 13,
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>

          {/* Requires capability */}
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary, display: "block", marginBottom: 4 }}>
              Requires capability (optional)
            </label>
            <input
              type="text"
              value={formData.requires_capability}
              onChange={(e) => setFormData({ ...formData, requires_capability: e.target.value })}
              placeholder="e.g., vision, code-execution"
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.inputBg,
                color: c.text,
                fontSize: 13,
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* Enabled toggle */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 13,
                color: c.text,
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              />
              Enabled on creation
            </label>
          </div>

          {/* Form actions */}
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: "8px 16px",
                borderRadius: t.radii.sm,
                border: "none",
                backgroundColor: c.success,
                color: "#FFFFFF",
                cursor: saving ? "default" : "pointer",
                fontSize: 12,
                fontWeight: 600,
                opacity: saving ? 0.5 : 1,
              }}
            >
              {saving ? "Saving..." : editingId ? "Update" : "Create"}
            </button>
            <button
              onClick={resetForm}
              style={{
                padding: "8px 16px",
                borderRadius: t.radii.sm,
                border: `1px solid ${c.border}`,
                backgroundColor: c.surface,
                color: c.textSecondary,
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: c.textSecondary }}>
          Loading prompt suggestions...
        </div>
      ) : suggestions.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            backgroundColor: c.surface,
            borderRadius: t.radii.lg,
            color: c.textSecondary,
          }}
        >
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
                backgroundColor: c.surface,
                borderRadius: t.radii.lg,
                border: `1px solid ${suggestion.enabled ? c.border : c.error + "40"}`,
                opacity: suggestion.enabled ? 1 : 0.7,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flex: 1 }}>
                  <span style={{ fontSize: 24 }}>{suggestion.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 15, fontWeight: 600, color: c.text }}>
                        {suggestion.title}
                      </span>
                      {!suggestion.enabled && (
                        <span
                          style={{
                            fontSize: 11,
                            padding: "2px 8px",
                            backgroundColor: c.error + "20",
                            color: c.error,
                            borderRadius: 4,
                          }}
                        >
                          Disabled
                        </span>
                      )}
                      {suggestion.requires_capability && (
                        <span
                          style={{
                            fontSize: 11,
                            padding: "2px 8px",
                            backgroundColor: c.primary + "20",
                            color: c.primary,
                            borderRadius: 4,
                          }}
                        >
                          Requires: {suggestion.requires_capability}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 13, color: c.textSecondary, marginBottom: 6 }}>
                      {suggestion.prompt_text}
                    </div>
                    <div style={{ display: "flex", gap: 8, fontSize: 12, color: c.textMuted }}>
                      <span
                        style={{
                          padding: "2px 8px",
                          backgroundColor: c.background,
                          borderRadius: 4,
                          textTransform: "capitalize",
                        }}
                      >
                        {suggestion.category}
                      </span>
                      <span>Order: {suggestion.display_order}</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => handleToggle(suggestion.id!)}
                    style={{
                      padding: "6px 12px",
                      backgroundColor: suggestion.enabled ? c.success + "20" : c.surface,
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
                      backgroundColor: c.surface,
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
                    onClick={() => handleDelete(suggestion.id!)}
                    style={{
                      padding: "6px 12px",
                      backgroundColor: c.error + "10",
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
