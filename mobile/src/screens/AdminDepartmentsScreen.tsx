import React from "react"
import { View, Text, ScrollView, useWindowDimensions } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

export function AdminDepartmentsScreen() {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const { width } = useWindowDimensions()
  const isTablet = width >= 768

  const departments = [
    { id: "eng", name: "Engineering", members: 34, head: "Dr. T. Moyo", projects: 8 },
    { id: "ops", name: "Operations", members: 52, head: "Eng. S. Ndlovu", projects: 12 },
    { id: "finance", name: "Finance", members: 18, head: "Mrs. P. Chikwanha", projects: 3 },
    { id: "hr", name: "Human Resources", members: 12, head: "Mr. K. Sibanda", projects: 2 },
    { id: "it", name: "IT & Systems", members: 28, head: "Ms. R. Dube", projects: 15 },
  ]

  return (
    <ScrollView style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ padding: isTablet ? t.spacing.lg : t.spacing.md, paddingBottom: t.spacing.xl }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: c.text, marginBottom: t.spacing.md }}>
        Departments
      </Text>

      {departments.map((dept) => (
        <View key={dept.id} style={{ backgroundColor: c.cardBg, borderRadius: t.radii.md, padding: t.spacing.sm, marginBottom: t.spacing.sm, borderWidth: 1, borderColor: c.border }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: t.spacing.xs }}>
            <Text style={{ fontSize: 14, fontWeight: "700", color: c.text }}>{dept.name}</Text>
            <Text style={{ fontSize: 13, color: c.primary, fontWeight: "600" }}>{dept.members} members</Text>
          </View>
          <View style={{ flexDirection: "row", gap: t.spacing.md }}>
            <Text style={{ fontSize: 12, color: c.textMuted }}>Head: {dept.head}</Text>
            <Text style={{ fontSize: 12, color: c.textMuted }}>•</Text>
            <Text style={{ fontSize: 12, color: c.textMuted }}>{dept.projects} active projects</Text>
          </View>
        </View>
      ))}
    </ScrollView>
  )
}
