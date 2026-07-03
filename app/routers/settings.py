"""
DocTel Settings Router.

Endpoints for UI settings and admin system settings.
"""

from pathlib import Path

from app.routers.deps import (
    # FastAPI
    APIRouter,
    Depends,
    Body,
    HTTPException,
    # Responses
    JSONResponse,
    # SQLAlchemy
    AsyncSession,
    select,
    # App
    get_db,
    settings,
    # Models
    User,
    SystemSetting,
    SettingsAudit,
    BasicResponse,
    # RBAC
    get_current_user,
    require_role,
    # System settings service
    get_effective_settings,
    validate_settings_payload,
    apply_live_settings,
    restart_recommended_for_keys,
    # Standard library
    datetime,
    json,
    Optional,
)

import yaml

router = APIRouter(tags=["settings"])


# ---------------------------------------------------------------------------
# UI settings  (/api/settings/ui)
# ---------------------------------------------------------------------------


@router.get("/api/settings/ui")
async def api_settings_ui(user: User = Depends(get_current_user)):
    return settings.ui.model_dump()


@router.post("/api/settings/ui", response_model=BasicResponse)
async def save_settings_ui(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
):
    theme = (payload or {}).get("theme", "").strip()
    if theme:
        return BasicResponse(ok=True)
    return BasicResponse(ok=False, error="no theme provided")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deep_get_value(d: dict, path: str):
    cur = d
    for p in (path or "").split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


# ---------------------------------------------------------------------------
# Admin settings  (/admin/settings)
# ---------------------------------------------------------------------------


@router.get("/admin/settings")
async def admin_settings_get(
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    effective, sources = await get_effective_settings(db)
    return {"effective": effective, "sources": sources}


@router.patch("/admin/settings")
async def admin_settings_patch(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    try:
        patch_flat = await validate_settings_payload(db, payload or {})
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_settings", "detail": str(e)},
        )
    effective_before, _ = await get_effective_settings(db)

    changed_keys = list(patch_flat.keys())
    for key, value in patch_flat.items():
        old_value = _deep_get_value(effective_before, key)
        res = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        row = res.scalar_one_or_none()
        if not row:
            row = SystemSetting(
                key=key,
                value_json=json.dumps(value),
                updated_by_user_id=user.id,
            )
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
    return {
        "ok": True,
        "restart_recommended": restart_map,
        "effective": effective_after,
        "sources": sources,
    }


@router.post("/admin/settings/test")
async def admin_settings_test(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    try:
        patch_flat = await validate_settings_payload(db, payload or {})
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_settings", "detail": str(e)},
        )
    restart_map = restart_recommended_for_keys(list(patch_flat.keys()))
    return {"ok": True, "restart_recommended": restart_map}


@router.post("/admin/settings/backup")
async def admin_settings_backup(
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    effective, _ = await get_effective_settings(db)
    out_dir = Path(settings.base_dir) / "backups" / "settings"
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
    db: AsyncSession = Depends(get_db),
):
    path = (payload.get("path") or "").strip()
    raw_yaml = payload.get("yaml")
    data = None
    if path:
        p = Path(path)
        if not p.exists():
            return JSONResponse(
                status_code=404, content={"error": "file_missing"}
            )
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    elif isinstance(raw_yaml, str) and raw_yaml.strip():
        data = yaml.safe_load(raw_yaml) or {}
    else:
        return JSONResponse(
            status_code=400, content={"error": "missing_restore_input"}
        )

    try:
        patch_flat = await validate_settings_payload(db, data or {})
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_settings", "detail": str(e)},
        )
    effective_before, _ = await get_effective_settings(db)
    changed_keys = list(patch_flat.keys())
    for key, value in patch_flat.items():
        old_value = _deep_get_value(effective_before, key)
        res = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        row = res.scalar_one_or_none()
        if not row:
            row = SystemSetting(
                key=key,
                value_json=json.dumps(value),
                updated_by_user_id=user.id,
            )
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
    return {
        "ok": True,
        "restart_recommended": restart_map,
        "effective": effective_after,
        "sources": sources,
    }


@router.get("/admin/settings/audit")
async def admin_settings_audit(
    limit: int = 100,
    key: Optional[str] = None,
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(500, int(limit)))
    q = (
        select(SettingsAudit)
        .order_by(SettingsAudit.changed_at.desc())
        .limit(lim)
    )
    if key:
        q = (
            select(SettingsAudit)
            .where(SettingsAudit.key == key)
            .order_by(SettingsAudit.changed_at.desc())
            .limit(lim)
        )
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
