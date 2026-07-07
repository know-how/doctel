import React, { useEffect, useState, useCallback } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions, TextInput, Alert } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { v2ListProviders, v2AddProvider, v2DeleteProvider, v2ReorderProviders } from "../api/client"
import type { V2Provider } from "../types/api"

export function ProvidersScreen({ onNavigate }: { onNavigate?: (path: string) => void }) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [providers, setProviders] = useState<V2Provider[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [showAddForm, setShowAddForm] = useState(false)
  const [addName, setAddName] = useState("")
  const [addVendor, setAddVendor] = useState("")
  const [addBaseUrl, setAddBaseUrl] = useState("")
  const [addDesc, setAddDesc] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const loadProviders = useCallback(async () => {
    try {
      setLoading(true)
      setError("")
      const res = await v2ListProviders()
      setProviders(res.providers || [])
    } catch (err: any) {
      setError(err.message || "Failed to load providers")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  const handleAddProvider = async () => {
    if (!addName.trim()) return
    try {
      setSubmitting(true)
      setError("")
      await v2AddProvider({
        name: addName.trim(),
        vendor: addVendor.trim() || undefined,
        base_url: addBaseUrl.trim() || undefined,
        description: addDesc.trim() || undefined,
      })
      setShowAddForm(false)
      setAddName("")
      setAddVendor("")
      setAddBaseUrl("")
      setAddDesc("")
      await loadProviders()
    } catch (err: any) {
      setError(err.message || "Failed to add provider")
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteProvider = (providerId: string, providerName: string) => {
    Alert.alert("Delete Provider", `Remove "${providerName}"?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            setError("")
            await v2DeleteProvider(providerId)
            await loadProviders()
          } catch (err: any) {
            setError(err.message || "Failed to delete provider")
          }
        },
      },
    ])
  }

  const handleMoveUp = async (index: number) => {
    if (index === 0) return
    const reordered = [...providers]
    ;[reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]]
    try {
      setError("")
      await v2ReorderProviders(reordered.map((p) => p.id))
      setProviders(reordered)
    } catch (err: any) {
      setError(err.message || "Failed to reorder")
      await loadProviders()
    }
  }

  const handleMoveDown = async (index: number) => {
    if (index >= providers.length - 1) return
    const reordered = [...providers]
    ;[reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]]
    try {
      setError("")
      await v2ReorderProviders(reordered.map((p) => p.id))
      setProviders(reordered)
    } catch (err: any) {
      setError(err.message || "Failed to reorder")
      await loadProviders()
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: 12, color: c.textMuted }}>Loading providers...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.md }}>
        <Text style={{ fontSize: 24, fontWeight: "800", color: c.text }}>🏪 Providers</Text>
        <Pressable
          onPress={() => setShowAddForm((p) => !p)}
          style={{
            backgroundColor: c.primary,
            paddingHorizontal: t.spacing.md,
            paddingVertical: t.spacing.sm,
            borderRadius: t.radii.md,
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "700", fontSize: 14 }}>
            {showAddForm ? "Cancel" : "Add Provider"}
          </Text>
        </Pressable>
      </View>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {/* Add Form */}
      {showAddForm ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>New Provider</Text>
          <TextInput
            placeholder="Name *"
            placeholderTextColor={c.textMuted}
            value={addName}
            onChangeText={setAddName}
            style={{
              backgroundColor: c.bgSecondary,
              borderRadius: t.radii.sm,
              padding: t.spacing.sm,
              color: c.text,
              marginBottom: t.spacing.sm,
              borderWidth: 1,
              borderColor: c.border,
            }}
          />
          <TextInput
            placeholder="Vendor (e.g. openai)"
            placeholderTextColor={c.textMuted}
            value={addVendor}
            onChangeText={setAddVendor}
            style={{
              backgroundColor: c.bgSecondary,
              borderRadius: t.radii.sm,
              padding: t.spacing.sm,
              color: c.text,
              marginBottom: t.spacing.sm,
              borderWidth: 1,
              borderColor: c.border,
            }}
          />
          <TextInput
            placeholder="Base URL"
            placeholderTextColor={c.textMuted}
            value={addBaseUrl}
            onChangeText={setAddBaseUrl}
            autoCapitalize="none"
            style={{
              backgroundColor: c.bgSecondary,
              borderRadius: t.radii.sm,
              padding: t.spacing.sm,
              color: c.text,
              marginBottom: t.spacing.sm,
              borderWidth: 1,
              borderColor: c.border,
            }}
          />
          <TextInput
            placeholder="Description"
            placeholderTextColor={c.textMuted}
            value={addDesc}
            onChangeText={setAddDesc}
            multiline
            style={{
              backgroundColor: c.bgSecondary,
              borderRadius: t.radii.sm,
              padding: t.spacing.sm,
              color: c.text,
              marginBottom: t.spacing.md,
              borderWidth: 1,
              borderColor: c.border,
              minHeight: 60,
            }}
          />
          <Pressable
            onPress={handleAddProvider}
            disabled={submitting || !addName.trim()}
            style={{
              backgroundColor: submitting || !addName.trim() ? c.textMuted : c.primary,
              paddingVertical: t.spacing.sm,
              borderRadius: t.radii.md,
              alignItems: "center",
            }}
          >
            <Text style={{ color: "#fff", fontWeight: "700", fontSize: 14 }}>
              {submitting ? "Adding..." : "Add Provider"}
            </Text>
          </Pressable>
        </View>
      ) : null}

      {/* Provider List */}
      {providers.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>🏪</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>No providers</Text>
          <Text style={{ fontSize: 13, color: c.textMuted, textAlign: "center" }}>
            Add a provider to get started with V2 model management.
          </Text>
        </View>
      ) : (
        providers.map((p, i) => (
          <Pressable
            key={p.id || i}
            onPress={() => onNavigate?.(`/admin/v2/providers/${encodeURIComponent(p.id)}`)}
            style={{
              backgroundColor: c.cardBg,
              borderRadius: t.radii.md,
              padding: t.spacing.md,
              marginBottom: t.spacing.sm,
              borderWidth: 1,
              borderColor: c.border,
            }}
          >
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.sm, flex: 1 }}>
                <Text style={{ fontSize: 24 }}>{p.icon || "🏪"}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: "700", color: c.text }}>{p.name}</Text>
                  {p.vendor ? (
                    <Text style={{ fontSize: 12, color: c.textMuted }}>{p.vendor}</Text>
                  ) : null}
                  {p.description ? (
                    <Text style={{ fontSize: 12, color: c.textMuted, marginTop: 2 }} numberOfLines={1}>
                      {p.description}
                    </Text>
                  ) : null}
                </View>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.xs }}>
                <Text style={{ color: c.textMuted, fontSize: 12, marginRight: t.spacing.sm }}>
                  {p.models?.length ?? 0} models
                </Text>
                <Pressable onPress={() => handleMoveUp(i)} style={{ padding: 4 }}>
                  <Text style={{ color: c.textMuted, fontSize: 16 }}>▲</Text>
                </Pressable>
                <Pressable onPress={() => handleMoveDown(i)} style={{ padding: 4 }}>
                  <Text style={{ color: c.textMuted, fontSize: 16 }}>▼</Text>
                </Pressable>
                <Pressable onPress={() => handleDeleteProvider(p.id, p.name)} style={{ padding: 4 }}>
                  <Text style={{ color: c.error, fontSize: 16 }}>✕</Text>
                </Pressable>
              </View>
            </View>
          </Pressable>
        ))
      )}
    </ScrollView>
  )
}
