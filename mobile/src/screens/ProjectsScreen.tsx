import React, { useEffect, useState } from "react"
import { View, Text, FlatList, Pressable, ActivityIndicator, TextInput, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getWorkspaces, createProject } from "../api/client"

interface ProjectItem {
  id: string
  name: string
  document_count?: number
  created_at?: string
  updated_at?: string
}

interface ProjectsScreenProps {
  onSelectProject: (proj: ProjectItem) => void
}

export function ProjectsScreen({ onSelectProject }: ProjectsScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [loading, setLoading] = useState(true)
  const [newProjectName, setNewProjectName] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    const loadProjects = async () => {
      try {
        setLoading(true)
        setError("")
        const res = await getWorkspaces()
        setProjects(res.projects || [])
      } catch (err: any) {
        setError(err.message || "Failed to load projects")
      } finally {
        setLoading(false)
      }
    }
    loadProjects()
  }, [])

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) { setError("Project name is required"); return }
    try {
      setError("")
      const newProj = await createProject({ name: newProjectName })
      setProjects([...projects, newProj])
      setNewProjectName("")
    } catch (err: any) {
      setError(err.message || "Failed to create project")
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm, color: c.textMuted }}>Loading projects...</Text>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm, backgroundColor: c.bg }}>
      <Text style={{ fontSize: 20, fontWeight: "700", color: c.text, marginBottom: t.spacing.md }}>📁 My Projects</Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <View style={{ marginBottom: t.spacing.md, gap: t.spacing.sm, flexDirection: isTablet ? "row" : "column" }}>
        <TextInput
          placeholder="New project name"
          value={newProjectName}
          onChangeText={setNewProjectName}
          style={{
            borderWidth: 1, borderColor: c.border, borderRadius: t.radii.md,
            paddingHorizontal: t.spacing.sm + 2, paddingVertical: 10, backgroundColor: c.inputBg, color: c.text, flex: isTablet ? 1 : undefined,
          }}
          placeholderTextColor={c.textMuted}
        />
        <Pressable
          onPress={handleCreateProject}
          style={{ backgroundColor: c.primary, borderRadius: t.radii.md, paddingVertical: t.spacing.sm + 2, alignItems: "center", paddingHorizontal: t.spacing.lg }}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 14 }}>Create Project</Text>
        </Pressable>
      </View>

      <FlatList
        data={projects}
        keyExtractor={(item) => item.id}
        numColumns={isTablet ? 2 : 1}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => onSelectProject(item)}
            style={{
              backgroundColor: c.cardBg, borderWidth: 1, borderColor: c.border,
              borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.sm,
              marginHorizontal: isTablet ? t.spacing.xs : 0,
            }}
          >
            <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: 4 }}>{item.name}</Text>
            {(item as any).description && <Text style={{ fontSize: 13, color: c.textMuted, marginBottom: t.spacing.sm }}>{(item as any).description}</Text>}
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ fontSize: 12, color: c.textMuted }}>{item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}</Text>
              <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, paddingHorizontal: t.spacing.sm, paddingVertical: 4 }}>
                <Text style={{ fontSize: 11, color: c.primary, fontWeight: "600" }}>{item.document_count ?? 0} docs</Text>
              </View>
            </View>
          </Pressable>
        )}
        scrollEnabled={true}
        ListEmptyComponent={
          <View style={{ alignItems: "center", paddingVertical: 40 }}>
            <Text style={{ color: c.textMuted, fontSize: 14 }}>No projects yet. Create one to get started!</Text>
          </View>
        }
      />
    </View>
  )
}
