import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getTeamMembers, updateMemberRole, getActivityLog, getMe } from "../api/client"

interface TeamMember {
  user_id: number
  display_name?: string
  ec_number?: string
  email?: string
  role: string
}

const roles = ["admin", "manager", "member", "viewer"]

export function CollaborationTeamScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const roleBadgeColors: Record<string, string> = {
    admin: c.error + "14",
    manager: c.warning + "18",
    member: c.primary + "14",
    viewer: c.accent + "18",
  }

  const roleTextColors: Record<string, string> = {
    admin: c.error,
    manager: c.warning,
    member: c.primary,
    viewer: c.accent,
  }

  const [members, setMembers] = useState<TeamMember[]>([])
  const [activityLog, setActivityLog] = useState<any[]>([])
  const [currentUser, setCurrentUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [changingRole, setChangingRole] = useState<number | null>(null)
  const [error, setError] = useState("")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [activeTab, setActiveTab] = useState<"members" | "activity">("members")

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError("")
      const [teamRes, activityRes, userRes] = await Promise.all([
        getTeamMembers().catch(() => ({ members: [] })),
        getActivityLog({ limit: "20" }).catch(() => ({ activity: [] })),
        getMe(),
      ])
      const rawMembers = (teamRes?.members || teamRes?.team || []).map((m: any) => ({
        user_id: m.user_id ?? m.id,
        display_name: m.display_name || "",
        ec_number: m.ec_number || "",
        email: m.email || "",
        role: m.role || "viewer",
      }))
      setMembers(rawMembers)
      setActivityLog(activityRes?.activities || activityRes?.activity || activityRes?.logs || activityRes?.items || [])
      setCurrentUser(userRes)
    } catch (err: any) {
      setError(err.message || "Failed to load team data")
    } finally {
      setLoading(false)
    }
  }

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      setChangingRole(userId)
      setError("")
      await updateMemberRole(userId, newRole)
      setMembers((prev) =>
        prev.map((m) => (m.user_id === userId ? { ...m, role: newRole } : m))
      )
    } catch (err: any) {
      setError(err.message || "Failed to update role")
    } finally {
      setChangingRole(null)
    }
  }

  const isAdmin = currentUser?.role === "admin"

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm + t.spacing.xs, color: c.textMuted }}>Loading team data...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Team Collaboration
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm + t.spacing.xs, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      <View style={{ flexDirection: "row", marginBottom: t.spacing.md, backgroundColor: c.bgSecondary, borderRadius: t.radii.md, padding: t.spacing.xs }}>
        {(["members", "activity"] as const).map((tab) => (
          <Pressable
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={{
              flex: 1,
              paddingVertical: t.spacing.sm + t.spacing.xs,
              borderRadius: t.radii.sm,
              backgroundColor: activeTab === tab ? c.cardBg : "transparent",
              alignItems: "center",
            }}
          >
            <Text style={{ fontSize: 14, fontWeight: "600", color: activeTab === tab ? c.primary : c.textMuted }}>
              {tab === "members" ? "Team Members" : "Activity Log"}
            </Text>
          </Pressable>
        ))}
      </View>

      {activeTab === "members" && (
        <>
          {isAdmin && (
            <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm + t.spacing.xs, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
              <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm }}>
                Invite Member
              </Text>
              <TextInput
                placeholder="Email address"
                value={inviteEmail}
                onChangeText={setInviteEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                placeholderTextColor={c.textMuted}
                style={{
                  backgroundColor: c.inputBg,
                  borderRadius: t.radii.md,
                  padding: t.spacing.sm + t.spacing.xs,
                  borderWidth: 1,
                  borderColor: c.border,
                  color: c.text,
                  marginBottom: t.spacing.sm,
                }}
              />
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: t.spacing.sm }}>
                {roles.map((r) => (
                  <Pressable
                    key={r}
                    onPress={() => setInviteRole(r)}
                    style={{
                      paddingHorizontal: t.spacing.sm + t.spacing.xs,
                      paddingVertical: 6,
                      borderRadius: 16,
                      backgroundColor: inviteRole === r ? c.primary : c.bgSecondary,
                      marginRight: t.spacing.sm,
                    }}
                  >
                    <Text style={{ color: inviteRole === r ? "#FFFFFF" : c.text, fontSize: 12, fontWeight: "600" }}>
                      {r.charAt(0).toUpperCase() + r.slice(1)}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
              <Pressable
                style={{
                  backgroundColor: c.primary,
                  borderRadius: t.radii.sm,
                  paddingVertical: t.spacing.sm,
                  alignItems: "center",
                }}
              >
                <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 13 }}>Send Invitation</Text>
              </Pressable>
            </View>
          )}

          {members.length === 0 ? (
            <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
              <Text style={{ fontSize: 40, marginBottom: t.spacing.sm + t.spacing.xs }}>👥</Text>
              <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
                No team members yet
              </Text>
              <Text style={{ fontSize: 13, color: c.textMuted }}>
                Invite members to collaborate
              </Text>
            </View>
          ) : (
            <View style={isTablet ? { flexDirection: "row", flexWrap: "wrap", gap: t.spacing.sm } : undefined}>
              {members.map((member) => (
                <View
                  key={member.user_id}
                  style={{
                    backgroundColor: c.cardBg,
                    borderRadius: t.radii.md,
                    padding: t.spacing.sm + t.spacing.xs,
                    marginBottom: t.spacing.sm + t.spacing.xs,
                    borderWidth: 1,
                    borderColor: c.border,
                    ...(isTablet ? { width: "48%" } : {}),
                  }}
                >
                  <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
                        {member.display_name || member.ec_number || `User ${member.user_id}`}
                      </Text>
                      {member.email ? (
                        <Text style={{ fontSize: 12, color: c.textMuted, marginBottom: t.spacing.xs }}>
                          {member.email}
                        </Text>
                      ) : null}
                      {member.ec_number ? (
                        <Text style={{ fontSize: 12, color: c.textMuted }}>
                          EC: {member.ec_number}
                        </Text>
                      ) : null}
                    </View>
                    <View
                      style={{
                        backgroundColor: roleBadgeColors[member.role] || c.primary + "14",
                        borderRadius: t.radii.sm,
                        paddingHorizontal: t.spacing.sm,
                        paddingVertical: 3,
                        marginLeft: t.spacing.sm,
                      }}
                    >
                      <Text style={{ fontSize: 11, color: roleTextColors[member.role] || c.primary, fontWeight: "600" }}>
                        {member.role.toUpperCase()}
                      </Text>
                    </View>
                  </View>

                  {isAdmin && member.user_id !== currentUser?.user_id && (
                    <View style={{ borderTopWidth: 1, borderTopColor: c.bgSecondary, paddingTop: t.spacing.sm + t.spacing.xs, marginTop: t.spacing.sm + t.spacing.xs }}>
                      <Text style={{ fontSize: 11, fontWeight: "600", color: c.textMuted, marginBottom: 6 }}>
                        Change Role:
                      </Text>
                      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                        {roles.map((r) => (
                          <Pressable
                            key={r}
                            onPress={() => handleRoleChange(member.user_id, r)}
                            disabled={changingRole === member.user_id || member.role === r}
                            style={{
                              paddingHorizontal: t.spacing.sm + t.spacing.xs,
                              paddingVertical: 5,
                              borderRadius: 14,
                              backgroundColor: member.role === r ? c.success + "18" : changingRole === member.user_id ? c.bgSecondary : c.primary + "14",
                              marginRight: 6,
                              borderWidth: 1,
                              borderColor: member.role === r ? c.success : "transparent",
                            }}
                          >
                            <Text style={{ fontSize: 11, fontWeight: "600", color: member.role === r ? c.success : c.primary }}>
                              {changingRole === member.user_id && "⏳"} {r}
                            </Text>
                          </Pressable>
                        ))}
                      </ScrollView>
                    </View>
                  )}
                </View>
              ))}
            </View>
          )}
        </>
      )}

      {activeTab === "activity" && (
        <>
          <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm }}>
            Recent Activity
          </Text>
          {activityLog.length === 0 ? (
            <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.xl, alignItems: "center", borderWidth: 1, borderColor: c.border }}>
              <Text style={{ fontSize: 40, marginBottom: t.spacing.sm + t.spacing.xs }}>📋</Text>
              <Text style={{ fontSize: 16, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>
                No activity yet
              </Text>
              <Text style={{ fontSize: 13, color: c.textMuted }}>
                Activity will appear here
              </Text>
            </View>
          ) : (
            activityLog.map((entry, index) => {
              const action = entry.action || entry.event || entry.type || "action"
              const user = entry.user || entry.display_name || entry.ec_number || "User"
              const timestamp = entry.created_at || entry.timestamp || entry.date
              const details = entry.details || entry.description || entry.message || ""

              return (
                <View
                  key={entry.id || index}
                  style={{
                    backgroundColor: c.cardBg,
                    borderRadius: t.radii.md,
                    padding: t.spacing.sm + t.spacing.xs,
                    marginBottom: t.spacing.sm,
                    borderWidth: 1,
                    borderColor: c.border,
                    flexDirection: "row",
                    alignItems: "flex-start",
                    gap: t.spacing.sm,
                  }}
                >
                  <View
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 16,
                      backgroundColor: c.primary + "14",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Text style={{ fontSize: 14 }}>👤</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 13, color: c.text }}>
                      <Text style={{ fontWeight: "600" }}>{user}</Text> {action}
                    </Text>
                    {details ? (
                      <Text style={{ fontSize: 12, color: c.textMuted, marginTop: t.spacing.xs }}>
                        {details}
                      </Text>
                    ) : null}
                    {timestamp ? (
                      <Text style={{ fontSize: 11, color: c.textMuted, marginTop: t.spacing.xs }}>
                        {new Date(timestamp).toLocaleString()}
                      </Text>
                    ) : null}
                  </View>
                </View>
              )
            })
          )}
        </>
      )}
    </ScrollView>
  )
}