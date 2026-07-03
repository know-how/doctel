import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, Platform, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getMyDocuments, runExtraction } from "../api/client"
import { MyDocument } from "../types/api"

export function AnalyzeExtractionScreen() {
  const [schema, setSchema] = useState("")
  const [documents, setDocuments] = useState<MyDocument[]>([])
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [results, setResults] = useState<any>(null)
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

  const handleRunExtraction = async () => {
    if (!schema.trim()) {
      setError("Please enter an extraction schema")
      return
    }
    if (selectedDocs.size === 0) {
      setError("Please select at least one document")
      return
    }
    try {
      setLoading(true)
      setError("")
      setResults(null)
      const res = await runExtraction(schema, Array.from(selectedDocs))
      setResults(res)
    } catch (err: any) {
      setError(err.message || "Extraction failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: 32 }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: 16 }}>
        Data Extraction
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: 8 }}>
        Extraction Schema
      </Text>
      <TextInput
        placeholder={`{\n  "title": "string",\n  "parties": ["string"],\n  "effective_date": "date",\n  "obligations": ["string"]\n}`}
        value={schema}
        onChangeText={setSchema}
        placeholderTextColor={c.textMuted}
        multiline
        numberOfLines={8}
        textAlignVertical="top"
        style={{
          backgroundColor: c.cardBg,
          borderRadius: t.radii.sm,
          padding: 12,
          borderWidth: 1,
          borderColor: c.border,
          color: c.text,
          fontSize: 13,
          fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
          marginBottom: 16,
          minHeight: 160,
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
        onPress={handleRunExtraction}
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
        {loading ? (
          <ActivityIndicator size="small" color="#FFFFFF" />
        ) : null}
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>
          {loading ? "Extracting..." : "Run Extraction"}
        </Text>
      </Pressable>

      {results && (
        <View>
          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: 10 }}>
            Results
          </Text>
          <View
            style={{
              backgroundColor: c.bgSecondary,
              borderRadius: t.radii.sm,
              padding: 12,
            }}
          >
            <Text
              style={{
                fontSize: 12,
                color: c.textMuted,
                fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
              }}
              selectable
            >
              {typeof results === "string" ? results : JSON.stringify(results, null, 2)}
            </Text>
          </View>
        </View>
      )}
    </ScrollView>
  )
}
