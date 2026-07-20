import React from "react"
import { View, Text, Pressable, Image, Alert, Linking, Platform } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"
import { fileIconInfo, truncate, chunkLabel, downloadAndOpenDocument } from "../utils/documentUtils"

interface Citation {
  document_id?: string | null
  filename?: string
  chunk_index?: number
  text?: string
  snippet?: string
  full_text_available?: boolean
  distance?: number
  can_view?: boolean
  can_download?: boolean
  open_url?: string
  download_url?: string
  preview_url?: string
  source_type?: string
  project_id?: string | number
}

interface AttachmentMeta {
  name: string
  type: "image" | "document" | "audio"
  dataUrl?: string
}

export interface Message {
  id: number | string
  role: "user" | "assistant" | "system"
  content: string
  reasoning?: string
  uiStatus: "waiting" | "streaming" | "done" | "error"
  citations: Citation[]
  createdAt?: string
  attachment?: AttachmentMeta | null
}

interface ChatMessageProps {
  msg: Message
  prevMsg?: Message
  onRetry: (msg: Message) => void
  formatTime: (iso?: string) => string
  formatDate: (iso?: string) => string
  onOpenDocument?: (documentId: string, filename?: string) => void
}

const THIRTY_MIN_MS = 30 * 60 * 1000

const shouldShowDateSeparator = (prev: Message, curr: Message): boolean => {
  try {
    const p = new Date(prev.createdAt!).getTime()
    const c = new Date(curr.createdAt!).getTime()
    return !isNaN(p) && !isNaN(c) && c - p > THIRTY_MIN_MS
  } catch {
    return false
  }
}

/** Handle tapping on a citation */
function handleCitationTap(cite: Citation, onOpenDocument?: (documentId: string, filename?: string) => void) {
  // If we have a document_id and an onOpenDocument callback, use it
  if (cite.document_id && onOpenDocument) {
    onOpenDocument(cite.document_id, cite.filename)
    return
  }

  // If we have a preview_url, open it in browser
  if (cite.preview_url) {
    Linking.openURL(cite.preview_url).catch(() => {})
    return
  }

  // If we can view and have an open_url, open it
  if (cite.can_view && cite.open_url) {
    Linking.openURL(cite.open_url).catch(() => {})
    return
  }

  // If we have a document_id, try download/open directly
  if (cite.document_id) {
    downloadAndOpenDocument(cite.document_id, cite.filename, cite.preview_url)
    return
  }

  // Last resort: show the snippet in an alert
  Alert.alert(
    cite.filename || "Source",
    truncate(cite.text || cite.snippet || "No preview available.", 500),
    [{ text: "OK" }],
  )
}

// ── Single Citation Card ──────────────────────────────────────────────────────

function CitationCard({
  cite,
  isUser,
  cardBg,
  border,
  primary,
  textColor,
  textMuted,
  textSecondary,
  surfaceActive,
  onOpenDocument,
}: {
  cite: Citation
  isUser: boolean
  cardBg: string
  border: string
  primary: string
  textColor: string
  textMuted: string
  textSecondary: string
  surfaceActive: string
  onOpenDocument?: (documentId: string, filename?: string) => void
}) {
  const { letter, color: iconColor } = fileIconInfo(cite.filename)
  const distLabel = cite.distance !== undefined ? `rel: ${cite.distance.toFixed(3)}` : null

  return (
    <Pressable
      onPress={() => handleCitationTap(cite, onOpenDocument)}
      style={({ pressed }) => ({
        backgroundColor: isUser ? "rgba(255,255,255,0.1)" : surfaceActive,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: isUser ? "rgba(255,255,255,0.08)" : border,
        marginBottom: 6,
        overflow: "hidden",
        opacity: pressed ? 0.8 : 1,
      })}
    >
      {/* Header */}
      <View style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        paddingHorizontal: 8,
        paddingVertical: 6,
        borderBottomWidth: 1,
        borderBottomColor: isUser ? "rgba(255,255,255,0.08)" : border,
      }}>
        {/* File icon */}
        <View style={{
          width: 22,
          height: 22,
          borderRadius: 4,
          backgroundColor: iconColor + "22",
          alignItems: "center",
          justifyContent: "center",
        }}>
          <Text style={{ fontSize: 10, fontWeight: "700", color: iconColor }}>{letter}</Text>
        </View>

        {/* Filename */}
        <Text
          style={{
            fontSize: 10,
            fontWeight: "600",
            color: isUser ? "#FFFFFFcc" : primary,
            flex: 1,
          }}
          numberOfLines={1}
        >
          {cite.filename || "Source document"}
        </Text>

        {/* Chunk badge */}
        {cite.chunk_index !== undefined && (
          <View style={{
            backgroundColor: isUser ? "rgba(255,255,255,0.15)" : cardBg,
            borderRadius: 4,
            paddingHorizontal: 5,
            paddingVertical: 1,
          }}>
            <Text style={{ fontSize: 9, fontWeight: "600", color: isUser ? "#FFFFFFaa" : textMuted }}>
              {chunkLabel(cite.chunk_index)}
            </Text>
          </View>
        )}
      </View>

      {/* Text preview */}
      {cite.text && (
        <View style={{ paddingHorizontal: 8, paddingVertical: 4 }}>
          <Text
            style={{
              fontSize: 10,
              lineHeight: 15,
              color: isUser ? "rgba(255,255,255,0.7)" : textSecondary,
            }}
            numberOfLines={2}
          >
            {truncate(cite.text)}
          </Text>
        </View>
      )}

      {/* Footer: distance + actions */}
      {(distLabel || cite.can_view !== false || cite.can_download !== false) && (
        <View style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 4,
          paddingHorizontal: 8,
          paddingVertical: 4,
          borderTopWidth: 1,
          borderTopColor: isUser ? "rgba(255,255,255,0.08)" : border,
        }}>
          {distLabel && (
            <Text style={{
              fontSize: 8.5,
              color: isUser ? "rgba(255,255,255,0.5)" : textMuted,
              fontWeight: "500",
              marginRight: "auto",
            }}>
              {distLabel}
            </Text>
          )}

          {cite.can_view !== false && (
            <View style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 3,
              backgroundColor: isUser ? "rgba(255,255,255,0.12)" : cardBg,
              borderRadius: 4,
              paddingHorizontal: 6,
              paddingVertical: 2,
            }}>
              <Text style={{ fontSize: 8, color: isUser ? "#FFFFFFaa" : primary, fontWeight: "600" }}>
                👁 Preview
              </Text>
            </View>
          )}

          {cite.can_download !== false && (
            <View style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 3,
              backgroundColor: isUser ? "rgba(255,255,255,0.12)" : cardBg,
              borderRadius: 4,
              paddingHorizontal: 6,
              paddingVertical: 2,
            }}>
              <Text style={{ fontSize: 8, color: isUser ? "#FFFFFFaa" : textSecondary, fontWeight: "600" }}>
                ⬇ Download
              </Text>
            </View>
          )}

          {cite.full_text_available && cite.can_view !== false && (
            <View style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 3,
              backgroundColor: isUser ? "rgba(255,255,255,0.12)" : cardBg,
              borderRadius: 4,
              paddingHorizontal: 6,
              paddingVertical: 2,
            }}>
              <Text style={{ fontSize: 8, color: isUser ? "#FFFFFF88" : textMuted, fontWeight: "600" }}>
                📄 Full
              </Text>
            </View>
          )}
        </View>
      )}
    </Pressable>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ChatMessage({ msg, prevMsg, onRetry, formatTime, formatDate, onOpenDocument }: ChatMessageProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors

  const isUser = msg.role === "user"
  const isWaiting = msg.uiStatus === "waiting"
  const isError = msg.uiStatus === "error"
  const showAvatar = !prevMsg || prevMsg.role !== msg.role

  return (
    <View style={{ marginBottom: showAvatar ? 20 : 6 }}>
      {/* Date separator */}
      {prevMsg && msg.createdAt && prevMsg.createdAt && shouldShowDateSeparator(prevMsg, msg) && (
        <View style={{ alignItems: "center", marginBottom: 14 }}>
          <View style={{
            backgroundColor: c.cardBg,
            borderRadius: 12,
            paddingHorizontal: 12,
            paddingVertical: 4,
            borderWidth: 1,
            borderColor: c.border,
          }}>
            <Text style={{ fontSize: 10, color: c.textMuted }}>{formatDate(msg.createdAt)}</Text>
          </View>
        </View>
      )}

      <View style={{
        flexDirection: isUser ? "row-reverse" : "row",
        alignItems: "flex-start",
        gap: 10,
      }}>
        {/* Avatar */}
        {showAvatar ? (
          <View style={{
            width: 32,
            height: 32,
            borderRadius: 16,
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            ...(isUser ? {
              backgroundColor: c.primary,
              borderWidth: 2,
              borderColor: c.primary + "60",
            } : {
              backgroundColor: c.surface,
              borderWidth: 1,
              borderColor: c.border,
            }),
          }}>
            <Text style={{ fontSize: 12, color: isUser ? "#FFFFFF" : c.textSecondary }}>
              {isUser ? "👤" : "✦"}
            </Text>
          </View>
        ) : (
          <View style={{ width: 32, flexShrink: 0 }} />
        )}

        {/* Message bubble */}
        <View style={{
          maxWidth: "80%",
          minWidth: 60,
          padding: isWaiting ? 12 : 12,
          borderRadius: 16,
          borderBottomRightRadius: isUser ? 4 : 16,
          borderBottomLeftRadius: isUser ? 16 : 4,
          backgroundColor: isError
            ? c.cardBg
            : isUser
              ? c.primary
              : c.cardBg,
          borderWidth: isUser ? 0 : 1,
          borderColor: isUser ? "transparent" : c.border,
        }}>
          {/* Attachment preview */}
          {msg.attachment && msg.role === "user" && msg.attachment.type === "image" && msg.attachment.dataUrl && (
            <Image
              source={{ uri: msg.attachment.dataUrl }}
              style={{ width: "100%", height: 120, borderRadius: 8, marginBottom: 8 }}
              resizeMode="cover"
            />
          )}
          {msg.attachment && msg.role === "user" && msg.attachment.type !== "image" && (
            <View style={{
              flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8,
              backgroundColor: isUser ? "rgba(255,255,255,0.15)" : c.surfaceActive,
              borderRadius: 8, padding: 6,
            }}>
              <Text style={{ fontSize: 14 }}>{msg.attachment.type === "audio" ? "🎵" : "📎"}</Text>
              <Text style={{ fontSize: 11, color: isUser ? "#FFFFFF" : c.text, fontWeight: "500" }} numberOfLines={1}>
                {msg.attachment.name}
              </Text>
            </View>
          )}

          {/* Waiting animation */}
          {isWaiting ? (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              {[0, 1, 2].map((i) => (
                <View key={i} style={{
                  width: 8, height: 8, borderRadius: 4,
                  backgroundColor: c.primary,
                  opacity: 0.3 + i * 0.3,
                }} />
              ))}
              <Text style={{ fontSize: 11, color: c.textMuted, marginLeft: 4 }}>Thinking...</Text>
            </View>
          ) : isError ? (
            <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6 }}>
              <Text style={{ fontSize: 14 }}>⚠️</Text>
              <View style={{ flex: 1 }}>
                <Text style={{ color: c.error, fontSize: 13, marginBottom: 6 }}>{msg.content}</Text>
                <Pressable
                  onPress={() => onRetry(msg)}
                  style={{
                    backgroundColor: c.surfaceActive,
                    borderRadius: 6,
                    paddingHorizontal: 10,
                    paddingVertical: 4,
                    alignSelf: "flex-start",
                  }}
                >
                  <Text style={{ color: c.primary, fontSize: 11, fontWeight: "600" }}>Retry</Text>
                </Pressable>
              </View>
            </View>
          ) : msg.uiStatus === "streaming" ? (
            <Text style={{ color: c.text, fontSize: 14, lineHeight: 20 }}>
              {msg.content}
              <Text style={{ color: c.primary, opacity: 0.7 }}>|</Text>
            </Text>
          ) : (
            <Text style={{
              color: isUser ? "#FFFFFF" : c.text,
              fontSize: 14,
              lineHeight: 20,
            }}>
              {msg.content}
            </Text>
          )}

          {/* ── Tappable Citations ── */}
          {msg.citations && msg.citations.length > 0 && (
            <View style={{
              marginTop: 10,
              paddingTop: 8,
              borderTopWidth: 1,
              borderTopColor: isUser ? "rgba(255,255,255,0.2)" : c.border,
            }}>
              <Text style={{
                fontSize: 9,
                color: isUser ? "rgba(255,255,255,0.6)" : c.textMuted,
                fontWeight: "700",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: 0.5,
              }}>
                Sources ({msg.citations.length})
              </Text>
              {msg.citations.map((cite, ci) => (
                <CitationCard
                  key={ci}
                  cite={cite}
                  isUser={isUser}
                  cardBg={c.cardBg}
                  border={c.border}
                  primary={c.primary}
                  textColor={c.text}
                  textMuted={c.textMuted}
                  textSecondary={c.textSecondary}
                  surfaceActive={c.surfaceActive}
                  onOpenDocument={onOpenDocument}
                />
              ))}
              {msg.citations.length > 3 && (
                <Text style={{
                  fontSize: 9,
                  color: isUser ? "rgba(255,255,255,0.5)" : c.textMuted,
                  fontWeight: "500",
                  textAlign: "center",
                  marginTop: 2,
                }}>
                  +{msg.citations.length - 3} more sources
                </Text>
              )}
            </View>
          )}

          {/* Reasoning */}
          {!isUser && msg.reasoning && (
            <View style={{ marginTop: 10 }}>
              <Text style={{ fontSize: 10, color: c.textMuted, fontWeight: "600" }}>
                💭 Reasoning
              </Text>
              <Text style={{
                fontSize: 11,
                color: c.textSecondary,
                fontStyle: "italic",
                marginTop: 4,
                lineHeight: 16,
              }}>
                {msg.reasoning}
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Timestamp */}
      {msg.createdAt && (
        <View style={{
          flexDirection: "row",
          marginTop: 4,
          justifyContent: isUser ? "flex-end" : "flex-start",
          paddingHorizontal: 42,
        }}>
          <Text style={{ fontSize: 9, color: c.textMuted, opacity: 0.55 }}>
            {formatTime(msg.createdAt)}
          </Text>
        </View>
      )}
    </View>
  )
}
