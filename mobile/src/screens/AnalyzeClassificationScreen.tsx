import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getMyDocuments, classifyDocuments } from "../api/client"
import { MyDocument } from "../types/api"

export function AnalyzeClassificationScreen() {
  const [rules, setRules] = useState("")
  const [documents, setDocuments] = useState<MyDocument[]>([])
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [error, setError] = useState("")
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      setLoadingDocs(true)
      const res = await getMyDocuments()
      setDocuments(res?.documents || [])
    } catch {
      setError("Failed to load documents")
    } finally {
      setLoadingDocs(false)
    }
  }

  const toggleDoc = (id: string) => {
    setSelectedDocs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleRunClassification = async () => {
    if (!rules.trim()) {
      setError("Please enter classification rules")
      return
    }
    if (selectedDocs.size === 0) {
      setError("Please select at least one document")
      return
    }
    try {
      setLoading(true)
      setError("")
      const res = await classifyDocuments(rules, Array.from(selectedDocs))
      const items = res?.results || res?.classifications || (Array.isArray(res) ? res : [res])
      setResults(items)
    } catch (err: any) {
      setError(err.message || "Classification failed")
    } finally {
      setLoading(false)
    }
  }

  const tagColors = [c.primary + "14", c.success + "18", c.accent + "18", c.secondary + "18", c.accent + "28", c.error + "14"]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: 32 }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: 16 }}>
        Document Classification
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: 8 }}>
        Classification Rules
      </Text>
      <TextInput
        placeholder="Classify documents based on content type:\n- Legal: contracts, NDAs, agreements\n- Financial: invoices, budgets, reports\n- Technical: specs, manuals, diagrams\n- HR: policies, reviews, onboarding"
        value={rules}
        onChangeText={setRules}
        placeholderTextColor={c.textMuted}
        multiline
        numberOfLines={6}
        textAlignVertical="top"
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.sm,
          padding: 12,
          borderWidth: 1,
          borderColor: c.border,
          color: c.text,
          fontSize: 13,
          marginBottom: 16,
          minHeight: 120,
        }}
      />

      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: 8 }}>
        Select Documents
      </Text>
      {loadingDocs ? (
        <ActivityIndicator size="small" color={c.primary} style={{ marginBottom: 12 }} />
      ) : (
        <View style={{ marginBottom: 16, flexDirection: isTablet ? "row" : "column", flexWrap: isTablet ? "wrap" : "nowrap", gap: 6 }}>
          {documents.map((doc) => (
            <Pressable
              key={doc.id}
              onPress={() => toggleDoc(doc.id)}
              style={{
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: 8,
                paddingHorizontal: 12,
                backgroundColor: selectedDocs.has(doc.id) ? c.primary + "14" : c.cardBg,
                borderRadius: t.radii.sm,
                marginBottom: isTablet ? 0 : 6,
                borderWidth: 1,
                borderColor: selectedDocs.has(doc.id) ? c.primary : c.border,
                minWidth: isTablet ? "45%" : undefined,
              }}
            >
              <Text style={{ fontSize: 16, marginRight: 10 }}>
                {selectedDocs.has(doc.id) ? "☑️" : "⬜"}
              </Text>
              <Text style={{ fontSize: 13, color: c.text, flex: 1 }}>{doc.filename}</Text>
            </Pressable>
          ))}
        </View>
      )}

      <Pressable
        onPress={handleRunClassification}
        disabled={loading}
        style={{
          backgroundColor: loading ? c.textMuted : c.primary,
          borderRadius: t.radii.sm,
          paddingVertical: 14,
          alignItems: "center",
          flexDirection: "row",
          justifyContent: "center",
          gap: 8,
          marginBottom: 20,
        }}
      >
        {loading ? <ActivityIndicator size="small" color="#FFFFFF" /> : null}
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>
          {loading ? "Classifying..." : "Run Classification"}
        </Text>
      </Pressable>

      {results.length > 0 && (
        <View>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: 10 }}>
            Results ({results.length})
          </Text>
          <View style={isTablet ? { flexDirection: "row", flexWrap: "wrap", gap: 10 } : undefined}>
            {results.map((item: any, index: number) => {
              const tags = item.tags || item.classifications || item.labels || []
              const confidence = item.confidence || item.score
              return (
                <View
                  key={index}
                  style={{
                    backgroundColor: c.cardBg,
                    borderRadius: t.radii.sm,
                    padding: 12,
                    marginBottom: isTablet ? 0 : 10,
                    borderWidth: 1,
                    borderColor: c.border,
                    minWidth: isTablet ? "45%" : undefined,
                    flex: isTablet ? 1 : undefined,
                  }}
                >
                  <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                    <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, flex: 1 }}>
                      📄 {item.filename || item.document_name || `Document ${index + 1}`}
                    </Text>
                    {typeof confidence === "number" && (
                      <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, paddingHorizontal: 8, paddingVertical: 3, marginLeft: 8 }}>
                        <Text style={{ fontSize: 11, color: c.primary, fontWeight: "600" }}>
                          {Math.round(confidence * 100)}%
                        </Text>
                      </View>
                    )}
                  </View>
                  {tags.length > 0 ? (
                    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
                      {tags.map((tag: string, i: number) => (
                        <View
                          key={i}
                          style={{
                            backgroundColor: tagColors[i % tagColors.length],
                            borderRadius: 12,
                            paddingHorizontal: 10,
                            paddingVertical: 4,
                          }}
                        >
                          <Text style={{ fontSize: 11, fontWeight: "600", color: c.text }}>
                            {tag}
                          </Text>
                        </View>
                      ))}
                    </View>
                  ) : (
                    <Text style={{ fontSize: 12, color: c.textMuted }}>No tags assigned</Text>
                  )}
                </View>
              )
            })}
          </View>
        </View>
      )}
    </ScrollView>
  )
}
