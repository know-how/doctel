import React, { useEffect, useState } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getOutputs } from "../api/client"

const typeIcons: Record<string, string> = {
  summary: "📝",
  extraction: "🔍",
  classification: "🏷️",
  comparison: "⚖️",
  export: "📤",
}

export function OutputsHistoryScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const typeBadgeColors: Record<string, string> = {
    summary: c.success + "18",
    extraction: c.primary + "14",
    classification: c.accent + "18",
    comparison: c.warning + "18",
    export: c.accent + "18",
  }

  const [outputs, setOutputs] = useState<any[]>([])
  const [filteredOutputs, setFilteredOutputs] = useState<any[]>([])
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    loadOutputs()
  }, [])

  useEffect(() => {
    if (selectedType) {
      setFilteredOutputs(outputs.filter((o) => o.type === selectedType || o.output_type === selectedType))
    } else {
      setFilteredOutputs(outputs)
    }
  }, [selectedType, outputs])

  const loadOutputs = async () => {
    try {
      setLoading(true)
      setError("")
      const res = await getOutputs()
      const items = res?.outputs || res?.results || res?.items || (Array.isArray(res) ? res : [])
      setOutputs(items)
    } catch (err: any) {
      setError(err.message || "Failed to load outputs")
    } finally {
      setLoading(false)
    }
  }

  const types = Array.from(new Set(outputs.map((o) => o.type || o.output_type).filter(Boolean)))

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm + t.spacing.xs, color: c.textMuted }}>Loading outputs...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Outputs History
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm + t.spacing.xs, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {types.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: t.spacing.md }}>
          <Pressable
            onPress={() => setSelectedType(null)}
            style={{
              paddingHorizontal: t.spacing.sm + t.spacing.xs + t.spacing.xs,
              paddingVertical: 7,
              borderRadius: 20,
              backgroundColor: !selectedType ? c.primary : c.bgSecondary,
              marginRight: t.spacing.sm,
            }}
          >
            <Text style={{ color: !selectedType ? "#FFFFFF" : c.text, fontSize: 13, fontWeight: "600" }}>
              All
            </Text>
          </Pressable>
          {types.map((type) => (
            <Pressable
              key={type}
              onPress={() => setSelectedType(selectedType === type ? null : type)}
              style={{
                paddingHorizontal: t.spacing.sm + t.spacing.xs + t.spacing.xs,
                paddingVertical: 7,
                borderRadius: 20,
                backgroundColor: selectedType === type ? (typeBadgeColors[type] || c.primary + "14") : c.bgSecondary,
                marginRight: t.spacing.sm,
              }}
            >
              <Text style={{ color: selectedType === type ? c.text : c.textMuted, fontSize: 13, fontWeight: "600" }}>
                {typeIcons[type] || "📋"} {type.charAt(0).toUpperCase() + type.slice(1)}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

      {filteredOutputs.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm + t.spacing.xs }}>📭</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
            No outputs yet
          </Text>
          <Text style={{ fontSize: 13, color: c.textMuted, textAlign: "center" }}>
            Run analysis tasks to generate outputs
          </Text>
        </View>
      ) : (
        <View style={isTablet ? { flexDirection: "row", flexWrap: "wrap", gap: t.spacing.sm } : undefined}>
          {filteredOutputs.map((item, index) => {
            const itemType = item.type || item.output_type || "unknown"
            const title = item.title || item.name || item.filename || `Output ${index + 1}`
            const preview = item.preview || item.summary || item.description || item.content || ""
            const date = item.created_at || item.generated_at || item.date

            return (
              <View
                key={item.id || index}
                style={{
                  backgroundColor: c.cardBg,
                  borderRadius: t.radii.md,
                  padding: t.spacing.sm + t.spacing.xs,
                  marginBottom: t.spacing.sm + t.spacing.xs,
                  borderWidth: 1,
                  borderColor: c.border,
                  ...(isTablet ? { width: "48%", marginBottom: t.spacing.sm } : {}),
                }}
              >
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: t.spacing.sm }}>
                  <View style={{ flex: 1, flexDirection: "row", alignItems: "center", gap: t.spacing.sm }}>
                    <Text style={{ fontSize: 20 }}>{typeIcons[itemType] || "📋"}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }} numberOfLines={1}>
                        {title}
                      </Text>
                      <Text style={{ fontSize: 11, color: c.textMuted }}>
                        {date ? new Date(date).toLocaleDateString() : "Unknown date"}
                      </Text>
                    </View>
                  </View>
                  <View
                    style={{
                      backgroundColor: typeBadgeColors[itemType] || c.primary + "14",
                      borderRadius: t.radii.sm,
                      paddingHorizontal: t.spacing.sm,
                      paddingVertical: 3,
                      marginLeft: t.spacing.sm,
                    }}
                  >
                    <Text style={{ fontSize: 10, fontWeight: "700", color: c.text }}>
                      {itemType.toUpperCase()}
                    </Text>
                  </View>
                </View>

                {preview && typeof preview === "string" && preview.length > 0 ? (
                  <Text style={{ fontSize: 12, color: c.textMuted, lineHeight: 18, marginBottom: t.spacing.sm + t.spacing.xs }} numberOfLines={3}>
                    {preview.slice(0, 150)}{preview.length > 150 ? "..." : ""}
                  </Text>
                ) : null}

                <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: t.spacing.sm, borderTopWidth: 1, borderTopColor: c.bgSecondary, paddingTop: t.spacing.sm + t.spacing.xs }}>
                  <Pressable
                    style={{
                      backgroundColor: c.primary,
                      borderRadius: t.radii.sm,
                      paddingVertical: 6,
                      paddingHorizontal: t.spacing.sm + t.spacing.xs,
                    }}
                  >
                    <Text style={{ color: "#FFFFFF", fontSize: 12, fontWeight: "600" }}>View</Text>
                  </Pressable>
                  <Pressable
                    style={{
                      backgroundColor: c.bgSecondary,
                      borderRadius: t.radii.sm,
                      paddingVertical: 6,
                      paddingHorizontal: t.spacing.sm + t.spacing.xs,
                    }}
                  >
                    <Text style={{ color: c.text, fontSize: 12, fontWeight: "600" }}>Re-run</Text>
                  </Pressable>
                  <Pressable
                    style={{
                      backgroundColor: c.primary + "14",
                      borderRadius: t.radii.sm,
                      paddingVertical: 6,
                      paddingHorizontal: t.spacing.sm + t.spacing.xs,
                    }}
                  >
                    <Text style={{ color: c.primary, fontSize: 12, fontWeight: "600" }}>Export</Text>
                  </Pressable>
                </View>
              </View>
            )
          })}
        </View>
      )}
    </ScrollView>
  )
}