import React from "react"
import { View, Text, Pressable, Image, Alert, Linking, Platform, ScrollView } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens, ThemeTokens } from "../theme/themeTokens"
import { fileIconInfo, truncate, downloadAndOpenDocument } from "../utils/documentUtils"
import { ReasoningBlock } from "./ReasoningBlock"

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

// ── Helpers (mirror web frontend SourceCitationCard.tsx) ──────────────────────

/** Convert raw filename into a human-readable title. */
function humanReadableTitle(filename?: string): string {
  if (!filename) return "Source document"
  const noExt = filename.replace(/\.[^.]+$/, "")
  // Strip leading numbers/prefixes like "2_" or "01-" that differ across project copies
  const noLeadingNum = noExt.replace(/^\d+[._-]+/, "")
  const unprefixed = noLeadingNum.replace(/^(ZETDC_|DocTel_|draft_|v\d+_)/i, "")
  const spaced = unprefixed.replace(/[_-]/g, " ")
  return spaced.replace(/\s+/g, " ").trim()
}

/** Derive a relevance label and color from the distance score. */
function relevanceInfo(distance?: number): { label: string; color: string } {
  if (distance === undefined || distance === null) return { label: "Source", color: "#888" }
  if (distance <= 0.3) return { label: "High relevance", color: "#16a34a" }
  if (distance <= 0.6) return { label: "Medium relevance", color: "#ca8a04" }
  return { label: "Low relevance", color: "#dc2626" }
}

// ── Single Citation Card (collapsible, per-section detail) ──────────────────

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
  // Optional prev/next section context for navigation
  prevSectionNum,
  nextSectionNum,
  onNavigateSection,
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
  prevSectionNum?: number | null
  nextSectionNum?: number | null
  onNavigateSection?: (chunkIndex: number) => void
}) {
  const { letter, color: iconColor } = fileIconInfo(cite.filename)
  const [expanded, setExpanded] = React.useState(false)
  const title = humanReadableTitle(cite.filename)
  const badge = relevanceInfo(cite.distance)
  const sectionNum = cite.chunk_index !== undefined ? cite.chunk_index + 1 : null

  return (
    <Pressable
      onPress={() => {
        setExpanded(!expanded)
      }}
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
      {/* ── Header (always visible) ── */}
      <View style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        paddingHorizontal: 8,
        paddingVertical: 6,
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

        {/* Human-readable title */}
        <Text
          style={{
            fontSize: 10,
            fontWeight: "600",
            color: isUser ? "#FFFFFFcc" : primary,
            flex: 1,
          }}
          numberOfLines={1}
        >
          {title}
        </Text>

        {/* Relevance badge */}
        <View style={{
          backgroundColor: badge.color + "18",
          borderRadius: 10,
          paddingHorizontal: 6,
          paddingVertical: 1,
        }}>
          <Text style={{ fontSize: 8, fontWeight: "600", color: badge.color }}>
            {badge.label}
          </Text>
        </View>

        {/* Chevron */}
        <Text style={{
          fontSize: 8,
          color: isUser ? "#FFFFFFaa" : textMuted,
          transform: expanded ? [{ rotate: "180deg" }] : [{ rotate: "0deg" }],
        }}>
          ▼
        </Text>
      </View>

      {/* ── Detail panel (conditionally rendered) ── */}
      {expanded && (
        <View style={{
          borderTopWidth: 1,
          borderTopColor: isUser ? "rgba(255,255,255,0.08)" : border,
        }}>
          {/* Section reference */}
          {sectionNum !== null && (
            <View style={{ paddingHorizontal: 8, paddingVertical: 3 }}>
              <Text style={{ fontSize: 9, color: isUser ? "#FFFFFFaa" : textMuted, fontWeight: "500" }}>
                Section {sectionNum}
              </Text>
            </View>
          )}

          {/* Text preview */}
          {cite.text && (
            <View style={{ paddingHorizontal: 8, paddingVertical: 4 }}>
              <Text
                style={{
                  fontSize: 10,
                  lineHeight: 15,
                  color: isUser ? "rgba(255,255,255,0.7)" : textSecondary,
                }}
                numberOfLines={5}
              >
                {truncate(cite.text, 500)}
              </Text>
            </View>
          )}

          {/* ── Section context navigation (prev / next) ── */}
          {(prevSectionNum || nextSectionNum) && (
            <View style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
              paddingHorizontal: 8,
              paddingVertical: 3,
              borderTopWidth: 1,
              borderTopColor: isUser ? "rgba(255,255,255,0.08)" : border,
            }}>
              {prevSectionNum != null && onNavigateSection && (
                <Pressable
                  onPress={() => onNavigateSection(prevSectionNum - 1)}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 2,
                    backgroundColor: isUser ? "rgba(255,255,255,0.1)" : cardBg,
                    borderRadius: 4,
                    paddingHorizontal: 5,
                    paddingVertical: 2,
                  }}
                >
                  <Text style={{ fontSize: 8, color: isUser ? "#FFFFFFaa" : primary, fontWeight: "600" }}>
                    ◀ Section {prevSectionNum}
                  </Text>
                </Pressable>
              )}
              {prevSectionNum != null && nextSectionNum != null && (
                <Text style={{ fontSize: 8, color: textMuted }}>|</Text>
              )}
              {nextSectionNum != null && onNavigateSection && (
                <Pressable
                  onPress={() => onNavigateSection(nextSectionNum - 1)}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 2,
                    backgroundColor: isUser ? "rgba(255,255,255,0.1)" : cardBg,
                    borderRadius: 4,
                    paddingHorizontal: 5,
                    paddingVertical: 2,
                  }}
                >
                  <Text style={{ fontSize: 8, color: isUser ? "#FFFFFFaa" : primary, fontWeight: "600" }}>
                    Section {nextSectionNum} ▶
                  </Text>
                </Pressable>
              )}
            </View>
          )}

          {/* Actions */}
          <View style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 4,
            paddingHorizontal: 8,
            paddingVertical: 4,
            borderTopWidth: 1,
            borderTopColor: isUser ? "rgba(255,255,255,0.08)" : border,
          }}>
            {cite.can_view !== false && (
              <Pressable
                onPress={() => handleCitationTap(cite, onOpenDocument)}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 3,
                  backgroundColor: isUser ? "rgba(255,255,255,0.12)" : cardBg,
                  borderRadius: 4,
                  paddingHorizontal: 6,
                  paddingVertical: 2,
                }}
              >
                <Text style={{ fontSize: 8, color: isUser ? "#FFFFFFaa" : primary, fontWeight: "600" }}>
                  👁 Preview
                </Text>
              </Pressable>
            )}
            {cite.can_download !== false && (
              <Pressable
                onPress={() => handleCitationTap(cite, onOpenDocument)}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 3,
                  backgroundColor: isUser ? "rgba(255,255,255,0.12)" : cardBg,
                  borderRadius: 4,
                  paddingHorizontal: 6,
                  paddingVertical: 2,
                }}
              >
                <Text style={{ fontSize: 8, color: isUser ? "#FFFFFFaa" : textSecondary, fontWeight: "600" }}>
                  ⬇ Download
                </Text>
              </Pressable>
            )}
          </View>
        </View>
      )}
    </Pressable>
  )
}

// ── Grouped Citations Section (mirrors web frontend ChatMessage.tsx pattern) ──

function GroupedCitations({
  citations,
  isUser,
  colors,
  onOpenDocument,
}: {
  citations: Citation[]
  isUser: boolean
  colors: ThemeTokens["colors"]
  onOpenDocument?: (documentId: string, filename?: string) => void
}) {
  const [expanded, setExpanded] = React.useState(false)
  const [activeSectionIdx, setActiveSectionIdx] = React.useState<number | null>(null)
  const scrollViewRef = React.useRef<ScrollView>(null)
  const sectionYOffsets = React.useRef<Map<number, number>>(new Map())

  // ── Normalized grouping key from a citation ──
  // Uses human-readable title so the same document always produces the same
  // key even when raw filenames differ slightly across project copies.
  function citationGroupKey(c: Citation): string {
    const title = humanReadableTitle(c.filename)
    if (title) return title.toLowerCase().replace(/\s+/g, " ")
    return c.document_id || c.filename || "unknown"
  }

  // ── Group by NORMALIZED title, merge same-title groups, deduplicate sections ──
  const groups = new Map<string, {
    title: string; sections: Citation[]; seenChunks: Set<number | undefined>; distance: number
  }>()
  let totalUniqueSections = 0
  for (const c of citations) {
    const key = citationGroupKey(c)
    const displayTitle = humanReadableTitle(c.filename) || "Source"

    // Before creating a new group, check if any EXISTING group has
    // the same display title (fuzzy merge for edge cases where
    // normalization still produces different keys for same doc).
    let group = groups.get(key)
    if (!group) {
      for (const [, existingGroup] of groups) {
        if (existingGroup.title === displayTitle) {
          group = existingGroup
          break
        }
      }
    }
    if (!group) {
      group = { title: displayTitle, sections: [], seenChunks: new Set(), distance: c.distance ?? 1 }
      groups.set(key, group)
    }
    // Deduplicate sections by unique chunk_index
    if (!group.seenChunks.has(c.chunk_index)) {
      group.seenChunks.add(c.chunk_index)
      group.sections.push(c)
      totalUniqueSections++
    }
    group.distance = Math.min(group.distance, c.distance ?? 1)
  }
  const groupEntries = Array.from(groups.entries())
  const totalDocs = groupEntries.length

  return (
    <View style={{
      marginTop: 10,
      paddingTop: 8,
      borderTopWidth: 1,
      borderTopColor: isUser ? "rgba(255,255,255,0.2)" : colors.border,
    }}>
      {/* ── Section header (always visible) ── */}
      <Pressable
        onPress={() => setExpanded(!expanded)}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 6,
          marginBottom: 6,
        }}
      >
        <Text style={{ fontSize: 11 }}>📄</Text>
        <Text style={{
          fontSize: 9,
          color: isUser ? "rgba(255,255,255,0.6)" : colors.textMuted,
          fontWeight: "700",
          textTransform: "uppercase",
          letterSpacing: 0.5,
          flex: 1,
        }}>
          Sources ({totalDocs} document{totalDocs !== 1 ? "s" : ""}, {totalUniqueSections} section{totalUniqueSections !== 1 ? "s" : ""})
        </Text>
        <Text style={{
          fontSize: 8,
          color: isUser ? "rgba(255,255,255,0.5)" : colors.textMuted,
          transform: expanded ? [{ rotate: "180deg" }] : [{ rotate: "0deg" }],
        }}>
          ▼
        </Text>
      </Pressable>

      {/* ── Grouped cards (shown when expanded) ── */}
      {expanded && groupEntries.map(([key, group]) => (
        <View
          key={key}
          style={{
            backgroundColor: isUser ? "rgba(255,255,255,0.08)" : colors.surfaceActive,
            borderRadius: 10,
            padding: 10,
            borderWidth: 1,
            borderColor: isUser ? "rgba(255,255,255,0.1)" : colors.border,
            marginBottom: 8,
          }}
        >
          {/* Document title */}
          <View style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            marginBottom: 6,
          }}>
            <Text style={{ fontSize: 11 }}>📄</Text>
            <Text style={{
              fontSize: 11,
              fontWeight: "600",
              color: isUser ? "#FFFFFFdd" : colors.text,
              flex: 1,
            }} numberOfLines={1}>
              {group.title}
            </Text>
          </View>

          {/* Section badges */}
          <View style={{
            flexDirection: "row",
            flexWrap: "wrap",
            gap: 4,
          }}>
            {group.sections.map((s, si) => (
              <View key={si} style={{
                backgroundColor: isUser ? "rgba(255,255,255,0.12)" : colors.primary + "18",
                borderRadius: 4,
                paddingHorizontal: 6,
                paddingVertical: 2,
              }}>
                <Text style={{
                  fontSize: 9,
                  fontWeight: "500",
                  color: isUser ? "#FFFFFFbb" : colors.primary,
                }}>
                  Section {s.chunk_index !== undefined ? s.chunk_index + 1 : "?"}
                </Text>
              </View>
            ))}
          </View>

          {/* Relevance badge */}
          {(() => {
            const badge = relevanceInfo(group.distance)
            if (group.distance <= 0.6) {
              return (
                <Text style={{
                  marginTop: 6,
                  fontSize: 9,
                  fontWeight: "500",
                  color: group.distance <= 0.3 ? "#16a34a" : "#ca8a04",
                }}>
                  {badge.label}
                </Text>
              )
            }
            return null
          })()}

          {/* Per-section detail cards in a scrollable container with prev/next navigation */}
          <ScrollView
            ref={scrollViewRef}
            nestedScrollEnabled
            style={{ maxHeight: 300 }}
            showsVerticalScrollIndicator={true}
          >
            {group.sections.map((s, si) => {
              const prevSec = si > 0 ? group.sections[si - 1].chunk_index ?? (si - 1) : null
              const nextSec = si < group.sections.length - 1 ? group.sections[si + 1].chunk_index ?? (si + 1) : null

              return (
                <View
                  key={si}
                  style={{ marginTop: 4 }}
                  onLayout={(e) => {
                    // Accumulate Y offset for scroll navigation
                    let offset = 0
                    for (let i = 0; i < si; i++) {
                      offset += sectionYOffsets.current.get(i) || 0
                    }
                    sectionYOffsets.current.set(si, e.nativeEvent.layout.height + 4)
                  }}
                >
                  <CitationCard
                    cite={s}
                    isUser={isUser}
                    cardBg={colors.cardBg}
                    border={colors.border}
                    primary={colors.primary}
                    textColor={colors.text}
                    textMuted={colors.textMuted}
                    textSecondary={colors.textSecondary}
                    surfaceActive={colors.surfaceActive}
                    onOpenDocument={onOpenDocument}
                    prevSectionNum={prevSec !== null ? prevSec + 1 : null}
                    nextSectionNum={nextSec !== null ? nextSec + 1 : null}
                    onNavigateSection={(chunkIndex) => {
                      // Find the target section index by matching chunk_index
                      const targetIdx = group.sections.findIndex(s2 => s2.chunk_index === chunkIndex)
                      if (targetIdx >= 0) {
                        setActiveSectionIdx(targetIdx)
                        // Accumulate scroll offset to the target section
                        let scrollToY = 0
                        for (let i = 0; i < targetIdx; i++) {
                          scrollToY += sectionYOffsets.current.get(i) || 0
                        }
                        scrollViewRef.current?.scrollTo({ y: scrollToY, animated: true })
                      }
                    }}
                  />
                </View>
              )
            })}
          </ScrollView>
        </View>
      ))}
    </View>
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
              <View style={{ flex: 1, flexShrink: 1 }}>
                <Text style={{
                  color: c.error, fontSize: 13, marginBottom: 6,
                  flexWrap: "wrap",
                }}>{msg.content}</Text>
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

          {/* ── Collapsible Sources section — grouped by document (mirrors web frontend) ── */}
          {msg.citations && msg.citations.length > 0 && (
            <GroupedCitations
              citations={msg.citations}
              isUser={isUser}
              colors={c}
              onOpenDocument={onOpenDocument}
            />
          )}

          {/* Reasoning / Thinking block — collapsible, matching web frontend */}
          {!isUser && msg.reasoning && <ReasoningBlock reasoning={msg.reasoning} colors={c} />}
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
