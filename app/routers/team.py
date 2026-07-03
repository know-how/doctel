"""
DocTel team router.

Endpoints for team member listing, role management, and activity log.
"""

from fastapi import APIRouter

from app.routers.deps import (
    Body,
    Depends,
    User,
    AsyncSession,
    get_db,
    require_role,
    HTTPException,
    select,
    ProjectMember,
    Document,
)

router = APIRouter(tags=["team"])


# ─────────────────────────────────────────────────────────────────────────────
# Team & Activity API
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/team")
async def get_team_members(
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    members = []
    for u in users:
        proj_result = await db.execute(select(ProjectMember).where(ProjectMember.user_id == u.id))
        memberships = proj_result.scalars().all()
        roles = list(set(m.role_in_project for m in memberships if m.role_in_project))
        members.append({
            "id": u.id,
            "username": u.username or "",
            "ec_number": u.ec_number or "",
            "email": u.email or "",
            "display_name": u.display_name or "",
            "role": u.role,
            "project_roles": roles,
        })
    return {"members": members}


@router.patch("/api/team/{user_id}/role")
async def update_member_role(
    user_id: int,
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    target_result = await db.execute(select(User).where(User.id == user_id))
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    new_role = (payload.get("role") or "").strip()
    allowed = ["admin", "analyst", "viewer"]
    if new_role not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {allowed}")
    target.role = new_role
    db.add(target)
    await db.commit()
    return {"ok": True, "id": target.id, "role": target.role}


@router.get("/api/activity")
async def get_activity_log(
    limit: int = 50,
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(500, int(limit)))
    recent_docs = await db.execute(select(Document).order_by(Document.created_at.desc()).limit(lim))
    docs = list(recent_docs.scalars().all())
    activities = []
    for d in docs:
        activities.append({
            "id": f"act_doc_{d.id}",
            "type": "document_upload",
            "user_id": d.uploaded_by_user_id,
            "target_id": f"doc_{d.id}",
            "target_name": d.filename,
            "timestamp": str(d.created_at) if d.created_at else "",
            "details": {"status": d.status, "project_id": str(d.project_id) if d.project_id else None},
        })
    return {"activities": activities, "total": len(activities)}
