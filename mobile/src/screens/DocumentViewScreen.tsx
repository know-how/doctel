import React, { useEffect, useState } from "react"
import {
  View, Text, Pressable, ScrollView, ActivityIndicator, Alert, Linking,
  useWindowDimensions,
} from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import {
  getDocumentAnalysis,
  downloadDocumentFileApi,
  getDocumentLibrary,
  getIngestStatus,
  retryIngest,
} from "../api/client"
import { DocumentAnalysisResponse } from "../types/api"
import { fileIconInfo, truncate, downloadAndOpenDocument } from "../utils/documentUtils"

interface DocumentViewScreenProps {
  documentId: string
  onNavigate: (path: string) => void
  filename?: string
}

export function DocumentViewScreen({ documentId, onNavigate, filename: initialFilename }: DocumentViewScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null)
  const [documentInfo, setDocumentInfo] = useState<{
    filename: string
    status: string
    created_at: string
    project_name?: string
    document_type?: string
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [ingestStatus, setIngestStatus] = useState<string | null>(null)

  const { letter: fileLetter, color: fileColor } = fileIconInfo(initialFilename || documentInfo?.filename)

  // Load document analysis and metadata
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [analysisRes, docLibRes] = await Promise.all([
          getDocumentAnalysis(documentId).catch(() => null),
          getDocumentLibrary({ id: documentId }).catch(() => null),
        ])
        if (analysisRes) setAnalysis(analysisRes)

        // Extract document info from library response
        if (docLibRes?.documents) {
          const docs = Array.isArray(docLibRes.documents) ? docLibRes.documents : []
          const info = docs.find((d: any) => d.id === documentId)
          if (info) {
            setDocumentInfo({
              filename: info.filename || initialFilename || "Unknown",
              status: info.status || "",
              created_at: info.created_at || "",
              project_name: info.project_name,
              document_type: info.document_type,
            })
          }
        } else if (initialFilename) {
          setDocumentInfo({
            filename: initialFilename,
            status: "unknown",
            created_at: "",
          })
        }

        // Check ingest status if analysis isn't ready
        if (!analysisRes || analysisRes.status !== "READY") {
          try {
            const s = await getIngestStatus(documentId)
            if (s?.status) setIngestStatus(s.status)
          } catch {}
        }

        // If no info yet, try getting from analysis fallback
        if (!documentInfo && analysisRes) {
          setDocumentInfo({
            filename: initialFilename || `Document ${documentId}`,
            status: analysisRes.status,
            created_at: "",
          })
        }
      } catch (err: any) {
        setError(err?.message || "Failed to load document")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [documentId])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await downloadAndOpenDocument(documentId, documentInfo?.filename)
    } catch (err: any) {
      Alert.alert("Error", err?.message || "Failed to download document")
    } finally {
      setDownloading(false)
    }
  }

  const handleRetryIngest = async () => {
    try {
      await retryIngest(documentId)
      setIngestStatus("retrying")
      Alert.alert("Retrying", "Ingestion has been retried. Please check back shortly.")
    } catch (err: any) {
      Alert.alert("Error", err?.message || "Failed to retry ingestion")
    }
  }

  const handleOpenInBrowser = () => {
    const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || "http://172.16.4.60:8000"
    Linking.openURL(`${baseUrl}/documents/${encodeURIComponent(documentId)}/file`).catch(() => {
      Alert.alert("Error", "Could not open in browser")
    })
  }

  // Loading state
  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg, gap: 12 }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ color: c.textMuted, fontSize: 13 }}>Loading document...</Text>
      </View>
    )
  }

  // Error state
  if (error && !analysis) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg, padding: 24 }}>
        <Text style={{ fontSize: 40, marginBottom: 12 }}>⚠️</Text>
        <Text style={{ color: c.error, fontSize: 15, fontWeight: "600", marginBottom: 8, textAlign: "center" }}>
          Failed to Load Document
        </Text>
        <Text style={{ color: c.textMuted, fontSize: 13, textAlign: "center", marginBottom: 20 }}>
          {error}
        </Text>
        <Pressable
          onPress={handleOpenInBrowser}
          style={{
            backgroundColor: c.primary,
            borderRadius: 10,
            paddingVertical: 10,
            paddingHorizontal: 24,
          }}
        >
          <Text style={{ color: "#FFFFFF", fontSize: 13, fontWeight: "600" }}>
            Open in Browser
          </Text>
        </Pressable>
      </View>
    )
  }

  const displayFilename = documentInfo?.filename || initialFilename || `Document ${documentId}`
  const docStatus = analysis?.status || documentInfo?.status || ingestStatus || "unknown"
  const isReady = analysis?.status === "READY" || docStatus === "completed"

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.bg }}
      contentContainerStyle={{ padding: 16, maxWidth: 800, width: "100%", alignSelf: "center" }}
    >
      {/* ── Header: File icon + name + status ── */}
      <View style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        marginBottom: 16,
      }}>
        <View style={{
          width: 44,
          height: 44,
          borderRadius: 10,
          backgroundColor: fileColor + "18",
          alignItems: "center",
          justifyContent: "center",
        }}>
          <Text style={{ fontSize: 18, fontWeight: "700", color: fileColor }}>{fileLetter}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }} numberOfLines={2}>
            {displayFilename}
          </Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 2 }}>
            <View style={{
              paddingHorizontal: 6,
              paddingVertical: 1,
              borderRadius: 4,
              backgroundColor: isReady ? "#10B98122" : "#F59E0B22",
              alignSelf: "flex-start",
            }}>
              <Text style={{
                fontSize: 9,
                fontWeight: "700",
                color: isReady ? "#10B981" : "#F59E0B",
                textTransform: "uppercase",
              }}>
                {isReady ? "Ready" : "Processing"}
              </Text>
            </View>
            {documentInfo?.created_at && (
              <Text style={{ fontSize: 10, color: c.textMuted }}>
                {new Date(documentInfo.created_at).toLocaleDateString()}
              </Text>
            )}
          </View>
        </View>
      </View>

      {/* ── Action buttons ── */}
      <View style={{
        flexDirection: "row",
        gap: 8,
        marginBottom: 20,
      }}>
        <Pressable
          onPress={handleDownload}
          disabled={downloading}
          style={{
            flex: 1,
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            backgroundColor: c.primary,
            borderRadius: 10,
            paddingVertical: 10,
            opacity: downloading ? 0.6 : 1,
          }}
        >
          <Text style={{ fontSize: 14 }}>⬇</Text>
          <Text style={{ color: "#FFFFFF", fontSize: 13, fontWeight: "600" }}>
            {downloading ? "Opening..." : "Download & Open"}
          </Text>
        </Pressable>

        <Pressable
          onPress={handleOpenInBrowser}
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            backgroundColor: c.surfaceActive,
            borderRadius: 10,
            paddingVertical: 10,
            paddingHorizontal: 14,
            borderWidth: 1,
            borderColor: c.border,
          }}
        >
          <Text style={{ fontSize: 14 }}>🌐</Text>
          <Text style={{ color: c.text, fontSize: 13, fontWeight: "600" }}>Open</Text>
        </Pressable>
      </View>

      {/* ── Not ready state ── */}
      {!isReady && (
        <View style={{
          backgroundColor: c.cardBg,
          borderRadius: 12,
          borderWidth: 1,
          borderColor: c.border,
          padding: 16,
          marginBottom: 16,
          alignItems: "center",
        }}>
          <Text style={{ fontSize: 32, marginBottom: 8 }}>⏳</Text>
          <Text style={{ color: c.text, fontSize: 14, fontWeight: "600", marginBottom: 4 }}>
            Document is being processed
          </Text>
          <Text style={{ color: c.textMuted, fontSize: 12, textAlign: "center", marginBottom: 12 }}>
            The document analysis will be available once processing is complete.
          </Text>
          {docStatus === "failed" ? (
            <Pressable
              onPress={handleRetryIngest}
              style={{
                backgroundColor: c.error + "22",
                borderRadius: 8,
                paddingVertical: 8,
                paddingHorizontal: 16,
              }}
            >
              <Text style={{ color: c.error, fontSize: 12, fontWeight: "600" }}>Retry Processing</Text>
            </Pressable>
          ) : (
            <Text style={{ color: c.textMuted, fontSize: 11 }}>Auto-refreshing...</Text>
          )}
        </View>
      )}

      {/* ── Analysis Dashboard ── */}
      {analysis && (
        <>
          {/* Executive Summary */}
          {analysis.executive_summary && (
            <View style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 14,
              marginBottom: 12,
            }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: c.primary, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Summary
              </Text>
              <Text style={{ fontSize: 13, color: c.text, lineHeight: 19 }}>
                {analysis.executive_summary}
              </Text>
            </View>
          )}

          {/* Detailed Summary */}
          {analysis.detailed_summary && analysis.detailed_summary.length > 0 && (
            <View style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 14,
              marginBottom: 12,
            }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: c.primary, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Key Points
              </Text>
              {analysis.detailed_summary.slice(0, 6).map((point, i) => (
                <View key={i} style={{ flexDirection: "row", gap: 6, marginBottom: 4 }}>
                  <Text style={{ color: c.primary, fontSize: 12, marginTop: 1 }}>•</Text>
                  <Text style={{ color: c.textSecondary, fontSize: 12, lineHeight: 18, flex: 1 }}>{point}</Text>
                </View>
              ))}
              {analysis.detailed_summary.length > 6 && (
                <Text style={{ color: c.textMuted, fontSize: 10, marginTop: 4 }}>
                  +{analysis.detailed_summary.length - 6} more points
                </Text>
              )}
            </View>
          )}

          {/* Two-column section: Topics, Sentiment, Entities */}
          <View style={{ flexDirection: isTablet ? "row" : "column", gap: 12, marginBottom: 12 }}>
            {/* Topics */}
            {analysis.topics && analysis.topics.length > 0 && (
              <View style={{
                flex: 1,
                backgroundColor: c.cardBg,
                borderRadius: 12,
                borderWidth: 1,
                borderColor: c.border,
                padding: 14,
              }}>
                <Text style={{ fontSize: 11, fontWeight: "700", color: c.textMuted, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Topics
                </Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
                  {analysis.topics.slice(0, 8).map((topic, i) => (
                    <View key={i} style={{
                      backgroundColor: c.surfaceActive,
                      borderRadius: 6,
                      paddingHorizontal: 6,
                      paddingVertical: 2,
                    }}>
                      <Text style={{ fontSize: 10, color: c.textSecondary, fontWeight: "500" }}>{topic}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {/* Sentiment */}
            {analysis.sentiment && (
              <View style={{
                flex: 1,
                backgroundColor: c.cardBg,
                borderRadius: 12,
                borderWidth: 1,
                borderColor: c.border,
                padding: 14,
              }}>
                <Text style={{ fontSize: 11, fontWeight: "700", color: c.textMuted, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Sentiment
                </Text>
                <Text style={{ fontSize: 24, marginBottom: 2 }}>
                  {analysis.sentiment === "positive" ? "😊" : analysis.sentiment === "negative" ? "😟" : "😐"}
                </Text>
                <Text style={{ fontSize: 13, color: c.text, fontWeight: "600", textTransform: "capitalize" }}>
                  {analysis.sentiment}
                </Text>
              </View>
            )}
          </View>

          {/* Entities */}
          {analysis.entities && analysis.entities.length > 0 && (
            <View style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 14,
              marginBottom: 12,
            }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: c.textMuted, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Key Entities
              </Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
                {analysis.entities.slice(0, 12).map((entity, i) => (
                  <View key={i} style={{
                    backgroundColor: c.surfaceActive,
                    borderRadius: 6,
                    paddingHorizontal: 8,
                    paddingVertical: 3,
                  }}>
                    <Text style={{ fontSize: 10, color: c.textSecondary, fontWeight: "500" }}>{entity}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* Key Entities (rich format) */}
          {analysis.key_entities && Object.keys(analysis.key_entities).length > 0 && (
            <View style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 14,
              marginBottom: 12,
            }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: c.textMuted, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Detailed Entities
              </Text>
              {Object.entries(analysis.key_entities).slice(0, 6).map(([category, items]) => (
                <View key={category} style={{ marginBottom: 6 }}>
                  <Text style={{ fontSize: 11, color: c.primary, fontWeight: "600", marginBottom: 2, textTransform: "capitalize" }}>
                    {category.replace(/_/g, " ")}
                  </Text>
                  <Text style={{ fontSize: 11, color: c.textSecondary, lineHeight: 17 }}>
                    {Array.isArray(items) ? items.join(", ") : String(items)}
                  </Text>
                </View>
              ))}
            </View>
          )}

          {/* Action Items & Decisions */}
          {(analysis.action_items && analysis.action_items.length > 0) && (
            <View style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 14,
              marginBottom: 12,
            }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: "#F59E0B", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                ⚡ Action Items
              </Text>
              {analysis.action_items.slice(0, 5).map((item, i) => (
                <View key={i} style={{ flexDirection: "row", gap: 6, marginBottom: 3 }}>
                  <Text style={{ color: "#F59E0B", fontSize: 12 }}>☐</Text>
                  <Text style={{ color: c.textSecondary, fontSize: 12, lineHeight: 18, flex: 1 }}>{item}</Text>
                </View>
              ))}
            </View>
          )}

          {(analysis.decisions && analysis.decisions.length > 0) && (
            <View style={{
              backgroundColor: c.cardBg,
              borderRadius: 12,
              borderWidth: 1,
              borderColor: c.border,
              padding: 14,
              marginBottom: 12,
            }}>
              <Text style={{ fontSize: 11, fontWeight: "700", color: "#8B5CF6", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
                ✅ Decisions
              </Text>
              {analysis.decisions.slice(0, 5).map((dec, i) => (
                <View key={i} style={{ flexDirection: "row", gap: 6, marginBottom: 3 }}>
                  <Text style={{ color: "#8B5CF6", fontSize: 12 }}>✓</Text>
                  <Text style={{ color: c.textSecondary, fontSize: 12, lineHeight: 18, flex: 1 }}>{dec}</Text>
                </View>
              ))}
            </View>
          )}
        </>
      )}

      {/* ── Metadata footer ── */}
      {documentInfo && (
        <View style={{
          flexDirection: "row",
          flexWrap: "wrap",
          gap: 8,
          marginTop: 8,
          marginBottom: 24,
          paddingTop: 12,
          borderTopWidth: 1,
          borderTopColor: c.border,
        }}>
          {documentInfo.document_type && (
            <View style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
              backgroundColor: c.surfaceActive,
              borderRadius: 6,
              paddingHorizontal: 8,
              paddingVertical: 3,
            }}>
              <Text style={{ fontSize: 10, color: c.textMuted }}>📄 Type:</Text>
              <Text style={{ fontSize: 10, color: c.textSecondary, fontWeight: "600" }}>{documentInfo.document_type}</Text>
            </View>
          )}
          {documentInfo.project_name && (
            <View style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
              backgroundColor: c.surfaceActive,
              borderRadius: 6,
              paddingHorizontal: 8,
              paddingVertical: 3,
            }}>
              <Text style={{ fontSize: 10, color: c.textMuted }}>📁 Project:</Text>
              <Text style={{ fontSize: 10, color: c.textSecondary, fontWeight: "600" }}>{documentInfo.project_name}</Text>
            </View>
          )}
          <View style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 4,
            backgroundColor: c.surfaceActive,
            borderRadius: 6,
            paddingHorizontal: 8,
            paddingVertical: 3,
          }}>
            <Text style={{ fontSize: 10, color: c.textMuted }}>🆔 ID:</Text>
            <Text style={{ fontSize: 10, color: c.textSecondary, fontWeight: "500" }}>{documentId}</Text>
          </View>
        </View>
      )}

      {/* ── Chat about this document ── */}
      <Pressable
        onPress={() => onNavigate("/analyze/chat")}
        style={{
          backgroundColor: c.primary,
          borderRadius: 12,
          paddingVertical: 12,
          paddingHorizontal: 20,
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <Text style={{ color: "#FFFFFF", fontSize: 14, fontWeight: "600" }}>
          💬 Chat about this document
        </Text>
      </Pressable>
    </ScrollView>
  )
}
