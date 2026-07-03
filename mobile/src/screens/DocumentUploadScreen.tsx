import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import * as DocumentPicker from "expo-document-picker"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { uploadDocument, getWorkspaces } from "../api/client"
import { ProjectSummary } from "../types/api"

interface DocumentUploadScreenProps {
  onUploaded?: (documentId: string) => void
}

export function DocumentUploadScreen({ onUploaded }: DocumentUploadScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string>("")
  const [projectName, setProjectName] = useState("")
  const [documentType, setDocumentType] = useState("")
  const [documentDate, setDocumentDate] = useState("")
  const [fileName, setFileName] = useState("")
  const [fileUri, setFileUri] = useState("")
  const [fileType, setFileType] = useState("")
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [loadingProjects, setLoadingProjects] = useState(true)

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await getWorkspaces()
        setProjects(res.projects)
      } catch (e: any) {
        console.warn("Failed to load projects", e)
      } finally {
        setLoadingProjects(false)
      }
    }
    fetchProjects()
  }, [])

  const pickFile = async () => {
    setError("")
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
      ],
      copyToCacheDirectory: true,
    })
    if (result.canceled) {
      return
    }
    const asset = result.assets[0]
    setFileName(asset.name ?? "document")
    setFileUri(asset.uri)
    setFileType(asset.mimeType ?? "application/octet-stream")
  }

  const submit = async () => {
    if (!fileUri) {
      setError("Please select a file to upload.")
      return
    }
    setLoading(true)
    setError("")
    setStatus("")

    const resolvedProjectName =
      selectedProjectId === "new"
        ? projectName.trim() || undefined
        : selectedProjectId
          ? projects.find((p) => p.id === selectedProjectId)?.name
          : undefined

    if (selectedProjectId === "new" && !resolvedProjectName) {
      setError("Repository name is required")
      setLoading(false)
      return
    }

    try {
      const response = await uploadDocument(fileUri, fileName, fileType, {
        project_name: resolvedProjectName,
        document_type: documentType || undefined,
        document_date: documentDate || undefined,
      })
      setStatus(`Uploaded ${response.filename} (${response.id})`)
      if (onUploaded) {
        onUploaded(response.id)
      }
    } catch (e: any) {
      setError(e.message ?? "Upload failed.")
    } finally {
      setLoading(false)
    }
  }

  const chipStyle = {
    paddingHorizontal: t.spacing.sm,
    paddingVertical: 6,
    borderRadius: t.radii.lg,
    borderWidth: 1,
    borderColor: c.border,
    backgroundColor: c.cardBg,
  }

  const chipActiveStyle = {
    backgroundColor: c.primary + "14",
    borderColor: c.primary,
  }

  const chipText = {
    color: c.text,
    fontSize: 13,
  }

  const chipActiveText = {
    color: c.primaryHover,
    fontWeight: "600" as const,
  }

  const inputStyle = {
    borderWidth: 1,
    borderColor: c.border,
    borderRadius: t.radii.md,
    paddingHorizontal: t.spacing.sm,
    paddingVertical: 10,
    backgroundColor: c.cardBg,
  }

  const primaryButtonStyle = {
    backgroundColor: c.primary,
    paddingVertical: 14,
    borderRadius: t.radii.full,
    alignItems: "center" as const,
    marginTop: t.spacing.xs,
  }

  const secondaryButtonStyle = {
    backgroundColor: c.primary + "14",
    borderWidth: 1,
    borderColor: c.primary,
    paddingVertical: t.spacing.lg,
    borderRadius: t.radii.md,
    alignItems: "center" as const,
    marginTop: t.spacing.xs,
  }

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: t.spacing.md, paddingBottom: t.spacing.lg, padding: isTablet ? t.spacing.lg : t.spacing.md, maxWidth: isTablet ? 600 : undefined, alignSelf: "center" }}>
      <Text style={{ fontSize: 18, fontWeight: "600", color: c.text }}>
        Upload Document
      </Text>

      <View style={{ gap: t.spacing.xs }}>
        <Text style={{ fontSize: 13, color: c.textMuted }}>Repository</Text>
        {loadingProjects ? (
          <ActivityIndicator size="small" color={c.primary} style={{ alignSelf: "flex-start" }} />
        ) : (
          <View style={{ flexDirection: isTablet ? "row" : "row", flexWrap: "wrap", gap: t.spacing.xs }}>
            <Pressable
              style={[chipStyle, selectedProjectId === "" && chipActiveStyle]}
              onPress={() => {
                setSelectedProjectId("")
                setProjectName("")
              }}
            >
              <Text style={[chipText, selectedProjectId === "" && chipActiveText]}>
                No repository
              </Text>
            </Pressable>
            {projects.map((project) => (
              <Pressable
                key={project.id}
                style={[chipStyle, selectedProjectId === project.id && chipActiveStyle]}
                onPress={() => setSelectedProjectId(project.id)}
              >
                <Text style={[chipText, selectedProjectId === project.id && chipActiveText]}>
                  {project.name}
                </Text>
              </Pressable>
            ))}
            <Pressable
              style={[chipStyle, selectedProjectId === "new" && chipActiveStyle]}
              onPress={() => setSelectedProjectId("new")}
            >
              <Text style={[chipText, selectedProjectId === "new" && chipActiveText]}>
                New repository...
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {selectedProjectId === "new" && (
        <View style={{ gap: t.spacing.xs }}>
          <Text style={{ fontSize: 13, color: c.textMuted }}>New Repository Name</Text>
          <TextInput
            value={projectName}
            onChangeText={setProjectName}
            placeholder="Repository Name"
            placeholderTextColor={c.textMuted}
            style={inputStyle}
          />
        </View>
      )}

      <View style={{ gap: t.spacing.xs }}>
        <Text style={{ fontSize: 13, color: c.textMuted }}>Document Type</Text>
        <TextInput
          value={documentType}
          onChangeText={setDocumentType}
          placeholder="Document Type"
          placeholderTextColor={c.textMuted}
          style={inputStyle}
        />
      </View>

      <View style={{ gap: t.spacing.xs }}>
        <Text style={{ fontSize: 13, color: c.textMuted }}>Document Date</Text>
        <TextInput
          value={documentDate}
          onChangeText={setDocumentDate}
          placeholder="YYYY-MM-DD"
          placeholderTextColor={c.textMuted}
          style={inputStyle}
        />
      </View>

      <Pressable onPress={pickFile} style={secondaryButtonStyle}>
        <Text style={{ color: c.primaryHover, fontWeight: "500" }}>Select File</Text>
        <Text style={{ color: c.textMuted, fontSize: 12, marginTop: t.spacing.xs }}>
          PDF, DOCX, TXT
        </Text>
      </Pressable>

      {!!fileName && (
        <Text style={{ fontSize: 12, color: c.primary }}>
          Selected: {fileName}
        </Text>
      )}

      {error ? <Text style={{ color: c.error }}>{error}</Text> : null}
      {status ? <Text style={{ color: c.primary }}>{status}</Text> : null}

      <Pressable onPress={submit} style={[primaryButtonStyle, loading && { opacity: 0.7 }]} disabled={loading}>
        <Text style={{ color: "#FFFFFF", fontWeight: "600" }}>
          {loading ? "Uploading..." : "Upload Document"}
        </Text>
      </Pressable>
    </ScrollView>
  )
}