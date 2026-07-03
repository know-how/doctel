import React, { useState, useEffect, useCallback } from "react"
import { View, Text, Pressable, ScrollView, useWindowDimensions, Image } from "react-native"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { useTheme } from "../context/ThemeContext"
import { sidebarConfig, NavItem } from "./sidebarConfig"
import zetdcLogo from "../assets/zetdc-logo.png"

const EXPANDED_WIDTH = 280
const COLLAPSED_WIDTH = 64
const EXPANDED_SECTIONS_KEY = "docintel_sidebar_expanded_inline"

interface InlineSidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  onNavigate: (path: string) => void
  onLogout: () => void
  currentPath: string
  userRole: string
  displayName: string
}

export function InlineSidebar({
  collapsed,
  onToggleCollapse,
  onNavigate,
  onLogout,
  currentPath,
  userRole,
  displayName,
}: InlineSidebarProps) {
  const { isDark, toggleTheme, tokens: t } = useTheme()
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({})

  useEffect(() => {
    AsyncStorage.getItem(EXPANDED_SECTIONS_KEY).then((stored) => {
      if (stored) {
        try {
          const parsed = JSON.parse(stored) as Record<string, boolean>
          setExpandedSections(parsed)
        } catch {}
      }
    })
  }, [])

  const toggleSection = useCallback((sectionId: string) => {
    setExpandedSections((prev) => {
      const updated = { ...prev, [sectionId]: !prev[sectionId] }
      AsyncStorage.setItem(EXPANDED_SECTIONS_KEY, JSON.stringify(updated)).catch(() => {})
      return updated
    })
  }, [])

  const isNavVisible = (item: NavItem): boolean => {
    if (!item.roles || item.roles.length === 0) return true
    return item.roles.includes(userRole)
  }

  const visibleItems = sidebarConfig.filter(isNavVisible)

  const width = collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH

  const getInitial = (name: string): string => {
    if (!name) return "?"
    return name.charAt(0).toUpperCase()
  }

  return (
    <View
      style={{
        width,
        backgroundColor: t.colors.sidebar,
        borderRightWidth: 1,
        borderRightColor: t.colors.sidebarBorder,
        flexShrink: 0,
      }}
    >
      <Pressable
        onPress={onToggleCollapse}
        style={{
          height: 56,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
          paddingHorizontal: collapsed ? 0 : t.spacing.md,
          borderBottomWidth: 1,
          borderBottomColor: t.colors.sidebarBorder,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: collapsed ? 0 : 10, flex: 1 }}>
          <Image
            source={zetdcLogo}
            style={{ width: collapsed ? 28 : 32, height: collapsed ? 28 : 32, resizeMode: "contain" }}
          />
          {!collapsed && (
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 11, fontWeight: "800", color: t.colors.primary, letterSpacing: 0.3 }}>
                DOCTEL LARGE LANGUAGE MODEL
              </Text>
              <Text style={{ fontSize: 8, fontWeight: "600", color: t.colors.textMuted, letterSpacing: 0.5 }}>
                Zimbabwe Electricity Transmission and Distribution Company
              </Text>
            </View>
          )}
        </View>
        <View
          style={{
            width: 36,
            height: 36,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: t.radii.md,
            backgroundColor: t.colors.surface,
          }}
        >
          <Text style={{ fontSize: 16, color: t.colors.textSecondary }}>
            {collapsed ? "☰" : "◀"}
          </Text>
        </View>
      </Pressable>

      <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
        {!collapsed && (
          <View style={{ paddingHorizontal: t.spacing.md, paddingVertical: t.spacing.sm }}>
            <Text
              style={{
                fontSize: 11,
                fontWeight: "700",
                color: t.colors.textMuted,
                textTransform: "uppercase",
                letterSpacing: 1.5,
                paddingHorizontal: t.spacing.sm,
              }}
            >
              Navigation
            </Text>
          </View>
        )}

        {visibleItems.map((item) => (
          <InlineSidebarItem
            key={item.id}
            item={item}
            collapsed={collapsed}
            t={t}
            currentPath={currentPath}
            expandedSections={expandedSections}
            toggleSection={toggleSection}
            onNavigate={onNavigate}
          />
        ))}
      </ScrollView>

      <View style={{ borderTopWidth: 1, borderTopColor: t.colors.sidebarBorder, paddingVertical: t.spacing.sm }}>
        {!collapsed && (
          <>
            <Pressable
              onPress={toggleTheme}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: t.spacing.sm + 2,
                paddingHorizontal: t.spacing.md + 4,
                marginHorizontal: t.spacing.sm,
                borderRadius: t.radii.md,
                backgroundColor: pressed ? t.colors.surfaceHover : "transparent",
              })}
            >
              <Text style={{ fontSize: 18, marginRight: t.spacing.sm }}>{isDark ? "☀️" : "🌙"}</Text>
              <Text style={{ fontSize: 14, color: t.colors.textSecondary, fontWeight: "500" }}>
                {isDark ? "Light Mode" : "Dark Mode"}
              </Text>
            </Pressable>

            <Pressable
              onPress={onLogout}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: t.spacing.sm + 2,
                paddingHorizontal: t.spacing.md + 4,
                marginHorizontal: t.spacing.sm,
                borderRadius: t.radii.md,
                backgroundColor: pressed ? t.colors.surfaceHover : "transparent",
              })}
            >
              <Text style={{ fontSize: 16, marginRight: t.spacing.sm }}>🚪</Text>
              <Text style={{ fontSize: 14, color: t.colors.error, fontWeight: "500" }}>Logout</Text>
            </Pressable>
          </>
        )}

        {collapsed && (
          <View style={{ alignItems: "center", gap: t.spacing.sm }}>
            <Pressable
              onPress={toggleTheme}
              style={{
                width: 36,
                height: 36,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: t.radii.md,
                backgroundColor: t.colors.surface,
              }}
            >
              <Text style={{ fontSize: 16 }}>{isDark ? "☀️" : "🌙"}</Text>
            </Pressable>
            <Pressable
              onPress={onLogout}
              style={{
                width: 36,
                height: 36,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: t.radii.md,
                backgroundColor: t.colors.surface,
              }}
            >
              <Text style={{ fontSize: 16 }}>🚪</Text>
            </Pressable>
          </View>
        )}

        <View
          style={{
            flexDirection: collapsed ? "column" : "row",
            alignItems: "center",
            paddingHorizontal: collapsed ? t.spacing.xs : t.spacing.md + 4,
            paddingVertical: t.spacing.sm,
            marginHorizontal: t.spacing.sm,
          }}
        >
          <View
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              backgroundColor: t.colors.primary,
              alignItems: "center",
              justifyContent: "center",
              marginRight: collapsed ? 0 : t.spacing.sm,
              marginBottom: collapsed ? t.spacing.xs : 0,
            }}
          >
            <Text style={{ color: "#FFFFFF", fontSize: 13, fontWeight: "700" }}>
              {getInitial(displayName)}
            </Text>
          </View>
          {!collapsed && (
            <View style={{ flex: 1 }}>
              <Text style={{ color: t.colors.text, fontSize: 13, fontWeight: "600" }} numberOfLines={1}>
                {displayName || "User"}
              </Text>
              <Text style={{ color: t.colors.textMuted, fontSize: 11, fontWeight: "600", textTransform: "uppercase" }}>
                {userRole || "user"}
              </Text>
            </View>
          )}
        </View>
      </View>
    </View>
  )
}

function InlineSidebarItem({
  item,
  collapsed,
  t,
  currentPath,
  expandedSections,
  toggleSection,
  onNavigate,
}: {
  item: NavItem
  collapsed: boolean
  t: ReturnType<typeof useTheme>["tokens"]
  currentPath: string
  expandedSections: Record<string, boolean>
  toggleSection: (id: string) => void
  onNavigate: (path: string) => void
}) {
  const hasChildren = !!(item.children && item.children.length > 0)
  const isExpanded = !!expandedSections[item.id]
  const isActive = currentPath === item.path

  const handlePress = () => {
    if (hasChildren) {
      toggleSection(item.id)
    } else {
      onNavigate(item.path)
    }
  }

  if (collapsed) {
    return (
      <View style={{ alignItems: "center", marginVertical: 2 }}>
        <Pressable
          onPress={handlePress}
          style={{
            width: 44,
            height: 44,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: t.radii.md,
            backgroundColor: isActive ? t.colors.surfaceActive : "transparent",
          }}
        >
          <Text style={{ fontSize: 20 }}>{item.icon}</Text>
        </Pressable>
      </View>
    )
  }

  return (
    <View style={{ marginBottom: 2 }}>
      <Pressable
        onPress={handlePress}
        style={({ pressed }) => ({
          flexDirection: "row",
          alignItems: "center",
          paddingVertical: t.spacing.sm + 2,
          paddingHorizontal: t.spacing.md + 4,
          marginHorizontal: t.spacing.sm,
          borderRadius: t.radii.md,
          backgroundColor: pressed
            ? t.colors.surfaceHover
            : isActive
              ? t.colors.surfaceActive
              : "transparent",
        })}
      >
        <Text style={{ fontSize: 17, marginRight: t.spacing.sm }}>{item.icon}</Text>
        <Text style={{ flex: 1, fontSize: 14, fontWeight: "600", color: t.colors.text }}>
          {item.label}
        </Text>
        {hasChildren && (
          <Text style={{ fontSize: 12, color: t.colors.textMuted, transform: [{ rotate: isExpanded ? "90deg" : "0deg" }] }}>
            ▶
          </Text>
        )}
      </Pressable>

      {hasChildren && isExpanded && (
        <View style={{ paddingLeft: t.spacing.lg }}>
          {item.children!.map((child) => {
            const childActive = currentPath === child.path
            return (
              <Pressable
                key={child.id}
                onPress={() => onNavigate(child.path)}
                style={({ pressed }) => ({
                  flexDirection: "row",
                  alignItems: "center",
                  paddingVertical: t.spacing.sm,
                  paddingHorizontal: t.spacing.md + 4,
                  marginRight: t.spacing.sm,
                  borderRadius: t.radii.md,
                  backgroundColor: pressed
                    ? t.colors.surfaceHover
                    : childActive
                      ? t.colors.surfaceActive
                      : "transparent",
                  borderLeftWidth: 2,
                  borderLeftColor: childActive ? t.colors.primary : "transparent",
                })}
              >
                <Text style={{ fontSize: 14, marginRight: t.spacing.sm }}>{child.icon}</Text>
                <Text
                  style={{
                    fontSize: 13,
                    color: childActive ? t.colors.primary : t.colors.textSecondary,
                    fontWeight: childActive ? "600" : "500",
                  }}
                >
                  {child.label}
                </Text>
              </Pressable>
            )
          })}
        </View>
      )}
    </View>
  )
}
