import React, { useEffect, useRef } from "react";
import { View, Animated, Text } from "react-native";

export const RobotSearching = () => {
  const bounceAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(bounceAnim, { toValue: -4, duration: 500, useNativeDriver: true }),
        Animated.timing(bounceAnim, { toValue: 0, duration: 500, useNativeDriver: true })
      ])
    ).start();

    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 0.4, duration: 800, useNativeDriver: true })
      ])
    ).start();
  }, [bounceAnim, pulseAnim]);

  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 }}>
      <Animated.View style={{ transform: [{ translateY: bounceAnim }] }}>
        <Text style={{ fontSize: 20 }}>🤖</Text>
      </Animated.View>
      <Animated.Text style={{ opacity: pulseAnim, color: "rgba(255,255,255,0.7)", fontSize: 13, fontWeight: "500" }}>
        AI is searching...
      </Animated.Text>
    </View>
  );
};
