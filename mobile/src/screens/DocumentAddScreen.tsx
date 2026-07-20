import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions, Platform } from "react-native"
import * as DocumentPicker from "expo-document-picker"
import DateTimePicker from "@react-native-community/datetimepicker"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { uploadDocument, getWorkspaces, createProject } from "../api/client"

type ContentCategory = "document" | "image" | "audio" | "video"

const CATEGORY_CONFIG: Record<ContentCategory, { label: string; icon: string; types: string[]; description: string }> = {
  document: {
    label: "Document",
    icon: "📄",
    types: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"],
    description: "PDF, Word, TXT",
  },
  image: {
    label: "Image",
    icon: "🖼️",
    types: ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"],
    description: "PNG, JPG, WebP, GIF",
  },
  audio: {
    label: "Audio",
    icon: "🎙️",
    types: ["audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg", "audio/webm", "audio/flac", "audio/x-m4a"],
    description: "WAV, MP3, M4A, OGG",
  },
  video: {
    label: "Video",
    icon: "🎬",
    types: ["video/mp4", "video/avi", "video/quicktime"],
    description: "MP4, AVI, MOV",
  },
}

interface FileEntry {
  uri: string
  name: string
  mimeType: string
  id: string
  size: number
}

interface DocumentAddScreenProps {
  onUploaded?: (documentId: string) => void
}

type UploadState = "idle" | "uploading" | "success" | "error"

export function DocumentAddScreen({ onUploaded }: DocumentAddScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768
  const isDark = theme === "dark"

  const [workspaces, setWorkspaces] = useState<any[]>([])
  const [files, setFiles] = useState<FileEntry[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState("")
  const [newWorkspaceName, setNewWorkspaceName] = useState("")
  const [workspaceMode, setWorkspaceMode] = useState<"existing" | "new">("existing")
  const [documentType, setDocumentType] = useState("")
  const [documentDate, setDocumentDate] = useState("")
  const [isPublic, setIsPublic] = useState(false)
  const [uploadState, setUploadState] = useState<UploadState>("idle")
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState("")
  const [uploadedIds, setUploadedIds] = useState<string[]>([])
  const [contentCategory, setContentCategory] = useState<ContentCategory>("document")
  const [showDatePicker, setShowDatePicker] = useState(false)
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(true)

  useEffect(() => {
    loadWorkspaces()
  }, [])

  const loadWorkspaces = async () => {
    try {
      setLoadingWorkspaces(true)
      const res = await getWorkspaces()
      setWorkspaces(res?.projects || res?.workspaces || [])
    } catch {
      // ignore
    } finally {
      setLoadingWorkspaces(false)
    }
  }

  const pickFiles = async () => {
    try {
      setError("")
      setUploadState("idle")
      const result = await DocumentPicker.getDocumentAsync({
        type: CATEGORY_CONFIG[contentCategory].types,
        copyToCacheDirectory: true,
        multiple: true,
      })
      if (result.canceled) return
      const newFiles = (result.assets || []).map((asset) => ({
        uri: asset.uri,
        name: asset.name || "file",
        mimeType: asset.mimeType || "application/octet-stream",
        id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        size: asset.size || 0,
      }))
      setFiles((prev) => [...prev, ...newFiles])
    } catch {
      setError("Failed to pick file")
    }
  }

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setError("Please select at least one file")
      return
    }

    setUploadState("uploading")
    setProgress(0)
    setError("")
    const uploaded: string[] = []

    try {
      const effectiveProjectId = workspaceMode === "new" ? null : selectedProjectId
      const effectiveProjectName = workspaceMode === "new" ? newWorkspaceName.trim() || "Uncategorized"
        : selectedProjectId ? null : "Uncategorized"

      // Create workspace if needed
      if (workspaceMode === "new" && newWorkspaceName.trim()) {
        try {
          const proj = await createProject({ name: newWorkspaceName.trim() })
          const newId = String((proj as any).id ?? (proj as any).project_id ?? "")
          if (newId) {
            setSelectedProjectId(newId)
            setWorkspaceMode("existing")
            loadWorkspaces()
          }
        } catch {
          // Continue with project_name
        }
      }

      const total = files.length
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const result = await uploadDocument(file.uri, file.name, file.mimeType, {
          project_id: effectiveProjectId || null,
          project_name: effectiveProjectName,
          document_type: documentType || null,
          document_date: documentDate || null,
        })
        uploaded.push(result.id || String(result.id))
        setProgress(Math.round(((i + 1) / total) * 100))
        setUploadedIds([...uploaded])
      }

      setProgress(100)
      setUploadState("success")
      setUploadedIds(uploaded)
      if (uploaded.length === 1) {
        onUploaded?.(uploaded[0])
      }
    } catch (err: any) {
      setUploadState("error")
      const msg = err?.message ?? err?.data?.detail ?? err?.data?.error ?? ""
      if (msg.includes("413") || msg.toLowerCase().includes("too large")) {
        setError("File too large. Maximum size is 64 MB.")
      } else if (msg.includes("Network") || msg.includes("fetch") || msg.includes("network")) {
        setError("Network error. Please check your connection.")
      } else {
        setError(msg || "Upload failed")
      }
      setProgress(0)
    }
  }

  const reset = () => {
    setFiles([])
    setSelectedProjectId("")
    setNewWorkspaceName("")
    setWorkspaceMode("existing")
    setDocumentType("")
    setDocumentDate("")
    setIsPublic(false)
    setUploadState("idle")
    setProgress(0)
    setError("")
    setUploadedIds([])
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.bg }}
      contentContainerStyle={{
        padding: isTablet ? 24 : 16,
        paddingBottom: 48,
        maxWidth: isTablet ? 760 : undefined,
        alignSelf: "center",
        width: "100%",
      }}
    >
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, letterSpacing: -0.3, marginBottom: 4 }}>
        Upload Documents
      </Text>
      <Text style={{ fontSize: 13, color: c.textSecondary, marginBottom: 20 }}>
        Add files for analysis, processing, and ZETDC knowledge training
      </Text>

      {/* Error */}
      {error && (
        <View style={{
          backgroundColor: c.error + "14",
          borderRadius: 12,
          padding: 12,
          marginBottom: 16,
          borderWidth: 1,
          borderColor: c.error + "28",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}>
          <Text style={{ color: c.error, fontSize: 13, flex: 1 }}>{error}</Text>
          <Pressable onPress={() => setError("")} style={{ marginLeft: 12 }}>
            <Text style={{ color: c.error, fontWeight: "600", fontSize: 12 }}>Dismiss</Text>
          </Pressable>
        </View>
      )}

      {/* Success state */}
      {uploadState === "success" && (
        <View style={{
          backgroundColor: c.cardBg,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: c.border,
          padding: 32,
          alignItems: "center",
          marginBottom: 20,
        }}>
          <View style={{
            width: 56, height: 56, borderRadius: 28,
            backgroundColor: c.success + "18",
            borderWidth: 2, borderColor: c.success,
            alignItems: "center", justifyContent: "center",
            marginBottom: 16,
          }}>
            <Text style={{ color: c.success, fontSize: 28 }}>✓</Text>
          </View>
          <Text style={{ fontSize: 18, fontWeight: "700", color: c.text, marginBottom: 6 }}>
            {uploadedIds.length} document{uploadedIds.length > 1 ? "s" : ""} uploaded
          </Text>
          <Text style={{ fontSize: 13, color: c.textSecondary, marginBottom: 20, textAlign: "center" }}>
            {files.map((f) => f.name).join(", ")}
          </Text>
          <View style={{ flexDirection: "row", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
            <Pressable onPress={reset} style={{
              paddingVertical: 10, paddingHorizontal: 20,
              borderRadius: 8, borderWidth: 1, borderColor: c.border,
            }}>
              <Text style={{ fontSize: 13, fontWeight: "600", color: c.textSecondary }}>Upload More</Text>
            </Pressable>
            {uploadedIds.length === 1 && (
              <Pressable onPress={() => onUploaded?.(uploadedIds[0])} style={{
                paddingVertical: 10, paddingHorizontal: 20,
                borderRadius: 8, backgroundColor: c.primary,
              }}>
                <Text style={{ fontSize: 13, fontWeight: "600", color: "#FFFFFF" }}>Open Document</Text>
              </Pressable>
            )}
          </View>
        </View>
      )}

      {/* Error state */}
      {uploadState === "error" && (
        <View style={{
          backgroundColor: c.cardBg,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: c.border,
          padding: 32,
          alignItems: "center",
          marginBottom: 20,
        }}>
          <View style={{
            width: 56, height: 56, borderRadius: 28,
            backgroundColor: c.error + "18",
            borderWidth: 2, borderColor: c.error,
            alignItems: "center", justifyContent: "center",
            marginBottom: 16,
          }}>
            <Text style={{ color: c.error, fontSize: 28 }}>✕</Text>
          </View>
          <Text style={{ fontSize: 18, fontWeight: "700", color: c.error, marginBottom: 6 }}>Upload Failed</Text>
          <Text style={{ fontSize: 13, color: c.textSecondary, marginBottom: 20, textAlign: "center" }}>{error}</Text>
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Pressable onPress={reset} style={{
              paddingVertical: 10, paddingHorizontal: 20,
              borderRadius: 8, borderWidth: 1, borderColor: c.border,
            }}>
              <Text style={{ fontSize: 13, fontWeight: "600", color: c.textSecondary }}>Cancel</Text>
            </Pressable>
            <Pressable onPress={handleUpload} style={{
              paddingVertical: 10, paddingHorizontal: 20,
              borderRadius: 8, backgroundColor: c.primary,
            }}>
              <Text style={{ fontSize: 13, fontWeight: "600", color: "#FFFFFF" }}>Retry</Text>
            </Pressable>
          </View>
        </View>
      )}

      {/* Main form */}
      {uploadState !== "success" && uploadState !== "error" && (
        <>
          {/* Category selector */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
            <View style={{ flexDirection: "row", gap: 8 }}>
              {(Object.keys(CATEGORY_CONFIG) as ContentCategory[]).map((cat) => {
                const cfg = CATEGORY_CONFIG[cat]
                const active = contentCategory === cat
                return (
                  <Pressable
                    key={cat}
                    onPress={() => { setContentCategory(cat); setFiles([]); setError(""); setUploadState("idle") }}
                    style={{
                      paddingVertical: 8,
                      paddingHorizontal: 14,
                      borderRadius: 10,
                      borderWidth: 1,
                      borderColor: active ? c.primary : c.border,
                      backgroundColor: active ? c.surfaceActive : "transparent",
                      flexDirection: "row",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <Text style={{ fontSize: 14 }}>{cfg.icon}</Text>
                    <Text style={{ fontSize: 12, fontWeight: "600", color: active ? c.primary : c.textMuted }}>
                      {cfg.label}
                    </Text>
                  </Pressable>
                )
              })}
            </View>
          </ScrollView>

          {/* Drop zone / file picker */}
          <Pressable
            onPress={pickFiles}
            style={{
              backgroundColor: c.cardBg,
              borderRadius: 14,
              borderWidth: 2,
              borderStyle: "dashed",
              borderColor: c.primary,
              padding: 32,
              alignItems: "center",
              marginBottom: 20,
            }}
          >
            {files.length > 0 ? (
              <>
                <Text style={{ fontSize: 36, marginBottom: 10 }}>{CATEGORY_CONFIG[contentCategory].icon}</Text>
                <Text style={{ fontWeight: "700", color: c.text, fontSize: 14, marginBottom: 12 }}>
                  {files.length} file{files.length > 1 ? "s" : ""} selected
                </Text>
                {/* File list */}
                <View style={{ width: "100%", maxWidth: 400, gap: 6 }}>
                  {files.map((f) => (
                    <View key={f.id} style={{
                      flexDirection: "row",
                      alignItems: "center",
                      paddingVertical: 8,
                      paddingHorizontal: 12,
                      backgroundColor: c.surfaceActive,
                      borderRadius: 8,
                      gap: 8,
                    }}>
                      <Text style={{ flex: 1, fontSize: 12, color: c.text }} numberOfLines={1}>{f.name}</Text>
                      {f.size > 0 && (
                        <Text style={{ fontSize: 10, color: c.textMuted }}>{(f.size / 1024).toFixed(1)} KB</Text>
                      )}
                      <Pressable onPress={() => removeFile(f.id)} hitSlop={8}>
                        <Text style={{ color: c.error, fontSize: 16, fontWeight: "700" }}>✕</Text>
                      </Pressable>
                    </View>
                  ))}
                </View>
                <Pressable onPress={pickFiles} style={{ marginTop: 12 }}>
                  <Text style={{ fontSize: 12, fontWeight: "600", color: c.primary }}>+ Add more files</Text>
                </Pressable>
              </>
            ) : (
              <>
                <Text style={{ fontSize: 40, marginBottom: 10 }}>{CATEGORY_CONFIG[contentCategory].icon}</Text>
                <Text style={{ fontWeight: "600", color: c.primary, fontSize: 14, marginBottom: 6 }}>
                  Tap to select {CATEGORY_CONFIG[contentCategory].label.toLowerCase()}s
                </Text>
                <Text style={{ fontSize: 12, color: c.textMuted }}>
                  Supported: {CATEGORY_CONFIG[contentCategory].description}
                </Text>
              </>
            )}
          </Pressable>

          {/* Upload progress */}
          {uploadState === "uploading" && (
            <View style={{ marginBottom: 20 }}>
              <View style={{
                height: 8,
                borderRadius: 999,
                backgroundColor: c.surface,
                overflow: "hidden",
              }}>
                <View style={{
                  height: "100%",
                  borderRadius: 999,
                  backgroundColor: c.primary,
                  width: `${progress}%`,
                }} />
              </View>
              <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 6, textAlign: "right" }}>
                Uploading {Math.round(progress)}% · {files.length} file{files.length > 1 ? "s" : ""}
              </Text>
            </View>
          )}

          {/* Metadata fields */}
          <View style={{ marginBottom: 20, gap: 16 }}>
            {/* Repository / Workspace */}
            <View>
              <Text style={{
                fontSize: 11, fontWeight: "700", color: c.textSecondary,
                marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5,
              }}>
                Repository / Workspace
              </Text>
              <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
                {(["existing" as const, "new" as const]).map((mode) => (
                  <Pressable
                    key={mode}
                    onPress={() => setWorkspaceMode(mode)}
                    style={{
                      flex: 1,
                      paddingVertical: 8,
                      paddingHorizontal: 12,
                      borderRadius: 8,
                      borderWidth: 1,
                      borderColor: workspaceMode === mode ? c.primary : c.border,
                      backgroundColor: workspaceMode === mode ? c.surfaceActive : "transparent",
                      alignItems: "center",
                    }}
                  >
                    <Text style={{
                      fontSize: 12,
                      fontWeight: "600",
                      color: workspaceMode === mode ? c.primary : c.textMuted,
                    }}>
                      {mode === "existing" ? "Select existing" : "Create new"}
                    </Text>
                  </Pressable>
                ))}
              </View>

              {workspaceMode === "existing" ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={{ flexDirection: "row", gap: 6 }}>
                    <Pressable
                      onPress={() => setSelectedProjectId("")}
                      style={{
                        paddingVertical: 6,
                        paddingHorizontal: 12,
                        borderRadius: 999,
                        backgroundColor: !selectedProjectId ? c.primary : c.surface,
                      }}
                    >
                      <Text style={{ fontSize: 11, fontWeight: "600", color: !selectedProjectId ? "#FFFFFF" : c.text }}>
                        None
                      </Text>
                    </Pressable>
                    {loadingWorkspaces ? (
                      <ActivityIndicator size="small" color={c.primary} />
                    ) : (
                      workspaces.map((ws: any) => (
                        <Pressable
                          key={ws.id}
                          onPress={() => setSelectedProjectId(ws.id)}
                          style={{
                            paddingVertical: 6,
                            paddingHorizontal: 12,
                            borderRadius: 999,
                            backgroundColor: selectedProjectId === ws.id ? c.primary : c.surface,
                          }}
                        >
                          <Text style={{
                            fontSize: 11, fontWeight: "600",
                            color: selectedProjectId === ws.id ? "#FFFFFF" : c.text,
                          }}>
                            {ws.name}
                          </Text>
                        </Pressable>
                      ))
                    )}
                  </View>
                </ScrollView>
              ) : (
                <TextInput
                  placeholder="Enter workspace name"
                  value={newWorkspaceName}
                  onChangeText={setNewWorkspaceName}
                  placeholderTextColor={c.textMuted}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: c.border,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 13,
                  }}
                />
              )}
            </View>

            {/* Document type + date */}
            <View style={{ flexDirection: isTablet ? "row" : "column", gap: 16 }}>
              <View style={{ flex: 1 }}>
                <Text style={{
                  fontSize: 11, fontWeight: "700", color: c.textSecondary,
                  marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5,
                }}>
                  Document Type
                </Text>
                <TextInput
                  placeholder="e.g. Report, Memo, Contract"
                  value={documentType}
                  onChangeText={setDocumentType}
                  placeholderTextColor={c.textMuted}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: c.border,
                    backgroundColor: c.inputBg,
                    color: c.text,
                    fontSize: 13,
                  }}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{
                  fontSize: 11, fontWeight: "700", color: c.textSecondary,
                  marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5,
                }}>
                  Document Date
                </Text>
                <Pressable
                  onPress={() => setShowDatePicker(true)}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: c.border,
                    backgroundColor: c.inputBg,
                  }}
                >
                  <Text style={{ color: documentDate ? c.text : c.textMuted, fontSize: 13 }}>
                    {documentDate || "Select date"}
                  </Text>
                </Pressable>
                {showDatePicker && (
                  <DateTimePicker
                    value={documentDate ? new Date(documentDate) : new Date()}
                    mode="date"
                    display="default"
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
              </View>
            </View>

            {/* Visibility */}
            <View>
              <Text style={{
                fontSize: 11, fontWeight: "700", color: c.textSecondary,
                marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5,
              }}>
                Visibility
              </Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable
                  onPress={() => setIsPublic(false)}
                  style={{
                    flex: 1,
                    paddingVertical: 10,
                    paddingHorizontal: 14,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: !isPublic ? c.primary : c.border,
                    backgroundColor: !isPublic ? c.surfaceActive : "transparent",
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                  }}
                >
                  <Text style={{ fontSize: 12 }}>🔒</Text>
                  <Text style={{
                    fontSize: 12, fontWeight: "600",
                    color: !isPublic ? c.primary : c.textMuted,
                  }}>
                    Private
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => setIsPublic(true)}
                  style={{
                    flex: 1,
                    paddingVertical: 10,
                    paddingHorizontal: 14,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: isPublic ? c.primary : c.border,
                    backgroundColor: isPublic ? c.surfaceActive : "transparent",
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                  }}
                >
                  <Text style={{ fontSize: 12 }}>🌐</Text>
                  <Text style={{
                    fontSize: 12, fontWeight: "600",
                    color: isPublic ? c.primary : c.textMuted,
                  }}>
                    Public
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>

          {/* Transfer learning info */}
          <View style={{
            padding: 14,
            backgroundColor: isDark ? "rgba(251,191,36,0.06)" : "rgba(243,111,33,0.05)",
            borderRadius: 10,
            borderWidth: 1,
            borderColor: c.accent + "20",
            flexDirection: "row",
            gap: 10,
            marginBottom: 20,
          }}>
            <Text style={{ fontSize: 16 }}>⚡</Text>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 12, fontWeight: "700", color: c.text, marginBottom: 3 }}>
                Transfer Learning Ready
              </Text>
              <Text style={{ fontSize: 11, color: c.textSecondary, lineHeight: 16 }}>
                After uploading, local Llama models are automatically trained on ZETDC documents.
                This enables models to learn your organization's knowledge for accurate, domain-specific responses.
              </Text>
            </View>
          </View>

          {/* Upload button */}
          <Pressable
            onPress={handleUpload}
            disabled={files.length === 0 || uploadState === "uploading"}
            style={{
              paddingVertical: 14,
              borderRadius: 10,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: files.length === 0 || uploadState === "uploading" ? c.border : c.primary,
              opacity: files.length === 0 ? 0.5 : 1,
            }}
          >
            <Text style={{ color: "#FFFFFF", fontSize: 15, fontWeight: "700", letterSpacing: 0.3 }}>
              {uploadState === "uploading"
                ? `Uploading ${files.length} file${files.length > 1 ? "s" : ""}… ${progress}%`
                : `Upload ${files.length > 0 ? files.length : ""} Document${files.length > 1 ? "s" : ""}`}
            </Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  )
}
