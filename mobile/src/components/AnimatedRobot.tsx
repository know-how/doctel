import React, { useRef, useEffect } from "react"
import { View, Animated, Easing } from "react-native"
import { useTheme } from "../context/ThemeContext"
import { getTokens } from "../theme/themeTokens"

interface AnimatedRobotProps {
  size?: number
  state?: "idle" | "thinking" | "searching" | "processing" | "error"
  showLabel?: boolean
  label?: string
}

function usePulseAnimation(duration = 2000, min = 0.4, max = 1) {
  const anim = useRef(new Animated.Value(min)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: max, duration: duration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(anim, { toValue: min, duration: duration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [duration])
  return anim
}

function useFloatAnimation(duration = 4000, range = 12) {
  const translateY = useRef(new Animated.Value(0)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(translateY, { toValue: -range, duration: duration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(translateY, { toValue: 0, duration: duration / 2, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [duration, range])
  return translateY
}

function useBlinkAnimation() {
  const scaleY = useRef(new Animated.Value(1)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.delay(3000),
        Animated.timing(scaleY, { toValue: 0.1, duration: 100, easing: Easing.linear, useNativeDriver: true }),
        Animated.timing(scaleY, { toValue: 1, duration: 100, easing: Easing.linear, useNativeDriver: true }),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [])
  return scaleY
}

function useScanAnimation() {
  const height = useRef(new Animated.Value(0)).current
  const opacity = useRef(new Animated.Value(0)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(height, { toValue: 1, duration: 1500, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
          Animated.timing(opacity, { toValue: 0.6, duration: 1500, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
        ]),
        Animated.parallel([
          Animated.timing(height, { toValue: 0, duration: 1500, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
          Animated.timing(opacity, { toValue: 0, duration: 1500, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
        ]),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [])
  return { height, opacity }
}

function useShakeAnimation() {
  const translateX = useRef(new Animated.Value(0)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(translateX, { toValue: -4, duration: 50, useNativeDriver: true }),
        Animated.timing(translateX, { toValue: 4, duration: 50, useNativeDriver: true }),
        Animated.timing(translateX, { toValue: -3, duration: 50, useNativeDriver: true }),
        Animated.timing(translateX, { toValue: 3, duration: 50, useNativeDriver: true }),
        Animated.timing(translateX, { toValue: -1, duration: 50, useNativeDriver: true }),
        Animated.timing(translateX, { toValue: 1, duration: 50, useNativeDriver: true }),
        Animated.timing(translateX, { toValue: 0, duration: 50, useNativeDriver: true }),
        Animated.delay(2000),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [])
  return translateX
}

function useSpinAnimation(duration = 1500) {
  const spin = useRef(new Animated.Value(0)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(spin, { toValue: 1, duration, easing: Easing.linear, useNativeDriver: true }),
    )
    loop.start()
    return () => loop.stop()
  }, [duration])
  return spin.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  })
}

export function AnimatedRobot({
  size = 180,
  state = "idle",
  showLabel = false,
  label,
}: AnimatedRobotProps) {
  const { theme } = useTheme()
  const t = getTokens(theme)
  const c = t.colors
  const isDark = theme === "dark"

  const floatY = useFloatAnimation(state === "thinking" ? 3000 : 4000, state === "thinking" ? 8 : 12)
  const blinkScale = useBlinkAnimation()
  const scan = useScanAnimation()
  const shakeX = useShakeAnimation()
  const spin = useSpinAnimation()

  const accentColor = state === "error" ? "#EF4444"
    : state === "processing" ? "#A855F7"
    : state === "searching" ? "#1FE7FF"
    : "#5B88FF"
  const glowColor = state === "error" ? "rgba(239,68,68,0.25)"
    : state === "processing" ? "rgba(168,85,247,0.2)"
    : state === "searching" ? "rgba(31,231,255,0.2)"
    : "rgba(91,136,255,0.2)"
  const headFill = isDark ? "#1A1F35" : "#E8EDF4"
  const eyeBg = isDark ? "#0A0E1A" : "#D0D8E4"
  const scannerColor = state === "error" ? "rgba(239,68,68,0.5)"
    : state === "thinking" ? "rgba(31,231,255,0.5)"
    : "rgba(91,136,255,0.3)"

  const bodyAnimStyle = state === "error"
    ? { transform: [{ translateX: shakeX }] }
    : { transform: [{ translateY: floatY }] }

  const pulseOpacity = usePulseAnimation(
    state === "error" ? 500 : 2000,
    state === "error" ? 0.6 : 0.3,
    state === "error" ? 1 : 0.8,
  )

  const eyeScale = state === "error" ? 1 : blinkScale

  const labelText = label || (
    state === "error" ? "Error" :
    state === "thinking" ? "Thinking..." :
    state === "searching" ? "Searching..." :
    state === "processing" ? "Processing..." :
    "AI Assistant"
  )

  const scanHeightInterpolated = scan.height.interpolate({
    inputRange: [0, 1],
    outputRange: [0, size * 0.5],
  })

  const s = size
  const es = s * 0.06 // eye size ratio

  return (
    <View style={{ alignItems: "center", width: s, height: s + (showLabel ? 30 : 0) }}>
      {/* Glow backdrop */}
      <Animated.View
        style={{
          position: "absolute",
          width: s + 30,
          height: s + 30,
          borderRadius: (s + 30) / 2,
          top: -15,
          left: -15,
          backgroundColor: glowColor,
          opacity: pulseOpacity,
        }}
      />

      {state === "searching" && (
        <View style={{ position: "absolute", width: s, height: s, justifyContent: "center", alignItems: "center" }}>
          <Animated.View
            style={{
              position: "absolute",
              width: s * 0.6,
              height: s * 0.6,
              borderRadius: s * 0.3,
              borderWidth: 2,
              borderColor: accentColor,
              opacity: pulseOpacity,
            }}
          />
        </View>
      )}

      {/* Spinner for processing */}
      {state === "processing" && (
        <Animated.View
          style={{
            position: "absolute",
            width: s * 0.7,
            height: s * 0.7,
            borderRadius: s * 0.35,
            top: s * 0.15,
            left: s * 0.15,
            borderWidth: 3,
            borderColor: accentColor + "20",
            borderTopColor: accentColor,
            transform: [{ rotate: spin }],
          }}
        />
      )}

      {/* Body */}
      <Animated.View style={[{ alignItems: "center" }, bodyAnimStyle]}>
        {/* Scanner beam (thinking) */}
        {state === "thinking" && (
          <Animated.View
            style={{
              width: s * 0.4,
              height: scanHeightInterpolated,
              backgroundColor: scannerColor,
              borderBottomLeftRadius: s * 0.1,
              borderBottomRightRadius: s * 0.1,
              opacity: scan.opacity,
              position: "absolute",
              top: s * 0.38,
              zIndex: -1,
            }}
          />
        )}

        {/* Antenna */}
        <View style={{ width: s * 0.04, height: s * 0.1, backgroundColor: accentColor, borderRadius: s * 0.02 }} />
        <Animated.View
          style={{
            width: s * 0.07,
            height: s * 0.07,
            borderRadius: s * 0.035,
            backgroundColor: accentColor,
            marginBottom: 4,
            opacity: state === "error" ? 0.3 : pulseOpacity,
          }}
        />

        {/* Head */}
        <View
          style={{
            width: s * 0.5,
            height: s * 0.38,
            borderRadius: s * 0.12,
            backgroundColor: headFill,
            borderWidth: 2.5,
            borderColor: accentColor,
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          {/* Glitch overlay for error */}
          {state === "error" && (
            <View
              style={{
                position: "absolute",
                width: "100%",
                height: "100%",
                backgroundColor: accentColor + "30",
              }}
            />
          )}

          {/* Eye background */}
          <View
            style={{
              width: "75%",
              height: "45%",
              borderRadius: s * 0.06,
              backgroundColor: eyeBg,
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-around",
              paddingHorizontal: s * 0.05,
            }}
          >
            {/* Left eye */}
            {state === "error" ? (
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <View style={{ width: es * 0.7, height: 2.5, backgroundColor: accentColor, transform: [{ rotate: "45deg" }], position: "absolute" }} />
                <View style={{ width: es * 0.7, height: 2.5, backgroundColor: accentColor, transform: [{ rotate: "-45deg" }] }} />
              </View>
            ) : state === "searching" ? (
              <Animated.View
                style={{
                  width: es * 0.6,
                  height: es * 0.7,
                  borderRadius: es * 0.3,
                  backgroundColor: accentColor,
                  transform: [{ translateX: pulseOpacity.interpolate({
                    inputRange: [0.3, 0.8],
                    outputRange: [-5, 5],
                  }) }],
                }}
              />
            ) : (
              <Animated.View
                style={{
                  width: es,
                  height: es,
                  borderRadius: es / 2,
                  backgroundColor: accentColor,
                  transform: [{ scaleY: eyeScale }],
                }}
              />
            )}

            {/* Right eye */}
            {state === "error" ? (
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <View style={{ width: es * 0.7, height: 2.5, backgroundColor: accentColor, transform: [{ rotate: "45deg" }], position: "absolute" }} />
                <View style={{ width: es * 0.7, height: 2.5, backgroundColor: accentColor, transform: [{ rotate: "-45deg" }] }} />
              </View>
            ) : state === "searching" ? (
              <Animated.View
                style={{
                  width: es * 0.6,
                  height: es * 0.7,
                  borderRadius: es * 0.3,
                  backgroundColor: accentColor,
                  transform: [{ translateX: pulseOpacity.interpolate({
                    inputRange: [0.3, 0.8],
                    outputRange: [5, -5],
                  }) }],
                }}
              />
            ) : (
              <Animated.View
                style={{
                  width: es,
                  height: es,
                  borderRadius: es / 2,
                  backgroundColor: accentColor,
                  transform: [{ scaleY: eyeScale }],
                }}
              />
            )}
          </View>

          {/* Mouth */}
          {state === "error" ? (
            <View style={{ flexDirection: "row", width: "40%", justifyContent: "center", marginTop: 3 }}>
              <View style={{ width: "60%", height: 2, borderRadius: 1, backgroundColor: accentColor, transform: [{ rotate: "180deg" }] }} />
            </View>
          ) : state === "thinking" || state === "processing" ? (
            <View style={{ width: "30%", height: 2, borderRadius: 1, backgroundColor: accentColor + "80", marginTop: 3 }} />
          ) : (
            <View style={{ width: "35%", height: 2.5, borderRadius: 1.5, backgroundColor: accentColor + "99", marginTop: 3 }} />
          )}
        </View>

        {/* Neck */}
        <View style={{ width: s * 0.14, height: s * 0.08, backgroundColor: accentColor, borderRadius: 2 }} />

        {/* Body / Chest */}
        <View
          style={{
            width: s * 0.34,
            height: s * 0.2,
            borderRadius: s * 0.06,
            backgroundColor: headFill,
            borderWidth: 1.5,
            borderColor: accentColor + "cc",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {/* Chest indicator */}
          <View
            style={{
              width: s * 0.08,
              height: s * 0.08,
              borderRadius: s * 0.04,
              backgroundColor: accentColor,
            }}
          />
        </View>

        {/* Thinking dots */}
        {state === "thinking" && (
          <View style={{ flexDirection: "row", gap: 5, marginTop: 8 }}>
            {[0, 1, 2].map((i) => {
              const dotOpacity = pulseOpacity.interpolate({
                inputRange: [0.3, 0.8],
                outputRange: i === 0 ? [0.3, 1] : i === 1 ? [0.5, 0.8] : [0.7, 0.6],
              })
              return (
                <Animated.View
                  key={i}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 3,
                    backgroundColor: accentColor,
                    opacity: dotOpacity,
                  }}
                />
              )
            })}</View>
        )}
      </Animated.View>

      {/* Label */}
      {showLabel && (
        <View
          style={{
            marginTop: 8,
            backgroundColor: isDark ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.9)",
            paddingHorizontal: 12,
            paddingVertical: 3,
            borderRadius: 10,
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: accentColor }} />
            <Animated.Text
              style={{
                fontSize: 11,
                fontWeight: "600",
                color: accentColor,
                letterSpacing: 0.3,
              }}
            >
              {labelText}
            </Animated.Text>
          </View>
        </View>
      )}
    </View>
  )
}
