import React, { useEffect, useState } from "react"
import { View, Text, FlatList, Pressable, ActivityIndicator, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface ProjectDocument {
  id: string
  name: string
  type?: string
  created_at?: string
  size?: number
}

interface Project {
  id: string
  name: string
  description?: string
  created_at?: string
  documents?: ProjectDocument[]
  document_count?: number
}

interface ProjectDetailScreenProps {
  project: Project
  onBack?: () => void
  onSelectDocument?: (documentId: string) => void
}

export function ProjectDetailScreen({ project, onBack, onSelectDocument }: ProjectDetailScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [loading, setLoading] = useState(false)
  const documents = project.documents || []
  const docCount = project.document_count || documents.length || 0

  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <View style={{ paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm, borderBottomWidth: 1, borderBottomColor: c.border, backgroundColor: c.cardBg }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.sm }}>
          <Text style={{ fontSize: 18, fontWeight: "700", color: c.text }}>📁 {project.name}</Text>
          {onBack && (
            <Pressable onPress={onBack}>
              <Text style={{ fontSize: 14, color: c.primary }}>← Back</Text>
            </Pressable>
          )}
        </View>

        {project.description && <Text style={{ fontSize: 13, color: c.textMuted, marginBottom: t.spacing.sm }}>{project.description}</Text>}

        <View style={{ backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, paddingHorizontal: t.spacing.sm + 2, paddingVertical: t.spacing.sm }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <View>
              <Text style={{ fontSize: 11, color: c.textMuted }}>Documents</Text>
              <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }}>{docCount}</Text>
            </View>
            {project.created_at && (
              <View style={{ alignItems: "flex-end" }}>
                <Text style={{ fontSize: 11, color: c.textMuted }}>Created</Text>
                <Text style={{ fontSize: 12, fontWeight: "600", color: c.text }}>{new Date(project.created_at).toLocaleDateString()}</Text>
              </View>
            )}
          </View>
        </View>
      </View>

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color={c.primary} />
          <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading documents...</Text>
        </View>
      ) : documents.length === 0 ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center", paddingHorizontal: t.spacing.md }}>
          <Text style={{ fontSize: 16, color: c.textMuted, textAlign: "center", marginBottom: t.spacing.md }}>No documents in this project yet</Text>
        </View>
      ) : (
        <FlatList
          data={documents}
          keyExtractor={(item) => item.id}
          numColumns={isTablet ? 2 : 1}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => onSelectDocument?.(item.id)}
              style={{
                backgroundColor: c.cardBg, borderBottomWidth: 1, borderBottomColor: c.border,
                paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm + 2,
                marginHorizontal: isTablet ? t.spacing.xs : 0,
              }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>📄 {item.name}</Text>
                  <View style={{ flexDirection: "row", gap: t.spacing.sm, marginTop: 6 }}>
                    {item.type && (
                      <View style={{ paddingHorizontal: t.spacing.sm, paddingVertical: 4, borderRadius: t.radii.sm, backgroundColor: c.primary + "14" }}>
                        <Text style={{ fontSize: 11, color: c.primary }}>{item.type}</Text>
                      </View>
                    )}
                    {item.created_at && <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 4 }}>{new Date(item.created_at).toLocaleDateString()}</Text>}
                  </View>
                </View>
                <Pressable
                  onPress={() => onSelectDocument?.(item.id)}
                  style={{ paddingHorizontal: t.spacing.sm, paddingVertical: t.spacing.xs + 2, borderRadius: t.radii.sm, backgroundColor: c.primary, marginLeft: t.spacing.sm }}
                >
                  <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 12 }}>View</Text>
                </Pressable>
              </View>
            </Pressable>
          )}
          contentContainerStyle={{ paddingTop: t.spacing.sm }}
        />
      )}
    </View>
  )
}
