import psutil
from typing import Optional, Tuple
from app.config import settings

_force_model: Optional[str] = None
_last_selection: Tuple[str, str, int] = ("", "", 0)  # (model, reason, free_ram_mb)


def _free_ram_mb() -> int:
    try:
        vm = psutil.virtual_memory()
        return int(vm.available / (1024 * 1024))
    except Exception:
        return 0


def force_select(model: Optional[str]) -> None:
    global _force_model
    _force_model = model


def active() -> dict:
    model, reason, free_ram = _last_selection
    return {"selected_model": model, "reason": reason, "free_ram_mb": free_ram}


def select_text_model(task_type: str = "rag") -> str:
    """
    task_type: 'summary_long' | 'rag' | 'short_qa'
    """
    global _last_selection
    if _force_model:
        m = _force_model
        _last_selection = (m, "forced", _free_ram_mb())
        return m

    free_mb = _free_ram_mb()

    allow = settings.available_models or []
    base_default = settings.default_model or settings.text_model

    if settings.automatic_switching:
        if settings.enable_qwen_9b and task_type in ("summary_long", "rag"):
            if free_mb >= settings.min_free_ram_for_qwen9b_mb:
                m = settings.qwen_9b_model
                _last_selection = (m, f"qwen9b_enabled_free_mb_{free_mb}", free_mb)
                return m if (not allow or m in allow) else base_default
        if free_mb >= settings.min_free_ram_for_8b_mb:
            m = settings.text_model
            _last_selection = (m, f"llama8b_free_mb_{free_mb}", free_mb)
            return m if (not allow or m in allow) else base_default
        m = settings.fallback_text_model
        _last_selection = (m, f"fallback_3b_free_mb_{free_mb}", free_mb)
        return m if (not allow or m in allow) else base_default

    # No automatic switching
    m = base_default
    _last_selection = (m, "static", free_mb)
    return m
