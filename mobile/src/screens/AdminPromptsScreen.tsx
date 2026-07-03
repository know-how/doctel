import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getPrompts, savePrompt } from "../api/client"

interface PromptEntry {
  id?: string
  prompt_type: string
  content: string
  version?: number
  updated_at?: string
}

const promptTypeIcons: Record<string, string> = {
  chat: "💬",
  summary: "📝",
  extraction: "🔍",
  classification: "🏷️",
  comparison: "⚖️",
}

export function AdminPromptsScreen() {
  const [prompts, setPrompts] = useState<PromptEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [savingId, setSavingId] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState("")
  const [editValues, setEditValues] = useState<Record<string, string>>({})
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  useEffect(() => {
    loadPrompts()
  }, [])

  const loadPrompts = async () => {
    try {
      setLoading(true)
      setError("")
      const res = await getPrompts()
      const items = res?.prompts || res?.results || (Array.isArray(res) ? res : [])
      setPrompts(items)
      const ev: Record<string, string> = {}
      items.forEach((p: any) => {
        ev[p.prompt_type || p.id || p.title || 'default'] = p.content
      })
      setEditValues(ev)
    } catch (err: any) {
      setError(err.message || "Failed to load prompts")
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (promptType: string) => {
    const content = editValues[promptType]
    if (!content?.trim()) return
    try {
      setSavingId(promptType)
      setError("")
      setSuccessMsg("")
      await savePrompt(promptType, content)
      setSuccessMsg(`Saved ${promptType} prompt`)
      setTimeout(() => setSuccessMsg(""), 3000)
    } catch (err: any) {
      setError(err.message || "Failed to save prompt")
    } finally {
      setSavingId(null)
    }
  }

  const groupedPrompts = prompts.reduce((acc: Record<string, PromptEntry[]>, p: PromptEntry) => {
    const group = p.prompt_type || "general"
    if (!acc[group]) acc[group] = []
    acc[group].push(p)
    return acc
  }, {})

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading prompts...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        System Prompts
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {successMsg ? (
        <View style={{ backgroundColor: c.success + "18", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.success + "28" }}>
          <Text style={{ color: c.success, fontSize: 13, fontWeight: "600" }}>{successMsg}</Text>
        </View>
      ) : null}

      {Object.keys(groupedPrompts).length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>📋</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
            No prompts configured
          </Text>
          <Text style={{ fontSize: 13, color: c.textMuted }}>Prompts will appear here once configured</Text>
        </View>
      ) : (
        <View style={{ flexDirection: isTablet ? "row" : "column", flexWrap: isTablet ? "wrap" : "nowrap", gap: t.spacing.lg }}>
          {Object.entries(groupedPrompts).map(([group, groupPrompts]) => (
            <View key={group} style={{ marginBottom: t.spacing.lg, width: isTablet ? "48%" : "100%" }}>
              <Text style={{ fontSize: 16, fontWeight: "700", color: c.primary, marginBottom: t.spacing.sm }}>
                {promptTypeIcons[group] || "📋"} {group.charAt(0).toUpperCase() + group.slice(1)}
              </Text>
              {groupPrompts.map((prompt, idx) => (
                <View
                  key={prompt.id || idx}
                  style={{
                    backgroundColor: c.cardBg,
                    borderRadius: t.radii.md,
                    padding: t.spacing.sm,
                    marginBottom: t.spacing.sm,
                    borderWidth: 1,
                    borderColor: c.border,
                  }}
                >
                  <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.sm }}>
                    <Text style={{ fontSize: 12, color: c.textMuted }}>
                      {prompt.prompt_type || "Prompt"} {prompt.version ? `v${prompt.version}` : ""}
                    </Text>
                    {prompt.updated_at && (
                      <Text style={{ fontSize: 11, color: c.textMuted }}>
                        Updated: {new Date(prompt.updated_at).toLocaleDateString()}
                      </Text>
                    )}
                  </View>
                  <TextInput
                    value={editValues[prompt.prompt_type || prompt.id || group] || prompt.content}
                    onChangeText={(text) => {
                      setEditValues((prev) => ({
                        ...prev,
                        [prompt.prompt_type || prompt.id || group]: text,
                      }))
                    }}
                    multiline
                    numberOfLines={6}
                    textAlignVertical="top"
                    style={{
                      backgroundColor: c.inputBg,
                      borderRadius: t.radii.md,
                      padding: t.spacing.sm,
                      borderWidth: 1,
                      borderColor: c.border,
                      color: c.text,
                      fontSize: 13,
                      marginBottom: t.spacing.sm,
                      minHeight: 100,
                    }}
                  />
                  <Pressable
                    onPress={() => handleSave(prompt.prompt_type || prompt.id || group)}
                    disabled={savingId === (prompt.prompt_type || prompt.id || group)}
                    style={{
                      backgroundColor: savingId === (prompt.prompt_type || prompt.id || group) ? c.textMuted : c.primary,
                      borderRadius: t.radii.sm,
                      paddingVertical: t.spacing.sm,
                      alignItems: "center",
                    }}
                  >
                    <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 13 }}>
                      {savingId === (prompt.prompt_type || prompt.id || group) ? "Saving..." : "Save"}
                    </Text>
                  </Pressable>
                </View>
              ))}
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  )
}