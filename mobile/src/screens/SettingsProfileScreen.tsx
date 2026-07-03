import React, { useEffect, useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"
import { getMe, updateUserProfile } from "../api/client"

export function SettingsProfileScreen() {
  const { theme, toggleTheme, isDark } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [ecNumber, setEcNumber] = useState("")
  const [role, setRole] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [successMsg, setSuccessMsg] = useState("")

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      setLoading(true)
      const user = await getMe()
      setDisplayName(user?.display_name || "")
      setEmail(user?.email || "")
      setEcNumber(user?.ec_number || user?.username || "")
      setRole(user?.role || "")
    } catch (err: any) {
      setError(err.message || "Failed to load profile")
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError("")
      setSuccessMsg("")
      await updateUserProfile({
        display_name: displayName,
        email,
      })
      setSuccessMsg("Profile updated successfully")
      setTimeout(() => setSuccessMsg(""), 3000)
    } catch (err: any) {
      setError(err.message || "Failed to save profile")
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: c.bg }}>
        <ActivityIndicator size="large" color={c.primary} />
        <Text style={{ marginTop: t.spacing.sm + t.spacing.xs, color: c.textMuted }}>Loading profile...</Text>
      </View>
    )
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl, maxWidth: isTablet ? 600 : undefined, alignSelf: isTablet ? "center" : undefined }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Profile Settings
      </Text>

      {error ? (
        <View style={{ backgroundColor: c.error + "14", borderRadius: t.radii.md, padding: t.spacing.sm + t.spacing.xs, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.error + "28" }}>
          <Text style={{ color: c.error, fontSize: 13 }}>{error}</Text>
        </View>
      ) : null}

      {successMsg ? (
        <View style={{ backgroundColor: c.success + "18", borderRadius: t.radii.md, padding: t.spacing.sm + t.spacing.xs, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.success + "28" }}>
          <Text style={{ color: c.success, fontSize: 13, fontWeight: "600" }}>{successMsg}</Text>
        </View>
      ) : null}

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm }}>
          Display Name
        </Text>
        <TextInput
          value={displayName}
          onChangeText={setDisplayName}
          placeholderTextColor={c.textMuted}
          style={{
            backgroundColor: c.inputBg,
            borderRadius: t.radii.md,
            padding: t.spacing.sm + t.spacing.xs,
            borderWidth: 1,
            borderColor: c.border,
            color: c.text,
            marginBottom: t.spacing.md,
          }}
        />

        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm }}>
          Email
        </Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="Email address"
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
            marginBottom: t.spacing.md,
          }}
        />

        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm }}>
          EC Number
        </Text>
        <TextInput
          value={ecNumber}
          editable={false}
          style={{
            backgroundColor: c.bgSecondary,
            borderRadius: t.radii.md,
            padding: t.spacing.sm + t.spacing.xs,
            borderWidth: 1,
            borderColor: c.border,
            color: c.textMuted,
            marginBottom: t.spacing.md,
          }}
        />

        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm }}>
          Role
        </Text>
        <TextInput
          value={role}
          editable={false}
          style={{
            backgroundColor: c.bgSecondary,
            borderRadius: t.radii.md,
            padding: t.spacing.sm + t.spacing.xs,
            borderWidth: 1,
            borderColor: c.border,
            color: c.textMuted,
            marginBottom: t.spacing.md,
          }}
        />
      </View>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 14, fontWeight: "600", color: c.text, marginBottom: t.spacing.sm + t.spacing.xs }}>
          Appearance
        </Text>
        <Pressable
          onPress={toggleTheme}
          style={{
            backgroundColor: c.inputBg,
            borderRadius: t.radii.md,
            padding: t.spacing.sm + t.spacing.xs + t.spacing.xs,
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            borderWidth: 1,
            borderColor: c.border,
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Text style={{ fontSize: 20 }}>{isDark ? "🌙" : "☀️"}</Text>
            <Text style={{ fontSize: 14, fontWeight: "500", color: c.text }}>
              {isDark ? "Dark Mode" : "Light Mode"}
            </Text>
          </View>
          <View
            style={{
              width: 44,
              height: 24,
              borderRadius: 12,
              backgroundColor: isDark ? c.primary : c.bgSecondary,
              justifyContent: "center",
              paddingHorizontal: 3,
            }}
          >
            <View
              style={{
                width: 18,
                height: 18,
                borderRadius: 9,
                backgroundColor: "#FFFFFF",
                alignSelf: isDark ? "flex-end" : "flex-start",
              }}
            />
          </View>
        </Pressable>
      </View>

      <Pressable
        onPress={handleSave}
        disabled={saving}
        style={{
          backgroundColor: saving ? c.textMuted : c.primary,
          borderRadius: t.radii.md,
          paddingVertical: t.spacing.md - 2,
          alignItems: "center",
        }}
      >
        <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>
          {saving ? "Saving..." : "Save Changes"}
        </Text>
      </Pressable>
    </ScrollView>
  )
}