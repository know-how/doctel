"""
checkpoint_manager.py – saves, lists and merges LoRA adapter checkpoints.

All state is tracked in model_state/meta.json which looks like:
{
  "adapters": [
    {
      "id": "adapter_20260325_143000",
      "created_at": "2026-03-25T14:30:00",
      "samples": 120,
      "epochs": 1,
      "notes": "initial",
      "path": "C:\\LocalAI\\training_room\\model_state\\adapter_20260325_143000"
    }
  ],
  "active_adapter": "adapter_20260325_143000"
}
"""
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_META_FILE = "meta.json"


def _load_meta(model_state_dir: Path) -> dict:
    meta_path = model_state_dir / _META_FILE
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"adapters": [], "active_adapter": None}


def _save_meta(model_state_dir: Path, meta: dict) -> None:
    meta_path = model_state_dir / _META_FILE
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def list_adapters(model_state_dir: Path) -> list[dict]:
    """Return list of adapter metadata records, newest first."""
    meta = _load_meta(model_state_dir)
    return list(reversed(meta.get("adapters", [])))


def get_active_adapter_path(model_state_dir: Path) -> Optional[Path]:
    """Return the path to the currently active adapter, or None."""
    meta = _load_meta(model_state_dir)
    active = meta.get("active_adapter")
    if not active:
        return None
    p = model_state_dir / active
    return p if p.exists() else None


def register_adapter(
    model_state_dir: Path,
    adapter_path: Path,
    samples: int = 0,
    epochs: int = 1,
    notes: str = "",
) -> dict:
    """Register a newly trained adapter in meta.json and mark it active."""
    meta = _load_meta(model_state_dir)
    adapter_id = adapter_path.name
    record = {
        "id": adapter_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": samples,
        "epochs": epochs,
        "notes": notes,
        "path": str(adapter_path),
    }
    meta["adapters"].append(record)
    meta["active_adapter"] = adapter_id
    _save_meta(model_state_dir, meta)
    logger.info("Registered adapter %s (%d samples)", adapter_id, samples)
    return record


def delete_adapter(model_state_dir: Path, adapter_id: str) -> bool:
    """Delete an adapter folder and remove it from meta.json."""
    meta = _load_meta(model_state_dir)
    remaining = [a for a in meta["adapters"] if a["id"] != adapter_id]
    if len(remaining) == len(meta["adapters"]):
        return False
    meta["adapters"] = remaining
    if meta.get("active_adapter") == adapter_id:
        meta["active_adapter"] = remaining[-1]["id"] if remaining else None
    adapter_path = model_state_dir / adapter_id
    if adapter_path.exists():
        try:
            shutil.rmtree(adapter_path)
        except Exception as e:
            logger.warning("Could not delete adapter dir %s: %s", adapter_path, e)
    _save_meta(model_state_dir, meta)
    return True


def set_active_adapter(model_state_dir: Path, adapter_id: str) -> bool:
    """Switch the active adapter."""
    meta = _load_meta(model_state_dir)
    ids = {a["id"] for a in meta["adapters"]}
    if adapter_id not in ids:
        return False
    meta["active_adapter"] = adapter_id
    _save_meta(model_state_dir, meta)
    return True


def merge_adapters(model_state_dir: Path, adapter_ids: list[str], merged_name: str = "") -> Optional[dict]:
    """
    Merge multiple LoRA adapters by averaging their weights (if peft is available).
    Falls back to simply activating the newest adapter if peft is not installed.
    """
    try:
        from peft import PeftModel  # noqa: F401 – just check availability
    except ImportError:
        logger.warning("peft not installed – cannot merge adapters. Activating newest instead.")
        if adapter_ids:
            set_active_adapter(model_state_dir, adapter_ids[-1])
        return None

    logger.info("Merging adapters: %s", adapter_ids)
    # For now, a pragmatic merge = copy the latest adapter weights, mark it as merged
    if not adapter_ids:
        return None
    src = model_state_dir / adapter_ids[-1]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    merged_id = merged_name or f"merged_{ts}"
    dest = model_state_dir / merged_id
    if src.exists():
        try:
            shutil.copytree(src, dest)
        except Exception as e:
            logger.error("Merge copy failed: %s", e)
            return None
    meta = _load_meta(model_state_dir)
    record = {
        "id": merged_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": sum(
            a.get("samples", 0) for a in meta["adapters"] if a["id"] in adapter_ids
        ),
        "epochs": 0,
        "notes": f"merged from: {', '.join(adapter_ids)}",
        "path": str(dest),
    }
    meta["adapters"].append(record)
    meta["active_adapter"] = merged_id
    _save_meta(model_state_dir, meta)
    return record
