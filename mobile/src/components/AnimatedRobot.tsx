import React, { useEffect, useRef } from "react";
import { View, Animated, Easing, Text } from "react-native";

export const AnimatedRobot = () => {
  const floatAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim, {
          toValue: -15,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(floatAnim, {
          toValue: 0,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, [floatAnim]);

  return (
    <Animated.View style={{ transform: [{ translateY: floatAnim }], alignItems: 'center', marginVertical: 30 }}>
      <View style={{
        width: 90, height: 90, borderRadius: 28,
        backgroundColor: "rgba(91,136,255,0.15)",
        borderWidth: 2, borderColor: "#1FE7FF",
        alignItems: 'center', justifyContent: 'center',
        shadowColor: "#1FE7FF", shadowOpacity: 0.6, shadowRadius: 20, shadowOffset: { width: 0, height: 0 },
        elevation: 10
      }}>
        <Text style={{ fontSize: 46 }}>🤖</Text>
      </View>
      {/* Scanner beam */}
      <View style={{
        width: 140, height: 50, borderBottomLeftRadius: 70, borderBottomRightRadius: 70,
        backgroundColor: "rgba(31,231,255,0.12)", marginTop: -15, zIndex: -1
      }} />
    </Animated.View>
  );
};
