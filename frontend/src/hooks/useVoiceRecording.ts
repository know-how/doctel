/**
 * useVoiceRecording.ts – React hook for WebRTC audio recording with waveform visualization
 *
 * Features:
 *   - MediaRecorder API integration
 *   - Push-to-talk mode
 *   - Continuous listening mode (VAD-based)
 *   - Real-time audio level detection for waveform
 *   - Audio format conversion (WebM → WAV)
 *   - Browser compatibility detection
 *   - Error handling for permission denial
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

export interface WaveformPoint {
  /** Normalized amplitude (0-1) */
  value: number;
  /** Timestamp for animation key */
  id: number;
}

export type RecordingState =
  | "idle"
  | "requesting"
  | "recording"
  | "stopping"
  | "processing"
  | "error";

export type VoiceMode = "push-to-talk" | "continuous";

export interface VoiceRecordingOptions {
  /** Audio constraints for getUserMedia */
  audioConstraints?: MediaTrackConstraints;
  /** Recording mode */
  mode?: VoiceMode;
  /** Silence threshold for VAD (0-1) */
  silenceThreshold?: number;
  /** Silence duration in ms before auto-stop (continuous mode) */
  silenceTimeoutMs?: number;
  /** MIME type for recording */
  mimeType?: string;
  /** Audio bits per second */
  audioBitsPerSecond?: number;
  /** Max recording duration in ms (0 = unlimited) */
  maxDurationMs?: number;
}

export interface VoiceRecordingReturn {
  /** Current recording state */
  state: RecordingState;
  /** Current audio level (0-1) */
  audioLevel: number;
  /** Waveform data for visualization */
  waveform: WaveformPoint[];
  /** Duration of current recording in ms */
  durationMs: number;
  /** Error message if state is "error" */
  error: string | null;
  /** Whether microphone is available */
  micAvailable: boolean;
  /** Whether the browser supports MediaRecorder */
  browserSupported: boolean;
  /** Start recording */
  start: () => Promise<void>;
  /** Stop recording and get audio blob */
  stop: () => Promise<Blob | null>;
  /** Toggle between push-to-talk and continuous */
  setMode: (mode: VoiceMode) => void;
  /** Get the recorded audio blob */
  getBlob: () => Blob | null;
  /** Reset to idle state */
  reset: () => void;
  /** Playback the recorded audio */
  play: () => Promise<void>;
  /** Is currently playing back */
  isPlaying: boolean;
  /** Frequencies for spectrum visualization */
  frequencies: Uint8Array | null;
}

// ── Browser detection ────────────────────────────────────────────────────────

function detectBrowserSupport(): boolean {
  return !!(
    navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

async function detectMicAvailability(): Promise<boolean> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.some((d) => d.kind === "audioinput");
  } catch {
    return false;
  }
}

// ── Audio processing helpers ─────────────────────────────────────────────────

function createAudioContext(): AudioContext | null {
  try {
    return new (window.AudioContext || (window as any).webkitAudioContext)();
  } catch {
    return null;
  }
}

/**
 * Converts audio blob to WAV format for better compatibility with speech-to-text.
 */
function blobToWav(blob: Blob): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const arrayBuffer = reader.result as ArrayBuffer;
        const audioCtx = createAudioContext();
        if (!audioCtx) {
          resolve(blob); // fallback: return original
          return;
        }
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        const numChannels = audioBuffer.numberOfChannels;
        const sampleRate = audioBuffer.sampleRate;
        const length = audioBuffer.length;
        const wavBuffer = encodeWav(
          audioBuffer.getChannelData(0),
          sampleRate,
          numChannels
        );
        resolve(new Blob([wavBuffer], { type: "audio/wav" }));
      } catch {
        resolve(blob); // fallback
      }
    };
    reader.onerror = () => resolve(blob);
    reader.readAsArrayBuffer(blob);
  });
}

function encodeWav(
  samples: Float32Array,
  sampleRate: number,
  numChannels: number
): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  const byteRate = sampleRate * numChannels * 2;
  const blockAlign = numChannels * 2;
  const dataSize = samples.length * 2;

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return buffer;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useVoiceRecording(
  options: VoiceRecordingOptions = {}
): VoiceRecordingReturn {
  const {
    audioConstraints = { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
    mode: initialMode = "push-to-talk",
    silenceThreshold = 0.02,
    silenceTimeoutMs = 1500,
    mimeType = "audio/webm;codecs=opus",
    audioBitsPerSecond = 16000,
    maxDurationMs = 60000,
  } = options;

  // ── State ──────────────────────────────────────────────────────────────────
  const [state, setState] = useState<RecordingState>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const [waveform, setWaveform] = useState<WaveformPoint[]>([]);
  const [durationMs, setDurationMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [micAvailable, setMicAvailable] = useState(false);
  const [browserSupported] = useState(detectBrowserSupport());
  const [mode, setMode] = useState<VoiceMode>(initialMode);
  const [isPlaying, setIsPlaying] = useState(false);
  const [frequencies, setFrequencies] = useState<Uint8Array | null>(null);

  // ── Refs ───────────────────────────────────────────────────────────────────
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const blobRef = useRef<Blob | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animationFrameRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const maxDurationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // ── Check mic availability ─────────────────────────────────────────────────
  useEffect(() => {
    detectMicAvailability().then(setMicAvailable);
    const handleDeviceChange = () => detectMicAvailability().then(setMicAvailable);
    navigator.mediaDevices?.addEventListener("devicechange", handleDeviceChange);
    return () => navigator.mediaDevices?.removeEventListener("devicechange", handleDeviceChange);
  }, []);

  // ── Cleanup on unmount ─────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  // ── Cleanup function ───────────────────────────────────────────────────────
  const cleanup = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = 0;
    }
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (maxDurationTimerRef.current) {
      clearTimeout(maxDurationTimerRef.current);
      maxDurationTimerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
  }, []);

  // ── Audio level analysis loop ──────────────────────────────────────────────
  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

    // Get time-domain data for waveform
    analyserRef.current.getByteTimeDomainData(dataArray);

    // Calculate RMS level
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const value = (dataArray[i] - 128) / 128;
      sum += value * value;
    }
    const rms = Math.sqrt(sum / dataArray.length);
    const normalizedLevel = Math.min(1, rms * 2);

    setAudioLevel(normalizedLevel);

    // Update waveform (downsampled)
    setWaveform((prev) => {
      const now = Date.now();
      const newPoint: WaveformPoint = { value: normalizedLevel, id: now };
      const updated = [...prev, newPoint];
      // Keep last 60 points for display
      return updated.length > 60 ? updated.slice(-60) : updated;
    });

    // Get frequency data for spectrum visualization
    try {
      const freqArray = new Uint8Array(analyserRef.current.frequencyBinCount);
      analyserRef.current.getByteFrequencyData(freqArray);
      setFrequencies(freqArray);
    } catch {
      // Ignore
    }

    // VAD: auto-stop on silence in continuous mode
    if (mode === "continuous" && normalizedLevel < silenceThreshold) {
      if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          if (state === "recording") {
            stop().catch(() => {});
          }
        }, silenceTimeoutMs);
      }
    } else {
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
    }

    animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
  }, [mode, silenceThreshold, silenceTimeoutMs, state]);

  // ── Start recording ────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    if (!browserSupported) {
      setError("Your browser does not support audio recording.");
      setState("error");
      return;
    }

    try {
      setState("requesting");
      setError(null);
      setDurationMs(0);
      setWaveform([]);
      setFrequencies(null);
      chunksRef.current = [];
      blobRef.current = null;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: audioConstraints,
      });
      streamRef.current = stream;

      // Set up audio analysis
      const audioCtx = createAudioContext();
      if (audioCtx) {
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        source.connect(analyser);
        analyserRef.current = analyser;

        // Resume context if suspended (autoplay policy)
        if (audioCtx.state === "suspended") {
          await audioCtx.resume();
        }
      }

      // Determine best MIME type
      const preferredMimeTypes = [
        mimeType,
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ];
      let selectedMimeType = "";
      for (const mt of preferredMimeTypes) {
        if (MediaRecorder.isTypeSupported(mt)) {
          selectedMimeType = mt;
          break;
        }
      }

      // Create recorder
      const recorder = new MediaRecorder(stream, {
        mimeType: selectedMimeType || undefined,
        audioBitsPerSecond,
      });
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: selectedMimeType || "audio/webm",
        });
        blobRef.current = blob;
      };

      recorder.onerror = () => {
        setError("Recording error occurred.");
        setState("error");
      };

      recorder.start(100); // Collect data every 100ms
      startTimeRef.current = Date.now();
      setState("recording");

      // Start level analysis
      updateAudioLevel();

      // Duration tracking
      durationIntervalRef.current = setInterval(() => {
        setDurationMs(Date.now() - startTimeRef.current);
      }, 100);

      // Max duration limit
      if (maxDurationMs > 0) {
        maxDurationTimerRef.current = setTimeout(() => {
          if (state === "recording") {
            stop().catch(() => {});
          }
        }, maxDurationMs);
      }
    } catch (err: any) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setError("Microphone access denied. Please allow microphone access in your browser settings.");
      } else if (err.name === "NotFoundError") {
        setError("No microphone found. Please connect a microphone.");
      } else {
        setError(err.message || "Failed to start recording.");
      }
      setState("error");
    }
  }, [audioConstraints, audioBitsPerSecond, browserSupported, maxDurationMs, mimeType, state, updateAudioLevel]);

  // ── Stop recording ─────────────────────────────────────────────────────────
  const stop = useCallback(async (): Promise<Blob | null> => {
    if (!recorderRef.current || recorderRef.current.state === "inactive") {
      return blobRef.current;
    }

    return new Promise((resolve) => {
      setState("stopping");

      // Stop level analysis
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = 0;
      }

      const recorder = recorderRef.current!;

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        blobRef.current = blob;

        // Clean up stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }

        // Clean up audio context
        if (audioContextRef.current && audioContextRef.current.state !== "closed") {
          audioContextRef.current.close().catch(() => {});
          audioContextRef.current = null;
        }
        analyserRef.current = null;

        // Clear timers
        if (durationIntervalRef.current) {
          clearInterval(durationIntervalRef.current);
          durationIntervalRef.current = null;
        }
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
        if (maxDurationTimerRef.current) {
          clearTimeout(maxDurationTimerRef.current);
          maxDurationTimerRef.current = null;
        }

        setState("processing");

        // Convert to WAV for better STT compatibility
        try {
          const wavBlob = await blobToWav(blob);
          blobRef.current = wavBlob;
        } catch {
          // Keep original blob
        }

        setState("idle");
        setAudioLevel(0);
        setFrequencies(null);
        resolve(blobRef.current);
      };

      // If recorder is already stopping, wait for it
      if (recorder.state === "recording") {
        recorder.stop();
      } else {
        resolve(blobRef.current);
      }
    });
  }, []);

  // ── Get blob ───────────────────────────────────────────────────────────────
  const getBlob = useCallback(() => {
    return blobRef.current;
  }, []);

  // ── Reset ──────────────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    cleanup();
    chunksRef.current = [];
    blobRef.current = null;
    setState("idle");
    setAudioLevel(0);
    setWaveform([]);
    setDurationMs(0);
    setError(null);
    setFrequencies(null);
  }, [cleanup]);

  // ── Playback ───────────────────────────────────────────────────────────────
  const play = useCallback(async () => {
    const blob = blobRef.current;
    if (!blob) return;

    try {
      setIsPlaying(true);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      await audio.play();

      audio.onended = () => {
        URL.revokeObjectURL(url);
        setIsPlaying(false);
        audioRef.current = null;
      };
    } catch {
      setIsPlaying(false);
    }
  }, []);

  return {
    state,
    audioLevel,
    waveform,
    durationMs,
    error,
    micAvailable,
    browserSupported,
    start,
    stop,
    setMode,
    getBlob,
    reset,
    play,
    isPlaying,
    frequencies,
  };
}

// ── Utility export ───────────────────────────────────────────────────────────

export function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}:${seconds.toString().padStart(2, "0")}` : `0:${seconds.toString().padStart(2, "0")}`;
}
