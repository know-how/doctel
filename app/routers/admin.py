"""
DocTel admin router.

Endpoints for admin model selection, settings management, system reset,
logs, and the model registry CRUD.
"""

import yaml

from fastapi import Path as FAPath
from pathlib import Path as FPath

from app.routers.deps import (
    Body,
    Depends,
    HTTPException,
    JSONResponse,
    FileResponse,
    Query,
    User,
    DbSession,
    get_db,
    get_current_user,
    require_role,
    settings,
    asyncio,
    datetime,
    json,
    shutil,
    Optional,
    select,
    delete,
    model_active,
    model_force,
    BasicResponse,
    run_bootstrap_scan,
    get_bootstrap_status,
    get_effective_settings,
    validate_settings_payload,
    apply_live_settings,
    restart_recommended_for_keys,
    SystemSetting,
    SettingsAudit,
    SystemPrompt,
    DbMessage,
    Chunk,
    Embedding,
    SuggestedPrompt,
    DocAnalysis,
    DbDocument,
    DocumentLink,
    Diagram,
    ProjectMember,
    Project,
    UserIdentityProvider,
    _deep_get_value,
    logger,
)
from app.services.model_registry_service import (
    get_all_providers,
    get_provider,
    add_provider,
    update_provider,
    delete_provider,
    add_model_to_provider,
    remove_model_from_provider,
    get_registry_flat,
)
from app.services.system_settings_service import (
    save_settings_with_verification,
    invalidate_settings_cache,
)

from fastapi import APIRouter

router = APIRouter(tags=["admin"])


# ── Model selection ──────────────────────────────────────────────────────────


@router.get("/admin/models/active")
async def admin_models_active():
    """Return the currently active / forced model."""
    return model_active()


@router.post("/admin/models/select")
async def admin_models_select(payload: dict = Body(...)):
    """Force-select a specific model for the server."""
    model = payload.get("model")
    model_force(model)
    return {"selected": model}


# ── Settings CRUD ────────────────────────────────────────────────────────────


@router.get("/admin/settings")
async def admin_settings_get(
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Return effective settings and their sources."""
    effective, sources = await get_effective_settings(db)
    return {"effective": effective, "sources": sources}


@router.patch("/admin/settings")
async def admin_settings_patch(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Update one or more settings with database transaction verification."""
    try:
        patch_flat = await validate_settings_payload(db, payload or {})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "invalid_settings", "detail": str(e)})

    # Use the verified save flow: save → verify → cache → return
    success, error_msg, result = await save_settings_with_verification(
        db, patch_flat, user_id=user.id,
    )

    if not success:
        return JSONResponse(
            status_code=500,
            content={"error": "save_failed", "detail": error_msg},
        )

    restart_map = restart_recommended_for_keys(result.get("changed_keys", []))
    effective_after, sources = await get_effective_settings(db)
    return {
        "ok": True,
        "restart_recommended": restart_map,
        "effective": effective_after,
        "sources": sources,
        "verified": True,
    }


@router.post("/admin/settings/test")
async def admin_settings_test(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Validate settings changes without persisting them."""
    try:
        patch_flat = await validate_settings_payload(db, payload or {})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "invalid_settings", "detail": str(e)})
    restart_map = restart_recommended_for_keys(list(patch_flat.keys()))
    return {"ok": True, "restart_recommended": restart_map}


@router.post("/admin/settings/backup")
async def admin_settings_backup(
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Dump current effective settings to a YAML backup file."""
    effective, _ = await get_effective_settings(db)
    out_dir = FPath(settings.base_dir) / "backups" / "settings"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{ts}.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(effective, f, sort_keys=False)
    return {"ok": True, "path": str(out_path)}


@router.post("/admin/settings/restore")
async def admin_settings_restore(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Restore settings from a YAML file path or inline YAML string."""
    path_str = (payload.get("path") or "").strip()
    raw_yaml = payload.get("yaml")
    data = None
    if path_str:
        p = FPath(path_str)
        if not p.exists():
            return JSONResponse(status_code=404, content={"error": "file_missing"})
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    elif isinstance(raw_yaml, str) and raw_yaml.strip():
        data = yaml.safe_load(raw_yaml) or {}
    else:
        return JSONResponse(status_code=400, content={"error": "missing_restore_input"})

    try:
        patch_flat = await validate_settings_payload(db, data or {})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "invalid_settings", "detail": str(e)})
    effective_before, _ = await get_effective_settings(db)
    changed_keys = list(patch_flat.keys())
    for key, value in patch_flat.items():
        old_value = _deep_get_value(effective_before, key)
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = res.scalar_one_or_none()
        if not row:
            row = SystemSetting(key=key, value_json=json.dumps(value), updated_by_user_id=user.id)
        else:
            row.value_json = json.dumps(value)
            row.updated_by_user_id = user.id
        db.add(row)
        db.add(
            SettingsAudit(
                key=key,
                old_value_json=json.dumps(old_value),
                new_value_json=json.dumps(value),
                changed_by_user_id=user.id,
            )
        )
    await db.commit()

    effective_after, sources = await get_effective_settings(db)
    apply_live_settings(effective_after)
    restart_map = restart_recommended_for_keys(changed_keys)
    return {"ok": True, "restart_recommended": restart_map, "effective": effective_after, "sources": sources}


# ── Settings audit log ───────────────────────────────────────────────────────


@router.get("/admin/settings/audit")
async def admin_settings_audit(
    limit: int = 100,
    key: Optional[str] = None,
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Return the settings change audit trail."""
    lim = max(1, min(500, int(limit)))
    q = select(SettingsAudit).order_by(SettingsAudit.changed_at.desc()).limit(lim)
    if key:
        q = select(SettingsAudit).where(SettingsAudit.key == key).order_by(SettingsAudit.changed_at.desc()).limit(lim)
    res = await db.execute(q)
    rows = list(res.scalars().all())
    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "key": r.key,
                "old_value": r.old_value_json,
                "new_value": r.new_value_json,
                "changed_by_user_id": r.changed_by_user_id,
                "changed_at": str(r.changed_at) if r.changed_at else "",
            }
        )
    return {"audit": items}


# ── System reset ─────────────────────────────────────────────────────────────


@router.post("/admin/reset/hard")
async def admin_reset_hard(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: DbSession = Depends(get_db),
):
    """Hard reset: wipes chats, documents, projects; optionally drops users."""
    token = (payload.get("confirm_token") or "").strip()
    drop_users = bool(payload.get("drop_users", False))
    if token != "RESET_DOCTEL":
        return JSONResponse(status_code=400, content={"error": "confirm_token_required", "expected": "RESET_DOCTEL"})

    base_dir = FPath(settings.base_dir)
    db_path = base_dir / "db" / "app.db"
    chroma_path = FPath(settings.chroma_path)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_dir = base_dir / "backups" / "db"
    chroma_backup_dir = base_dir / "backups" / "chroma"
    db_backup_dir.mkdir(parents=True, exist_ok=True)
    chroma_backup_dir.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        shutil.copy2(str(db_path), str(db_backup_dir / f"app_{ts}.db"))
    if chroma_path.exists():
        dst = chroma_backup_dir / f"chroma_{ts}"
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(str(chroma_path), str(dst))

    await db.execute(delete(DbMessage))
    await db.execute(delete(DbSession))
    await db.execute(delete(Chunk))
    await db.execute(delete(Embedding))
    await db.execute(delete(SuggestedPrompt))
    await db.execute(delete(DocAnalysis))
    await db.execute(delete(DbDocument))
    await db.execute(delete(DocumentLink))
    await db.execute(delete(Diagram))
    await db.execute(delete(ProjectMember))
    await db.execute(delete(Project))
    if drop_users:
        await db.execute(delete(UserIdentityProvider))
        await db.execute(delete(User))
    await db.commit()

    try:
        if chroma_path.exists():
            shutil.rmtree(chroma_path, ignore_errors=True)
        chroma_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    res = await db.execute(select(SystemSetting).where(SystemSetting.key == "bootstrap_required"))
    row = res.scalar_one_or_none()
    if not row:
        row = SystemSetting(key="bootstrap_required", value_json=json.dumps(True), updated_by_user_id=user.id)
    else:
        row.value_json = json.dumps(True)
        row.updated_by_user_id = user.id
    db.add(row)
    await db.commit()

    asyncio.create_task(run_bootstrap_scan())
    return {"ok": True, "db_backup": str(db_backup_dir / f"app_{ts}.db"), "chroma_backup": str(chroma_backup_dir / f"chroma_{ts}")}


# ── Logs ─────────────────────────────────────────────────────────────────────


@router.get("/api/logs/tail")
async def logs_tail(
    lines: int = 200,
    user: User = Depends(require_role(["admin"])),
):
    """Return the last N lines from the application log file."""
    log_path = settings.projects_dir.parent.parent / "logs" / "app.log"
    if not log_path.exists():
        return {"lines": []}
    n = max(1, min(1000, int(lines)))
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.readlines()
    return {"lines": data[-n:]}


# ═════════════════════════════════════════════════════════════════════════════
# Model Registry CRUD  (admin-only)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/api/models/registry")
async def registry_list(
    user: User = Depends(require_role(["admin"])),
):
    """List all providers and their models in the registry."""
    return {"providers": get_all_providers()}


@router.post("/api/models/registry")
async def registry_add_provider(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
):
    """Add a new model provider to the registry."""
    name = (payload.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name_required"})
    provider = add_provider(
        name=name,
        vendor=payload.get("vendor", ""),
        base_url=payload.get("base_url", ""),
        api_key_env=payload.get("api_key_env", ""),
        models=payload.get("models"),
    )
    return {"provider": provider}


@router.put("/api/models/registry/{provider_id}")
async def registry_update_provider(
    provider_id: str = FAPath(...),
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
):
    """Update a provider's metadata (name, vendor, base_url, api_key_env)."""
    allowed_keys = {"name", "vendor", "base_url", "api_key_env"}
    updates = {k: v for k, v in payload.items() if k in allowed_keys}
    result = update_provider(provider_id, updates)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    return {"provider": result}


@router.delete("/api/models/registry/{provider_id}")
async def registry_delete_provider(
    provider_id: str = FAPath(...),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a provider and all its models."""
    if not delete_provider(provider_id):
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    return {"ok": True}


@router.post("/api/models/registry/{provider_id}/models")
async def registry_add_model(
    provider_id: str = FAPath(...),
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
):
    """Add a model under an existing provider."""
    model_id = (payload.get("id") or "").strip()
    name = (payload.get("name") or "").strip()
    if not model_id or not name:
        return JSONResponse(status_code=400, content={"error": "id_and_name_required"})
    result = add_model_to_provider(
        provider_id=provider_id,
        model_id=model_id,
        name=name,
        vision=bool(payload.get("vision", False)),
        toolCalling=bool(payload.get("toolCalling", False)),
        context_window=int(payload.get("context_window", 4096)),
        capabilities=payload.get("capabilities"),
    )
    if result is None:
        return JSONResponse(status_code=404, content={"error": "provider_not_found"})
    return {"model": result}


@router.delete("/api/models/registry/{provider_id}/models/{model_id}")
async def registry_remove_model(
    provider_id: str = FAPath(...),
    model_id: str = FAPath(...),
    user: User = Depends(require_role(["admin"])),
):
    """Remove a model from a provider."""
    if not remove_model_from_provider(provider_id, model_id):
        return JSONResponse(status_code=404, content={"error": "provider_or_model_not_found"})
    return {"ok": True}


@router.get("/api/models/registry/flat")
async def registry_flat(
    user: User = Depends(require_role(["admin"])),
):
    """Return a flat list of all models with provider info."""
    return {"models": get_registry_flat()}


# ── System Prompts management ───────────────────────────────────────────────


@router.get("/admin/prompts")
async def admin_get_prompts(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Return all distinct prompt types with their latest version."""
    from sqlalchemy import select as sa_select, desc as sa_desc

    # Get all records ordered by prompt_type, version desc
    result = await db.execute(
        sa_select(SystemPrompt).order_by(SystemPrompt.prompt_type, sa_desc(SystemPrompt.version))
    )
    rows = result.scalars().all()

    # Build response: group by prompt_type
    type_map: dict[str, dict] = {}
    for r in rows:
        if r.prompt_type not in type_map:
            type_map[r.prompt_type] = {
                "id": r.id,
                "prompt_type": r.prompt_type,
                "content": r.content,
                "version": r.version,
                "created_at": (r.created_at.isoformat() if r.created_at else None),
                "versions": [],
            }
        type_map[r.prompt_type]["versions"].append({
            "id": r.id,
            "content": r.content,
            "version": r.version,
            "created_at": (r.created_at.isoformat() if r.created_at else None),
        })

    prompts_list = list(type_map.values())
    return {"prompts": prompts_list}


@router.post("/admin/prompts")
async def admin_save_prompt(
    payload: dict = Body(...),
    db: DbSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a new version of a system prompt (upsert by prompt_type)."""
    from sqlalchemy import select as sa_select, desc as sa_desc

    prompt_type = (payload.get("prompt_type") or "").strip()
    content = (payload.get("content") or "").strip()
    if not prompt_type or not content:
        return JSONResponse(status_code=400, content={"error": "prompt_type_and_content_required"})

    # Find the latest version for this prompt_type
    result = await db.execute(
        sa_select(SystemPrompt)
        .where(SystemPrompt.prompt_type == prompt_type)
        .order_by(sa_desc(SystemPrompt.version))
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    new_version = (existing.version + 1) if existing else 1

    record = SystemPrompt(
        prompt_type=prompt_type,
        content=content,
        version=new_version,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "prompt": {
            "id": record.id,
            "prompt_type": record.prompt_type,
            "content": record.content,
            "version": record.version,
            "created_at": (record.created_at.isoformat() if record.created_at else None),
        }
    }


# ── Bootstrap status / reindex ──────────────────────────────────────────────


@router.get("/api/bootstrap/status")
async def bootstrap_status(
    user: User = Depends(get_current_user),
):
    """Return bootstrap scan status."""
    return get_bootstrap_status()


@router.post("/api/admin/reindex", response_model=BasicResponse)
async def admin_reindex(
    user: User = Depends(require_role(["admin"])),
):
    """Trigger a full reindex / bootstrap scan."""
    asyncio.create_task(run_bootstrap_scan())
    return BasicResponse(ok=True)
