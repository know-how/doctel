import React, { useEffect, useRef, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, Animated, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getDocumentLibrary, getWorkspaces } from "../api/client"
import { MyDocument } from "../types/api"

interface DocumentLibraryScreenProps {
  onSelectDocument: (doc: MyDocument) => void
  initialProjectId?: string | null
}

const fileIcons: Record<string, string> = {
  pdf: "📄",
  docx: "📝",
  txt: "📃",
  csv: "📊",
  xlsx: "📈",
  pptx: "📽️",
  default: "📎",
}

function getFileIcon(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() || ""
  return fileIcons[ext] || fileIcons.default
}

function SkeletonCard() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const opacity = useRef(new Animated.Value(0.4)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 600, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 600, useNativeDriver: true }),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [])
  return (
    <Animated.View
      style={{
        opacity,
        backgroundColor: c.bgSecondary,
        borderRadius: t.radii.sm,
        padding: t.spacing.sm,
        marginBottom: t.spacing.sm,
        height: 90,
      }}
    />
  )
}

export function DocumentLibraryScreen({ onSelectDocument, initialProjectId }: DocumentLibraryScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [documents, setDocuments] = useState<MyDocument[]>([])
  const [projects, setProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [searchText, setSearchText] = useState("")
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [page, setPage] = useState(1)
  const [totalDocs, setTotalDocs] = useState(0)
  const pageSize = 20

  const statusColors: Record<string, string> = {
    ready: c.primary + "14",
    processing: c.warning + "18",
    completed: c.success + "18",
    failed: c.error + "14",
  }

  const statusTextColors: Record<string, string> = {
    ready: c.primary,
    processing: c.warning,
    completed: c.success,
    failed: c.error,
  }

  useEffect(() => {
    loadData()
  }, [page])

  useEffect(() => {
    if (initialProjectId) setSelectedProject(initialProjectId)
  }, [initialProjectId])

  const loadData = async () => {
    try {
      setLoading(true)
      setError("")
      const [docsRes, projRes] = await Promise.all([
        getDocumentLibrary({ page: String(page), page_size: String(pageSize) }),
        getWorkspaces(),
      ])
      setDocuments(docsRes?.documents || [])
      setTotalDocs(docsRes?.total || (docsRes?.documents || []).length)
      setProjects(projRes?.projects || [])
    } catch (err: any) {
      setError(err.message || "Failed to load documents")
    } finally {
      setLoading(false)
    }
  }

  const filteredDocuments = documents.filter((doc) => {
    if (searchText.trim() && !doc.filename.toLowerCase().includes(searchText.toLowerCase())) return false
    if (selectedProject && doc.project_id !== selectedProject) return false
    if (statusFilter && doc.status !== statusFilter) return false
    return true
  })

  if (loading) {
    return (
      <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md }}>
        <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
          Document Library
        </Text>
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </ScrollView>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Document Library
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <TextInput
        placeholder="Search documents..."
        value={searchText}
        onChangeText={setSearchText}
        placeholderTextColor={c.textMuted}
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.sm,
          padding: t.spacing.sm,
          borderWidth: 1,
          borderColor: c.border,
          color: c.text,
          marginBottom: t.spacing.sm,
        }}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: t.spacing.md, gap: t.spacing.xs }}>
        {projects.map((proj) => (
          <Pressable
            key={proj.id}
            onPress={() => setSelectedProject(selectedProject === proj.id ? null : proj.id)}
            style={{
              paddingHorizontal: 14,
              paddingVertical: 7,
              borderRadius: t.radii.full,
              backgroundColor: selectedProject === proj.id ? c.primary : c.bgSecondary,
              marginRight: t.spacing.xs,
            }}
          >
            <Text style={{ color: selectedProject === proj.id ? "#FFFFFF" : c.text, fontSize: 13, fontWeight: "600" }}>
              {proj.name}
            </Text>
          </Pressable>
        ))}
        <Pressable
          onPress={() => setSelectedProject(null)}
          style={{
            paddingHorizontal: 14,
            paddingVertical: 7,
            borderRadius: t.radii.full,
            backgroundColor: !selectedProject ? c.primary : c.bgSecondary,
            marginRight: t.spacing.xs,
          }}
        >
          <Text style={{ color: !selectedProject ? "#FFFFFF" : c.text, fontSize: 13, fontWeight: "600" }}>
            All
          </Text>
        </Pressable>
      </ScrollView>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: t.spacing.md, gap: t.spacing.xs }}>
        {["ready", "processing", "completed", "failed"].map((status) => (
          <Pressable
            key={status}
            onPress={() => setStatusFilter(statusFilter === status ? null : status)}
            style={{
              paddingHorizontal: 14,
              paddingVertical: 5,
              borderRadius: t.radii.full,
              backgroundColor: statusFilter === status ? (statusColors[status] || c.bgSecondary) : c.bgSecondary,
              borderWidth: 1,
              borderColor: statusFilter === status ? (statusTextColors[status] || c.primary) : "transparent",
              marginRight: t.spacing.xs,
            }}
          >
            <Text style={{ color: statusFilter === status ? (statusTextColors[status] || c.primary) : c.textMuted, fontSize: 12, fontWeight: "600" }}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      {filteredDocuments.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.sm, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>📭</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
            No documents found
          </Text>
          <Text style={{ fontSize: 13, color: c.textMuted, textAlign: "center" }}>
            Upload documents to get started with AI analysis
          </Text>
        </View>
      ) : (
        <View style={{ flexDirection: isTablet ? "row" : "column", flexWrap: isTablet ? "wrap" : undefined, gap: t.spacing.sm }}>
          {filteredDocuments.map((doc) => (
            <View
              key={doc.id}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: t.radii.sm,
                padding: t.spacing.sm,
                marginBottom: isTablet ? 0 : 10,
                width: isTablet ? "48%" : "100%",
                borderWidth: 1,
                borderColor: c.border,
              }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
                <View style={{ flex: 1, flexDirection: "row", alignItems: "flex-start", gap: t.spacing.xs }}>
                  <Text style={{ fontSize: 24, marginTop: 2 }}>{getFileIcon(doc.filename)}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
                      {doc.filename}
                    </Text>
                    <Text style={{ fontSize: 12, color: c.textMuted, marginBottom: t.spacing.xs }}>
                      {doc.project_name || "Uncategorized"}
                    </Text>
                    <Text style={{ fontSize: 11, color: c.textMuted }}>
                      {new Date(doc.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                </View>
                <View
                  style={{
                    backgroundColor: statusColors[doc.status] || c.primary + "14",
                    borderRadius: t.radii.sm,
                    paddingHorizontal: t.spacing.sm,
                    paddingVertical: 3,
                  }}
                >
                  <Text style={{ fontSize: 11, color: statusTextColors[doc.status] || c.primary, fontWeight: "600" }}>
                    {doc.status || "ready"}
                  </Text>
                </View>
              </View>
              <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: t.spacing.xs, marginTop: t.spacing.sm, borderTopWidth: 1, borderTopColor: c.bgSecondary, paddingTop: t.spacing.sm }}>
                <Pressable
                  onPress={() => onSelectDocument(doc)}
                  style={{
                    backgroundColor: c.primary,
                    borderRadius: t.radii.sm,
                    paddingVertical: t.spacing.xs,
                    paddingHorizontal: 14,
                  }}
                >
                  <Text style={{ color: "#FFFFFF", fontSize: 12, fontWeight: "600" }}>Open</Text>
                </Pressable>
                <Pressable
                  style={{
                    backgroundColor: c.bgSecondary,
                    borderRadius: t.radii.sm,
                    paddingVertical: t.spacing.xs,
                    paddingHorizontal: 14,
                  }}
                >
                  <Text style={{ color: c.text, fontSize: 12, fontWeight: "600" }}>Download</Text>
                </Pressable>
                <Pressable
                  style={{
                    backgroundColor: c.error + "14",
                    borderRadius: t.radii.sm,
                    paddingVertical: t.spacing.xs,
                    paddingHorizontal: 14,
                  }}
                >
                  <Text style={{ color: c.error, fontSize: 12, fontWeight: "600" }}>Delete</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </View>
      )}
      {Math.ceil(totalDocs / pageSize) > 1 && (
        <View style={{ flexDirection: "row", justifyContent: "center", alignItems: "center", gap: t.spacing.sm, paddingVertical: t.spacing.md }}>
          <Pressable
            onPress={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{ opacity: page <= 1 ? 0.4 : 1, backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, paddingHorizontal: t.spacing.lg, paddingVertical: t.spacing.sm }}
          >
            <Text style={{ color: c.text, fontSize: 13 }}>← Prev</Text>
          </Pressable>
          <Text style={{ color: c.textMuted, fontSize: 13 }}>{page} / {Math.ceil(totalDocs / pageSize)}</Text>
          <Pressable
            onPress={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(totalDocs / pageSize)}
            style={{ opacity: page >= Math.ceil(totalDocs / pageSize) ? 0.4 : 1, backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, paddingHorizontal: t.spacing.lg, paddingVertical: t.spacing.sm }}
          >
            <Text style={{ color: c.text, fontSize: 13 }}>Next →</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  )
}