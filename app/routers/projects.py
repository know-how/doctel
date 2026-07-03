"""
DocTel project management router.

Endpoints for listing, creating, updating, and deleting projects
as well as querying project members.
"""

from app.routers.deps import (
    APIRouter,
    Depends,
    HTTPException,
    Body,
    select,
    func,
    Project,
    ProjectMember,
    User,
    Document,
    AsyncSession,
    get_current_user,
    get_db,
    require_role,
    check_project_access,
    ensure_project_membership,
    ProjectsListResponse,
    ProjectInfo,
    _accessible_project_ids,
)

logger = __import__("logging").getLogger(__name__)

router = APIRouter(tags=["projects"])


# ---------------------------------------------------------------------------
# GET /api/projects — list accessible projects
# ---------------------------------------------------------------------------
@router.get("/api/projects", response_model=ProjectsListResponse)
async def list_projects_api(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "admin":
        result = await db.execute(select(Project))
    else:
        member_q = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        member_res = await db.execute(member_q)
        member_ids = [row[0] for row in member_res.all()]
        owned_q = select(Project).where(Project.owner_user_id == user.id)
        owned_result = await db.execute(owned_q)
        owned_ids = [p.id for p in owned_result.scalars().all()]
        all_ids = list(set(member_ids + owned_ids))
        result = await db.execute(select(Project).where(Project.id.in_(all_ids))) if all_ids else await db.execute(select(Project).where(Project.id == -1))
    rows = result.scalars().all()
    items = []
    for p in rows:
        doc_count_q = select(func.count(Document.id)).where(Document.project_id == p.id)
        c = await db.execute(doc_count_q)
        doc_count = int(c.scalar() or 0)
        last_doc_q = select(Document.created_at).where(Document.project_id == p.id).order_by(Document.created_at.desc()).limit(1)
        last_doc_res = await db.execute(last_doc_q)
        last_doc_row = last_doc_res.first()
        last_activity = str(last_doc_row[0]) if last_doc_row else ""
        items.append(ProjectInfo(
            id=str(p.id),
            name=p.name,
            document_count=doc_count,
            created_at=str(getattr(p, "created_at", "")) if getattr(p, "created_at", None) else "",
            updated_at=str(getattr(p, "updated_at", "")) if getattr(p, "updated_at", None) else "",
            last_activity=last_activity,
        ))
    return ProjectsListResponse(projects=items)


# ---------------------------------------------------------------------------
# PUT /api/projects/{project_id} — rename a project
# ---------------------------------------------------------------------------
@router.put("/api/projects/{project_id}")
async def update_project(project_id: int, payload: dict = Body(...), user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await check_project_access(project_id, user, db)
    name = (payload.get("name") or "").strip()
    if name:
        existing = await db.execute(select(Project).where(func.lower(Project.name) == name.lower(), Project.id != project_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"A workspace named \"{name}\" already exists")
        project.name = name
        db.add(project)
        await db.commit()
    return {"id": str(project.id), "name": project.name}


# ---------------------------------------------------------------------------
# DELETE /api/projects/{project_id} — delete a project (must be empty)
# ---------------------------------------------------------------------------
@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role != "admin" and project.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project owner or admin can delete this project")
    doc_result = await db.execute(select(Document).where(Document.project_id == project_id))
    docs = list(doc_result.scalars().all())
    if docs:
        raise HTTPException(status_code=409, detail=f"Cannot delete project with {len(docs)} document(s). Delete or move documents first.")
    member_result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id))
    for member in member_result.scalars().all():
        await db.delete(member)
    await db.delete(project)
    await db.commit()
    return {"ok": True, "id": str(project_id)}


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/members — list project members
# ---------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/members")
async def get_project_members(project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await check_project_access(project_id, user, db)
    member_result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    members = []
    for m in member_result.scalars().all():
        u_result = await db.execute(select(User).where(User.id == m.user_id))
        u = u_result.scalar_one_or_none()
        members.append({
            "id": u.id if u else m.user_id,
            "display_name": u.display_name if u else "",
            "email": u.email if u else "",
            "role": u.role if u else "",
            "role_in_project": m.role_in_project or "",
        })
    owner = await db.execute(select(User).where(User.id == project.owner_user_id))
    owner_user = owner.scalar_one_or_none()
    owner_info = {
        "id": owner_user.id if owner_user else project.owner_user_id,
        "display_name": owner_user.display_name if owner_user else "",
        "email": owner_user.email if owner_user else "",
        "role": owner_user.role if owner_user else "",
        "role_in_project": "owner",
    }
    member_ids = {m["id"] for m in members}
    if owner_info["id"] not in member_ids:
        members.append(owner_info)
    return {"project_id": str(project_id), "members": members}


# ---------------------------------------------------------------------------
# POST /api/projects — create a new project
# ---------------------------------------------------------------------------
@router.post("/api/projects")
async def create_project(payload: dict = Body(...), user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    name = (payload or {}).get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    existing = await db.execute(select(Project).where(func.lower(Project.name) == name.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"A workspace named \"{name}\" already exists")
    project = Project(name=name, owner_user_id=user.id)
    db.add(project)
    await db.commit()
    await ensure_project_membership(project.id, user, db, role_in_project="admin" if user.role == "admin" else "analyst")
    return {"id": project.id, "name": project.name}


# ---------------------------------------------------------------------------
# GET /api/me/projects — projects visible to the current user (with role)
# ---------------------------------------------------------------------------
@router.get("/api/me/projects")
async def my_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "admin":
        pres = await db.execute(select(Project))
        projects = list(pres.scalars().all())
        return {"projects": [{"id": str(p.id), "name": p.name, "role": "admin", "owner_user_id": p.owner_user_id, "member_count": 0} for p in projects]}
    owned_res = await db.execute(select(Project).where(Project.owner_user_id == user.id))
    owned = list(owned_res.scalars().all())
    proj_map: dict[int, dict] = {}
    for p in owned:
        proj_map[int(p.id)] = {"id": str(p.id), "name": p.name, "role": "owner", "owner_user_id": p.owner_user_id, "member_count": 0}
    member_res = await db.execute(select(ProjectMember).where(ProjectMember.user_id == user.id))
    for m in member_res.scalars().all():
        if int(m.project_id) not in proj_map:
            p_res = await db.execute(select(Project).where(Project.id == m.project_id))
            p = p_res.scalar_one_or_none()
            proj_map[int(m.project_id)] = {"id": str(m.project_id), "name": p.name if p else "Unknown", "role": m.role_in_project or "member", "owner_user_id": p.owner_user_id if p else None, "member_count": 0}
    for pid in proj_map:
        mc_res = await db.execute(select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == pid))
        mc = int(mc_res.scalar() or 0) + 1
        proj_map[pid]["member_count"] = mc
    return {"projects": list(proj_map.values())}


# ---------------------------------------------------------------------------
# GET /users/me/projects — alias for my_projects
# ---------------------------------------------------------------------------
@router.get("/users/me/projects")
async def my_projects_alias(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await my_projects(user=user, db=db)
