import React, { useEffect, useState, useCallback, useMemo, useRef } from "react"
import { View, Text, TextInput, Pressable, ScrollView, Animated, useWindowDimensions, Alert } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getWorkspaces, getMyDocuments, getChatSessions, createProject, updateProject, deleteProject } from "../api/client"
import { AnimatedRobot } from "../components/AnimatedRobot"

interface Workspace {
  id: string
  name: string
  document_count?: number
  created_at?: string
  updated_at?: string
}

interface DocItem {
  id: string
  filename: string
  project_id: string | null
  project_name: string
  status: string
  created_at: string
}

interface SessionItem {
  session_id: string
  project_id: string | null
  document_id: string | null
  model: string
  started_at: string
  updated_at?: string
  title?: string
}

type TimelineItem = {
  kind: "document"
  data: DocItem
} | {
  kind: "session"
  data: SessionItem
}

const FILE_ICON: Record<string, string> = {
  pdf: "📕", docx: "📘", doc: "📘", txt: "📄",
  xlsx: "📊", xls: "📊", csv: "📊",
  pptx: "📙", ppt: "📙",
  png: "🖼️", jpg: "🖼️", jpeg: "🖼️",
}

function fileIcon(filename: string): string {
  const ext = (filename.split(".").pop() || "").toLowerCase()
  return FILE_ICON[ext] || "📎"
}

function statusColor(status: string, colors: any): string {
  const map: Record<string, string> = {
    ready: colors.success, completed: colors.success, processed: colors.success,
    processing: colors.warning, queued: colors.warning, ingested: colors.secondary,
    uploaded: colors.primary, failed: colors.error, error: colors.error,
  }
  return map[status?.toLowerCase()] ?? colors.textMuted
}

function formatDate(iso: string): string {
  if (!iso) return "—"
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) } catch { return iso.slice(0, 10) }
}

function formatDateTime(iso: string): string {
  if (!iso) return "—"
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) } catch { return iso.slice(0, 16) }
}

function SkeletonCard() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const opacity = useRef(new Animated.Value(0.4)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 600, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 600, useNativeDriver: true }),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [])
  return (
    <Animated.View style={{
      opacity, backgroundColor: t.colors.bgSecondary,
      borderRadius: t.radii.md, padding: t.spacing.md,
      marginBottom: t.spacing.sm, height: 80,
    }} />
  )
}

interface WorkspacesScreenProps {
  onOpenDocument?: (id: string) => void
  onNavigate?: (path: string) => void
  onSelectProject?: (proj: any) => void
}

const PAGE_SIZE = 20

export function WorkspacesScreen({ onOpenDocument, onNavigate, onSelectProject }: WorkspacesScreenProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [documents, setDocuments] = useState<DocItem[]>([])
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [expandedRepos, setExpandedRepos] = useState<Record<string, boolean>>({})
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [showUncategorized, setShowUncategorized] = useState(true)
  const [docPage, setDocPage] = useState(1)
  const [docTotal, setDocTotal] = useState(0)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [wsRes, docsRes, sessRes] = await Promise.all([
        getWorkspaces(),
        getMyDocuments().catch(() => ({ documents: [], total: 0 })),
        getChatSessions().catch(() => ({ sessions: [] })),
      ])
      setWorkspaces(wsRes.projects || wsRes.workspaces || [])
      setDocuments(docsRes.documents || [])
      setDocTotal((docsRes as any).total || (docsRes.documents || []).length)
      setSessions(sessRes.sessions || [])
    } catch (e: any) {
      setError(e.message || "Failed to load workspace data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) return
    const duplicate = workspaces.find((w) => w.name.toLowerCase().trim() === name.toLowerCase())
    if (duplicate) { setCreateError(`A workspace named "${duplicate.name}" already exists`); return }
    try {
      setCreating(true)
      setCreateError(null)
      await createProject({ name })
      setNewName("")
      await fetchAll()
    } catch (e: any) {
      setCreateError(e.message || "Failed to create workspace")
    } finally {
      setCreating(false)
    }
  }

  const handleRename = async (id: string) => {
    const name = editName.trim()
    if (!name) { setEditingId(null); return }
    const duplicate = workspaces.find((w) => w.id !== id && w.name.trim().toLowerCase() === name.toLowerCase())
    if (duplicate) { setError(`A workspace named "${duplicate.name}" already exists`); return }
    try {
      setRenaming(id)
      await updateProject(id, { name })
      setEditingId(null)
      await fetchAll()
    } catch (e: any) {
      setError(e.message || "Failed to rename")
    } finally {
      setRenaming(null)
    }
  }

  const handleDelete = (id: string, name: string) => {
    Alert.alert(
      `Delete "${name}"?`,
      "Documents in this workspace may need reassignment.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              setDeleting(id)
              await deleteProject(id)
              await fetchAll()
            } catch (e: any) {
              setError(e.message || "Failed to delete workspace")
            } finally {
              setDeleting(null)
            }
          },
        },
      ],
    )
  }

  const toggleExpand = (repoId: string) => setExpandedRepos((prev) => ({ ...prev, [repoId]: !prev[repoId] }))
  const expandAll = () => { const all: Record<string, boolean> = {}; workspaces.forEach((w) => (all[w.id] = true)); setExpandedRepos(all) }
  const collapseAll = () => setExpandedRepos({})

  const uncategorizedDocs = documents.filter((d) => !d.project_id || !workspaces.some((w) => w.id === d.project_id))
  const uncategorizedSessions = sessions.filter((s) => !s.project_id || !workspaces.some((w) => w.id === s.project_id))

  const getRepoTimeline = useCallback((repoId: string): TimelineItem[] => {
    const repoDocs = documents.filter((d) => d.project_id === repoId)
    const repoSessions = sessions.filter((s) => s.project_id === repoId)
    const items: TimelineItem[] = [
      ...repoDocs.map((d) => ({ kind: "document" as const, data: d })),
      ...repoSessions.map((s) => ({ kind: "session" as const, data: s })),
    ]
    items.sort((a, b) => {
      const aDate = a.kind === "document" ? a.data.created_at : (a.data.updated_at || a.data.started_at)
      const bDate = b.kind === "document" ? b.data.created_at : (b.data.updated_at || b.data.started_at)
      return new Date(bDate).getTime() - new Date(aDate).getTime()
    })
    return items.slice(0, PAGE_SIZE)
  }, [documents, sessions])

  const uncategorizedTimeline: TimelineItem[] = useMemo(() => {
    const items: TimelineItem[] = [
      ...uncategorizedDocs.map((d) => ({ kind: "document" as const, data: d })),
      ...uncategorizedSessions.map((s) => ({ kind: "session" as const, data: s })),
    ]
    items.sort((a, b) => {
      const aDate = a.kind === "document" ? a.data.created_at : (a.data.updated_at || a.data.started_at)
      const bDate = b.kind === "document" ? b.data.created_at : (b.data.updated_at || b.data.started_at)
      return new Date(bDate).getTime() - new Date(aDate).getTime()
    })
    return items.slice(0, PAGE_SIZE)
  }, [uncategorizedDocs, uncategorizedSessions])

  const totalPages = Math.ceil(docTotal / PAGE_SIZE)

  const renderItem = (item: TimelineItem) => {
    if (item.kind === "document") {
      const d = item.data
      const sc = statusColor(d.status, c)
      return (
        <View key={d.id} style={{
          flexDirection: "row", alignItems: "center", gap: 10,
          paddingVertical: 10, paddingHorizontal: 14,
          borderTopWidth: 1, borderTopColor: c.border,
        }}>
          <Text style={{ fontSize: 18 }}>{fileIcon(d.filename)}</Text>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={{ fontWeight: "600", color: c.text, fontSize: 13 }} numberOfLines={1}>{d.filename}</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 }}>
              <View style={{
                backgroundColor: sc + "18", borderRadius: 999,
                paddingHorizontal: 6, paddingVertical: 1,
                borderWidth: 1, borderColor: sc + "30",
              }}>
                <Text style={{ fontSize: 9, fontWeight: "700", color: sc }}>● {d.status}</Text>
              </View>
              <Text style={{ fontSize: 10, color: c.textMuted }}>{formatDate(d.created_at)}</Text>
            </View>
          </View>
          {onOpenDocument && (
            <Pressable
              onPress={() => onOpenDocument(d.id)}
              style={{
                paddingVertical: 4, paddingHorizontal: 10, borderRadius: 6,
                borderWidth: 1, borderColor: c.border,
              }}
            >
              <Text style={{ fontSize: 11, fontWeight: "600", color: c.textSecondary }}>Open</Text>
            </Pressable>
          )}
        </View>
      )
    }
    const s = item.data
    return (
      <View key={s.session_id} style={{
        flexDirection: "row", alignItems: "center", gap: 10,
        paddingVertical: 10, paddingHorizontal: 14,
        borderTopWidth: 1, borderTopColor: c.border,
      }}>
        <View style={{
          width: 28, height: 28, borderRadius: 8,
          backgroundColor: c.secondary + "18",
          borderWidth: 1, borderColor: c.secondary + "30",
          alignItems: "center", justifyContent: "center",
        }}>
          <Text style={{ fontSize: 12 }}>💬</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={{ fontWeight: "600", color: c.text, fontSize: 13 }} numberOfLines={1}>
            {s.title || "Conversation"}
          </Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 }}>
            <Text style={{ fontSize: 10, color: c.textMuted, fontWeight: "500" }}>{s.model || "default"}</Text>
            <Text style={{ fontSize: 10, color: c.textMuted }}>{formatDateTime(s.updated_at || s.started_at)}</Text>
          </View>
        </View>
      </View>
    )
  }

  const renderRepo = (ws: Workspace) => {
    const timeline = getRepoTimeline(ws.id)
    const isExpanded = expandedRepos[ws.id] ?? false
    const repoDocs = documents.filter((d) => d.project_id === ws.id)
    const repoSessions = sessions.filter((s) => s.project_id === ws.id)
    const isEditing = editingId === ws.id
    const isDeleting = deleting === ws.id

    return (
      <View key={ws.id} style={{
        backgroundColor: c.cardBg,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: c.border,
        overflow: "hidden",
      }}>
        {/* Header */}
        <Pressable
          onPress={() => toggleExpand(ws.id)}
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 12,
            padding: 14,
          }}
        >
          <View style={{
            width: 36, height: 36, borderRadius: 10,
            backgroundColor: c.primary + "14",
            borderWidth: 1, borderColor: c.primary + "28",
            alignItems: "center", justifyContent: "center",
          }}>
            <Text style={{ fontSize: 16 }}>{isExpanded ? "📂" : "🗂️"}</Text>
          </View>

          <View style={{ flex: 1, minWidth: 0 }}>
            {isEditing ? (
              <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
                <TextInput
                  value={editName}
                  onChangeText={setEditName}
                  onSubmitEditing={() => handleRename(ws.id)}
                  autoFocus
                  style={{
                    flex: 1, paddingVertical: 6, paddingHorizontal: 10,
                    borderRadius: 6, borderWidth: 1, borderColor: c.primary,
                    backgroundColor: c.inputBg, color: c.text, fontSize: 13,
                  }}
                />
                <Pressable
                  onPress={() => handleRename(ws.id)}
                  disabled={renaming === ws.id}
                  style={{
                    paddingVertical: 4, paddingHorizontal: 10, borderRadius: 6,
                    backgroundColor: c.primary, opacity: renaming === ws.id ? 0.5 : 1,
                  }}
                >
                  <Text style={{ color: "#FFFFFF", fontSize: 11, fontWeight: "600" }}>
                    {renaming === ws.id ? "..." : "Save"}
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => setEditingId(null)}
                  style={{ paddingVertical: 4, paddingHorizontal: 8, borderRadius: 6, borderWidth: 1, borderColor: c.border }}
                >
                  <Text style={{ fontSize: 11, color: c.textSecondary }}>Cancel</Text>
                </Pressable>
              </View>
            ) : (
              <>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Text style={{ fontWeight: "700", color: c.text, fontSize: 14 }} numberOfLines={1}>
                    {ws.name}
                  </Text>
                  <View style={{
                    backgroundColor: c.primary + "14", borderRadius: 10,
                    paddingHorizontal: 6, paddingVertical: 1,
                  }}>
                    <Text style={{ fontSize: 10, fontWeight: "600", color: c.primary }}>
                      {(ws.document_count ?? repoDocs.length)} docs
                    </Text>
                  </View>
                </View>
                <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 1 }}>
                  {repoSessions.length} chat{repoSessions.length !== 1 ? "s" : ""}
                  {ws.created_at && ` · Created ${formatDate(ws.created_at)}`}
                </Text>
              </>
            )}
          </View>

          {/* Actions */}
          <View style={{ flexDirection: "row", gap: 4, alignItems: "center" }}>
            {!isEditing && (
              <>
                {onSelectProject && (
                  <Pressable
                    onPress={() => onSelectProject(ws)}
                    style={{
                      paddingVertical: 4, paddingHorizontal: 8,
                      borderRadius: 6, borderWidth: 1, borderColor: c.primary + "40",
                    }}
                  >
                    <Text style={{ fontSize: 10, fontWeight: "600", color: c.primary }}>Library</Text>
                  </Pressable>
                )}
                <Pressable
                  onPress={() => { setEditingId(ws.id); setEditName(ws.name) }}
                  style={{ padding: 4 }}
                  hitSlop={6}
                >
                  <Text style={{ fontSize: 14, color: c.textMuted }}>✎</Text>
                </Pressable>
                <Pressable
                  onPress={() => handleDelete(ws.id, ws.name)}
                  disabled={isDeleting}
                  style={{ padding: 4 }}
                  hitSlop={6}
                >
                  <Text style={{ fontSize: 14, color: c.error }}>{isDeleting ? "..." : "🗑"}</Text>
                </Pressable>
              </>
            )}
            <Text style={{
              fontSize: 16, color: c.textMuted,
              transform: [{ rotate: isExpanded ? "180deg" : "0deg" }],
            }}>▼</Text>
          </View>
        </Pressable>

        {/* Timeline */}
        {isExpanded && (
          timeline.length === 0 ? (
            <View style={{
              padding: 20, alignItems: "center",
              borderTopWidth: 1, borderTopColor: c.border,
            }}>
              <Text style={{ color: c.textMuted, fontSize: 12 }}>
                No documents or conversations yet
              </Text>
            </View>
          ) : (
            <View style={{ borderTopWidth: 1, borderTopColor: c.border }}>
              {timeline.map(renderItem)}
            </View>
          )
        )}
      </View>
    )
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.bg }}
      contentContainerStyle={{
        padding: isTablet ? 24 : 16,
        paddingBottom: 48,
        maxWidth: isTablet ? 960 : undefined,
        alignSelf: "center",
        width: "100%",
      }}
    >
      {/* Header */}
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12, marginBottom: 20 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, letterSpacing: -0.3 }}>Workspaces</Text>
          <Text style={{ fontSize: 13, color: c.textSecondary, marginTop: 2 }}>Organize, manage, and explore your repositories</Text>
        </View>
        <View style={{ flexDirection: "row", gap: 6 }}>
          <Pressable onPress={expandAll} style={{
            paddingVertical: 6, paddingHorizontal: 12,
            borderRadius: 8, borderWidth: 1, borderColor: c.border,
          }}>
            <Text style={{ fontSize: 11, fontWeight: "600", color: c.textSecondary }}>Expand All</Text>
          </Pressable>
          <Pressable onPress={collapseAll} style={{
            paddingVertical: 6, paddingHorizontal: 12,
            borderRadius: 8, borderWidth: 1, borderColor: c.border,
          }}>
            <Text style={{ fontSize: 11, fontWeight: "600", color: c.textSecondary }}>Collapse All</Text>
          </Pressable>
          <Pressable onPress={fetchAll} disabled={loading} style={{
            paddingVertical: 6, paddingHorizontal: 12,
            borderRadius: 8, borderWidth: 1, borderColor: c.border,
            opacity: loading ? 0.6 : 1,
          }}>
            <Text style={{ fontSize: 11, fontWeight: "600", color: c.textSecondary }}>
              {loading ? "Loading…" : "↻ Refresh"}
            </Text>
          </Pressable>
        </View>
      </View>

      {/* Error banner */}
      {(error || createError) && (
        <View style={{
          backgroundColor: c.error + "14",
          borderRadius: 12, padding: 12, marginBottom: 16,
          borderWidth: 1, borderColor: c.error + "28",
          flexDirection: "row", alignItems: "center", justifyContent: "space-between",
        }}>
          <Text style={{ color: c.error, fontSize: 13, flex: 1 }}>{error || createError}</Text>
          <Pressable onPress={() => { setError(null); setCreateError(null) }} style={{ marginLeft: 12 }}>
            <Text style={{ color: c.error, fontWeight: "600", fontSize: 12 }}>Dismiss</Text>
          </Pressable>
        </View>
      )}

      {/* Create workspace */}
      <View style={{
        flexDirection: isTablet ? "row" : "column",
        gap: 10, marginBottom: 20,
        padding: 14,
        borderRadius: 12,
        backgroundColor: c.cardBg,
        borderWidth: 1, borderColor: c.border,
      }}>
        <TextInput
          placeholder="New workspace name…"
          value={newName}
          onChangeText={setNewName}
          onSubmitEditing={handleCreate}
          placeholderTextColor={c.textMuted}
          style={{
            flex: isTablet ? 1 : undefined,
            paddingVertical: 10, paddingHorizontal: 12,
            borderRadius: 8, borderWidth: 1, borderColor: c.border,
            backgroundColor: c.inputBg, color: c.text, fontSize: 13,
          }}
        />
        <Pressable
          onPress={handleCreate}
          disabled={creating || !newName.trim()}
          style={{
            paddingVertical: 10, paddingHorizontal: 20,
            borderRadius: 8, backgroundColor: c.primary,
            alignItems: "center",
            opacity: creating || !newName.trim() ? 0.5 : 1,
          }}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 14 }}>
            {creating ? "Creating…" : "Create Workspace"}
          </Text>
        </Pressable>
      </View>

      {/* Loading state */}
      {loading && workspaces.length === 0 ? (
        <View style={{ gap: 10 }}>
          {Array.from({ length: 3 }).map((_, i) => (<SkeletonCard key={i} />))}
        </View>
      ) : workspaces.length === 0 && uncategorizedDocs.length === 0 && uncategorizedSessions.length === 0 ? (
        /* Empty state */
        <View style={{
          backgroundColor: c.cardBg, borderRadius: 14,
          borderWidth: 1, borderColor: c.border,
          padding: 48, alignItems: "center",
        }}>
          <Text style={{ fontSize: 40, marginBottom: 12 }}>🗂️</Text>
          <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: 8 }}>No workspaces yet</Text>
          <Text style={{ fontSize: 13, color: c.textSecondary, textAlign: "center" }}>
            Create your first workspace above to get started.
          </Text>
        </View>
      ) : (
        /* Workspace list */
        <View style={{ gap: 10 }}>
          {workspaces.map(renderRepo)}

          {/* Uncategorized section */}
          {(uncategorizedDocs.length > 0 || uncategorizedSessions.length > 0) && (
            <View style={{
              backgroundColor: c.cardBg, borderRadius: 12,
              borderWidth: 1, borderColor: c.border, overflow: "hidden",
            }}>
              <Pressable
                onPress={() => setShowUncategorized((v) => !v)}
                style={{
                  flexDirection: "row", alignItems: "center", gap: 12, padding: 14,
                }}
              >
                <View style={{
                  width: 36, height: 36, borderRadius: 10,
                  backgroundColor: c.warning + "14", borderWidth: 1, borderColor: c.warning + "28",
                  alignItems: "center", justifyContent: "center",
                }}>
                  <Text style={{ fontSize: 16 }}>📂</Text>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={{ fontWeight: "700", color: c.text, fontSize: 14 }}>No Repository</Text>
                  <Text style={{ fontSize: 11, color: c.textMuted, marginTop: 1 }}>
                    {uncategorizedDocs.length} doc{uncategorizedDocs.length !== 1 ? "s" : ""} · {uncategorizedSessions.length} chat{uncategorizedSessions.length !== 1 ? "s" : ""} (uncategorized)
                  </Text>
                </View>
                <Text style={{
                  fontSize: 16, color: c.textMuted,
                  transform: [{ rotate: showUncategorized ? "180deg" : "0deg" }],
                }}>▼</Text>
              </Pressable>
              {showUncategorized && (
                <View style={{ borderTopWidth: 1, borderTopColor: c.border }}>
                  {uncategorizedTimeline.map(renderItem)}
                </View>
              )}
            </View>
          )}
        </View>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <View style={{ flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 12, marginTop: 20 }}>
          <Pressable
            onPress={() => setDocPage((p) => Math.max(1, p - 1))}
            disabled={docPage <= 1}
            style={{
              paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8,
              borderWidth: 1, borderColor: c.border,
              opacity: docPage <= 1 ? 0.4 : 1,
            }}
          >
            <Text style={{ fontSize: 13, color: c.text }}>← Prev</Text>
          </Pressable>
          <Text style={{ fontSize: 12, color: c.textMuted }}>Page {docPage} of {totalPages}</Text>
          <Pressable
            onPress={() => setDocPage((p) => p + 1)}
            disabled={docPage >= totalPages}
            style={{
              paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8,
              borderWidth: 1, borderColor: c.border,
              opacity: docPage >= totalPages ? 0.4 : 1,
            }}
          >
            <Text style={{ fontSize: 13, color: c.text }}>Next →</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  )
}
