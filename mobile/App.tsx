import React, { useEffect, useState } from "react"
import { SafeAreaView, View, Text, Pressable, Modal, TextInput, Image } from "react-native"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { DocumentUploadScreen } from "./src/screens/DocumentUploadScreen"
import { ChatScreen } from "./src/screens/ChatScreen"
import { useEcNumber } from "./src/hooks/useEcNumber"
import { colors } from "./src/theme/colors"
import { login, setAuthToken, requestEmailOtp, verifyEmailOtp } from "./src/api/client"
import zetdcLogo from "./src/assets/zetdc-logo.png"

export default function App() {
  const [documentId, setDocumentId] = useState("doc_1")
  const { ecNumber, setEcNumber } = useEcNumber()
  const [activeTab, setActiveTab] = useState<"chat" | "upload">("chat")
  const [inputValue, setInputValue] = useState(ecNumber)
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [emailCode, setEmailCode] = useState("")
  const [emailSent, setEmailSent] = useState(false)
  const [loginMode, setLoginMode] = useState<"ec" | "email">("ec")
  const [touched, setTouched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState("")
  const [hasToken, setHasToken] = useState(false)
  const [checkingToken, setCheckingToken] = useState(true)

  const hasEc = !!ecNumber
  const showError = touched && !inputValue.trim()
  const showPasswordError = touched && !password.trim()
  const isAuthenticated = hasEc && hasToken
  const showEmailError = touched && !email.trim()
  const showEmailCodeError = touched && !emailCode.trim()
  const isValidZetdcEmail =
    !!email.trim() && email.trim().toLowerCase().endsWith("@zetdc.co.zw")

  useEffect(() => {
    const loadToken = async () => {
      const token = await AsyncStorage.getItem("docintel_auth_token")
      setHasToken(!!token)
      setCheckingToken(false)
    }
    loadToken()
  }, [])

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <View
        style={{
          padding: 16,
          backgroundColor: colors.primary,
          borderBottomWidth: 2,
          borderBottomColor: colors.secondary,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Image
            source={zetdcLogo}
            resizeMode="contain"
            style={{
              width: 36,
              height: 36,
            }}
          />
          <View>
            <Text style={{ color: "#FFFFFF", fontSize: 18, fontWeight: "700" }}>
              ZETDC DocIntel
            </Text>
            <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 12 }}>
              Internal Document AI
            </Text>
          </View>
        </View>
      </View>

      <View style={{ flexDirection: "row", gap: 8, padding: 16 }}>
        <Pressable
          onPress={() => setActiveTab("chat")}
          style={[
            tabStyle,
            activeTab === "chat" ? activeTabStyle : inactiveTabStyle,
          ]}
        >
          <Text style={activeTab === "chat" ? activeTabText : inactiveTabText}>
            Chat
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setActiveTab("upload")}
          style={[
            tabStyle,
            activeTab === "upload" ? activeTabStyle : inactiveTabStyle,
          ]}
        >
          <Text style={activeTab === "upload" ? activeTabText : inactiveTabText}>
            Upload
          </Text>
        </Pressable>
      </View>

      <View style={{ flex: 1, padding: 16 }}>
        {activeTab === "chat" ? (
          isAuthenticated ? (
            <ChatScreen documentId={documentId} />
          ) : (
            <View style={{ gap: 8 }}>
              <Text style={{ fontSize: 16, fontWeight: "600", color: colors.textPrimary }}>
                Sign in to start chatting
              </Text>
              <Text style={{ fontSize: 13, color: colors.textMuted }}>
                Upload a document and verify your account to unlock insights.
              </Text>
            </View>
          )
        ) : (
          <DocumentUploadScreen
            onUploaded={(id) => {
              setDocumentId(id)
              setActiveTab("chat")
            }}
          />
        )}
      </View>

      <Modal visible={!isAuthenticated} transparent animationType="fade">
        <View style={overlayStyle}>
          <View style={modalStyle}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 10 }}>
              <Image
                source={zetdcLogo}
                resizeMode="contain"
                style={{
                  width: 44,
                  height: 44,
                }}
              />
              <View>
                <Text style={{ fontSize: 12, color: colors.textMuted, fontWeight: "600" }}>
                  Zimbabwe Electricity Transmission & Distribution
                </Text>
                <Text style={{ fontSize: 18, fontWeight: "700", color: colors.textPrimary }}>
                  DocIntel Portal
                </Text>
              </View>
            </View>
            <Text style={{ fontSize: 18, fontWeight: "600", color: colors.textPrimary }}>
              Sign in to continue
            </Text>
            <Text style={{ fontSize: 13, color: colors.textMuted, marginTop: 6 }}>
              Use your EC number or ZETDC email. Your history will be saved.
            </Text>
            {checkingToken ? (
              <Text style={{ marginTop: 12, color: colors.textMuted }}>Checking session...</Text>
            ) : (
              <>
                <View style={{ flexDirection: "row", gap: 8, marginTop: 12, marginBottom: 8 }}>
                  <Pressable
                    onPress={() => {
                      setLoginMode("ec")
                      setAuthError("")
                      setTouched(false)
                      setEmailSent(false)
                      setEmailCode("")
                    }}
                    style={[
                      toggleButtonStyle,
                      loginMode === "ec" ? toggleActiveStyle : toggleInactiveStyle,
                    ]}
                  >
                    <Text style={loginMode === "ec" ? toggleActiveText : toggleInactiveText}>
                      EC + Password
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={() => {
                      setLoginMode("email")
                      setAuthError("")
                      setTouched(false)
                    }}
                    style={[
                      toggleButtonStyle,
                      loginMode === "email" ? toggleActiveStyle : toggleInactiveStyle,
                    ]}
                  >
                    <Text style={loginMode === "email" ? toggleActiveText : toggleInactiveText}>
                      ZETDC Email
                    </Text>
                  </Pressable>
                </View>
                {loginMode === "ec" ? (
                  <>
                    <TextInput
                      value={inputValue}
                      onChangeText={setInputValue}
                      onBlur={() => setTouched(true)}
                      placeholder="EC12345"
                      style={inputStyle}
                    />
                    {showError ? (
                      <Text style={{ color: colors.danger, marginBottom: 8 }}>
                        EC number is required.
                      </Text>
                    ) : null}
                    <TextInput
                      value={password}
                      onChangeText={setPassword}
                      onBlur={() => setTouched(true)}
                      placeholder="Password"
                      secureTextEntry
                      style={inputStyle}
                    />
                    {showPasswordError ? (
                      <Text style={{ color: colors.danger, marginBottom: 8 }}>
                        Password is required.
                      </Text>
                    ) : null}
                  </>
                ) : (
                  <>
                    <TextInput
                      value={email}
                      onChangeText={setEmail}
                      onBlur={() => setTouched(true)}
                      placeholder="name@zetdc.co.zw"
                      autoCapitalize="none"
                      style={inputStyle}
                    />
                    {(showEmailError || (touched && !isValidZetdcEmail)) ? (
                      <Text style={{ color: colors.danger, marginBottom: 8 }}>
                        Enter a valid ZETDC email.
                      </Text>
                    ) : null}
                    {emailSent ? (
                      <>
                        <TextInput
                          value={emailCode}
                          onChangeText={setEmailCode}
                          onBlur={() => setTouched(true)}
                          placeholder="6-digit code"
                          keyboardType="number-pad"
                          style={inputStyle}
                        />
                        {showEmailCodeError ? (
                          <Text style={{ color: colors.danger, marginBottom: 8 }}>
                            Code is required.
                          </Text>
                        ) : null}
                        <Pressable
                          onPress={async () => {
                            try {
                              setLoading(true)
                              await requestEmailOtp({ email: email.trim() })
                            } catch (e: any) {
                              setAuthError(e.message ?? "Failed to resend code.")
                            } finally {
                              setLoading(false)
                            }
                          }}
                          style={secondaryButtonStyle}
                          disabled={loading}
                        >
                          <Text style={{ color: colors.primary }}>
                            Resend Code
                          </Text>
                        </Pressable>
                      </>
                    ) : null}
                  </>
                )}
                {authError ? (
                  <Text style={{ color: colors.danger, marginBottom: 8 }}>{authError}</Text>
                ) : null}
                <Pressable
                  onPress={async () => {
                    setTouched(true)
                    setAuthError("")
                    try {
                      setLoading(true)
                      if (loginMode === "ec") {
                        if (!inputValue.trim() || !password.trim()) return
                        const res = await login({
                          ec_number: inputValue.trim(),
                          password: password,
                        })
                        await setEcNumber(res.ec_number)
                        await setAuthToken(res.access_token)
                        setHasToken(true)
                        setPassword("")
                      } else {
                        if (!email.trim() || !isValidZetdcEmail) return
                        if (!emailSent) {
                          await requestEmailOtp({ email: email.trim() })
                          setEmailSent(true)
                        } else {
                          if (!emailCode.trim()) return
                          const res = await verifyEmailOtp({
                            email: email.trim(),
                            code: emailCode.trim(),
                          })
                          await setEcNumber(res.ec_number)
                          await setAuthToken(res.access_token)
                          setHasToken(true)
                          setEmailCode("")
                        }
                      }
                    } catch (e: any) {
                      setAuthError(e.message ?? "Login failed.")
                    } finally {
                      setLoading(false)
                    }
                  }}
                  style={[
                    primaryButtonStyle,
                    loading ? { opacity: 0.8 } : null,
                  ]}
                  disabled={loading}
                >
                  <Text style={{ color: "#FFFFFF" }}>
                    {loading
                      ? loginMode === "email" && !emailSent
                        ? "Sending..."
                        : "Signing in..."
                      : loginMode === "email" && !emailSent
                        ? "Send Code"
                        : "Continue"}
                  </Text>
                </Pressable>
              </>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  )
}

const tabStyle = {
  flex: 1,
  paddingVertical: 10,
  borderRadius: 8,
  alignItems: "center",
  borderWidth: 1,
  borderColor: colors.border,
} as const

const activeTabStyle = {
  backgroundColor: colors.primary,
} as const

const inactiveTabStyle = {
  backgroundColor: "#E7F0FF",
} as const

const activeTabText = {
  color: "#FFFFFF",
  fontWeight: "600",
} as const

const inactiveTabText = {
  color: colors.primaryDark,
  fontWeight: "600",
} as const

const toggleButtonStyle = {
  flex: 1,
  paddingVertical: 8,
  borderRadius: 999,
  alignItems: "center",
} as const

const toggleActiveStyle = {
  backgroundColor: "#E7F0FF",
  borderWidth: 1,
  borderColor: colors.primary,
} as const

const toggleInactiveStyle = {
  backgroundColor: "#FFFFFF",
  borderWidth: 1,
  borderColor: colors.border,
} as const

const toggleActiveText = {
  color: colors.textPrimary,
  fontWeight: "600",
  fontSize: 12,
} as const

const toggleInactiveText = {
  color: colors.textMuted,
  fontWeight: "600",
  fontSize: 12,
} as const

const overlayStyle = {
  flex: 1,
  backgroundColor: "rgba(11,78,162,0.35)",
  alignItems: "center",
  justifyContent: "center",
} as const

const modalStyle = {
  backgroundColor: "#FFFFFF",
  borderRadius: 12,
  padding: 20,
  width: "85%",
  borderWidth: 1,
  borderColor: colors.border,
  shadowColor: "#0B4EA2",
  shadowOpacity: 0.2,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 6 },
  elevation: 6,
} as const

const inputStyle = {
  borderWidth: 1,
  borderColor: colors.border,
  borderRadius: 8,
  paddingHorizontal: 12,
  paddingVertical: 8,
  marginTop: 12,
  marginBottom: 8,
  backgroundColor: "#FFFFFF",
} as const

const primaryButtonStyle = {
  backgroundColor: colors.primary,
  paddingVertical: 12,
  borderRadius: 8,
  alignItems: "center",
} as const

const secondaryButtonStyle = {
  marginTop: 8,
  borderWidth: 1,
  borderColor: colors.primary,
  paddingVertical: 10,
  borderRadius: 8,
  alignItems: "center",
  backgroundColor: "#FFFFFF",
} as const
