import React, { useEffect, useState } from "react"
import { View, Text, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getMyDocuments, compareDocuments } from "../api/client"
import { MyDocument } from "../types/api"

export function AnalyzeCompareScreen() {
  const [documents, setDocuments] = useState<MyDocument[]>([])
  const [docA, setDocA] = useState<string>("")
  const [docB, setDocB] = useState<string>("")
  const [docAName, setDocAName] = useState("")
  const [docBName, setDocBName] = useState("")
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [error, setError] = useState("")
  const [pickingSide, setPickingSide] = useState<"A" | "B" | null>(null)
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

  const pickDoc = (docId: string, docName: string) => {
    if (pickingSide === "A") {
      setDocA(docId)
      setDocAName(docName)
    } else if (pickingSide === "B") {
      setDocB(docId)
      setDocBName(docName)
    }
    setPickingSide(null)
  }

  const handleCompare = async () => {
    if (!docA || !docB) {
      setError("Please select both documents")
      return
    }
    try {
      setLoading(true)
      setError("")
      setResult(null)
      const res = await compareDocuments(docA, docB)
      setResult(res)
    } catch (err: any) {
      setError(err.message || "Comparison failed")
    } finally {
      setLoading(false)
    }
  }

  const similarityScore = result?.similarity || result?.similarity_score || result?.score
  const hasSimilarity = typeof similarityScore === "number"

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: 32 }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: 16 }}>
        Compare Documents
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.sm, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <View style={{ flexDirection: isTablet ? "row" : "column", gap: 12, marginBottom: 16 }}>
        <Pressable
          onPress={() => setPickingSide(pickingSide === "A" ? null : "A")}
          style={{
            flex: isTablet ? 1 : undefined,
            backgroundColor: pickingSide === "A" ? c.primary + "14" : c.cardBg,
            borderRadius: t.radii.sm,
            padding: 14,
            borderWidth: 2,
            borderColor: pickingSide === "A" ? c.primary : docA ? c.primary : c.border,
            alignItems: "center",
            marginBottom: isTablet ? 0 : 8,
          }}
        >
          <Text style={{ fontSize: 24, marginBottom: 4 }}>📄</Text>
          <Text style={{ fontSize: 12, fontWeight: "600", color: c.text, textAlign: "center" }}>
            {docAName || "Doc A"}
          </Text>
          <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 4 }}>Tap to select</Text>
        </Pressable>

        <View style={{ justifyContent: "center" }}>
          <Text style={{ fontSize: 20, color: c.textMuted }}>VS</Text>
        </View>

        <Pressable
          onPress={() => setPickingSide(pickingSide === "B" ? null : "B")}
          style={{
            flex: isTablet ? 1 : undefined,
            backgroundColor: pickingSide === "B" ? c.primary + "14" : c.cardBg,
            borderRadius: t.radii.sm,
            padding: 14,
            borderWidth: 2,
            borderColor: pickingSide === "B" ? c.primary : docB ? c.primary : c.border,
            alignItems: "center",
          }}
        >
          <Text style={{ fontSize: 24, marginBottom: 4 }}>📄</Text>
          <Text style={{ fontSize: 12, fontWeight: "600", color: c.text, textAlign: "center" }}>
            {docBName || "Doc B"}
          </Text>
          <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 4 }}>Tap to select</Text>
        </Pressable>
      </View>

      {pickingSide && (
        <View style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: c.border }}>
          <Text style={{ fontSize: 13, fontWeight: "600", color: c.primary, marginBottom: 8 }}>
            Select Document {pickingSide}
          </Text>
          {loadingDocs ? (
            <ActivityIndicator size="small" color={c.primary} />
          ) : (
            documents.map((doc) => (
              <Pressable
                key={doc.id}
                onPress={() => pickDoc(doc.id, doc.filename)}
                style={{
                  paddingVertical: 8,
                  paddingHorizontal: 12,
                  backgroundColor: (pickingSide === "A" && doc.id === docA) || (pickingSide === "B" && doc.id === docB) ? c.success + "18" : c.cardBg,
                  borderRadius: t.radii.sm,
                  marginBottom: 4,
                }}
              >
                <Text style={{ fontSize: 13, color: c.text }}>{doc.filename}</Text>
              </Pressable>
            ))
          )}
        </View>
      )}

      <Pressable
        onPress={handleCompare}
        disabled={loading || !docA || !docB}
        style={{
          backgroundColor: loading || !docA || !docB ? c.textMuted : c.primary,
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
          {loading ? "Comparing..." : "Compare Documents"}
        </Text>
      </Pressable>

      {result && (
        <View>
          {hasSimilarity && (
            <View style={{ marginBottom: 16 }}>
              <Text style={{ fontSize: 14, fontWeight: "700", color: c.text, marginBottom: 8 }}>
                Similarity Score
              </Text>
              <View style={{ backgroundColor: c.bgSecondary, borderRadius: t.radii.sm, height: 20, overflow: "hidden" }}>
                <View
                  style={{
                    backgroundColor: similarityScore > 70 ? c.success : similarityScore > 40 ? c.secondary : c.error,
                    height: "100%",
                    width: `${Math.min(similarityScore, 100)}%`,
                    borderRadius: t.radii.sm,
                    justifyContent: "center",
                    alignItems: "flex-end",
                    paddingRight: 8,
                  }}
                >
                  <Text style={{ color: "#FFFFFF", fontSize: 11, fontWeight: "700" }}>
                    {similarityScore}%
                  </Text>
                </View>
              </View>
            </View>
          )}

          <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: 10 }}>
            Comparison Results
          </Text>
          {isTablet ? (
            <View style={{ flexDirection: "row", gap: 12 }}>
              <View style={{ flex: 1, backgroundColor: c.cardBg, borderRadius: t.radii.sm, padding: 12, borderWidth: 1, borderColor: c.border }}>
                <Text style={{ fontSize: 13, fontWeight: "700", color: c.primary, marginBottom: 8 }}>
                  📄 {docAName}
                </Text>
                <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                  {result.doc_a_summary || result.document_a || JSON.stringify(result.a || {}, null, 2)}
                </Text>
              </View>
              <View style={{ flex: 1, backgroundColor: c.cardBg, borderRadius: t.radii.sm, padding: 12, borderWidth: 1, borderColor: c.border }}>
                <Text style={{ fontSize: 13, fontWeight: "700", color: c.primary, marginBottom: 8 }}>
                  📄 {docBName}
                </Text>
                <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                  {result.doc_b_summary || result.document_b || JSON.stringify(result.b || {}, null, 2)}
                </Text>
              </View>
            </View>
          ) : (
            <ScrollView horizontal showsHorizontalScrollIndicator={true}>
              <View style={{ flexDirection: "row", gap: 12 }}>
                <View style={{ width: width * 0.7, backgroundColor: c.cardBg, borderRadius: t.radii.sm, padding: 12, borderWidth: 1, borderColor: c.border }}>
                  <Text style={{ fontSize: 13, fontWeight: "700", color: c.primary, marginBottom: 8 }}>
                    📄 {docAName}
                  </Text>
                  <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                    {result.doc_a_summary || result.document_a || JSON.stringify(result.a || {}, null, 2)}
                  </Text>
                </View>
                <View style={{ width: width * 0.7, backgroundColor: c.cardBg, borderRadius: t.radii.sm, padding: 12, borderWidth: 1, borderColor: c.border }}>
                  <Text style={{ fontSize: 13, fontWeight: "700", color: c.primary, marginBottom: 8 }}>
                    📄 {docBName}
                  </Text>
                  <Text style={{ fontSize: 12, color: c.text, lineHeight: 18 }}>
                    {result.doc_b_summary || result.document_b || JSON.stringify(result.b || {}, null, 2)}
                  </Text>
                </View>
              </View>
            </ScrollView>
          )}

          {result.differences && (
            <View style={{ marginTop: 12 }}>
              <Text style={{ fontSize: 14, fontWeight: "700", color: c.text, marginBottom: 8 }}>
                Key Differences
              </Text>
              {(Array.isArray(result.differences) ? result.differences : []).map((diff: any, i: number) => (
                <View
                  key={i}
                  style={{
                    backgroundColor: c.secondary + "18",
                    borderRadius: t.radii.sm,
                    padding: 10,
                    marginBottom: 6,
                    borderLeftWidth: 3,
                    borderLeftColor: c.secondary,
                  }}
                >
                  <Text style={{ fontSize: 12, color: c.text }}>{typeof diff === "string" ? diff : JSON.stringify(diff)}</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </ScrollView>
  )
}
