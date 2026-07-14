from datetime import datetime, timedelta
import json
import secrets
from typing import Dict, Any
from urllib import request, error
from fastapi import HTTPException, Header
from sqlalchemy import select
from app.config import settings


# In-memory cache (fast lookup), backed by DB for persistence
_session_store: Dict[str, Dict[str, Any]] = {}
_email_code_store: Dict[str, Dict[str, Any]] = {}


async def _save_session_to_db(token: str, session_data: Dict[str, Any]) -> bool:
    try:
        from app.db.database import AsyncSessionLocal
        from app.db.models import AuthSession
        async with AsyncSessionLocal() as session:
            auth_session = AuthSession(
                token=token,
                user_id=int(session_data["user_id"]),
                provider=session_data.get("provider", ""),
                identity=session_data.get("identity", ""),
                display_name=session_data.get("display_name", ""),
            )
            session.add(auth_session)
            await session.commit()
            return True
    except Exception as e:
        print(f"[auth_service] Failed to save session to DB: {e}")
        return False


async def _load_session_from_db(token: str) -> Dict[str, Any] | None:
    try:
        from app.db.database import AsyncSessionLocal
        from app.db.models import AuthSession
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AuthSession).where(AuthSession.token == token)
            )
            auth_session = result.scalar_one_or_none()
            if auth_session:
                return {
                    "user_id": int(auth_session.user_id),
                    "provider": auth_session.provider,
                    "identity": auth_session.identity,
                    "display_name": auth_session.display_name,
                    "created_at": auth_session.created_at.isoformat() if auth_session.created_at else None,
                }
    except Exception as e:
        print(f"[auth_service] Failed to load session from DB: {e}")
    return None


async def _delete_session_from_db(token: str) -> bool:
    try:
        from app.db.database import AsyncSessionLocal
        from app.db.models import AuthSession
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AuthSession).where(AuthSession.token == token)
            )
            auth_session = result.scalar_one_or_none()
            if auth_session:
                await session.delete(auth_session)
                await session.commit()
                return True
    except Exception as e:
        print(f"[auth_service] Failed to delete session from DB: {e}")
    return False


def _build_ad_username(ec_number: str) -> str:
    if settings.ad_domain:
        if "\\" in settings.ad_domain:
            return f"{settings.ad_domain}\\{ec_number}"
        if "." in settings.ad_domain:
            return f"{ec_number}@{settings.ad_domain}"
    return ec_number


def verify_ad_credentials(ec_number: str, password: str) -> dict:
    try:
        from ldap3 import Server, Connection, ALL
    except Exception:
        raise HTTPException(status_code=500, detail="ldap3 is not installed")
    if not settings.ad_url:
        raise HTTPException(status_code=500, detail="AD is not configured")
    server = Server(settings.ad_url, use_ssl=settings.ad_use_tls, get_info=ALL)
    username = _build_ad_username(ec_number)
    try:
        connection = Connection(
            server,
            user=username,
            password=password,
            auto_bind=True,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    display_name = None
    email = None
    if settings.ad_base_dn:
        try:
            connection.search(
                settings.ad_base_dn,
                f"(sAMAccountName={ec_number})",
                attributes=["displayName", "mail", "userPrincipalName"],
            )
            if connection.entries:
                display_name = connection.entries[0].displayName.value
                try:
                    email = connection.entries[0].mail.value
                except Exception:
                    email = None
                if not email:
                    try:
                        email = connection.entries[0].userPrincipalName.value
                    except Exception:
                        email = None
        except Exception:
            display_name = None
    connection.unbind()
    return {"display_name": display_name, "email": email}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_valid_zetdc_email(email: str) -> bool:
    normalized = _normalize_email(email)
    domain = settings.allowed_email_domain.strip().lower()
    if not domain:
        return False
    return normalized.endswith(f"@{domain}")


def _send_email_code(email: str, code: str) -> None:
    subject = "DocIntel Verification Code"
    body = f"Your DocIntel verification code is: {code}"

    # Print OTP to backend terminal
    print(f"\n{'='*50}")
    print(f"[OTP] Verification code for {email}: {code}")
    print(f"{'='*50}\n")

    # Also write OTP to a temp file for debugging
    import os
    otp_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'tmp_otp.txt')
    try:
        with open(otp_file, 'w') as f:
            f.write(f"{email}:{code}")
        print(f"[DEBUG] OTP written to {otp_file}")
    except Exception as e:
        print(f"[DEBUG] Failed to write OTP file: {e}")

    endpoint = settings.email_server_endpoint or "/send"
    base_url = settings.email_server_url.rstrip("/")
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base_url}{endpoint}"

    if (
        not settings.email_sender_email
        or not settings.email_sender_password
        or not settings.email_sender_ews_url
    ):
        print(f"[DEV MODE] OTP for {email}: {code}")
        return

    clean_ews_url = settings.email_sender_ews_url.replace("http://", "").replace("https://", "")
    payload: Dict[str, Any] = {
        "sender_email": settings.email_sender_email,
        "sender_password": settings.email_sender_password,
        "ews_url": clean_ews_url,
        "receiver_email": email,
        "subject": subject,
        "message": body,
    }

    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8")

    try:
        req = request.Request(url, data=data, headers=headers, method="POST")
        with request.urlopen(req, timeout=15) as res:
            raw_body = res.read()
            decoded_body = raw_body.decode("utf-8", errors="ignore")
            if not (200 <= res.status < 300):
                raise HTTPException(status_code=502, detail="Email server error")
            print(f"[Email Sent] OTP sent to {email}")
            return
    except error.HTTPError as e:
        raise HTTPException(status_code=502, detail="Email server failed")
    except error.URLError as e:
        raise HTTPException(status_code=502, detail="Email server unreachable")
    except Exception as ex:
        raise HTTPException(status_code=500, detail="Email sending error")


def request_email_code(email: str) -> str:
    normalized = _normalize_email(email)
    if not _is_valid_zetdc_email(normalized):
        raise HTTPException(status_code=400, detail="Invalid ZETDC email")
    code = f"{secrets.randbelow(1000000):06d}"
    _email_code_store[normalized] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }

    # ── Print verification code prominently to console ──────────────────
    print("\n" + "!" * 60)
    print(f"  🔑 LOGIN VERIFICATION CODE for {normalized}")
    print(f"  📋 Code: {code}")
    print(f"  ⏰ Expires: {datetime.utcnow() + timedelta(minutes=10)}")
    print("!" * 60 + "\n")

    _send_email_code(normalized, code)

    return code


def verify_email_code(email: str, code: str) -> str:
    normalized = _normalize_email(email)
    entry = _email_code_store.get(normalized)
    if not entry:
        raise HTTPException(status_code=401, detail="Invalid code")
    if datetime.utcnow() > entry["expires_at"]:
        _email_code_store.pop(normalized, None)
        raise HTTPException(status_code=401, detail="Code expired")
    if entry["code"] != code:
        raise HTTPException(status_code=401, detail="Invalid code")
    _email_code_store.pop(normalized, None)
    return normalized


async def create_session(user_id: int, display_name: str | None, provider: str, identity: str) -> str:
    token = secrets.token_urlsafe(32)
    session_data = {
        "user_id": int(user_id),
        "provider": provider,
        "identity": identity,
        "display_name": display_name or "",
        "created_at": datetime.utcnow().isoformat(),
    }
    _session_store[token] = session_data
    await _save_session_to_db(token, session_data)
    return token


async def get_current_user(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = parts[1]

    user = _session_store.get(token)
    if user:
        return user

    user = await _load_session_from_db(token)
    if user:
        _session_store[token] = user
        return user

    raise HTTPException(status_code=401, detail="Invalid or expired token")


def validate_token(token: str) -> Dict[str, Any] | None:
    return _session_store.get(token)


async def revoke_token(token: str) -> bool:
    existed = _session_store.pop(token, None) is not None
    db_existed = await _delete_session_from_db(token)
    return existed or db_existed
