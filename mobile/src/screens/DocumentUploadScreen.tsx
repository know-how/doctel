import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator } from "react-native"
import * as DocumentPicker from "expo-document-picker"
import { colors } from "../theme/colors"
import { uploadDocument, getProjects } from "../api/client"
import { ProjectSummary } from "../types/api"

interface DocumentUploadScreenProps {
  onUploaded?: (documentId: string) => void
}

export const DocumentUploadScreen: React.FC<DocumentUploadScreenProps> = ({
  onUploaded,
}) => {
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
        const res = await getProjects()
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
      setError("Project name is required")
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

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 16, paddingBottom: 24 }}>
      <Text style={{ fontSize: 18, fontWeight: "600", color: colors.textPrimary }}>
        Upload Document
      </Text>

      <View style={{ gap: 8 }}>
        <Text style={{ fontSize: 13, color: colors.textMuted }}>Project</Text>
        {loadingProjects ? (
          <ActivityIndicator size="small" color={colors.primary} style={{ alignSelf: "flex-start" }} />
        ) : (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            <Pressable
              style={[chipStyle, selectedProjectId === "" && chipActiveStyle]}
              onPress={() => {
                setSelectedProjectId("")
                setProjectName("")
              }}
            >
              <Text style={[chipText, selectedProjectId === "" && chipActiveText]}>
                No project
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
                New project...
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {selectedProjectId === "new" && (
        <View style={{ gap: 8 }}>
          <Text style={{ fontSize: 13, color: colors.textMuted }}>New Project Name</Text>
          <TextInput
            value={projectName}
            onChangeText={setProjectName}
            placeholder="Project Name"
            style={inputStyle}
          />
        </View>
      )}

      <View style={{ gap: 8 }}>
        <Text style={{ fontSize: 13, color: colors.textMuted }}>Document Type</Text>
        <TextInput
          value={documentType}
          onChangeText={setDocumentType}
          placeholder="Document Type"
          style={inputStyle}
        />
      </View>

      <View style={{ gap: 8 }}>
        <Text style={{ fontSize: 13, color: colors.textMuted }}>Document Date</Text>
        <TextInput
          value={documentDate}
          onChangeText={setDocumentDate}
          placeholder="YYYY-MM-DD"
          style={inputStyle}
        />
      </View>

      <Pressable onPress={pickFile} style={secondaryButtonStyle}>
        <Text style={{ color: colors.primaryDark, fontWeight: "500" }}>Select File</Text>
        <Text style={{ color: colors.textMuted, fontSize: 12, marginTop: 4 }}>
          PDF, DOCX, TXT
        </Text>
      </Pressable>

      {!!fileName && (
        <Text style={{ fontSize: 12, color: colors.primary }}>
          Selected: {fileName}
        </Text>
      )}

      {error ? <Text style={{ color: colors.danger }}>{error}</Text> : null}
      {status ? <Text style={{ color: colors.primary }}>{status}</Text> : null}

      <Pressable onPress={submit} style={[primaryButtonStyle, loading && { opacity: 0.7 }]} disabled={loading}>
        <Text style={{ color: "#FFFFFF", fontWeight: "600" }}>
          {loading ? "Uploading..." : "Upload Document"}
        </Text>
      </Pressable>
    </ScrollView>
  )
}

const inputStyle = {
  borderWidth: 1,
  borderColor: colors.border,
  borderRadius: 10,
  paddingHorizontal: 12,
  paddingVertical: 10,
  backgroundColor: "#FFFFFF",
} as const

const primaryButtonStyle = {
  backgroundColor: colors.primary,
  paddingVertical: 14,
  borderRadius: 999,
  alignItems: "center",
  marginTop: 8,
} as const

const secondaryButtonStyle = {
  backgroundColor: "#E7F0FF",
  borderWidth: 1,
  borderColor: colors.primary,
  paddingVertical: 16,
  borderRadius: 10,
  alignItems: "center",
  marginTop: 8,
} as const

const chipStyle = {
  paddingHorizontal: 12,
  paddingVertical: 6,
  borderRadius: 16,
  borderWidth: 1,
  borderColor: colors.border,
  backgroundColor: "#FFFFFF",
} as const

const chipActiveStyle = {
  backgroundColor: "#E7F0FF",
  borderColor: colors.primary,
} as const

const chipText = {
  color: colors.textPrimary,
  fontSize: 13,
} as const

const chipActiveText = {
  color: colors.primaryDark,
  fontWeight: "600",
} as const
