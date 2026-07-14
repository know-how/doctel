/**
 * AI Avatar 7-State Definitions
 * Each state maps to a specific UI status in the chat lifecycle.
 */

export type AvatarState =
  | "idle"        // Default state — gentle floating, soft glow
  | "thinking"    // Model is generating a response — scanner active, particles
  | "searching"   // Retrieving documents — eyes scanning, search ring
  | "speaking"    // Response being delivered (TTS) — sound waves
  | "listening"   // Voice input active — audio visualization
  | "processing"  // Loading / busy — data flow spinner
  | "error"       // Error state — red glow, glitch

/** Visual configuration for each avatar state */
export interface AvatarStateConfig {
  /** Label shown beneath the avatar (accessibility & tooltip) */
  label: string
  /** Primary accent color for this state */
  accentColor: string
  /** Glow color (CSS shadow / filter) */
  glowColor: string
  /** Whether the scanner beam is visible */
  scannerVisible: boolean
  /** Scanner beam color */
  scannerColor: string
  /** Eye style: "normal" | "scan" | "x" | "pulse" | "wave" */
  eyeStyle: "normal" | "scan" | "x" | "pulse" | "wave" | "listening"
  /** Whether orbiting particles are shown */
  particles: boolean
  /** Particle color */
  particleColor: string
  /** Whether sound/audio waves are shown */
  waves: boolean
  /** Whether the antenna glow is active */
  antennaGlow: boolean
  /** CSS animation name for the body float */
  bodyAnimation: string
  /** Whether to show a glitch overlay */
  glitch: boolean
  /** Whether to show a ring pulse */
  ringPulse: boolean
  /** Whether to show a spinner ring */
  spinner: boolean
  /** Duration of the main animation cycle (seconds) */
  animationDuration: number
}

export const avatarStates: Record<AvatarState, AvatarStateConfig> = {
  idle: {
    label: "AI Assistant",
    accentColor: "#5B88FF",
    glowColor: "rgba(91,136,255,0.3)",
    scannerVisible: false,
    scannerColor: "rgba(31,231,255,0.3)",
    eyeStyle: "normal",
    particles: false,
    particleColor: "#1FE7FF",
    waves: false,
    antennaGlow: true,
    bodyAnimation: "ai-float",
    glitch: false,
    ringPulse: false,
    spinner: false,
    animationDuration: 4,
  },
  thinking: {
    label: "Thinking...",
    accentColor: "#5B88FF",
    glowColor: "rgba(91,136,255,0.5)",
    scannerVisible: true,
    scannerColor: "rgba(31,231,255,0.7)",
    eyeStyle: "pulse",
    particles: true,
    particleColor: "#5B88FF",
    waves: false,
    antennaGlow: true,
    bodyAnimation: "ai-float-slow",
    glitch: false,
    ringPulse: false,
    spinner: false,
    animationDuration: 3,
  },
  searching: {
    label: "Searching documents...",
    accentColor: "#1FE7FF",
    glowColor: "rgba(31,231,255,0.4)",
    scannerVisible: false,
    scannerColor: "rgba(31,231,255,0.5)",
    eyeStyle: "scan",
    particles: true,
    particleColor: "#1FE7FF",
    waves: false,
    antennaGlow: true,
    bodyAnimation: "ai-float",
    glitch: false,
    ringPulse: true,
    spinner: false,
    animationDuration: 2.5,
  },
  speaking: {
    label: "Speaking",
    accentColor: "#22C55E",
    glowColor: "rgba(34,197,94,0.4)",
    scannerVisible: false,
    scannerColor: "rgba(34,197,94,0.3)",
    eyeStyle: "wave",
    particles: false,
    particleColor: "#22C55E",
    waves: true,
    antennaGlow: true,
    bodyAnimation: "ai-float",
    glitch: false,
    ringPulse: false,
    spinner: false,
    animationDuration: 3,
  },
  listening: {
    label: "Listening...",
    accentColor: "#FBBF24",
    glowColor: "rgba(251,191,36,0.4)",
    scannerVisible: false,
    scannerColor: "rgba(251,191,36,0.3)",
    eyeStyle: "listening",
    particles: false,
    particleColor: "#FBBF24",
    waves: true,
    antennaGlow: true,
    bodyAnimation: "ai-float",
    glitch: false,
    ringPulse: true,
    spinner: false,
    animationDuration: 3,
  },
  processing: {
    label: "Processing...",
    accentColor: "#A855F7",
    glowColor: "rgba(168,85,247,0.4)",
    scannerVisible: false,
    scannerColor: "rgba(168,85,247,0.3)",
    eyeStyle: "pulse",
    particles: true,
    particleColor: "#A855F7",
    waves: false,
    antennaGlow: true,
    bodyAnimation: "ai-float",
    glitch: false,
    ringPulse: false,
    spinner: true,
    animationDuration: 2,
  },
  error: {
    label: "Error",
    accentColor: "#EF4444",
    glowColor: "rgba(239,68,68,0.5)",
    scannerVisible: false,
    scannerColor: "rgba(239,68,68,0.3)",
    eyeStyle: "x",
    particles: false,
    particleColor: "#EF4444",
    waves: false,
    antennaGlow: false,
    bodyAnimation: "ai-shake",
    glitch: true,
    ringPulse: false,
    spinner: false,
    animationDuration: 0.5,
  },
}
