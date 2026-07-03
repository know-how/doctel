import React, { useEffect, useRef, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, Animated, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getWorkspaces, createProject } from "../api/client"

interface WorkspacesScreenProps {
  onSelectProject: (proj: any) => void
}

function SkeletonCard() {
  const { theme } = useTheme()
  const t = getTokens(theme)
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
        backgroundColor: t.colors.bgSecondary,
        borderRadius: t.radii.md,
        padding: t.spacing.md,
        marginBottom: t.spacing.sm,
        height: 80,
      }}
    />
  )
}

export function WorkspacesScreen({ onSelectProject }: WorkspacesScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [projects, setProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [newProjectName, setNewProjectName] = useState("")
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => { loadProjects() }, [])

  const loadProjects = async () => {
    try {
      setLoading(true)
      setError("")
      const res = await getWorkspaces()
      setProjects(res?.projects || res?.workspaces || [])
    } catch (err: any) {
      setError(err.message || "Failed to load workspaces")
    } finally {
      setLoading(false)
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) { setError("Project name is required"); return }
    try {
      setCreating(true)
      setError("")
      const newProj = await createProject({ name: newProjectName.trim() })
      setProjects((prev) => [...prev, newProj])
      setNewProjectName("")
    } catch (err: any) {
      setError(err.message || "Failed to create workspace")
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return (
      <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md }}>
        <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>Workspaces</Text>
        {Array.from({ length: 3 }).map((_, i) => (<SkeletonCard key={i} />))}
      </ScrollView>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: t.spacing.md, paddingBottom: t.spacing.xxl, maxWidth: isTablet ? 960 : undefined, alignSelf: "center", width: "100%" }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Workspaces
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <View style={{ marginBottom: t.spacing.md, flexDirection: isTablet ? "row" : "column", gap: t.spacing.sm }}>
        <TextInput
          placeholder="New workspace name"
          value={newProjectName}
          onChangeText={setNewProjectName}
          placeholderTextColor={c.textMuted}
          style={{
            backgroundColor: c.inputBg,
            borderRadius: t.radii.md,
            padding: t.spacing.sm + 2,
            borderWidth: 1,
            borderColor: c.border,
            color: c.text,
            marginBottom: isTablet ? 0 : t.spacing.sm,
            flex: isTablet ? 1 : undefined,
          }}
        />
        <Pressable
          onPress={handleCreateProject}
          disabled={creating}
          style={{
            backgroundColor: creating ? c.textMuted : c.primary,
            borderRadius: t.radii.md,
            paddingVertical: t.spacing.sm + 2,
            paddingHorizontal: t.spacing.lg,
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 14 }}>
            {creating ? "Creating..." : "Create Workspace"}
          </Text>
        </Pressable>
      </View>

      {projects.length === 0 ? (
        <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xxl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>📁</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: 4 }}>No workspaces yet</Text>
          <Text style={{ fontSize: 13, color: c.textMuted, textAlign: "center" }}>Create a workspace to organize your documents</Text>
        </View>
      ) : (
        <View style={{ flexDirection: isTablet ? "row" : "column", flexWrap: "wrap", gap: t.spacing.sm }}>
          {projects.map((proj) => (
            <Pressable
              key={proj.id}
              onPress={() => onSelectProject(proj)}
              style={{
                backgroundColor: c.cardBg,
                borderRadius: t.radii.md,
                padding: t.spacing.md,
                borderWidth: 1,
                borderColor: c.border,
                width: isTablet ? "48%" : "100%",
                marginBottom: isTablet ? 0 : t.spacing.sm,
              }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: 4 }}>{proj.name}</Text>
                  {proj.description ? (<Text style={{ fontSize: 13, color: c.textMuted, marginBottom: t.spacing.sm }}>{proj.description}</Text>) : null}
                  <Text style={{ fontSize: 12, color: c.textMuted }}>Last activity: {proj.updated_at ? new Date(proj.updated_at).toLocaleDateString() : "N/A"}</Text>
                </View>
                <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, paddingHorizontal: t.spacing.sm, paddingVertical: 4 }}>
                  <Text style={{ fontSize: 11, color: c.primary, fontWeight: "600" }}>{proj.document_count ?? proj.document_ids?.length ?? 0} docs</Text>
                </View>
              </View>
            </Pressable>
          ))}
        </View>
      )}
    </ScrollView>
  )
}
