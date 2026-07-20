"""
DocTel compatibility router.

Frontend-facing endpoints that mirror the legacy API surface:
login, user profile, email auth, admin prompts/models/integrations.
"""

import datetime
import smtplib
import ssl

from fastapi import APIRouter

from app.routers.deps import (
    Body,
    Depends,
    User,
    AsyncSession,
    get_db,
    get_current_user,
    require_role,
    HTTPException,
    json,
    JSONResponse,
    Optional,
    select,
    delete,
    update,
    settings,
    Document,
    DocAnalysis,
    SuggestedPrompt,
    ProjectMember,
    DbSession,
    UserIdentityProvider,
    DbDocument,
    Project,
    _parse_document_id,
    _assert_document_workspace_access,
    check_project_access,
    ensure_project_membership,
    verify_ad_credentials,
    request_email_code,
    verify_email_code,
    create_session,
    force_select,
    logger,
)

router = APIRouter(tags=["compat"])


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility Endpoints
# ─────────────────────────────────────────────────────────────────────────────

# Auth stub for frontend login
@router.post("/auth/login")
async def login(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    ec_number = (payload.get("ec_number") or payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    if not ec_number or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")
    display_name = None
    ad_email = None
    try:
        ad = verify_ad_credentials(ec_number, password)
        display_name = ad.get("display_name")
        ad_email = ad.get("email")
    except HTTPException as e:
        if settings.environment == "production":
            raise
        display_name = ec_number
    if not ad_email and settings.allowed_email_domain and "@" not in ec_number:
        ad_email = f"{ec_number}@{settings.allowed_email_domain}".lower()

    provider = "ec_password"
    identity = ec_number
    ures = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = ures.scalar_one_or_none()
    user = None
    if prov:
        resu = await db.execute(select(User).where(User.id == prov.user_id))
        user = resu.scalar_one_or_none()
    if not user:
        resu = await db.execute(select(User).where((User.ec_number == ec_number) | (User.username == ec_number)))
        user = resu.scalar_one_or_none()
    if not user:
        user = User(username=ec_number, ec_number=ec_number, email=ad_email, display_name=display_name or ec_number, role="analyst")
        db.add(user)
        await db.commit()
    if not user.ec_number:
        user.ec_number = ec_number
    if ad_email and not user.email:
        user.email = ad_email
    if display_name and not user.display_name:
        user.display_name = display_name
    db.add(user)
    await db.commit()

    ures = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = ures.scalar_one_or_none()
    if not prov:
        prov = UserIdentityProvider(user_id=user.id, provider=provider, identity=identity, verified=True)
    prov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    prov.verified = True
    db.add(prov)
    if user.email:
        eres = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == "email_otp", UserIdentityProvider.identity == user.email))
        eprov = eres.scalar_one_or_none()
        if eprov and eprov.user_id and str(eprov.user_id) != str(user.id):
            primary_id = eprov.user_id
            secondary_id = user.id
            await db.execute(update(Project).where(Project.owner_user_id == secondary_id).values(owner_user_id=primary_id))
            await db.execute(update(ProjectMember).where(ProjectMember.user_id == secondary_id).values(user_id=primary_id))
            await db.execute(update(Document).where(Document.uploaded_by_user_id == secondary_id).values(uploaded_by_user_id=primary_id))
            await db.execute(update(DbSession).where(DbSession.user_id == secondary_id).values(user_id=primary_id))
            await db.execute(update(SystemSetting).where(SystemSetting.updated_by_user_id == secondary_id).values(updated_by_user_id=primary_id))
            await db.execute(update(SettingsAudit).where(SettingsAudit.changed_by_user_id == secondary_id).values(changed_by_user_id=primary_id))
            await db.execute(update(UserIdentityProvider).where(UserIdentityProvider.user_id == secondary_id).values(user_id=primary_id))
            await db.execute(delete(User).where(User.id == secondary_id))
            await db.commit()
            resu = await db.execute(select(User).where(User.id == primary_id))
            user = resu.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=500, detail="User merge failed")
            prov.user_id = user.id
            db.add(prov)
            eprov.user_id = user.id
        if not eprov:
            eprov = UserIdentityProvider(user_id=user.id, provider="email_otp", identity=user.email, verified=True)
        eprov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
        eprov.verified = True
        db.add(eprov)
    await db.commit()

    token = await create_session(user.id, user.display_name or display_name, provider, identity)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "ec_number": user.ec_number or ec_number,
        "email": user.email or "",
        "display_name": user.display_name or display_name,
        "role": user.role,
    }


@router.get("/users/me")
async def users_me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "ec_number": user.ec_number or user.username or "",
        "email": user.email or "",
        "display_name": user.display_name or "",
    }


@router.patch("/users/me")
async def update_user_profile(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    display_name = (payload.get("display_name") or "").strip()
    email = (payload.get("email") or "").strip()
    if display_name:
        user.display_name = display_name
    if email:
        user.email = email
    db.add(user)
    await db.commit()
    return {"ok": True, "user_id": user.id, "display_name": user.display_name or "", "email": user.email or ""}


@router.patch("/users/me/security")
async def update_user_security(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_password = (payload.get("new_password") or "").strip()
    current_password = (payload.get("current_password") or "").strip()
    if new_password:
        from app.security.rbac import hash_password
        user.password_hash = hash_password(new_password)
        db.add(user)
        await db.commit()
    return {"ok": True}


@router.post("/auth/email/request")
async def email_request(payload: dict = Body(...)):
    email = (payload.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    request_email_code(email)
    return {"message": "Verification code sent"}


@router.post("/auth/email/verify")
async def email_verify(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    email = (payload.get("email") or "").strip()
    code = (payload.get("code") or "").strip()
    print(f"DEBUG: email_verify - received email={email}, code={code}, payload={payload}")
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code required")
    normalized = verify_email_code(email, code)
    provider = "email_otp"
    identity = normalized
    resprov = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = resprov.scalar_one_or_none()
    user = None
    if prov:
        resu = await db.execute(select(User).where(User.id == prov.user_id))
        user = resu.scalar_one_or_none()
    if not user:
        resu = await db.execute(select(User).where((User.email == identity) | (User.username == identity)))
        user = resu.scalar_one_or_none()
    if not user:
        guess_ec = identity.split("@")[0] if "@" in identity else ""
        if guess_ec:
            resu = await db.execute(select(User).where((User.ec_number == guess_ec) | (User.username == guess_ec)))
            user = resu.scalar_one_or_none()
            if user and not user.email:
                user.email = identity
                db.add(user)
                await db.commit()
    if not user:
        display_name = identity.split("@")[0] if "@" in identity else identity
        user = User(username=identity, ec_number=display_name, email=identity, display_name=display_name, role="analyst")
        db.add(user)
        await db.commit()
    if not user.email:
        user.email = identity
    if not user.display_name:
        user.display_name = (identity.split("@")[0] if "@" in identity else identity)
    if not user.ec_number:
        user.ec_number = (identity.split("@")[0] if "@" in identity else identity)
    db.add(user)
    await db.commit()

    resprov = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = resprov.scalar_one_or_none()
    if not prov:
        prov = UserIdentityProvider(user_id=user.id, provider=provider, identity=identity, verified=True)
    prov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    prov.verified = True
    db.add(prov)
    await db.commit()

    token = await create_session(user.id, user.display_name, provider, identity)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "ec_number": user.ec_number or user.username or (user.email or ""),
        "email": user.email or "",
        "display_name": user.display_name or "",
        "role": user.role,
    }


@router.post("/admin/email/test")
async def admin_email_test(
    payload: dict = Body(None),
    user: User = Depends(get_current_user),
):
    to = (payload or {}).get("to") or (f"{user.username}@{settings.allowed_email_domain}" if "@" not in user.username else user.username)
    host, port, usr, pw, use_tls = settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_pass, settings.smtp_use_tls
    if not host or not usr or not pw:
        raise HTTPException(status_code=502, detail="SMTP not configured")
    msg = f"Subject: DocIntel Test\r\n\r\nThis is a DocIntel test message for {to}."
    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls(context=context)
                server.login(usr, pw)
                server.sendmail(usr, [to], msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.login(usr, pw)
                server.sendmail(usr, [to], msg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP error: {e}")
    return {"ok": True, "to": to}


@router.get("/users/me/summary-history")
async def summary_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocAnalysis))
    rows = result.scalars().all()
    items = []
    for row in rows:
        items.append({
            "document_id": f"doc_{row.document_id}",
            "executive_summary": row.executive_summary or "",
            "detailed_summary": [p for p in (row.detailed_summary or "").split("\n") if p.strip()],
            "topics": (json.loads(row.topics_json) if row.topics_json else []),
            "entities": (json.loads(row.entities_json) if row.entities_json else []),
            "sentiment": row.sentiment or "Neutral",
            "action_items": (json.loads(row.action_items_json) if getattr(row, "action_items_json", None) else []),
            "decisions": (json.loads(row.decisions_json) if getattr(row, "decisions_json", None) else []),
            "created_at": "",
        })
    return {"ec_number": user.username, "history": items}


@router.get("/documents/{document_id}/analysis")
async def get_document_analysis_compat(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc_row = doc_res.scalar_one_or_none()
    if not doc_row:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc_row, user, db)
    proj_name = ""
    if doc_row.project_id:
        proj_res = await db.execute(select(Project).where(Project.id == doc_row.project_id))
        proj_row = proj_res.scalar_one_or_none()
        proj_name = proj_row.name if proj_row else ""
    result = await db.execute(
        select(DocAnalysis)
        .where(DocAnalysis.document_id == doc_int)
        .order_by(DocAnalysis.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        status = doc_row.status
        return {
            "id": f"doc_{doc_int}",
            "project_name": proj_name,
            "filename": doc_row.filename or "",
            "document_type": doc_row.doc_type or "",
            "document_date": doc_row.doc_date or "",
            "executive_summary": "",
            "detailed_summary": [],
            "entities": [],
            "key_entities": {"people": [], "dates": [], "locations": []},
            "topics": [],
            "sentiment": "Neutral",
            "action_items": [],
            "decisions": [],
            "status": status.upper(),
        }
    return {
        "id": f"doc_{doc_int}",
        "project_name": proj_name,
        "filename": doc_row.filename or "",
        "document_type": doc_row.doc_type or "",
        "document_date": doc_row.doc_date or "",
        "executive_summary": row.executive_summary or "",
        "detailed_summary": [p for p in (row.detailed_summary or "").split("\n") if p.strip()],
        "entities": (json.loads(row.entities_json) if row.entities_json else []),
        "key_entities": {"people": [], "dates": [], "locations": []},
        "topics": (json.loads(row.topics_json) if row.topics_json else []),
        "sentiment": row.sentiment or "Neutral",
        "action_items": (json.loads(row.action_items_json) if getattr(row, "action_items_json", None) else []),
        "decisions": (json.loads(row.decisions_json) if getattr(row, "decisions_json", None) else []),
        "status": "READY",
    }


@router.get("/documents/{document_id}/prompts")
async def get_document_prompts_compat(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc_row = doc_res.scalar_one_or_none()
    if not doc_row:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc_row, user, db)
    result = await db.execute(select(SuggestedPrompt).where(SuggestedPrompt.document_id == doc_int))
    rows = result.scalars().all()
    prompts = [r.prompt_text for r in rows][:5]
    if not prompts:
        prompts = [
            "Summarize this document in 10 sentences or less.",
            "List the key topics and entities mentioned in this document.",
            "List all action items and decisions mentioned in this document.",
            "Generate a process flow diagram (Mermaid) based on this document.",
            "What are the key requirements, deadlines, and responsibilities mentioned?",
        ]
    return {"document_id": f"doc_{doc_int}", "prompts": prompts}


@router.get("/api/prompts/suggest")
async def api_prompts_suggest(
    document_id: Optional[str] = None,
    project_id: Optional[int] = None,
    scope: str = "document",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sc = (scope or "document").strip().lower()
    doc = None
    analysis = None
    resolved_project_id = None
    filename = ""
    if document_id:
        doc_int = _parse_document_id(document_id)
        dres = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
        doc = dres.scalar_one_or_none()
        if doc:
            await _assert_document_workspace_access(doc, user, db)
            resolved_project_id = int(doc.project_id)
            filename = doc.filename or ""
            ares = await db.execute(
                select(DocAnalysis)
                .where(DocAnalysis.document_id == doc_int)
                .order_by(DocAnalysis.id.desc())
                .limit(1)
            )
            analysis = ares.scalar_one_or_none()
            sc = "document"
    if resolved_project_id is None and project_id is not None:
        resolved_project_id = int(project_id)
        await check_project_access(resolved_project_id, user, db)
        await ensure_project_membership(resolved_project_id, user, db, role_in_project="analyst")
        sc = "project"

    name_low = filename.lower()
    doc_kind = "document"
    if "net" in name_low and "meter" in name_low:
        doc_kind = "net-metering"
    elif "sop" in name_low:
        doc_kind = "sop"
    elif "minute" in name_low:
        doc_kind = "minutes"
    elif "policy" in name_low:
        doc_kind = "policy"

    doc_prompts = []
    if sc == "document":
        doc_prompts = [
            f"Summarize this {doc_kind} document in 10 bullets.",
            "List action items with owners and deadlines.",
            "Extract key entities (people, departments, locations, systems, dates).",
            "Extract risks, mitigations, and compliance implications.",
            "Generate a process flow diagram (Mermaid) for the main workflow described.",
        ]
        if analysis and (analysis.executive_summary or "").strip():
            doc_prompts.insert(0, "Give a 5-sentence executive summary, then 10 key takeaways.")

    cross = [
        "Which internal ZETDC policies or SOPs are relevant to this topic? Cite document IDs where possible.",
        "Compare this document\u2019s requirements against ZETDC policy and highlight gaps.",
    ]

    diagrams = [
        "Draw a Mermaid flowchart showing the end-to-end process with decision points.",
        "Create a Mermaid sequence diagram of the main actors and steps.",
    ]

    spreadsheets = [
        "Propose 3 charts that could summarize the key numbers; specify x-axis and series.",
        "If this includes tables, suggest a bar chart and a trend line chart and what they show.",
    ]

    web_prompts = []
    if bool(getattr(settings, "zetdc", None) and getattr(settings.zetdc, "allow_web_search", False)):
        web_prompts = [
            "Find the latest regulator guidance relevant to this topic and summarize it with citations.",
        ]

    groups = [
        {"group": "Document", "prompts": doc_prompts[:6]},
        {"group": "Policy Cross-Refs", "prompts": cross},
        {"group": "Diagrams", "prompts": diagrams},
        {"group": "Spreadsheets/Charts", "prompts": spreadsheets},
    ]
    if web_prompts:
        groups.append({"group": "Web-Aware", "prompts": web_prompts})
    flat = []
    for g in groups:
        for p in g["prompts"]:
            if p and p not in flat:
                flat.append(p)
    return {"scope": sc, "groups": groups, "prompts": flat}


@router.get("/admin/prompts")
async def admin_get_prompts(
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SuggestedPrompt))
    prompts = list(result.scalars().all())
    items = []
    for p in prompts:
        items.append({"id": p.id, "text": p.text, "category": getattr(p, "category", "general"), "scope": getattr(p, "scope", "document")})
    return {"prompts": items}


@router.post("/admin/prompts")
async def admin_save_prompt(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    text = (payload.get("prompt_type") or payload.get("content") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="content is required")
    prompt = SuggestedPrompt(text=text, category=payload.get("category", "general"), scope=payload.get("scope", "document"))
    db.add(prompt)
    await db.commit()
    return {"ok": True, "id": prompt.id}


@router.post("/admin/models/default")
async def admin_set_default_model(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    task_type = (payload.get("task_type") or "").strip()
    model_id = (payload.get("model_id") or "").strip()
    if not task_type or not model_id:
        return JSONResponse(status_code=400, content={"error": "task_type_and_model_id_required"})
    # Persist using V2 task mapping
    from app.services.model_management_service import set_task_mapping
    # Determine provider id from model prefix
    if model_id.startswith("go/"):
        provider_id = "opencode-go"
    elif model_id.startswith("zen/"):
        provider_id = "opencode-go"
    elif model_id == "gemini-api":
        provider_id = "google-gemini"
    elif model_id == "deepseek-api":
        provider_id = "deepseek"
    else:
        provider_id = "ollama"
    if not set_task_mapping(task_type, provider_id, model_id):
        return JSONResponse(status_code=400, content={"error": "failed_to_set_task_mapping"})
    # Also update in-memory for immediate effect
    force_select(model_id)
    return {"ok": True, "model": model_id, "task_type": task_type}


@router.patch("/admin/integrations")
async def admin_update_integrations(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    allowed_keys = {
        "ollama_base_url", "gemini_api_key", "gemini_model",
        "deepseek_api_key", "deepseek_model", "deepseek_base_url",
        "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_use_tls",
    }
    updates = {k: v for k, v in payload.items() if k in allowed_keys}
    if not updates:
        return {"ok": True, "updated": {}}
    for key, value in updates.items():
        existing = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = existing.scalar_one_or_none()
        if setting:
            setting.value = str(value)
        else:
            setting = SystemSetting(key=key, value=str(value))
            db.add(setting)
    await db.commit()
    return {"ok": True, "updated": list(updates.keys())}
