import React, { useState } from "react"
import { View, Text, TextInput, Pressable, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function SettingsSecurityScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl, maxWidth: isTablet ? 600 : undefined, alignSelf: isTablet ? "center" : undefined }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Security Settings
      </Text>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, marginBottom: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: c.text, marginBottom: t.spacing.md }}>
          Change Password
        </Text>

        <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>Current Password</Text>
        <TextInput
          value={currentPassword}
          onChangeText={setCurrentPassword}
          secureTextEntry
          placeholder="••••••••"
          placeholderTextColor={c.textMuted}
          style={{
            backgroundColor: c.inputBg,
            borderRadius: t.radii.md,
            padding: t.spacing.sm,
            borderWidth: 1,
            borderColor: c.border,
            color: c.text,
            marginBottom: t.spacing.md,
          }}
        />

        <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>New Password</Text>
        <TextInput
          value={newPassword}
          onChangeText={setNewPassword}
          secureTextEntry
          placeholder="Min. 8 characters"
          placeholderTextColor={c.textMuted}
          style={{
            backgroundColor: c.inputBg,
            borderRadius: t.radii.md,
            padding: t.spacing.sm,
            borderWidth: 1,
            borderColor: c.border,
            color: c.text,
            marginBottom: t.spacing.md,
          }}
        />

        <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, marginBottom: t.spacing.xs }}>Confirm New Password</Text>
        <TextInput
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
          placeholder="Re-enter new password"
          placeholderTextColor={c.textMuted}
          style={{
            backgroundColor: c.inputBg,
            borderRadius: t.radii.md,
            padding: t.spacing.sm,
            borderWidth: 1,
            borderColor: c.border,
            color: c.text,
            marginBottom: t.spacing.md,
          }}
        />

        <Pressable
          style={{
            backgroundColor: c.primary,
            borderRadius: t.radii.md,
            paddingVertical: t.spacing.md - 2,
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>Update Password</Text>
        </Pressable>
      </View>

      <View style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.md, borderWidth: 1, borderColor: c.border }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View>
            <Text style={{ fontSize: 16, fontWeight: "700", color: c.text }}>Two-Factor Authentication</Text>
            <Text style={{ fontSize: 12, color: c.textMuted, marginTop: 2 }}>Add an extra layer of security to your account</Text>
          </View>
          <Pressable style={{ backgroundColor: c.primary + "14", borderRadius: t.radii.sm, paddingHorizontal: 12, paddingVertical: 6 }}>
            <Text style={{ color: c.primary, fontSize: 13, fontWeight: "600" }}>Enable</Text>
          </Pressable>
        </View>
      </View>
    </ScrollView>
  )
}
