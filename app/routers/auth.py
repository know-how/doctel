"""Authentication and user management endpoints."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.routers.deps import (
    _sse_broadcast,
    get_db,
    get_current_user,
    settings,
    User,
    DbSession,
    UserIdentityProvider,
    Project,
    ProjectMember,
    Document as DbDocument,
    SystemSetting,
    SettingsAudit,
    auth_service,
    verify_ad_credentials,
    request_email_code,
    verify_email_code,
    create_session,
)

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
async def login(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
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
    ures = await db.execute(
        select(UserIdentityProvider).where(
            UserIdentityProvider.provider == provider,
            UserIdentityProvider.identity == identity,
        )
    )
    prov = ures.scalar_one_or_none()
    user = None
    if prov:
        resu = await db.execute(select(User).where(User.id == prov.user_id))
        user = resu.scalar_one_or_none()
    if not user:
        resu = await db.execute(
            select(User).where(
                (User.ec_number == ec_number) | (User.username == ec_number)
            )
        )
        user = resu.scalar_one_or_none()
    if not user:
        user = User(
            username=ec_number,
            ec_number=ec_number,
            email=ad_email,
            display_name=display_name or ec_number,
            role="analyst",
        )
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

    ures = await db.execute(
        select(UserIdentityProvider).where(
            UserIdentityProvider.provider == provider,
            UserIdentityProvider.identity == identity,
        )
    )
    prov = ures.scalar_one_or_none()
    if not prov:
        prov = UserIdentityProvider(
            user_id=user.id, provider=provider, identity=identity, verified=True
        )
    prov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    prov.verified = True
    db.add(prov)
    if user.email:
        eres = await db.execute(
            select(UserIdentityProvider).where(
                UserIdentityProvider.provider == "email_otp",
                UserIdentityProvider.identity == user.email,
            )
        )
        eprov = eres.scalar_one_or_none()
        if eprov and eprov.user_id and int(eprov.user_id) != int(user.id):
            primary_id = int(eprov.user_id)
            secondary_id = int(user.id)
            await db.execute(
                update(Project)
                .where(Project.owner_user_id == secondary_id)
                .values(owner_user_id=primary_id)
            )
            await db.execute(
                update(ProjectMember)
                .where(ProjectMember.user_id == secondary_id)
                .values(user_id=primary_id)
            )
            await db.execute(
                update(DbDocument)
                .where(DbDocument.uploaded_by_user_id == secondary_id)
                .values(uploaded_by_user_id=primary_id)
            )
            await db.execute(
                update(DbSession)
                .where(DbSession.user_id == secondary_id)
                .values(user_id=primary_id)
            )
            await db.execute(
                update(SystemSetting)
                .where(SystemSetting.updated_by_user_id == secondary_id)
                .values(updated_by_user_id=primary_id)
            )
            await db.execute(
                update(SettingsAudit)
                .where(SettingsAudit.changed_by_user_id == secondary_id)
                .values(changed_by_user_id=primary_id)
            )
            await db.execute(
                update(UserIdentityProvider)
                .where(UserIdentityProvider.user_id == secondary_id)
                .values(user_id=primary_id)
            )
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
            eprov = UserIdentityProvider(
                user_id=user.id,
                provider="email_otp",
                identity=user.email,
                verified=True,
            )
        eprov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
        eprov.verified = True
        db.add(eprov)
    await db.commit()

    token = await create_session(
        user.id, user.display_name or display_name, provider, identity
    )
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
    return {
        "ok": True,
        "user_id": user.id,
        "display_name": user.display_name or "",
        "email": user.email or "",
    }


@router.patch("/users/me/security")
async def update_user_security(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_password = (payload.get("new_password") or "").strip()
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
    code = request_email_code(email)
    from app.config import settings
    resp = {"message": "Verification code sent"}
    # In dev mode (email not configured), return the code so the frontend can display it
    if (
        not settings.email_sender_email
        or not settings.email_sender_password
        or not settings.email_sender_ews_url
    ):
        resp["dev_code"] = code
    return resp


@router.post("/auth/email/verify")
async def email_verify(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    email = (payload.get("email") or "").strip()
    code = (payload.get("code") or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code required")
    normalized = verify_email_code(email, code)
    provider = "email_otp"
    identity = normalized
    resprov = await db.execute(
        select(UserIdentityProvider).where(
            UserIdentityProvider.provider == provider,
            UserIdentityProvider.identity == identity,
        )
    )
    prov = resprov.scalar_one_or_none()
    user = None
    if prov:
        resu = await db.execute(select(User).where(User.id == prov.user_id))
        user = resu.scalar_one_or_none()
    if not user:
        from app.db.database import AsyncSessionLocal as _AsyncSessionLocal

        async with _AsyncSessionLocal() as session:
            resu = await session.execute(
                select(User).where(User.email == normalized)
            )
            existing = resu.scalar_one_or_none()
            if existing:
                if prov:
                    prov.user_id = existing.id
                    prov.verified = True
                    session.add(prov)
                    await session.commit()
                token = await create_session(
                    existing.id,
                    existing.display_name or existing.username,
                    provider,
                    normalized,
                )
                if not existing.ec_number:
                    existing.ec_number = normalized.split("@")[0]
                    session.add(existing)
                    await session.commit()
                return {
                    "access_token": token,
                    "token_type": "bearer",
                    "user_id": existing.id,
                    "ec_number": existing.ec_number or existing.username or "",
                    "email": existing.email or "",
                    "display_name": existing.display_name or existing.username,
                    "role": existing.role,
                }
        user = User(
            username=normalized.split("@")[0],
            ec_number=normalized.split("@")[0],
            email=normalized,
            display_name=normalized.split("@")[0],
            role="analyst",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    if not prov:
        prov = UserIdentityProvider(
            user_id=user.id, provider=provider, identity=identity, verified=True
        )
    prov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    prov.verified = True
    db.add(prov)
    await db.commit()
    token = await create_session(
        user.id,
        user.display_name or user.username,
        provider,
        normalized,
    )
    if not user.ec_number:
        user.ec_number = normalized.split("@")[0]
        db.add(user)
        await db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "ec_number": user.ec_number or user.username or "",
        "email": user.email or "",
        "display_name": user.display_name or user.username,
        "role": user.role,
    }


@router.post("/auth/logout")
async def auth_logout_with_broadcast(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log out the current user: invalidate session token and broadcast logout event."""
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token and not token.startswith("local-"):
                await auth_service.revoke_token(token)
    except Exception:
        pass
    try:
        from app.services.ingest_worker import cancel_document_ids
        from sqlalchemy import select as _select
        from app.db.models import Document as _Document

        pending_result = await db.execute(
            _select(_Document.id).where(
                _Document.uploaded_by_user_id == user.id,
                _Document.status.in_(["uploaded", "ingesting"]),
            )
        )
        pending_ids = [row[0] for row in pending_result.all()]
        if pending_ids:
            cancel_document_ids(pending_ids)
    except Exception:
        pass
    try:
        from app.services.model_router import force_select

        force_select(None)
    except Exception:
        pass
    await _sse_broadcast(
        "session.logout", {"user_id": user.id, "ec_number": user.ec_number or ""}
    )
    return {"success": True, "broadcast": True}
