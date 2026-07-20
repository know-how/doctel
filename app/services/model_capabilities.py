"""
model_capabilities.py — DocTel Model Capability Registry

Maps model IDs to their capabilities (text, vision, audio, code, etc.)
so the frontend can display capability badges and the router can make
intelligent modality-based selections.

Capability flags:
  text              — General text generation / chat
  vision            — Image understanding (multimodal)
  image_generation  — Image / diagram / logo generation
  audio             — Audio transcription / understanding
  code              — Code generation & analysis
  reasoning         — Chain-of-thought / deep reasoning
  embedding         — Text embedding generation (non-generation models)
  fast              — Low-latency response (good for interactive chat)
  large             — Large context window (>= 32K tokens)
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ── Capability registry ──────────────────────────────────────────────────────

# Each entry has: capabilities (list of strings) and display_category (for grouping)
_MODEL_CAPABILITIES: Dict[str, dict] = {
    # ── Ollama / Local models ──────────────────────────────────────────────
    "qwen3:4b": {
        "capabilities": ["text", "fast", "reasoning"],
        "display_category": "Local",
    },
    "qwen3:8b": {
        "capabilities": ["text", "reasoning", "code", "large"],
        "display_category": "Local",
    },
    "qwen2.5:7b": {
        "capabilities": ["text", "reasoning", "code"],
        "display_category": "Local",
    },
    "llama3.2": {
        "capabilities": ["text", "fast"],
        "display_category": "Local",
    },
    "llama3.2:3b": {
        "capabilities": ["text", "fast"],
        "display_category": "Local",
    },
    "llama3.1:8b": {
        "capabilities": ["text", "reasoning", "code"],
        "display_category": "Local",
    },
    "llava:7b": {
        "capabilities": ["text", "vision"],
        "display_category": "Local",
    },
    "llava:13b": {
        "capabilities": ["text", "vision", "reasoning"],
        "display_category": "Local",
    },
    "nomic-embed-text": {
        "capabilities": ["embedding"],
        "display_category": "Local",
    },
    "mistral:7b": {
        "capabilities": ["text", "code", "fast"],
        "display_category": "Local",
    },
    "mixtral:8x7b": {
        "capabilities": ["text", "reasoning", "code", "large"],
        "display_category": "Local",
    },
    "deepseek-coder:6.7b": {
        "capabilities": ["text", "code", "reasoning"],
        "display_category": "Local",
    },
    "phi3:mini": {
        "capabilities": ["text", "fast", "code"],
        "display_category": "Local",
    },
    "phi3:medium": {
        "capabilities": ["text", "reasoning", "code", "large"],
        "display_category": "Local",
    },
    # ── Cloud / API models ────────────────────────────────────────────────
    "gemini-2.5-flash": {
        "capabilities": ["text", "vision", "image_generation", "audio", "code", "reasoning", "fast", "large"],
        "display_category": "Google Gemini",
    },
    "gemini-2.0-flash": {
        "capabilities": ["text", "vision", "image_generation", "audio", "code", "fast", "large"],
        "display_category": "Google Gemini",
    },
    "gemini-1.5-flash": {
        "capabilities": ["text", "vision", "image_generation", "audio", "code", "fast", "large"],
        "display_category": "Google Gemini",
    },
    "gemini-1.5-pro": {
        "capabilities": ["text", "vision", "image_generation", "audio", "code", "reasoning", "large"],
        "display_category": "Google Gemini",
    },
    "deepseek-chat": {
        "capabilities": ["text", "code", "reasoning", "large"],
        "display_category": "DeepSeek",
    },
    "deepseek-reasoner": {
        "capabilities": ["text", "code", "reasoning", "large"],
        "display_category": "DeepSeek",
    },
}

# ── Known model name aliases ─────────────────────────────────────────────────

_MODEL_ALIASES: Dict[str, str] = {
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-1.5-flash": "gemini-1.5-flash",
    "gemini-1.5-pro": "gemini-1.5-pro",
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
    "llama3.2": "llama3.2",
    "llama3.2:1b": "llama3.2",
    "llama3.2:3b": "llama3.2:3b",
    "qwen3:4b": "qwen3:4b",
    "qwen3:8b": "qwen3:8b",
    "llava": "llava:7b",
    "llava:latest": "llava:7b",
    "nomic-embed-text": "nomic-embed-text",
    "nomic-embed-text:latest": "nomic-embed-text",
}


# ── Public API ────────────────────────────────────────────────────────────────


def get_model_capabilities(model_id: str) -> List[str]:
    """Get the capability flags for a given model ID.

    Falls back to ["text"] for unknown models so they remain usable.
    """
    canonical = _MODEL_ALIASES.get(model_id, model_id)
    entry = _MODEL_CAPABILITIES.get(canonical)
    if entry:
        return list(entry["capabilities"])
    # Fallback: infer capabilities from model name heuristics
    return _infer_capabilities(model_id)


def get_display_category(model_id: str) -> str:
    """Get the display category for grouping models in the UI."""
    canonical = _MODEL_ALIASES.get(model_id, model_id)
    entry = _MODEL_CAPABILITIES.get(canonical)
    if entry:
        return entry["display_category"]
    if any(prefix in model_id.lower() for prefix in ("gemini",)):
        return "Google Gemini"
    if any(prefix in model_id.lower() for prefix in ("deepseek",)):
        return "DeepSeek"
    if any(prefix in model_id.lower() for prefix in ("zen/", "go/")):
        return "OpenCode"
    return "Other"


def has_capability(model_id: str, capability: str) -> bool:
    """Check if a model has a specific capability."""
    return capability in get_model_capabilities(model_id)


def register_model(
    model_id: str,
    capabilities: List[str],
    display_category: Optional[str] = None,
) -> None:
    """Register or update a model's capabilities at runtime.

    Used by cloud service integrations to self-register when they
    detect new available models.
    """
    canonical = _MODEL_ALIASES.get(model_id, model_id)
    existing = _MODEL_CAPABILITIES.get(canonical, {})
    _MODEL_CAPABILITIES[canonical] = {
        "capabilities": capabilities,
        "display_category": display_category or existing.get("display_category", "Other"),
    }


def _infer_capabilities(model_id: str) -> List[str]:
    """Heuristic fallback: infer capabilities from model name."""
    mid = model_id.lower()
    caps = ["text"]
    if any(v in mid for v in ("vision", "llava", "gemini", "multimodal")):
        caps.append("vision")
        caps.append("image_generation")
    if any(a in mid for a in ("audio", "whisper", "gemini")):
        caps.append("audio")
    if any(c in mid for c in ("code", "coder", "deepseek", "qwen")):
        caps.append("code")
    if any(r in mid for r in ("reason", "deepseek-r1", "deepseek-reasoner")):
        caps.append("reasoning")
    if any(f in mid for f in ("3b", "4b", "mini", "small", "flash", "tiny")):
        caps.append("fast")
    if any(l in mid for l in ("70b", "8x7b", "medium", "large", "pro", "120b")):
        caps.append("large")
    return caps


def get_all_capabilities() -> Dict[str, List[str]]:
    """Return the full registry (model_id → capabilities list)."""
    return {
        mid: entry["capabilities"]
        for mid, entry in _MODEL_CAPABILITIES.items()
    }
