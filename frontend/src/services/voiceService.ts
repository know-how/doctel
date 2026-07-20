/**
 * voiceService.ts – Voice Assistant API client for DocTel
 *
 * Handles:
 *   - Speech-to-text (audio file upload → transcription)
 *   - Text-to-speech (text → audio blob)
 *   - Voice command classification
 *   - Full voice conversation (transcribe → AI → TTS)
 *   - Availability checks
 */

const BASE_URL =
  (typeof import.meta !== "undefined" &&
    (import.meta as any).env?.VITE_API_BASE_URL) ||
  "";

function buildAuthHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? window.localStorage.getItem("docintel_auth_token")
      : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface VoiceConfig {
  config: {
    stt_providers: string[];
    tts_providers: string[];
    default_stt: string;
    default_tts: string;
    voices: Record<string, string[]>;
    voice_styles: Record<string, Record<string, string>>;
    commands: { categories: string[]; intents: string[] };
  };
  availability: Record<string, boolean>;
}

export interface TranscribeResponse {
  text: string;
  language: string;
  model: string;
  confidence: number;
  duration_ms: number;
}

export interface SpeakResponse {
  audio: Blob;
  provider: string;
  voice: string;
  duration: number;
}

export interface CommandResponse {
  intent: string;
  confidence: number;
  entities: { query?: string };
  raw_text: string;
  routing: {
    action: string;
    target: string;
    ui_hint: string;
  };
}

export interface ConverseResponse {
  transcript: string;
  text: string;
  session_id: string;
  audio_base64?: string;
  audio_format?: string;
  tts_provider?: string;
}

// ── API Functions ────────────────────────────────────────────────────────────

export async function getVoiceConfig(): Promise<VoiceConfig> {
  const res = await fetch(`${BASE_URL}/api/voice/config`, {
    headers: buildAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Voice config failed: ${res.status}`);
  return res.json();
}

export async function checkVoiceHealth(): Promise<{
  ok: boolean;
  stt_available: boolean;
  tts_available: boolean;
  edge_tts: boolean;
}> {
  const res = await fetch(`${BASE_URL}/api/voice/health`, {
    headers: buildAuthHeaders(),
  });
  if (!res.ok) return { ok: false, stt_available: false, tts_available: false, edge_tts: false };
  return res.json();
}

/**
 * Transcribe an audio blob to text.
 */
export async function transcribeAudio(
  audioBlob: Blob,
  language = "en",
  model = "auto"
): Promise<TranscribeResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.wav");
  formData.append("language", language);
  formData.append("model", model);

  const res = await fetch(`${BASE_URL}/api/voice/transcribe`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail?.message || `Transcription failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Convert text to speech audio blob.
 */
export async function speakText(
  text: string,
  voice = "alloy",
  provider = "openai",
  style = "professional",
  speed = 1.0
): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/api/voice/speak`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ text, voice, provider, style, speed }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail?.message || `TTS failed: ${res.status}`);
  }
  return res.blob();
}

/**
 * Classify a voice command and get routing information.
 */
export async function classifyCommand(
  text: string,
  context?: Record<string, unknown>
): Promise<CommandResponse> {
  const res = await fetch(`${BASE_URL}/api/voice/command`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ text, context }),
  });
  if (!res.ok) throw new Error(`Command classification failed: ${res.status}`);
  return res.json();
}

/**
 * Full voice conversation from audio file: transcribe → AI → TTS, all in one request.
 * Returns text + optional audio base64.
 */
export async function voiceConversation(
  audioBlob: Blob,
  sessionId = "",
): Promise<ConverseResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.wav");
  formData.append("session_id", sessionId);

  const res = await fetch(`${BASE_URL}/api/voice/converse`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || `Voice conversation failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Full voice conversation from pre-transcribed text: AI → TTS, all in one request.
 * Used by the VoiceAssistant component when transcription is done client-side.
 * Returns text + optional audio base64.
 */
export async function voiceConversationText(
  transcript: string,
  sessionId = "",
): Promise<ConverseResponse> {
  const res = await fetch(`${BASE_URL}/api/voice/converse-text`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ transcript, session_id: sessionId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || `Voice conversation failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Play audio blob using the Web Audio API.
 * Returns a cleanup function.
 */
export function playAudioBlob(
  blob: Blob,
  onEnded?: () => void
): () => void {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);

  audio.onended = () => {
    URL.revokeObjectURL(url);
    onEnded?.();
  };
  audio.onerror = () => {
    URL.revokeObjectURL(url);
    onEnded?.();
  };

  audio.play().catch(() => {
    URL.revokeObjectURL(url);
    onEnded?.();
  });

  return () => {
    audio.pause();
    audio.src = "";
    URL.revokeObjectURL(url);
  };
}

/**
 * Decode base64 audio and play it.
 */
export function playBase64Audio(
  base64: string,
  format = "mp3",
  onEnded?: () => void
): () => void {
  try {
    const byteChars = atob(base64);
    const byteNums = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
      byteNums[i] = byteChars.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNums);
    const blob = new Blob([byteArray], { type: `audio/${format}` });
    return playAudioBlob(blob, onEnded);
  } catch {
    onEnded?.();
    return () => {};
  }
}
