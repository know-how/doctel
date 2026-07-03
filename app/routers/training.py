"""
DocTel training router.

Endpoints for Training Room API (immediate / idle / batch training,
inbox management, adapter merging) and Advanced Training API
(Gemini + transfer learning, multi-model training, knowledge distillation).
"""

import asyncio

from fastapi import APIRouter

from pathlib import Path

from app.routers.deps import (
    Body,
    Depends,
    User,
    AsyncSession,
    get_db,
    require_role,
    get_current_user,
    HTTPException,
    UploadFile,
    File,
    settings,
    logger,
    _sse_broadcast,
)

router = APIRouter(tags=["training"])


# ─────────────────────────────────────────────────────────────────────────────
# Training Room API
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/training/now")
async def api_training_now(user: User = Depends(require_role(["admin"]))):
    """Trigger an immediate training job using inbox documents."""
    from app.training.training_scheduler import scheduler as _sched
    return await _sched.train_now()


@router.post("/api/training/idle")
async def api_training_idle(user: User = Depends(require_role(["admin"]))):
    """Trigger training only when sufficient RAM is available."""
    from app.training.training_scheduler import scheduler as _sched
    return await _sched.train_idle()


@router.post("/api/training/batch")
async def api_training_batch(
    payload: dict = Body(None),
    user: User = Depends(require_role(["admin"])),
):
    """
    Trigger a training job on a specific folder.
    Body: {"folder": "/absolute/path/to/folder"}  (optional; defaults to inbox)
    """
    from app.training.training_scheduler import scheduler as _sched
    folder = None
    if payload:
        folder = (payload.get("folder") or "").strip() or None
    return await _sched.train_batch(folder=folder)


@router.get("/api/training/status")
async def api_training_status(user: User = Depends(require_role(["admin"]))):
    """Return current training job state."""
    from app.training.training_scheduler import scheduler as _sched
    return _sched.status()


@router.get("/api/training/history")
async def api_training_history(user: User = Depends(require_role(["admin"]))):
    """Return list of completed LoRA adapters (from model_state/meta.json)."""
    from app.training.training_scheduler import scheduler as _sched
    return {"adapters": _sched.history()}


@router.post("/api/training/inbox")
async def api_training_inbox_upload(
    file: UploadFile = File(...),
    user: User = Depends(require_role(["admin"])),
):
    """Upload a document directly into the training inbox."""
    from app.training.training_config import get_training_paths, TrainingSettings
    paths = get_training_paths(settings.base_dir, TrainingSettings())
    inbox = paths["inbox"]
    safe_name = Path(file.filename).name
    dest = inbox / safe_name
    total = 0
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 64 * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large (max 64MB)")
            f.write(chunk)
    return {"ok": True, "filename": safe_name, "size_bytes": total, "inbox_path": str(dest)}


@router.get("/api/training/inbox")
async def api_training_inbox_list(user: User = Depends(require_role(["admin"]))):
    """List files currently in the training inbox."""
    from app.training.training_config import get_training_paths, TrainingSettings
    from app.training.data_preparer import SUPPORTED_EXTENSIONS
    paths = get_training_paths(settings.base_dir, TrainingSettings())
    inbox = paths["inbox"]
    files = []
    for f in sorted(inbox.iterdir()) if inbox.exists() else []:
        if f.is_file():
            files.append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "supported": f.suffix.lower() in SUPPORTED_EXTENSIONS,
            })
    return {"inbox": str(inbox), "files": files}


@router.post("/api/training/adapters/merge")
async def api_training_merge_adapters(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
):
    """Merge multiple LoRA adapters into one."""
    from app.training.training_config import get_training_paths, TrainingSettings
    from app.training.checkpoint_manager import merge_adapters
    adapter_ids = payload.get("adapter_ids") or []
    merged_name = (payload.get("merged_name") or "").strip() or ""
    if not adapter_ids:
        raise HTTPException(status_code=400, detail="adapter_ids required")
    paths = get_training_paths(settings.base_dir, TrainingSettings())
    result = merge_adapters(paths["model_state"], adapter_ids, merged_name)
    if result is None:
        return {"ok": False, "reason": "merge_failed_or_peft_unavailable"}
    return {"ok": True, "merged": result}


# ─────────────────────────────────────────────────────────────────────────────
# Advanced Training API – Gemini + Transfer Learning
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/training/export-from-projects")
async def api_training_export_from_projects(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Export documents from specified projects as JSONL training data.

    Body: {
        "project_ids": [1, 2, 3],
        "output_dir": "/optional/path" (optional)
    }

    Returns: {"ok": True, "batch_file": "/path/to/batch.jsonl", "sample_count": N}
    """
    project_ids = payload.get("project_ids") or []
    output_dir = (payload.get("output_dir") or "").strip() or None

    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids required")

    try:
        from app.services.training_export_service import export_documents_for_training

        batch_file = await export_documents_for_training(
            project_ids=project_ids,
            output_dir=output_dir,
            db=db,
        )

        # Count lines in batch file
        sample_count = 0
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                sample_count = sum(1 for _ in f)
        except Exception:
            pass

        logger.info(f"Exported {sample_count} training samples from projects {project_ids}")
        return {
            "ok": True,
            "batch_file": batch_file,
            "sample_count": sample_count,
        }
    except Exception as e:
        logger.exception("Training export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/api/training/models/status")
async def api_training_models_status(
    user: User = Depends(get_current_user),
):
    """Get training models status. Available to all authenticated users.
    The training model list and detailed status is admin-only."""
    from app.training.training_config import default_training_settings
    import os

    training_models_env = os.getenv("TRAINING_MODELS", "")
    models_list = [m.strip() for m in training_models_env.split(",") if m.strip()] if training_models_env else default_training_settings.base_models

    is_admin = user.role == "admin"

    return {
        "auto_train_enabled": True,
        "cooldown_seconds": 300,
        "models": models_list if is_admin else [],
        "models_count": len(models_list),
        "admin_only_details": not is_admin,
    }


@router.post("/api/training/train-all-models")
async def api_training_train_all_models(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
):
    """
    Train all configured base models (Llama 3.2, Qwen, etc.) on a JSONL batch.

    Body: {
        "batch_file": "/path/to/training_batch.jsonl",
        "sequential": True (optional, default: True for safety)
    }

    Returns: {
        "status": "training_started",
        "models": ["llama3.2-3b", "llama3.2-8b", "qwen2.5-7b"],
        "batch_file": "...",
        "job_id": "..."  (for tracking progress)
    }
    """
    batch_file = (payload.get("batch_file") or "").strip()
    sequential = payload.get("sequential", True)

    if not batch_file:
        raise HTTPException(status_code=400, detail="batch_file required")

    batch_path = Path(batch_file)
    if not batch_path.exists():
        raise HTTPException(status_code=404, detail=f"Batch file not found: {batch_file}")

    try:
        from app.services.multi_model_trainer import MultiModelTrainer
        from app.training.training_config import default_training_settings

        # Start training in background
        async def _background_train():
            try:
                trainer = MultiModelTrainer()
                results = await trainer.train_all_models(
                    batch_path=batch_path,
                    sequential=sequential,
                )
                logger.info(f"Multi-model training complete: {results}")
                await _sse_broadcast("training.complete", {
                    "results": {k: v for k, v in results.items() if isinstance(v, dict)},
                })
            except Exception as e:
                logger.exception("Background training failed")
                await _sse_broadcast("training.error", {"error": str(e)})

        # Dispatch background task
        asyncio.create_task(_background_train())

        return {
            "status": "training_started",
            "models": default_training_settings.base_models,
            "batch_file": batch_file,
            "sequential": sequential,
        }
    except Exception as e:
        logger.exception("Failed to start multi-model training")
        raise HTTPException(status_code=500, detail=f"Training start failed: {str(e)}")


@router.post("/api/training/train-from-projects")
async def api_training_train_from_projects(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Convenience endpoint: Export documents from projects AND train all models.

    This is the main workflow:
    1. Export documents from specified projects
    2. Train Llama 3.2 (3B + 8B) and Qwen models on the exported data
    3. Adapters are saved for runtime use

    Body: {
        "project_ids": [1, 2, 3],
        "sequential": True (optional)
    }

    Returns: {
        "status": "complete" | "error",
        "batch_file": "...",
        "results": {
            "meta-llama/Llama-3.2-3B-Instruct": {"ok": True, ...},
            "Qwen/Qwen2.5-7B-Instruct": {"ok": False, "error": "..."},
        }
    }
    """
    project_ids = payload.get("project_ids") or []
    sequential = payload.get("sequential", True)

    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids required")

    try:
        from app.services.multi_model_trainer import train_models_from_project

        # Run export + training
        result = await train_models_from_project(
            project_ids=project_ids,
            db=db,
        )

        # Broadcast success to SSE subscribers
        await _sse_broadcast("training.complete", result)

        logger.info(f"Project-based training complete for projects {project_ids}")
        return result

    except Exception as e:
        logger.exception("Project-based training failed")
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/api/training/distill-from-cloud")
async def api_training_distill_from_cloud(
    payload: dict = Body(default={}),
    user: User = Depends(require_role(["admin"])),
):
    """
    Distill ZETDC knowledge from cloud API models (Gemini, DeepSeek)
    into local model training data.

    This proactively queries cloud models with diverse ZETDC topics,
    captures Q&A pairs as JSONL for LoRA fine-tuning, and optionally
    triggers training afterwards.

    Body: {
        "topics": ["ZETDC substation safety", ...]  (optional, defaults to built-in list)
        "num_per_topic": 5                          (optional, default 5)
        "auto_train": true                          (optional, trigger training after distillation)
    }

    Returns: {
        "status": "complete",
        "total_samples": 150,
        "gemini_samples": 75,
        "deepseek_samples": 75,
        "topics_covered": 25,
        "output_file": "...",
        "training_triggered": true/false
    }
    """
    from app.services.knowledge_distillation_service import distill_zetdc_knowledge

    topics = payload.get("topics") or None
    num_per_topic = payload.get("num_per_topic", 5)
    auto_train = payload.get("auto_train", False)

    try:
        result = await distill_zetdc_knowledge(
            topics=topics,
            num_per_topic=num_per_topic,
        )

        if auto_train and result.get("total_samples", 0) > 0:
            try:
                from app.training.training_scheduler import scheduler
                scheduler.train_now(trigger="distillation_auto")
                result["training_triggered"] = True
            except Exception as e:
                logger.warning("Auto-train after distillation failed: %s", e)
                result["training_triggered"] = False
        else:
            result["training_triggered"] = False

        try:
            from app.services.knowledge_distillation_service import generate_transcription_training_data
            transcription_result = await generate_transcription_training_data()
            result["transcription_samples"] = transcription_result.get("total_samples", 0)
        except Exception as e:
            logger.warning("Transcription training generation failed: %s", e)
            result["transcription_samples"] = 0

        result["status"] = "complete"
        await _sse_broadcast("distillation.complete", result)
        return result

    except Exception as e:
        logger.exception("Knowledge distillation failed")
        raise HTTPException(status_code=500, detail=f"Distillation failed: {str(e)}")
