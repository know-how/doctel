import React, { useEffect, useRef } from "react";
import { View, Animated, Easing, Text } from "react-native";

export const DocChatAnimation = () => {
  const floatHuman = useRef(new Animated.Value(0)).current;
  const floatBolt = useRef(new Animated.Value(0)).current;
  const docX = useRef(new Animated.Value(0)).current;
  const docOpacity = useRef(new Animated.Value(1)).current;
  const answerX = useRef(new Animated.Value(0)).current;
  const answerOpacity = useRef(new Animated.Value(0)).current;
  const glassShimmer = useRef(new Animated.Value(0)).current;
  const boltPulse = useRef(new Animated.Value(0)).current;
  const typingDots = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Human floating
    Animated.loop(
      Animated.sequence([
        Animated.timing(floatHuman, {
          toValue: -6,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(floatHuman, {
          toValue: 0,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Bolt floating
    Animated.loop(
      Animated.sequence([
        Animated.timing(floatBolt, {
          toValue: -8,
          duration: 2200,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(floatBolt, {
          toValue: 0,
          duration: 2200,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Document animating right
    Animated.loop(
      Animated.sequence([
        Animated.timing(docOpacity, {
          toValue: 1,
          duration: 0,
          useNativeDriver: true,
        }),
        Animated.timing(docX, {
          toValue: 100,
          duration: 2500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(docOpacity, {
          toValue: 0,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(docX, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
        Animated.timing(docOpacity, {
          toValue: 0,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Answer animating left
    Animated.loop(
      Animated.sequence([
        Animated.timing(answerOpacity, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
        Animated.timing(answerX, {
          toValue: 100,
          duration: 2500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(answerOpacity, {
          toValue: 1,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(answerX, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
        Animated.timing(answerOpacity, {
          toValue: 0,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(answerX, {
          toValue: 100,
          duration: 2500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(answerOpacity, {
          toValue: 1,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(answerX, {
          toValue: 100,
          duration: 500,
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Glass shimmer
    Animated.loop(
      Animated.sequence([
        Animated.timing(glassShimmer, {
          toValue: 1,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(glassShimmer, {
          toValue: 0,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Bolt pulse
    Animated.loop(
      Animated.sequence([
        Animated.timing(boltPulse, {
          toValue: 1,
          duration: 1500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(boltPulse, {
          toValue: 0,
          duration: 1500,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Typing dots
    Animated.loop(
      Animated.sequence([
        Animated.timing(typingDots, {
          toValue: 1,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(typingDots, {
          toValue: 0,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  const boltOpacity = boltPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.6, 1],
  });

  const typingOpacity = typingDots.interpolate({
    inputRange: [0, 1],
    outputRange: [0.3, 1],
  });

  return (
    <View style={{ alignItems: "center", marginVertical: 20 }}>
      {/* Main scene container */}
      <View
        style={{
          width: 280,
          height: 170,
          position: "relative",
          backgroundColor: "rgba(10,16,32,0.4)",
          borderRadius: 20,
          borderWidth: 1,
          borderColor: "rgba(91,136,255,0.1)",
          overflow: "hidden",
        }}
      >
        {/* Desks */}
        <View
          style={{
            position: "absolute",
            bottom: 15,
            left: 15,
            width: 100,
            height: 6,
            borderRadius: 3,
            backgroundColor: "rgba(255,255,255,0.1)",
          }}
        />
        <View
          style={{
            position: "absolute",
            bottom: 15,
            right: 15,
            width: 100,
            height: 6,
            borderRadius: 3,
            backgroundColor: "rgba(255,255,255,0.1)",
          }}
        />

        {/* Glass partition */}
        <View
          style={{
            position: "absolute",
            left: "50%",
            top: 15,
            bottom: 25,
            width: 3,
            backgroundColor: "rgba(31,231,255,0.15)",
            borderRadius: 2,
          }}
        />
        <View
          style={{
            position: "absolute",
            left: "50%",
            top: 15,
            width: 3,
            height: 40,
            backgroundColor: "rgba(255,255,255,0.12)",
            borderRadius: 2,
          }}
        />

        {/* Human side */}
        <Animated.View
          style={{
            position: "absolute",
            left: 30,
            bottom: 45,
            transform: [{ translateY: floatHuman }],
          }}
        >
          {/* Head */}
          <View
            style={{
              width: 36,
              height: 36,
              borderRadius: 18,
              backgroundColor: "#374151",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ fontSize: 14 }}>👤</Text>
          </View>
          {/* Body */}
          <View
            style={{
              width: 28,
              height: 18,
              borderRadius: 8,
              backgroundColor: "rgba(99,102,241,0.7)",
              alignSelf: "center",
              marginTop: -4,
            }}
          />
        </Animated.View>

        {/* Bolt/AI side */}
        <Animated.View
          style={{
            position: "absolute",
            right: 25,
            bottom: 45,
            transform: [{ translateY: floatBolt }],
            opacity: boltOpacity,
          }}
        >
          {/* Bolt head */}
          <View
            style={{
              width: 46,
              height: 38,
              borderRadius: 12,
              backgroundColor: "#1A1F35",
              borderWidth: 2,
              borderColor: "#1FE7FF",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ fontSize: 14 }}>⚡</Text>
          </View>
          {/* Antenna */}
          <View
            style={{
              width: 2,
              height: 10,
              backgroundColor: "#5B88FF",
              alignSelf: "center",
            }}
          />
          <View
            style={{
              width: 7,
              height: 7,
              borderRadius: 4,
              backgroundColor: "#1FE7FF",
              alignSelf: "center",
              marginTop: -2,
              marginBottom: 2,
            }}
          />
          {/* Body */}
          <View
            style={{
              width: 30,
              height: 20,
              borderRadius: 5,
              backgroundColor: "rgba(31,231,255,0.7)",
              alignSelf: "center",
              marginTop: -4,
            }}
          />
          {/* Processing ring */}
          <View
            style={{
              width: 24,
              height: 24,
              borderRadius: 12,
              borderWidth: 2,
              borderColor: "#1FE7FF",
              borderStyle: "dashed",
              position: "absolute",
              top: -8,
              right: -8,
              opacity: 0.5,
            }}
          />
        </Animated.View>

        {/* Document moving right */}
        <Animated.View
          style={{
            position: "absolute",
            top: 40,
            left: 50,
            transform: [{ translateX: docX }],
            opacity: docOpacity,
          }}
        >
          <View
            style={{
              width: 24,
              height: 30,
              borderRadius: 4,
              backgroundColor: "#F59E0B",
              alignItems: "center",
              justifyContent: "center",
              borderWidth: 1,
              borderColor: "#D97706",
            }}
          >
            <Text style={{ fontSize: 8, color: "#78350F", fontWeight: "800" }}>PDF</Text>
          </View>
        </Animated.View>

        {/* Answer moving left */}
        <Animated.View
          style={{
            position: "absolute",
            top: 40,
            left: 190,
            transform: [{ translateX: Animated.multiply(answerX, -1) }],
            opacity: answerOpacity,
          }}
        >
          <View
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              backgroundColor: "#10B981",
              alignItems: "center",
              justifyContent: "center",
              borderWidth: 1,
              borderColor: "#34D399",
            }}
          >
            <Text style={{ fontSize: 14, color: "#FFFFFF" }}>✓</Text>
          </View>
        </Animated.View>

        {/* Chat bubble from human */}
        <View
          style={{
            position: "absolute",
            top: 18,
            left: 60,
            backgroundColor: "rgba(99,102,241,0.8)",
            paddingHorizontal: 8,
            paddingVertical: 4,
            borderRadius: 12,
            borderTopLeftRadius: 2,
          }}
        >
          <View style={{ flexDirection: "row", gap: 3 }}>
            <View style={{ width: 3, height: 3, borderRadius: 2, backgroundColor: "#FFF", opacity: 0.6 }} />
            <View style={{ width: 3, height: 3, borderRadius: 2, backgroundColor: "#FFF", opacity: 0.9 }} />
            <View style={{ width: 3, height: 3, borderRadius: 2, backgroundColor: "#FFF", opacity: 0.6 }} />
          </View>
        </View>

        {/* Chat bubble from AI */}
        <View
          style={{
            position: "absolute",
            top: 18,
            right: 60,
            backgroundColor: "rgba(31,231,255,0.8)",
            paddingHorizontal: 8,
            paddingVertical: 4,
            borderRadius: 12,
            borderTopRightRadius: 2,
          }}
        >
          <View style={{ flexDirection: "row", gap: 3 }}>
            <Animated.View style={{ width: 3, height: 3, borderRadius: 2, backgroundColor: "#FFF", opacity: typingOpacity }} />
            <Animated.View style={{ width: 3, height: 3, borderRadius: 2, backgroundColor: "#FFF", opacity: typingDots.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.4, 0.9, 0.4] }) }} />
            <Animated.View style={{ width: 3, height: 3, borderRadius: 2, backgroundColor: "#FFF", opacity: typingOpacity }} />
          </View>
        </View>
      </View>

      {/* Labels */}
      <View style={{ flexDirection: "row", justifyContent: "space-between", width: 240, marginTop: 8 }}>
        <Text style={{ fontSize: 9, color: "rgba(255,255,255,0.4)", fontWeight: "600" }}>
          User
        </Text>
        <Text style={{ fontSize: 9, color: "rgba(31,231,255,0.5)", fontWeight: "600" }}>
          DocIntel AI
        </Text>
      </View>
    </View>
  );
};