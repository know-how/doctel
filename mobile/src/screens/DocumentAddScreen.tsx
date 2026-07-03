import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, Platform, useWindowDimensions } from "react-native"
import * as DocumentPicker from "expo-document-picker"
import DateTimePicker from "@react-native-community/datetimepicker"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { uploadDocument, getWorkspaces } from "../api/client"

interface DocumentAddScreenProps {
  onUploaded?: (documentId: string) => void
}

export function DocumentAddScreen({ onUploaded }: DocumentAddScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [projects, setProjects] = useState<any[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string>("")
  const [documentType, setDocumentType] = useState("")
  const [documentDate, setDocumentDate] = useState("")
  const [fileName, setFileName] = useState("")
  const [fileUri, setFileUri] = useState("")
  const [fileType, setFileType] = useState("")
  const [uploading, setUploading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [uploadedDocId, setUploadedDocId] = useState("")
  const [error, setError] = useState("")
  const [showDatePicker, setShowDatePicker] = useState(false)
  const [loadingProjects, setLoadingProjects] = useState(true)

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      setLoadingProjects(true)
      const res = await getWorkspaces()
      setProjects(res?.projects || [])
    } catch (e: any) {
      console.warn("Failed to load projects", e)
    } finally {
      setLoadingProjects(false)
    }
  }

  const pickFile = async () => {
    setError("")
    setSuccess(false)
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "audio/wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "audio/webm",
        "audio/flac",
        "video/mp4",
        "video/avi",
        "video/quicktime",
      ],
      copyToCacheDirectory: true,
    })
    if (result.canceled) return
    const asset = result.assets[0]
    setFileName(asset.name ?? "document")
    setFileUri(asset.uri)
    setFileType(asset.mimeType ?? "application/octet-stream")
  }

  const handleUpload = async () => {
    if (!fileUri) {
      setError("Please select a file first")
      return
    }
    try {
      setUploading(true)
      setError("")
      setSuccess(false)
      if (!selectedProjectId) {
        setError("Please select a project / workspace before uploading.")
        setUploading(false)
        return
      }
      const res = await uploadDocument(fileUri, fileName, fileType, {
        project_id: selectedProjectId,
        document_type: documentType || null,
        document_date: documentDate || null,
      })
      setSuccess(true)
      setUploadedDocId(res.id)
      onUploaded?.(res.id)
    } catch (err: any) {
      const msg = err?.message ?? err?.data?.detail ?? err?.data?.error ?? ""
      if (msg.includes("400") || msg.toLowerCase().includes("unsupported")) {
        setError("Unsupported file type. Please use PDF, DOCX, TXT, PNG, or JPG.")
      } else if (msg.includes("413") || msg.toLowerCase().includes("too large")) {
        setError("File is too large. Maximum size is 64 MB.")
      } else if (msg.includes("Network") || msg.includes("network") || msg.includes("fetch")) {
        setError("Network error. Please check your connection and try again.")
      } else {
        setError(msg || "Upload failed. Please try again.")
      }
    } finally {
      setUploading(false)
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl, maxWidth: isTablet ? 600 : undefined, alignSelf: "center" }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Add Document
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28", flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <Text style={{ color: c.error, fontSize: 13, flex: 1 }}>{error}</Text>
          <Pressable onPress={() => { setError(""); handleUpload() }} style={{ marginLeft: t.spacing.sm }}>
            <Text style={{ color: c.primary, fontWeight: "600", fontSize: 13 }}>Retry</Text>
          </Pressable>
        </View>
      ) : null}

      {success ? (
        <View style={{ backgroundColor: c.success + "18", borderRadius: t.radii.sm, padding: t.spacing.lg, alignItems: "center", marginBottom: t.spacing.lg, borderWidth: 1, borderColor: c.success + "28" }}>
          <Text style={{ fontSize: 40, marginBottom: t.spacing.sm }}>✅</Text>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.success, marginBottom: t.spacing.sm }}>
            Upload successful!
          </Text>
          <Pressable
            onPress={() => onUploaded?.(uploadedDocId)}
            style={{
              backgroundColor: c.primary,
              borderRadius: t.radii.sm,
              paddingVertical: 10,
              paddingHorizontal: t.spacing.lg,
            }}
          >
            <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 14 }}>Open Document</Text>
          </Pressable>
        </View>
      ) : null}

      <Pressable
        onPress={pickFile}
        style={{
          borderWidth: 2,
          borderStyle: "dashed",
          borderColor: c.primary,
          borderRadius: t.radii.lg,
          padding: t.spacing.xl,
          alignItems: "center",
          marginBottom: t.spacing.lg,
          backgroundColor: c.primary + "14",
        }}
      >
        {fileUri ? (
          <>
            <Text style={{ fontSize: 32, marginBottom: t.spacing.sm }}>📄</Text>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.text }}>{fileName}</Text>
            <Text style={{ fontSize: 12, color: c.textMuted, marginTop: t.spacing.xs }}>Tap to change file</Text>
          </>
        ) : (
          <>
            <Text style={{ fontSize: 32, marginBottom: t.spacing.sm }}>⬆️</Text>
            <Text style={{ fontSize: 14, fontWeight: "600", color: c.primary }}>Tap to select a document</Text>
            <Text style={{ fontSize: 12, color: c.textMuted, marginTop: t.spacing.xs }}>PDF, Word, Excel, TXT supported</Text>
          </>
        )}
      </Pressable>

      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
        Project / Workspace
      </Text>
      {loadingProjects ? (
        <ActivityIndicator size="small" color={c.primary} style={{ marginBottom: t.spacing.sm }} />
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: t.spacing.lg }}>
          <Pressable
            onPress={() => setSelectedProjectId("")}
            style={{
              paddingHorizontal: 14,
              paddingVertical: t.spacing.xs,
              borderRadius: t.radii.full,
              backgroundColor: !selectedProjectId ? c.primary : c.bgSecondary,
              marginRight: t.spacing.xs,
            }}
          >
            <Text style={{ color: !selectedProjectId ? "#FFFFFF" : c.text, fontSize: 13, fontWeight: "600" }}>
              None
            </Text>
          </Pressable>
          {projects.map((proj) => (
            <Pressable
              key={proj.id}
              onPress={() => setSelectedProjectId(proj.id)}
              style={{
                paddingHorizontal: 14,
                paddingVertical: t.spacing.xs,
                borderRadius: t.radii.full,
                backgroundColor: selectedProjectId === proj.id ? c.primary : c.bgSecondary,
                marginRight: t.spacing.xs,
              }}
            >
              <Text style={{ color: selectedProjectId === proj.id ? "#FFFFFF" : c.text, fontSize: 13, fontWeight: "600" }}>
                {proj.name}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
        Document Type
      </Text>
      <TextInput
        placeholder="e.g. Report, Contract, Policy"
        value={documentType}
        onChangeText={setDocumentType}
        placeholderTextColor={c.textMuted}
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.sm,
          padding: t.spacing.sm,
          borderWidth: 1,
          borderColor: c.border,
          color: c.text,
          marginBottom: t.spacing.lg,
        }}
      />

      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
        Document Date
      </Text>
      <Pressable
        onPress={() => setShowDatePicker(true)}
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.sm,
          padding: t.spacing.sm,
          borderWidth: 1,
          borderColor: c.border,
          marginBottom: 20,
        }}
      >
        <Text style={{ color: documentDate ? c.text : c.textMuted, fontSize: 14 }}>
          {documentDate || "Select a date"}
        </Text>
      </Pressable>
      {showDatePicker && (
        <DateTimePicker
          value={documentDate ? new Date(documentDate) : new Date()}
          mode="date"
          display={Platform.OS === "ios" ? "spinner" : "default"}
          onChange={(event, selectedDate) => {
            setShowDatePicker(Platform.OS === "ios")
            if (event.type === "set" && selectedDate) {
              const yyyy = selectedDate.getFullYear()
              const mm = String(selectedDate.getMonth() + 1).padStart(2, "0")
              const dd = String(selectedDate.getDate()).padStart(2, "0")
              setDocumentDate(`${yyyy}-${mm}-${dd}`)
            }
          }}
        />
      )}

      <Pressable
        onPress={handleUpload}
        disabled={uploading || !fileUri}
        style={{
          backgroundColor: uploading || !fileUri ? c.textMuted : c.primary,
          borderRadius: t.radii.sm,
          paddingVertical: 14,
          alignItems: "center",
          flexDirection: "row",
          justifyContent: "center",
          gap: t.spacing.xs,
        }}
      >
        {uploading ? (
          <ActivityIndicator size="small" color="#FFFFFF" />
        ) : (
          <Text style={{ fontSize: 16 }}>⬆️</Text>
        )}
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>
          {uploading ? "Uploading..." : "Upload Document"}
        </Text>
      </Pressable>
    </ScrollView>
  )
}