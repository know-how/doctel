"""
training_scheduler.py – Background scheduler for LoRA training jobs.

Exposes a singleton `scheduler` with three public methods:
  - train_now()           → start immediately
  - train_idle()          → start only when free RAM >= threshold
  - train_batch(folder)   → prepare a specific folder then train
  - status()              → dict of current job state
  - history()             → list of past jobs (from checkpoint meta)
"""
import asyncio
import logging
import psutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from app.config import settings
from app.training.training_config import TrainingSettings, get_training_paths
from app.training.data_preparer import prepare_inbox, SUPPORTED_EXTENSIONS
from app.training.lora_trainer import run_lora_training, ProgressCallback, is_available as peft_available
from app.training.checkpoint_manager import (
    register_adapter, list_adapters, get_active_adapter_path
)

logger = logging.getLogger(__name__)


class TrainingJob:
    """Holds state for a single training run."""
    def __init__(self, trigger: str, folder: Optional[str] = None):
        self.id = datetime.now(timezone.utc).strftime("job_%Y%m%d_%H%M%S")
        self.trigger = trigger          # "now" | "idle" | "batch"
        self.folder = folder
        self.status = "pending"         # pending | running | done | error | skipped
        self.progress = 0.0
        self.message = "queued"
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.result: dict = {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "folder": self.folder,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
        }


def _free_ram_mb() -> int:
    try:
        return int(psutil.virtual_memory().available / (1024 * 1024))
    except Exception:
        return 0


class TrainingScheduler:
    def __init__(self):
        self._ts = TrainingSettings()
        self._current_job: Optional[TrainingJob] = None
        self._history: list[dict] = []
        self._lock = asyncio.Lock()
        self._thread: Optional[threading.Thread] = None
        self._on_complete: Optional[Callable[[str], None]] = None

    def set_completion_callback(self, cb: Callable[[str], None]) -> None:
        """Register a thread-safe callback invoked with the adapter_id when training succeeds."""
        self._on_complete = cb

    def _paths(self):
        return get_training_paths(settings.base_dir, self._ts)

    # ── public API ─────────────────────────────────────────────────────────────

    async def train_now(self) -> dict:
        """Start a training job immediately in a background thread."""
        async with self._lock:
            if self._current_job and self._current_job.status == "running":
                return {"ok": False, "reason": "already_running", "job": self._current_job.to_dict()}
            job = TrainingJob("now")
            self._current_job = job

        self._run_in_thread(job)
        return {"ok": True, "job": job.to_dict()}

    async def train_idle(self) -> dict:
        """Start training only if enough RAM is free."""
        free = _free_ram_mb()
        threshold = self._ts.min_free_ram_for_training_mb
        if free < threshold:
            return {
                "ok": False,
                "reason": "insufficient_ram",
                "free_mb": free,
                "required_mb": threshold,
            }
        return await self.train_now()

    async def train_batch(self, folder: Optional[str] = None) -> dict:
        """Prepare a specific folder (or inbox), then train."""
        async with self._lock:
            if self._current_job and self._current_job.status == "running":
                return {"ok": False, "reason": "already_running", "job": self._current_job.to_dict()}
            job = TrainingJob("batch", folder=folder)
            self._current_job = job

        self._run_in_thread(job, prepare_folder=folder)
        return {"ok": True, "job": job.to_dict()}

    def status(self) -> dict:
        """Return current job state."""
        if self._current_job is None:
            return {"status": "idle", "job": None}
        return {"status": self._current_job.status, "job": self._current_job.to_dict()}

    def history(self) -> list[dict]:
        """Return past training records."""
        paths = self._paths()
        adapters = list_adapters(paths["model_state"])
        return adapters

    # ── internal execution ─────────────────────────────────────────────────────

    def _run_in_thread(self, job: TrainingJob, prepare_folder: Optional[str] = None):
        t = threading.Thread(target=self._execute_job, args=(job, prepare_folder), daemon=True)
        t.start()
        self._thread = t

    def _execute_job(self, job: TrainingJob, prepare_folder: Optional[str] = None):
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.message = "starting"
        paths = self._paths()

        # ── step 1: prepare data ───────────────────────────────────────────────
        job.message = "preparing data"
        job.progress = 0.02
        try:
            inbox = Path(prepare_folder) if prepare_folder else paths["inbox"]
            prep = prepare_inbox(inbox, paths["batches"])
            if prep["pairs"] == 0:
                job.status = "skipped"
                job.message = "No training data found in inbox. Drop files into training_room/inbox/ first."
                job.finished_at = datetime.now(timezone.utc).isoformat()
                logger.info("Job %s skipped – inbox empty", job.id)
                return
            batch_path = Path(prep["batch_path"])
        except Exception as e:
            job.status = "error"
            job.message = f"Data preparation failed: {e}"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            logger.exception("Data preparation failed for job %s", job.id)
            return

        # ── step 2: check peft ────────────────────────────────────────────────
        if not peft_available():
            job.status = "error"
            job.message = (
                "Training skipped: peft/transformers/datasets not installed. "
                "Run: pip install peft transformers datasets"
            )
            job.finished_at = datetime.now(timezone.utc).isoformat()
            return

        # ── step 3: determine adapter output dir ──────────────────────────────
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        adapter_dir = paths["model_state"] / f"adapter_{ts_str}"

        # ── step 4: run training ───────────────────────────────────────────────
        def _on_progress(frac: float, msg: str):
            job.progress = frac
            job.message = msg

        cb = ProgressCallback(on_progress=_on_progress)
        cfg = self._ts
        result = run_lora_training(
            batch_path=batch_path,
            adapter_output_dir=adapter_dir,
            hf_base_model=cfg.hf_base_model,
            lora_r=cfg.lora.r,
            lora_alpha=cfg.lora.lora_alpha,
            lora_dropout=cfg.lora.lora_dropout,
            max_steps=cfg.run.max_steps,
            per_device_batch=cfg.run.per_device_train_batch_size,
            grad_acc=cfg.run.gradient_accumulation_steps,
            learning_rate=cfg.run.learning_rate,
            max_seq_length=cfg.run.max_seq_length,
            use_4bit=cfg.use_4bit_qlora,
            progress_cb=cb,
        )

        job.result = result
        if result.get("ok"):
            register_adapter(
                paths["model_state"],
                adapter_dir,
                samples=result.get("samples", 0),
                notes=f"trigger={job.trigger}",
            )
            job.status = "done"
            job.progress = 1.0
            job.message = f"Training complete – {result.get('samples', 0)} samples, {result.get('steps', 0)} steps"
            if self._on_complete:
                try:
                    self._on_complete(adapter_dir.name)
                except Exception as cb_err:
                    logger.debug("Completion callback failed: %s", cb_err)
        else:
            job.status = "error"
            job.message = result.get("error", "Unknown training error")

        job.finished_at = datetime.now(timezone.utc).isoformat()
        logger.info("Job %s finished: %s", job.id, job.status)


# Singleton
scheduler = TrainingScheduler()
