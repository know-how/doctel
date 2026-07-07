import React, { useEffect, useState, useCallback } from "react"
import {
  View, Text, Pressable, ScrollView, ActivityIndicator,
  useWindowDimensions, TextInput, Alert,
} from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  v2GetProvider, v2UpdateProvider, v2ListModels, v2AddModel,
} from "../api/client"
import type { V2Provider, V2ModelMetadata } from "../types/api"

export function ProviderDetailScreen({
  providerId,
  onNavigate,
}: {
  providerId: string
  onNavigate?: (path: string) => void
}) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [provider, setProvider] = useState<V2Provider | null>(null)
  const [models, setModels] = useState<V2ModelMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [editMode, setEditMode] = useState(false)
  const [editName, setEditName] = useState("")
  const [editVendor, setEditVendor] = useState("")
  const [editBaseUrl, setEditBaseUrl] = useState("")
  const [editDesc, setEditDesc] = useState("")
  const [showAddModel, setShowAddModel] = useState(false)
  const [newModelName, setNewModelName] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError("")
      const [provRes, modelsRes] = await Promise.all([
        v2GetProvider(providerId),
        v2ListModels(providerId),
      ])
      setProvider(provRes.provider || (provRes as any))
      setModels(modelsRes.models || [])
    } catch (err: any) {
      setError(err.message || "Failed to load provider detail")
    } finally {
      setLoading(false)
    }
  }, [providerId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const enterEditMode = () => {
    if (!provider) return
    setEditName(provider.name || "")
    setEditVendor(provider.vendor || "")
    setEditBaseUrl(provider.base_url || "")
    setEditDesc(provider.description || "")
    setEditMode(true)
  }

  const handleSave = async () => {
    if (!editName.trim()) return
    try {
      setSubmitting(true)
      setError("")
      const payload: Record<string, any> = { name: editName.trim() }
      if (editVendor.trim()) payload.vendor = editVendor.trim()
      if (editBaseUrl.trim()) payload.base_url = editBaseUrl.trim()
      if (editDesc.trim()) payload.description = editDesc.trim()
      await v2UpdateProvider(providerId, payload)
      setEditMode(false)
      await loadData()
    } catch (err: any) {
      setError(err.message || "Failed to update provider")
    } finally {
      setSubmitting(false)
    }
  }

  const handleAddModel = async () => {
    if (!newModelName.trim()) return
    try {
      setSubmitting(true)
      setError("")
      await v2AddModel(providerId, { name: newModelName.trim() })
      setShowAddModel(false)
      setNewModelName("")
      await loadData()
    } catch (err: any) {
      setError(err.message || "Failed to add model")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: 12, color: c.textMuted }}>Loading provider...</Text>
      </View>
    )
  }

  if (!provider && !loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>🔍</Text>
        <Text style={{ fontSize: 16, color: c.text }}>Provider not found</Text>
        <Pressable onPress={() => onNavigate?.("/admin/v2/providers")} style={{ marginTop: t.spacing.md }}>
          <Text style={{ color: c.primary, fontWeight: "600" }}>← Back to Providers</Text>
        </Pressable>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      {/* Header */}
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: t.spacing.md }}>
        <Pressable onPress={() => onNavigate?.("/admin/v2/providers")} style={{ marginRight: t.spacing.sm }}>
          <Text style={{ color: c.primary, fontSize: 16 }}>←</Text>
        </Pressable>
        <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, flex: 1 }}>
          {provider?.icon || "🏪"} {provider?.name || "Provider"}
        </Text>
        <Pressable
          onPress={editMode ? () => setEditMode(false) : enterEditMode}
          style={{
            backgroundColor: editMode ? c.textMuted : c.primary,
            paddingHorizontal: t.spacing.md,
            paddingVertical: t.spacing.sm,
            borderRadius: t.radii.md,
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "700", fontSize: 14 }}>
            {editMode ? "Cancel" : "Edit"}
          </Text>
        </Pressable>
      </View>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {/* Edit Form */}
      {editMode ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>Edit Provider</Text>
          <TextInput
            placeholder="Name *"
            placeholderTextColor={c.textMuted}
            value={editName}
            onChangeText={setEditName}
            style={{
              backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
              color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
            }}
          />
          <TextInput
            placeholder="Vendor"
            placeholderTextColor={c.textMuted}
            value={editVendor}
            onChangeText={setEditVendor}
            style={{
              backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
              color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
            }}
          />
          <TextInput
            placeholder="Base URL"
            placeholderTextColor={c.textMuted}
            value={editBaseUrl}
            onChangeText={setEditBaseUrl}
            autoCapitalize="none"
            style={{
              backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
              color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
            }}
          />
          <TextInput
            placeholder="Description"
            placeholderTextColor={c.textMuted}
            value={editDesc}
            onChangeText={setEditDesc}
            multiline
            style={{
              backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
              color: c.text, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border,
              minHeight: 60,
            }}
          />
          <View style={{ flexDirection: "row", gap: t.spacing.sm }}>
            <Pressable
              onPress={handleSave}
              disabled={submitting || !editName.trim()}
              style={{
                flex: 1, backgroundColor: submitting || !editName.trim() ? c.textMuted : c.primary,
                paddingVertical: t.spacing.sm, borderRadius: t.radii.md, alignItems: "center",
              }}
            >
              <Text style={{ color: "#fff", fontWeight: "700" }}>{submitting ? "Saving..." : "Save"}</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        /* Provider Info */
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
          <DetailRow label="Name" value={provider?.name} c={c} t={t} />
          <DetailRow label="Vendor" value={provider?.vendor} c={c} t={t} />
          <DetailRow label="Base URL" value={provider?.base_url} c={c} t={t} />
          <DetailRow label="Description" value={provider?.description} c={c} t={t} />
        </View>
      )}

      {/* Models Section */}
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.sm }}>
        <Text style={{ fontSize: 18, fontWeight: "700", color: c.text }}>Models</Text>
        <Pressable
          onPress={() => setShowAddModel((p) => !p)}
          style={{
            backgroundColor: c.primary,
            paddingHorizontal: t.spacing.md,
            paddingVertical: t.spacing.sm,
            borderRadius: t.radii.md,
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "700", fontSize: 14 }}>
            {showAddModel ? "Cancel" : "+ Model"}
          </Text>
        </Pressable>
      </View>

      {showAddModel ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
          <TextInput
            placeholder="Model name/ID *"
            placeholderTextColor={c.textMuted}
            value={newModelName}
            onChangeText={setNewModelName}
            style={{
              backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
              color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
            }}
          />
          <Pressable
            onPress={handleAddModel}
            disabled={submitting || !newModelName.trim()}
            style={{
              backgroundColor: submitting || !newModelName.trim() ? c.textMuted : c.primary,
              paddingVertical: t.spacing.sm, borderRadius: t.radii.md, alignItems: "center",
            }}
          >
            <Text style={{ color: "#fff", fontWeight: "700" }}>{submitting ? "Adding..." : "Add Model"}</Text>
          </Pressable>
        </View>
      ) : null}

      {models.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.lg, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 32, marginBottom: t.spacing.sm }}>🤖</Text>
          <Text style={{ fontSize: 14, color: c.textMuted }}>No models for this provider</Text>
        </View>
      ) : (
        models.map((m, i) => (
          <Pressable
            key={m.id || m.name || i}
            onPress={() => onNavigate?.(`/admin/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(m.id || m.name || "")}`)}
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
                <Text style={{ fontSize: 18 }}>🤖</Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: "700", color: c.text }}>{m.name || m.id}</Text>
                  {(m as any).capabilities?.length ? (
                    <Text style={{ fontSize: 11, color: c.textMuted }} numberOfLines={1}>
                      {(m as any).capabilities.join(", ")}
                    </Text>
                  ) : null}
                </View>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: t.spacing.xs }}>
                <View
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 5,
                    backgroundColor: (m as any).enabled !== false ? c.success : c.error,
                  }}
                />
                <Text style={{ color: c.textMuted, fontSize: 12 }}>
                  {(m as any).state || ((m as any).enabled !== false ? "active" : "inactive")}
                </Text>
              </View>
            </View>
          </Pressable>
        ))
      )}
    </ScrollView>
  )
}

function DetailRow({ label, value, c, t }: { label: string; value?: string | null; c: any; t: any }) {
  return (
    <View style={{ flexDirection: "row", paddingVertical: 4 }}>
      <Text style={{ color: c.textMuted, fontSize: 13, width: 100 }}>{label}</Text>
      <Text style={{ color: c.text, fontSize: 13, flex: 1 }}>{value || "—"}</Text>
    </View>
  )
}
