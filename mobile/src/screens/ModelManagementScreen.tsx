import React, { useEffect, useState, useCallback } from "react"
import {
  View, Text, Pressable, ScrollView, ActivityIndicator,
  useWindowDimensions, TextInput, Alert,
} from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  v2GetModel, v2SetModelState, v2ToggleModel, v2SetVisibility,
  v2SetModelRoles, v2SetModelDepartments, v2UpdateModel, v2GetCatalog,
} from "../api/client"
import type { V2ModelMetadata } from "../types/api"

const STATE_OPTIONS = ["active", "inactive", "draft", "deprecated"]

export function ModelManagementScreen({
  providerId,
  modelId,
  onNavigate,
}: {
  providerId: string
  modelId: string
  onNavigate?: (path: string) => void
}) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [model, setModel] = useState<V2ModelMetadata | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState<string | null>(null)

  // Edit fields
  const [editName, setEditName] = useState("")
  const [editState, setEditState] = useState("active")
  const [editEnabled, setEditEnabled] = useState(true)
  const [editVisible, setEditVisible] = useState(true)
  const [editRolesText, setEditRolesText] = useState("")
  const [editDeptsText, setEditDeptsText] = useState("")

  // Catalog reference for valid roles/departments
  const [validRoles, setValidRoles] = useState<string[]>([])
  const [validDepartments, setValidDepartments] = useState<string[]>([])

  const loadModel = useCallback(async () => {
    try {
      setLoading(true)
      setError("")
      const [modelRes, catalogRes] = await Promise.all([
        v2GetModel(providerId, modelId),
        v2GetCatalog().catch(() => null),
      ])
      const m = modelRes.model
      setModel(m)
      setEditName(m.name || "")
      setEditState(m.state || (m.enabled !== false ? "active" : "inactive"))
      setEditEnabled(m.enabled !== false)
      setEditVisible(m.visibleToUsers !== false)
      setEditRolesText((m.allowedRoles || []).join(", "))
      setEditDeptsText((m.departmentRestrictions || []).join(", "))
      if (catalogRes) {
        setValidRoles(catalogRes.validRoles || [])
        setValidDepartments(catalogRes.validDepartments || [])
      }
    } catch (err: any) {
      setError(err.message || "Failed to load model")
    } finally {
      setLoading(false)
    }
  }, [providerId, modelId])

  useEffect(() => {
    loadModel()
  }, [loadModel])

  const handleSaveState = async (newState: string) => {
    try {
      setSaving("state")
      setError("")
      await v2SetModelState(providerId, modelId, newState)
      setEditState(newState)
      setModel((prev) => prev ? { ...prev, state: newState } : prev)
    } catch (err: any) {
      setError(err.message || "Failed to update state")
    } finally {
      setSaving(null)
    }
  }

  const handleToggleEnabled = async () => {
    const newVal = !editEnabled
    try {
      setSaving("enabled")
      setError("")
      await v2ToggleModel(providerId, modelId, newVal)
      setEditEnabled(newVal)
      setModel((prev) => prev ? { ...prev, enabled: newVal } : prev)
    } catch (err: any) {
      setError(err.message || "Failed to toggle model")
    } finally {
      setSaving(null)
    }
  }

  const handleToggleVisibility = async () => {
    const newVal = !editVisible
    try {
      setSaving("visible")
      setError("")
      await v2SetVisibility(providerId, modelId, newVal)
      setEditVisible(newVal)
      setModel((prev) => prev ? { ...prev, visibleToUsers: newVal } : prev)
    } catch (err: any) {
      setError(err.message || "Failed to toggle visibility")
    } finally {
      setSaving(null)
    }
  }

  const handleSaveName = async () => {
    if (!editName.trim()) return
    try {
      setSaving("name")
      setError("")
      await v2UpdateModel(providerId, modelId, { name: editName.trim() })
      setModel((prev) => prev ? { ...prev, name: editName.trim() } : prev)
    } catch (err: any) {
      setError(err.message || "Failed to update name")
    } finally {
      setSaving(null)
    }
  }

  const handleSaveRoles = async () => {
    const roles = editRolesText
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean)
    try {
      setSaving("roles")
      setError("")
      await v2SetModelRoles(providerId, modelId, roles)
      setModel((prev) => prev ? { ...prev, allowedRoles: roles } : prev)
    } catch (err: any) {
      setError(err.message || "Failed to update roles")
    } finally {
      setSaving(null)
    }
  }

  const handleSaveDepartments = async () => {
    const depts = editDeptsText
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean)
    try {
      setSaving("departments")
      setError("")
      await v2SetModelDepartments(providerId, modelId, depts)
      setModel((prev) => prev ? { ...prev, departmentRestrictions: depts } : prev)
    } catch (err: any) {
      setError(err.message || "Failed to update departments")
    } finally {
      setSaving(null)
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: 12, color: c.textMuted }}>Loading model...</Text>
      </View>
    )
  }

  if (!model && !loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>🔍</Text>
        <Text style={{ fontSize: 16, color: c.text }}>Model not found</Text>
        <Pressable
          onPress={() => onNavigate?.(`/admin/v2/providers/${encodeURIComponent(providerId)}`)}
          style={{ marginTop: t.spacing.md }}
        >
          <Text style={{ color: c.primary, fontWeight: "600" }}>← Back to Provider</Text>
        </Pressable>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      {/* Header */}
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: t.spacing.md }}>
        <Pressable
          onPress={() => onNavigate?.(`/admin/v2/providers/${encodeURIComponent(providerId)}`)}
          style={{ marginRight: t.spacing.sm }}
        >
          <Text style={{ color: c.primary, fontSize: 16 }}>←</Text>
        </Pressable>
        <Text style={{ fontSize: 20, fontWeight: "800", color: c.text, flex: 1, numberOfLines: 1 } as any}>
          🤖 {model?.name || "Model"}
        </Text>
      </View>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {/* Info Card */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>📋 Model Info</Text>
        <InfoRow label="ID" value={model?.id} c={c} t={t} />
        <InfoRow label="Name" value={model?.name} c={c} t={t} />
        <InfoRow label="Context" value={model?.contextWindow ? `${model.contextWindow} tokens` : "—"} c={c} t={t} />
        <InfoRow label="State" value={model?.state || (model?.enabled !== false ? "active" : "inactive")} c={c} t={t} />
        <InfoRow label="Pricing" value={model?.pricingTier || "—"} c={c} t={t} />
        <InfoRow label="License" value={model?.license || "—"} c={c} t={t} />
        {(model?.capabilities?.length ?? 0) > 0 ? (
          <View style={{ marginTop: t.spacing.xs }}>
            <Text style={{ color: c.textMuted, fontSize: 12, marginBottom: 2 }}>Capabilities</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
              {(model?.capabilities || []).map((cap) => (
                <View
                  key={cap}
                  style={{
                    backgroundColor: c.primary + "20",
                    borderRadius: t.radii.sm,
                    paddingHorizontal: 8,
                    paddingVertical: 2,
                  }}
                >
                  <Text style={{ color: c.primary, fontSize: 11, fontWeight: "600" }}>{cap}</Text>
                </View>
              ))}
            </View>
          </View>
        ) : null}
        {(model?.forTasks?.length ?? 0) > 0 ? (
          <View style={{ marginTop: t.spacing.xs }}>
            <Text style={{ color: c.textMuted, fontSize: 12, marginBottom: 2 }}>Tasks</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
              {(model?.forTasks || []).map((task) => (
                <View
                  key={task}
                  style={{
                    backgroundColor: c.accent + "20",
                    borderRadius: t.radii.sm,
                    paddingHorizontal: 8,
                    paddingVertical: 2,
                  }}
                >
                  <Text style={{ color: c.accent, fontSize: 11, fontWeight: "600" }}>{task}</Text>
                </View>
              ))}
            </View>
          </View>
        ) : null}
      </View>

      {/* Name Edit */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>✏️ Display Name</Text>
        <TextInput
          placeholder="Model name"
          placeholderTextColor={c.textMuted}
          value={editName}
          onChangeText={setEditName}
          style={{
            backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
            color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
          }}
        />
        <Pressable
          onPress={handleSaveName}
          disabled={saving === "name" || !editName.trim()}
          style={{
            backgroundColor: saving === "name" || !editName.trim() ? c.textMuted : c.primary,
            paddingVertical: t.spacing.sm, borderRadius: t.radii.md, alignItems: "center",
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "700" }}>
            {saving === "name" ? "Saving..." : "Save Name"}
          </Text>
        </Pressable>
      </View>

      {/* State Selector */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>🔧 State</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: t.spacing.xs }}>
          {STATE_OPTIONS.map((opt) => {
            const active = editState === opt
            return (
              <Pressable
                key={opt}
                onPress={() => handleSaveState(opt)}
                disabled={saving === "state"}
                style={{
                  backgroundColor: active ? c.primary : c.bgSecondary,
                  paddingHorizontal: t.spacing.md,
                  paddingVertical: t.spacing.sm,
                  borderRadius: t.radii.sm,
                  borderWidth: 1,
                  borderColor: active ? c.primary : c.border,
                }}
              >
                <Text style={{ color: active ? "#fff" : c.text, fontWeight: "600", fontSize: 13 }}>
                  {saving === "state" && active ? "..." : opt}
                </Text>
              </Pressable>
            )
          })}
        </View>
      </View>

      {/* Toggle: Enabled */}
      <Pressable
        onPress={handleToggleEnabled}
        disabled={saving === "enabled"}
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.md,
          padding: t.spacing.md,
          marginBottom: t.spacing.md,
          borderWidth: 1,
          borderColor: c.border,
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <View>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }}>⚡ Enabled</Text>
          <Text style={{ fontSize: 12, color: c.textMuted }}>Model can process requests</Text>
        </View>
        <View
          style={{
            width: 52,
            height: 28,
            borderRadius: 14,
            backgroundColor: editEnabled ? c.success : c.textMuted,
            justifyContent: "center",
            paddingHorizontal: 4,
            alignItems: editEnabled ? "flex-end" : "flex-start",
          }}
        >
          <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: "#fff" }} />
        </View>
      </Pressable>

      {/* Toggle: Visible to Users */}
      <Pressable
        onPress={handleToggleVisibility}
        disabled={saving === "visible"}
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.md,
          padding: t.spacing.md,
          marginBottom: t.spacing.md,
          borderWidth: 1,
          borderColor: c.border,
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <View>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }}>👁️ Visible to Users</Text>
          <Text style={{ fontSize: 12, color: c.textMuted }}>Show in chat model selector</Text>
        </View>
        <View
          style={{
            width: 52,
            height: 28,
            borderRadius: 14,
            backgroundColor: editVisible ? c.success : c.textMuted,
            justifyContent: "center",
            paddingHorizontal: 4,
            alignItems: editVisible ? "flex-end" : "flex-start",
          }}
        >
          <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: "#fff" }} />
        </View>
      </Pressable>

      {/* Roles */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>👤 Allowed Roles</Text>
        <TextInput
          placeholder="admin, user, manager"
          placeholderTextColor={c.textMuted}
          value={editRolesText}
          onChangeText={setEditRolesText}
          autoCapitalize="none"
          style={{
            backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
            color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
          }}
        />
        {validRoles.length > 0 ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4, marginBottom: t.spacing.sm }}>
            {validRoles.map((role) => {
              const selected = editRolesText.split(",").map((r) => r.trim()).includes(role)
              return (
                <Pressable
                  key={role}
                  onPress={() => {
                    const current = editRolesText.split(",").map((r) => r.trim()).filter(Boolean)
                    const next = selected
                      ? current.filter((r) => r !== role)
                      : [...current, role]
                    setEditRolesText(next.join(", "))
                  }}
                  style={{
                    backgroundColor: selected ? c.primary + "30" : c.bgSecondary,
                    borderRadius: t.radii.sm,
                    paddingHorizontal: 8,
                    paddingVertical: 3,
                    borderWidth: 1,
                    borderColor: selected ? c.primary : c.border,
                  }}
                >
                  <Text style={{ color: selected ? c.primary : c.textMuted, fontSize: 12, fontWeight: "600" }}>
                    {role}
                  </Text>
                </Pressable>
              )
            })}
          </View>
        ) : null}
        <Pressable
          onPress={handleSaveRoles}
          disabled={saving === "roles"}
          style={{
            backgroundColor: saving === "roles" ? c.textMuted : c.primary,
            paddingVertical: t.spacing.sm, borderRadius: t.radii.md, alignItems: "center",
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "700" }}>
            {saving === "roles" ? "Saving..." : "Save Roles"}
          </Text>
        </Pressable>
      </View>

      {/* Departments */}
      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.sm }}>🏢 Department Restrictions</Text>
        <TextInput
          placeholder="hr, engineering, finance"
          placeholderTextColor={c.textMuted}
          value={editDeptsText}
          onChangeText={setEditDeptsText}
          autoCapitalize="none"
          style={{
            backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, padding: t.spacing.sm,
            color: c.text, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border,
          }}
        />
        {validDepartments.length > 0 ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4, marginBottom: t.spacing.sm }}>
            {validDepartments.map((dept) => {
              const selected = editDeptsText.split(",").map((d) => d.trim()).includes(dept)
              return (
                <Pressable
                  key={dept}
                  onPress={() => {
                    const current = editDeptsText.split(",").map((d) => d.trim()).filter(Boolean)
                    const next = selected
                      ? current.filter((d) => d !== dept)
                      : [...current, dept]
                    setEditDeptsText(next.join(", "))
                  }}
                  style={{
                    backgroundColor: selected ? c.accent + "30" : c.bgSecondary,
                    borderRadius: t.radii.sm,
                    paddingHorizontal: 8,
                    paddingVertical: 3,
                    borderWidth: 1,
                    borderColor: selected ? c.accent : c.border,
                  }}
                >
                  <Text style={{ color: selected ? c.accent : c.textMuted, fontSize: 12, fontWeight: "600" }}>
                    {dept}
                  </Text>
                </Pressable>
              )
            })}
          </View>
        ) : null}
        <Pressable
          onPress={handleSaveDepartments}
          disabled={saving === "departments"}
          style={{
            backgroundColor: saving === "departments" ? c.textMuted : c.primary,
            paddingVertical: t.spacing.sm, borderRadius: t.radii.md, alignItems: "center",
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "700" }}>
            {saving === "departments" ? "Saving..." : "Save Departments"}
          </Text>
        </Pressable>
      </View>
    </ScrollView>
  )
}

function InfoRow({ label, value, c, t }: { label: string; value?: string | null; c: any; t: any }) {
  return (
    <View style={{ flexDirection: "row", paddingVertical: 3 }}>
      <Text style={{ color: c.textMuted, fontSize: 13, width: 90 }}>{label}</Text>
      <Text style={{ color: c.text, fontSize: 13, flex: 1 }}>{value || "—"}</Text>
    </View>
  )
}
