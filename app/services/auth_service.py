from datetime import datetime, timedelta
import json
import secrets
from typing import Dict, Any
from urllib import request, error
from fastapi import HTTPException, Header
from app.config import settings


_session_store: Dict[str, Dict[str, Any]] = {}
_email_code_store: Dict[str, Dict[str, Any]] = {}


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
    """
    Send a DocIntel verification code to the user's email.

    This method supports two modes:
    1. DEVELOPMENT MODE: if email server is not configured, print OTP to console.
    2. PRODUCTION MODE: sends via configured EWS/SMTP relay API.
    """

    subject = "DocIntel Verification Code"
    body = f"Your DocIntel verification code is: {code}"

    # Build final email API endpoint
    endpoint = settings.email_server_endpoint or "/send"
    base_url = settings.email_server_url.rstrip("/")
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base_url}{endpoint}"

    # DEVELOPMENT MODE: no email server configured
    if (
        not settings.email_sender_email
        or not settings.email_sender_password
        or not settings.email_sender_ews_url
    ):
        print(f"[DEV MODE] No email server configured. OTP for {email}: {code}")
        return

    # Clean EWS URL for payload
    clean_ews_url = settings.email_sender_ews_url.replace("http://", "").replace("https://", "")

    # Construct payload
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
                print(f"[Email Error] Response status: {res.status}, body: {decoded_body}")
                raise HTTPException(status_code=502, detail="Email server returned an error.")

            # Success
            print(f"[Email Sent] Verification email sent to {email}. Server response: {decoded_body}")
            return

    except error.HTTPError as e:
        print(f"[Email HTTPError] {e.code}: {e.reason}")
        raise HTTPException(status_code=502, detail="Email server returned a failure response.")

    except error.URLError as e:
        print(f"[Email URLError] {e.reason}")
        raise HTTPException(status_code=502, detail="Email server unreachable.")

    except Exception as ex:
        print(f"[Email Unknown Error] {ex}")
        raise HTTPException(status_code=500, detail="Unexpected email sending error.")

def request_email_code(email: str) -> None:
    normalized = _normalize_email(email)
    if not _is_valid_zetdc_email(normalized):
        raise HTTPException(status_code=400, detail="Invalid ZETDC email")
    code = f"{secrets.randbelow(1000000):06d}"
    _email_code_store[normalized] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }
    _send_email_code(normalized, code)


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


def create_session(user_id: int, display_name: str | None, provider: str, identity: str) -> str:
    token = secrets.token_urlsafe(32)
    _session_store[token] = {
        "user_id": int(user_id),
        "provider": provider,
        "identity": identity,
        "display_name": display_name,
        "created_at": datetime.utcnow().isoformat(),
    }
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = parts[1]
    user = _session_store.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def validate_token(token: str) -> Dict[str, Any] | None:
    return _session_store.get(token)


def revoke_token(token: str) -> bool:
    return _session_store.pop(token, None) is not None
