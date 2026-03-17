import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView } from "react-native"
import { colors } from "../theme/colors"
import {
  chatWithDocument,
  getDocumentPrompts,
  getUserHistory,
  getSummaryHistory,
  getDocumentAnalysis,
} from "../api/client"
import { ChatResponse, UserHistoryEntry, SummaryHistoryEntry, DocumentAnalysisResponse } from "../types/api"

interface ChatScreenProps {
  documentId: string
}

export const ChatScreen: React.FC<ChatScreenProps> = ({ documentId }) => {
  const [prompts, setPrompts] = useState<string[]>([])
  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState<ChatResponse[]>([])
  const [history, setHistory] = useState<UserHistoryEntry[]>([])
  const [summaryHistory, setSummaryHistory] = useState<SummaryHistoryEntry[]>([])
  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingAnalysis, setLoadingAnalysis] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    setMessages([])
    setError("")
    const load = async () => {
      try {
        setLoadingAnalysis(true)
        const promptRes = await getDocumentPrompts(documentId)
        setPrompts(promptRes.prompts)
        const [historyRes, summaryRes, analysisRes] = await Promise.all([
          getUserHistory(),
          getSummaryHistory(),
          getDocumentAnalysis(documentId).catch(() => null)
        ])
        setHistory(historyRes.history)
        setSummaryHistory(summaryRes.history)
        if (analysisRes) {
          setAnalysis(analysisRes)
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to load chat data.")
      } finally {
        setLoadingAnalysis(false)
      }
    }
    load()
  }, [documentId])

  const handleAsk = async (q: string) => {
    if (!q.trim()) return
    setLoading(true)
    setError("")
    try {
      const res = await chatWithDocument(documentId, {
        question: q,
        session_id: undefined,
        history: undefined,
      })
      setMessages((prev) => [...prev, res])
      setQuestion("")
    } catch (e: any) {
      setError(e.message ?? "Failed to get answer.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 18, fontWeight: "600", color: colors.textPrimary }}>
        DocIntel Chat
      </Text>
      <Text style={{ fontSize: 13, color: colors.textMuted, marginBottom: 12 }}>
        Ask questions about the document. Your EC history is saved.
      </Text>

      {error ? <Text style={{ color: colors.danger }}>{error}</Text> : null}

      <ScrollView style={{ flex: 1, marginBottom: 12 }}>
        {loadingAnalysis && (
          <Text style={{ color: colors.textMuted, marginBottom: 12 }}>Loading analysis...</Text>
        )}

        {analysis && (
          <View style={{ gap: 16, marginBottom: 24 }}>
            <View style={cardStyle}>
              <View style={cardHeaderStyle}>
                <Text style={cardTitleStyle}>Executive Summary</Text>
                <View style={pillStyle}>
                  <Text style={pillTextStyle}>AI generated</Text>
                </View>
              </View>
              <Text style={bodyTextStyle}>{analysis.executive_summary}</Text>
            </View>

            <View style={cardStyle}>
              <View style={cardHeaderStyle}>
                <Text style={cardTitleStyle}>Detailed Summary</Text>
              </View>
              {analysis.detailed_summary.map((item, idx) => (
                <View key={idx} style={{ flexDirection: "row", marginBottom: 4, paddingRight: 10 }}>
                  <Text style={{ color: colors.textPrimary, marginRight: 6 }}>•</Text>
                  <Text style={bodyTextStyle}>{item}</Text>
                </View>
              ))}
            </View>

            <View style={cardStyle}>
              <View style={cardHeaderStyle}>
                <Text style={cardTitleStyle}>Key Insights</Text>
              </View>

              <View style={{ marginBottom: 12 }}>
                <Text style={sectionLabelStyle}>TOPICS</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                  {analysis.topics.map((topic) => (
                    <View key={topic} style={chipBlueStyle}>
                      <Text style={{ color: colors.primaryDark, fontSize: 12 }}>{topic}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View style={{ marginBottom: 12 }}>
                <Text style={sectionLabelStyle}>ENTITIES</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                  {analysis.entities.map((entity) => (
                    <View key={entity} style={chipOutlineStyle}>
                      <Text style={{ color: colors.primaryDark, fontSize: 12 }}>{entity}</Text>
                    </View>
                  ))}
                </View>
              </View>

              {(analysis.key_entities?.dates?.length ?? 0) > 0 && (
                <View style={{ marginBottom: 12 }}>
                  <Text style={sectionLabelStyle}>DATES</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                    {analysis.key_entities?.dates?.map((date) => (
                      <View key={date} style={chipOutlineStyle}>
                        <Text style={{ color: colors.primaryDark, fontSize: 12 }}>{date}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}

              {(analysis.key_entities?.locations?.length ?? 0) > 0 && (
                <View style={{ marginBottom: 12 }}>
                  <Text style={sectionLabelStyle}>LOCATIONS</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                    {analysis.key_entities?.locations?.map((loc) => (
                      <View key={loc} style={chipOutlineStyle}>
                        <Text style={{ color: colors.primaryDark, fontSize: 12 }}>{loc}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}

              {(analysis.action_items?.length ?? 0) > 0 && (
                <View style={{ marginBottom: 12 }}>
                  <Text style={sectionLabelStyle}>ACTION ITEMS</Text>
                  {analysis.action_items?.slice(0, 6).map((item, idx) => (
                    <View key={idx} style={{ flexDirection: "row", marginBottom: 4, paddingRight: 10 }}>
                      <Text style={{ color: colors.textPrimary, marginRight: 6 }}>•</Text>
                      <Text style={bodyTextStyle}>{item}</Text>
                    </View>
                  ))}
                </View>
              )}

              <View>
                <Text style={sectionLabelStyle}>SENTIMENT</Text>
                <View
                  style={[
                    pillStyle,
                    {
                      alignSelf: "flex-start",
                      backgroundColor:
                        analysis.sentiment.toLowerCase() === "negative" ||
                          analysis.sentiment.toLowerCase() === "urgent"
                          ? colors.danger
                          : colors.primary,
                    },
                  ]}
                >
                  <Text style={pillTextStyle}>{analysis.sentiment}</Text>
                </View>
              </View>

            </View>
          </View>
        )}

        <View style={cardStyle}>
          <View style={cardHeaderStyle}>
            <Text style={cardTitleStyle}>Copilot Chat History</Text>
          </View>

          {summaryHistory.length > 0 && (
            <View style={{ marginBottom: 16 }}>
              <Text style={{ fontSize: 13, color: colors.textMuted, marginBottom: 6 }}>
                Summary History
              </Text>
              {summaryHistory.map((entry, idx) => (
                <View key={`${entry.document_id}-${idx}`} style={historyCardStyle}>
                  <Text style={{ fontSize: 12, color: colors.textMuted }}>
                    {entry.document_id}
                  </Text>
                  <Text style={{ marginTop: 4, color: colors.textPrimary }}>
                    {entry.executive_summary}
                  </Text>
                </View>
              ))}
            </View>
          )}
          {history.length > 0 && (
            <View style={{ marginBottom: 16 }}>
              <Text style={{ fontSize: 13, color: colors.textMuted, marginBottom: 6 }}>
                Previous Questions
              </Text>
              {history.map((entry, idx) => (
                <View key={`${entry.document_id}-${idx}`} style={historyCardStyle}>
                  <Text style={{ fontSize: 12, color: colors.textMuted }}>
                    {entry.document_id}
                  </Text>
                  <Text style={{ marginTop: 4, color: colors.textPrimary }}>
                    {entry.question}
                  </Text>
                  <Text style={{ marginTop: 4, color: colors.textMuted }}>
                    {entry.answer}
                  </Text>
                </View>
              ))}
            </View>
          )}

          {messages.map((msg, idx) => (
            <View key={`${msg.document_id}-${idx}`} style={{ marginBottom: 12 }}>
              <View style={userBubbleStyle}>
                <Text style={{ color: "#FFFFFF" }}>{msg.question}</Text>
              </View>
              <View style={assistantBubbleStyle}>
                <Text style={{ color: colors.textPrimary }}>{msg.answer}</Text>
                <View style={{ marginTop: 6, gap: 4 }}>
                  {msg.sources.map((src) => (
                    <Text key={src.chunk_id} style={{ fontSize: 11, color: colors.textMuted }}>
                      Source: {src.chunk_id}
                    </Text>
                  ))}
                </View>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>

      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        {prompts.map((p) => (
          <Pressable key={p} onPress={() => handleAsk(p)} style={promptChipStyle}>
            <Text style={{ color: colors.primaryDark, fontSize: 12 }}>{p}</Text>
          </Pressable>
        ))}
      </View>

      <View style={{ flexDirection: "row", gap: 8 }}>
        <TextInput
          value={question}
          onChangeText={setQuestion}
          placeholder="Ask a question"
          style={[inputStyle, { flex: 1 }]}
        />
        <Pressable onPress={() => handleAsk(question)} style={primaryButtonStyle} disabled={loading}>
          <Text style={{ color: "#FFFFFF" }}>{loading ? "..." : "Send"}</Text>
        </Pressable>
      </View>
    </View>
  )
}

const inputStyle = {
  borderWidth: 1,
  borderColor: colors.border,
  borderRadius: 8,
  paddingHorizontal: 12,
  paddingVertical: 8,
  backgroundColor: "#FFFFFF",
} as const

const primaryButtonStyle = {
  backgroundColor: colors.primary,
  paddingHorizontal: 16,
  borderRadius: 8,
  alignItems: "center",
  justifyContent: "center",
} as const

const promptChipStyle = {
  backgroundColor: "#FFF5D6",
  borderWidth: 1,
  borderColor: colors.secondary,
  paddingHorizontal: 10,
  paddingVertical: 6,
  borderRadius: 14,
} as const

const userBubbleStyle = {
  alignSelf: "flex-end",
  backgroundColor: colors.primary,
  padding: 10,
  borderRadius: 12,
  marginBottom: 6,
} as const

const assistantBubbleStyle = {
  alignSelf: "flex-start",
  backgroundColor: colors.surface,
  borderWidth: 1,
  borderColor: colors.border,
  padding: 10,
  borderRadius: 12,
} as const

const historyCardStyle = {
  backgroundColor: "#FFFFFF",
  borderWidth: 1,
  borderColor: colors.border,
  padding: 10,
  borderRadius: 10,
  marginBottom: 8,
} as const

const cardStyle = {
  backgroundColor: colors.surface,
  borderRadius: 12,
  padding: 16,
  borderWidth: 1,
  borderColor: colors.border,
} as const

const cardHeaderStyle = {
  flexDirection: "row" as const,
  justifyContent: "space-between" as const,
  alignItems: "center" as const,
  marginBottom: 12,
}

const cardTitleStyle = {
  fontWeight: "600" as const,
  color: colors.textPrimary,
  fontSize: 16,
}

const bodyTextStyle = {
  fontSize: 14,
  color: colors.textPrimary,
  lineHeight: 20,
}

const sectionLabelStyle = {
  fontSize: 12,
  fontWeight: "600" as const,
  color: colors.textMuted,
  marginBottom: 6,
}

const chipBlueStyle = {
  paddingHorizontal: 10,
  paddingVertical: 4,
  borderRadius: 16,
  backgroundColor: "#E7F0FF",
}

const chipOutlineStyle = {
  paddingHorizontal: 10,
  paddingVertical: 4,
  borderRadius: 16,
  borderWidth: 1,
  borderColor: colors.primary,
  backgroundColor: colors.surface,
}

const pillStyle = {
  paddingHorizontal: 8,
  paddingVertical: 4,
  borderRadius: 999,
  backgroundColor: "#FFE6B7",
}

const pillTextStyle = {
  fontSize: 11,
  color: colors.primaryDark,
  fontWeight: "600" as const,
}
