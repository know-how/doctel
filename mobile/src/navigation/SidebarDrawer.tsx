import React, { useState, useEffect, useRef, useCallback } from "react"
import {
  View,
  Text,
  Pressable,
  ScrollView,
  Animated,
  Dimensions,
  TouchableOpacity,
  Image,
} from "react-native"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { useTheme } from "../context/ThemeContext"
import { sidebarConfig, NavItem } from "./sidebarConfig"
import zetdcLogo from "../assets/zetdc-logo.png"

const DRAWER_WIDTH = 300
const SCREEN_WIDTH = Dimensions.get("window").width
const ANIM_DURATION = 300
const EXPANDED_SECTIONS_KEY = "docintel_sidebar_expanded"

interface SidebarDrawerProps {
  visible: boolean
  onClose: () => void
  onNavigate: (path: string) => void
  onLogout: () => void
  userRole: string
  displayName: string
}

export function SidebarDrawer({
  visible,
  onClose,
  onNavigate,
  onLogout,
  userRole,
  displayName,
}: SidebarDrawerProps) {
  const { isDark, toggleTheme, tokens } = useTheme()
  const t = tokens

  const translateX = useRef(new Animated.Value(-DRAWER_WIDTH)).current
  const backdropOpacity = useRef(new Animated.Value(0)).current
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({})
  const expandedAnimValues = useRef<Record<string, Animated.Value>>({})
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    if (visible) {
      setMounted(true)
      Animated.parallel([
        Animated.timing(translateX, {
          toValue: 0,
          duration: ANIM_DURATION,
          useNativeDriver: true,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 1,
          duration: ANIM_DURATION,
          useNativeDriver: true,
        }),
      ]).start()
    } else {
      Animated.parallel([
        Animated.timing(translateX, {
          toValue: -DRAWER_WIDTH,
          duration: ANIM_DURATION,
          useNativeDriver: true,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 0,
          duration: ANIM_DURATION,
          useNativeDriver: true,
        }),
      ]).start(() => {
        setMounted(false)
      })
    }
  }, [visible])

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

  const toggleSection = useCallback(
    (sectionId: string) => {
      setExpandedSections((prev) => {
        const updated = { ...prev, [sectionId]: !prev[sectionId] }
        AsyncStorage.setItem(EXPANDED_SECTIONS_KEY, JSON.stringify(updated)).catch(() => {})
        return updated
      })
    },
    [],
  )

  const handleNavigate = useCallback(
    (path: string) => {
      onNavigate(path)
      onClose()
    },
    [onNavigate, onClose],
  )

  const isNavVisible = (item: NavItem): boolean => {
    if (!item.roles || item.roles.length === 0) return true
    return item.roles.includes(userRole)
  }

  const getInitial = (name: string): string => {
    if (!name) return "?"
    return name.charAt(0).toUpperCase()
  }

  const visibleItems = sidebarConfig.filter(isNavVisible)

  if (!mounted) {
    return null
  }

  return (
    <View style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, zIndex: 1000 }} pointerEvents="box-none">
      <Animated.View
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: t.colors.overlay,
          opacity: backdropOpacity,
        }}
      >
        <TouchableOpacity
          activeOpacity={1}
          onPress={onClose}
          style={{ flex: 1 }}
        />
      </Animated.View>

      <Animated.View
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          bottom: 0,
          width: DRAWER_WIDTH,
          backgroundColor: t.colors.sidebar,
          borderRightWidth: 1,
          borderRightColor: t.colors.sidebarBorder,
          transform: [{ translateX }],
          paddingTop: 50,
        }}
      >
        <View style={{ flex: 1 }}>
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 10,
              paddingHorizontal: t.spacing.md,
              paddingBottom: t.spacing.md,
              borderBottomWidth: 1,
              borderBottomColor: t.colors.sidebarBorder,
              marginBottom: t.spacing.sm,
            }}
          >
            <Image source={zetdcLogo} style={{ width: 36, height: 36, resizeMode: "contain" }} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 12, fontWeight: "800", color: t.colors.primary, letterSpacing: 0.3 }}>
                DOCTEL LARGE LANGUAGE MODEL
              </Text>
              <Text style={{ fontSize: 8, fontWeight: "600", color: t.colors.textMuted, letterSpacing: 0.5 }}>
                Zimbabwe Electricity Transmission and Distribution Company
              </Text>
            </View>
          </View>
          <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>

            {visibleItems.map((item) => (
              <SidebarSection
                key={item.id}
                item={item}
                t={t}
                expandedSections={expandedSections}
                toggleSection={toggleSection}
                handleNavigate={handleNavigate}
                expandedAnimValues={expandedAnimValues}
              />
            ))}
          </ScrollView>

          <View style={{ borderTopWidth: 1, borderTopColor: t.colors.sidebarBorder, paddingVertical: t.spacing.sm }}>
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

            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                paddingHorizontal: t.spacing.md + 4,
                paddingVertical: t.spacing.sm + 4,
                marginHorizontal: t.spacing.sm,
              }}
            >
              <View
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 18,
                  backgroundColor: t.colors.primary,
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: t.spacing.sm,
                }}
              >
                <Text style={{ color: "#FFFFFF", fontSize: 15, fontWeight: "700" }}>
                  {getInitial(displayName)}
                </Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text
                  style={{ color: t.colors.text, fontSize: 14, fontWeight: "600" }}
                  numberOfLines={1}
                >
                  {displayName || "User"}
                </Text>
                <View
                  style={{
                    backgroundColor: t.colors.surface,
                    paddingHorizontal: 8,
                    paddingVertical: 2,
                    borderRadius: t.radii.sm,
                    alignSelf: "flex-start",
                    marginTop: 2,
                  }}
                >
                  <Text style={{ color: t.colors.textMuted, fontSize: 11, fontWeight: "600", textTransform: "uppercase" }}>
                    {userRole || "user"}
                  </Text>
                </View>
              </View>
            </View>
          </View>
        </View>
      </Animated.View>
    </View>
  )
}

function SidebarSection({
  item,
  t,
  expandedSections,
  toggleSection,
  handleNavigate,
  expandedAnimValues,
}: {
  item: NavItem
  t: ReturnType<typeof useTheme>["tokens"]
  expandedSections: Record<string, boolean>
  toggleSection: (id: string) => void
  handleNavigate: (path: string) => void
  expandedAnimValues: React.MutableRefObject<Record<string, Animated.Value>>
}) {
  const hasChildren = !!(item.children && item.children.length > 0)
  const isExpanded = !!expandedSections[item.id]

  const chevronAnim = useRef(new Animated.Value(isExpanded ? 1 : 0)).current

  useEffect(() => {
    Animated.timing(chevronAnim, {
      toValue: isExpanded ? 1 : 0,
      duration: 200,
      useNativeDriver: true,
    }).start()
  }, [isExpanded])

  const rotateZ = chevronAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "90deg"],
  })

  const handlePress = () => {
    if (hasChildren) {
      toggleSection(item.id)
    } else {
      handleNavigate(item.path)
    }
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
          backgroundColor: pressed ? t.colors.surfaceHover : "transparent",
        })}
      >
        <Text style={{ fontSize: 17, marginRight: t.spacing.sm }}>{item.icon}</Text>
        <Text style={{ flex: 1, fontSize: 14, fontWeight: "600", color: t.colors.text }}>
          {item.label}
        </Text>
        {hasChildren && (
          <Animated.Text style={{ fontSize: 12, color: t.colors.textMuted, transform: [{ rotateZ }] }}>
            ▶
          </Animated.Text>
        )}
      </Pressable>

      {hasChildren && isExpanded && (
        <View style={{ paddingLeft: t.spacing.lg }}>
          {item.children!.map((child) => (
            <Pressable
              key={child.id}
              onPress={() => handleNavigate(child.path)}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: t.spacing.sm,
                paddingHorizontal: t.spacing.md + 4,
                marginRight: t.spacing.sm,
                borderRadius: t.radii.md,
                backgroundColor: pressed ? t.colors.surfaceHover : "transparent",
                borderLeftWidth: 2,
                borderLeftColor: "transparent",
              })}
            >
              <Text style={{ fontSize: 14, marginRight: t.spacing.sm }}>{child.icon}</Text>
              <Text style={{ fontSize: 13, color: t.colors.textSecondary, fontWeight: "500" }}>
                {child.label}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  )
}
