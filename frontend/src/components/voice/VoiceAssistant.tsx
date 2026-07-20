/**
 * VoiceAssistant.tsx – Multimodal voice assistant component for DocTel
 *
 * Features:
 *   - Push-to-talk button with animated ring
 *   - Continuous listening mode with VAD auto-stop
 *   - Real-time waveform visualization
 *   - Spectrum/bar visualization mode
 *   - Transcription state display (Listening → Transcribing → AI Responding)
 *   - Voice conversation (STT → AI → TTS) in one flow
 *   - Voice command detection and routing
 *   - Audio playback for AI responses
 *   - Voice mode toggle (PTT / Continuous)
 *   - Duration counter
 *   - Error handling with user-friendly messages
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useVoiceRecording, WaveformPoint, formatDuration } from "../../hooks/useVoiceRecording";
import {
  transcribeAudio,
  checkVoiceHealth,
  playBase64Audio,
  voiceConversationText,
} from "../../services/voiceService";

// ── Types ────────────────────────────────────────────────────────────────────

export type VoiceState =
  | "idle"
  | "listening"
  | "transcribing"
  | "processing"
  | "responding"
  | "error";

export interface VoiceAssistantProps {
  /** Called when transcription is complete with the text */
  onTranscriptionComplete?: (text: string) => void;
  /** Called when a voice command is detected */
  onCommandDetected?: (command: string, intent: string) => void;
  /** Called when the AI voice response is complete */
  onResponseComplete?: (text: string) => void;
  /** Disable the voice assistant */
  disabled?: boolean;
  /** Visual variant */
  variant?: "full" | "compact" | "minimal";
  /** Voice mode */
  defaultMode?: "push-to-talk" | "continuous";
  /** Enable full conversation mode (STT + AI + TTS) */
  conversationMode?: boolean;
  /** Session ID for conversation continuity */
  sessionId?: string;
}

// ── Waveform Visualizer ──────────────────────────────────────────────────────

interface WaveformVisualizerProps {
  waveform: WaveformPoint[];
  audioLevel: number;
  isRecording: boolean;
  isResponding?: boolean;
  variant?: "wave" | "bars" | "circle";
  color?: string;
}

const WaveformVisualizer: React.FC<WaveformVisualizerProps> = ({
  waveform,
  audioLevel,
  isRecording,
  isResponding,
  variant = "wave",
  color = "#5B88FF",
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width;
    const h = rect.height;

    ctx.clearRect(0, 0, w, h);

    if (variant === "wave") {
      // Smooth wave visualization
      const points = waveform.map((p) => p.value);
      const midY = h / 2;

      ctx.beginPath();
      ctx.moveTo(0, midY);

      for (let i = 0; i < points.length; i++) {
        const x = (i / Math.max(points.length - 1, 1)) * w;
        const amplitude = points[i] * (h * 0.4);
        ctx.lineTo(x, midY - amplitude);
      }

      // Mirror bottom
      for (let i = points.length - 1; i >= 0; i--) {
        const x = (i / Math.max(points.length - 1, 1)) * w;
        const amplitude = points[i] * (h * 0.4);
        ctx.lineTo(x, midY + amplitude);
      }

      ctx.closePath();

      if (isResponding) {
        const gradient = ctx.createLinearGradient(0, 0, w, 0);
        gradient.addColorStop(0, "#10B981");
        gradient.addColorStop(0.5, color);
        gradient.addColorStop(1, "#8B5CF6");
        ctx.fillStyle = gradient;
      } else {
        ctx.fillStyle = isRecording ? color : "rgba(91,136,255,0.3)";
      }

      ctx.globalAlpha = isRecording || isResponding ? 0.8 : 0.3;
      ctx.fill();
    } else if (variant === "bars") {
      // Bar visualization
      const barCount = Math.min(waveform.length, 32);
      const barWidth = w / barCount - 2;
      const barGap = 2;

      for (let i = 0; i < barCount; i++) {
        const value = waveform[i]?.value || 0;
        const barHeight = Math.max(2, value * h * 0.6);
        const x = i * (barWidth + barGap);
        const y = (h - barHeight) / 2;

        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, [barWidth / 2, barWidth / 2, barWidth / 2, barWidth / 2]);
        const hue = isResponding ? 160 + i * 2 : 220 + i * 2;
        ctx.fillStyle = `hsl(${hue}, 70%, ${50 + value * 30}%)`;
        ctx.globalAlpha = 0.7 + value * 0.3;
        ctx.fill();
      }
    } else if (variant === "circle") {
      // Circular visualization
      const cx = w / 2;
      const cy = h / 2;
      const radius = Math.min(cx, cy) - 10;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = isResponding ? "#10B981" : color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.2;
      ctx.stroke();

      // Active ring
      const activeAngle = audioLevel * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, -Math.PI / 2, -Math.PI / 2 + activeAngle);
      ctx.strokeStyle = isResponding ? "#34D399" : color;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 0.8;
      ctx.stroke();

      // Inner pulse
      const pulseRadius = 4 + audioLevel * 12;
      const pulseGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseRadius);
      pulseGrad.addColorStop(0, isResponding ? "#10B981" : color);
      pulseGrad.addColorStop(1, "transparent");
      ctx.fillStyle = pulseGrad;
      ctx.globalAlpha = 0.5;
      ctx.fill();
    }

    animRef.current = requestAnimationFrame(() => {});
    return () => cancelAnimationFrame(animRef.current);
  }, [waveform, audioLevel, isRecording, isResponding, variant, color, w, h]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: "100%",
        height: variant === "circle" ? 80 : 48,
        borderRadius: 12,
      }}
    />
  );
};

// ── Voice State Display ──────────────────────────────────────────────────────

const VoiceStateDisplay: React.FC<{
  state: VoiceState;
  error: string | null;
  durationMs: number;
  audioLevel: number;
  isRecording: boolean;
}> = ({ state, error, durationMs, audioLevel, isRecording }) => {
  const stateConfig: Record<VoiceState, { label: string; emoji: string; color: string }> = {
    idle: { label: "Press to speak", emoji: "🎤", color: "rgba(255,255,255,0.4)" },
    listening: { label: "Listening...", emoji: "🔴", color: "#EF4444" },
    transcribing: { label: "Transcribing...", emoji: "🔄", color: "#F59E0B" },
    processing: { label: "Searching knowledge base...", emoji: "🔍", color: "#5B88FF" },
    responding: { label: "Speaking...", emoji: "🔊", color: "#10B981" },
    error: { label: error || "Error", emoji: "⚠️", color: "#EF4444" },
  };

  const cfg = stateConfig[state];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px",
        borderRadius: 10,
        background: "rgba(255,255,255,0.04)",
        border: `1px solid ${cfg.color}33`,
      }}
    >
      {/* Animated indicator */}
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          backgroundColor: cfg.color,
          animation: isRecording || state === "responding" ? "pulse 1s ease-in-out infinite" : "none",
          flexShrink: 0,
        }}
      />

      {/* Label */}
      <span style={{ fontSize: 12, color: cfg.color, fontWeight: 500, fontFamily: "'Inter', sans-serif" }}>
        {cfg.emoji} {cfg.label}
      </span>

      {/* Duration */}
      {isRecording && (
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", fontFamily: "'Inter', sans-serif", marginLeft: "auto" }}>
          {formatDuration(durationMs)}
        </span>
      )}

      {/* Audio level meter */}
      {isRecording && (
        <div
          style={{
            width: 40,
            height: 4,
            borderRadius: 2,
            background: "rgba(255,255,255,0.1)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${audioLevel * 100}%`,
              height: "100%",
              background: `linear-gradient(90deg, ${cfg.color}, ${cfg.color}88)`,
              borderRadius: 2,
              transition: "width 0.08s linear",
            }}
          />
        </div>
      )}
    </div>
  );
};

// ── Main Component ───────────────────────────────────────────────────────────

export const VoiceAssistant: React.FC<VoiceAssistantProps> = ({
  onTranscriptionComplete,
  onCommandDetected,
  onResponseComplete,
  disabled = false,
  variant = "full",
  defaultMode = "push-to-talk",
  conversationMode = false,
  sessionId: propSessionId,
}) => {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [mode, setModeInternal] = useState<"push-to-talk" | "continuous">(defaultMode);
  const [transcript, setTranscript] = useState<string>("");
  const [responseText, setResponseText] = useState<string>("");
  const [voiceReady, setVoiceReady] = useState<boolean | null>(null);
  const sessionIdRef = useRef<string>(propSessionId || crypto.randomUUID());

  const {
    state: recState,
    audioLevel,
    waveform,
    durationMs,
    error: recError,
    micAvailable,
    browserSupported,
    start,
    stop,
    getBlob,
    reset,
    play,
    isPlaying,
    setMode: setRecMode,
  } = useVoiceRecording({
    mode: defaultMode === "continuous" ? "continuous" : "push-to-talk",
    silenceTimeoutMs: 1500,
    maxDurationMs: 30000,
  });

  // ── Check voice health on mount ────────────────────────────────────────────
  useEffect(() => {
    checkVoiceHealth()
      .then((h) => setVoiceReady(h.ok && (h.stt_available || h.edge_tts)))
      .catch(() => setVoiceReady(false));
  }, []);

  // ── Sync recording state to voice state ────────────────────────────────────
  useEffect(() => {
    if (recState === "recording") {
      setVoiceState("listening");
    } else if (recState === "processing") {
      setVoiceState("transcribing");
    } else if (recState === "error") {
      setVoiceState("error");
    } else if (voiceState !== "responding" && voiceState !== "transcribing") {
      setVoiceState("idle");
    }
  }, [recState]);

  // ── Handle voice result (transcription complete) ───────────────────────────
  const handleVoiceResult = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      setTranscript(text);
      setVoiceState("processing");

      // Check for voice commands first
      try {
        const { classifyCommand } = await import("../../services/voiceService");
        const cmd = await classifyCommand(text);
        if (cmd.confidence > 0.6) {
          onCommandDetected?.(text, cmd.intent);
        }
      } catch {
        // Continue with normal transcription
      }

      if (conversationMode) {
        // Full conversation mode: transcribe → AI → TTS
        setVoiceState("responding");

        try {
          const data = await voiceConversationText(text, sessionIdRef.current);
          setResponseText(data.text || "");

          if (data.audio_base64) {
            playBase64Audio(data.audio_base64, data.audio_format || "mp3", () => {
              setVoiceState("idle");
              onResponseComplete?.(data.text || "");
            });
            return;
          }
        } catch {
          // TTS failed, just return text
        }

        setVoiceState("idle");
        onResponseComplete?.(text);
      } else {
        // Simple mode: just return the transcription
        setVoiceState("idle");
        onTranscriptionComplete?.(text);
      }

      setTranscript("");
    },
    [conversationMode, onCommandDetected, onResponseComplete, onTranscriptionComplete]
  );

  // ── Handle recording completion ────────────────────────────────────────────
  const handleRecordingComplete = useCallback(async () => {
    const blob = getBlob();
    if (!blob) return;

    setVoiceState("transcribing");

    try {
      const result = await transcribeAudio(blob);
      if (result.text?.trim()) {
        await handleVoiceResult(result.text);
      } else {
        setVoiceState("idle");
      }
    } catch (err: any) {
      setVoiceState("error");
      console.error("Transcription failed:", err);
      setTimeout(() => setVoiceState("idle"), 2000);
    }
  }, [getBlob, handleVoiceResult]);

  // ── Push-to-talk click handler ─────────────────────────────────────────────
  const handlePushToTalk = useCallback(async () => {
    if (disabled || !voiceReady) return;

    if (recState === "recording") {
      await stop();
      await handleRecordingComplete();
    } else {
      reset();
      await start();
    }
  }, [disabled, voiceReady, recState, stop, handleRecordingComplete, reset, start]);

  // ── Continuous mode auto-handler ───────────────────────────────────────────
  useEffect(() => {
    if (mode !== "continuous") return;
    if (recState === "idle" && voiceState === "idle") {
      const timer = setTimeout(() => {
        start().catch(() => {});
      }, 500);
      return () => clearTimeout(timer);
    }
    if (recState === "idle" && voiceState === "transcribing") {
      // Recording was auto-stopped by VAD, process the result
      handleRecordingComplete();
    }
  }, [mode, recState, voiceState, start, handleRecordingComplete]);

  // ── Mode toggle ────────────────────────────────────────────────────────────
  const handleModeToggle = useCallback(() => {
    const nextMode = mode === "push-to-talk" ? "continuous" : "push-to-talk";
    setModeInternal(nextMode);
    setRecMode(nextMode);
    reset();
  }, [mode, setRecMode, reset]);

  // ── Styles ─────────────────────────────────────────────────────────────────

  const containerStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: variant === "minimal" ? "row" : "column",
    alignItems: "center",
    gap: variant === "minimal" ? 8 : 10,
    padding: variant === "minimal" ? "4px 8px" : "12px 16px",
    borderRadius: 14,
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
  };

  const buttonStyle: React.CSSProperties = {
    position: "relative",
    width: variant === "minimal" ? 36 : variant === "compact" ? 44 : 52,
    height: variant === "minimal" ? 36 : variant === "compact" ? 44 : 52,
    borderRadius: "50%",
    border: "none",
    cursor: disabled || !voiceReady ? "not-allowed" : "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: variant === "minimal" ? 16 : 20,
    transition: "all 0.15s ease",
    background: recState === "recording"
      ? "linear-gradient(135deg, #EF4444, #DC2626)"
      : voiceReady
        ? "linear-gradient(135deg, #5B88FF, #4A6FE8)"
        : "rgba(255,255,255,0.08)",
    boxShadow: recState === "recording"
      ? "0 0 0 4px rgba(239,68,68,0.3), 0 4px 16px rgba(239,68,68,0.3)"
      : voiceReady
        ? "0 0 0 1px rgba(91,136,255,0.3), 0 4px 16px rgba(91,136,255,0.2)"
        : "0 0 0 1px rgba(255,255,255,0.1)",
    flexShrink: 0,
  };

  // ── Inject CSS keyframes ──────────────────────────────────────────────────
  useEffect(() => {
    const id = "voice-assistant-animations";
    if (!document.getElementById(id)) {
      const style = document.createElement("style");
      style.id = id;
      style.textContent = `
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.6; }
          70% { transform: scale(1.6); opacity: 0; }
          100% { transform: scale(1.6); opacity: 0; }
        }
      `;
      document.head.appendChild(style);
    }
    return () => { document.getElementById(id)?.remove(); };
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────────

  if (voiceReady === false) {
    return (
      <div
        style={{
          ...containerStyle,
          opacity: 0.5,
          cursor: "not-allowed",
        }}
        title="Voice services not available. Configure OPENAI_API_KEY or GEMINI_API_KEY."
      >
        <div style={buttonStyle}>
          <span>🎤</span>
        </div>
        {variant !== "minimal" && (
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", fontFamily: "'Inter', sans-serif" }}>
            Voice unavailable
          </span>
        )}
      </div>
    );
  }

  if (variant === "minimal") {
    return (
      <div style={containerStyle}>
        <button
          onClick={handlePushToTalk}
          onMouseEnter={(e) => {
            if (!disabled && voiceReady && recState !== "recording") {
              e.currentTarget.style.transform = "scale(1.05)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
          }}
          style={buttonStyle}
          disabled={disabled || !voiceReady}
          title={
            recState === "recording"
              ? "Click to stop recording"
              : "Click to start recording"
          }
        >
          <span>{recState === "recording" ? "■" : "🎤"}</span>

          {/* Pulse ring when recording */}
          {recState === "recording" && (
            <div
              style={{
                position: "absolute",
                inset: -8,
                borderRadius: "50%",
                border: "2px solid rgba(239,68,68,0.4)",
                animation: "pulse-ring 1.5s ease-out infinite",
                pointerEvents: "none",
              }}
            />
          )}
        </button>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* Waveform visualization */}
      {(recState === "recording" || voiceState === "responding") && (
        <WaveformVisualizer
          waveform={waveform}
          audioLevel={audioLevel}
          isRecording={recState === "recording"}
          isResponding={voiceState === "responding"}
          variant="wave"
          color="#5B88FF"
        />
      )}

      {/* State display */}
      <VoiceStateDisplay
        state={voiceState}
        error={recError}
        durationMs={durationMs}
        audioLevel={audioLevel}
        isRecording={recState === "recording"}
      />

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
        {/* PTT button */}
        <button
          onClick={handlePushToTalk}
          onMouseEnter={(e) => {
            if (!disabled && voiceReady && recState !== "recording") {
              e.currentTarget.style.transform = "scale(1.08)";
              e.currentTarget.style.boxShadow = "0 0 20px rgba(91,136,255,0.4)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
            e.currentTarget.style.boxShadow = recState === "recording"
              ? "0 0 0 4px rgba(239,68,68,0.3)"
              : "0 0 0 1px rgba(91,136,255,0.3)";
          }}
          style={buttonStyle}
          disabled={disabled || !voiceReady}
        >
          <span>{recState === "recording" ? "■" : "🎤"}</span>

          {/* Pulse ring when recording */}
          {recState === "recording" && (
            <div
              style={{
                position: "absolute",
                inset: -10,
                borderRadius: "50%",
                border: "2px solid rgba(239,68,68,0.3)",
                animation: "pulse-ring 1.5s ease-out infinite",
                pointerEvents: "none",
              }}
            />
          )}
        </button>

        {/* Mode toggle */}
        <button
          onClick={handleModeToggle}
          style={{
            padding: "6px 12px",
            borderRadius: 8,
            border: "1px solid rgba(255,255,255,0.1)",
            background: mode === "continuous" ? "rgba(91,136,255,0.15)" : "rgba(255,255,255,0.04)",
            color: mode === "continuous" ? "#5B88FF" : "rgba(255,255,255,0.6)",
            fontSize: 11,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "'Inter', sans-serif",
            transition: "all 0.15s ease",
            whiteSpace: "nowrap",
          }}
          title={
            mode === "push-to-talk"
              ? "Switch to continuous listening mode"
              : "Switch to push-to-talk mode"
          }
        >
          {mode === "push-to-talk" ? "🎤 PTT" : "🔄 Auto"}
        </button>

        {/* Playback button */}
        {getBlob() && !isPlaying && (
          <button
            onClick={play}
            style={{
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.1)",
              background: "rgba(255,255,255,0.04)",
              color: "rgba(255,255,255,0.6)",
              fontSize: 14,
              cursor: "pointer",
              fontFamily: "'Inter', sans-serif",
              transition: "all 0.15s ease",
            }}
            title="Play back recording"
          >
            ▶️
          </button>
        )}

        {/* Cancel / Reset button */}
        {(recState === "recording" || transcript || responseText) && (
          <button
            onClick={() => {
              reset();
              setTranscript("");
              setResponseText("");
              setVoiceState("idle");
            }}
            style={{
              marginLeft: "auto",
              padding: "6px 10px",
              borderRadius: 8,
              border: "none",
              background: "rgba(255,255,255,0.06)",
              color: "rgba(255,255,255,0.5)",
              fontSize: 12,
              cursor: "pointer",
              fontFamily: "'Inter', sans-serif",
              transition: "all 0.15s ease",          }}
        >
          ✕ Clear
          </button>
        )}

        {/* Mic status */}
        {!browserSupported && (
          <span style={{ fontSize: 10, color: "#F87171", marginLeft: "auto", fontFamily: "'Inter', sans-serif" }}>
            Browser not supported
          </span>
        )}
        {!micAvailable && (
          <span style={{ fontSize: 10, color: "#F87171", marginLeft: "auto", fontFamily: "'Inter', sans-serif" }}>
            No mic detected
          </span>
        )}
      </div>

      {/* Transcription / Response display */}
      {transcript && (
        <div
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.04)",
            fontSize: 12,
            color: "rgba(255,255,255,0.7)",
            fontFamily: "'Inter', sans-serif",
            lineHeight: 1.5,
            wordBreak: "break-word",
          }}
        >
          🎤 {transcript}
        </div>
      )}

      {responseText && (
        <div
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(16,185,129,0.06)",
            border: "1px solid rgba(16,185,129,0.15)",
            fontSize: 12,
            color: "#34D399",
            fontFamily: "'Inter', sans-serif",
            lineHeight: 1.5,
            wordBreak: "break-word",
          }}
        >
          🔊 {responseText}
        </div>
      )}
    </div>
  );
};
