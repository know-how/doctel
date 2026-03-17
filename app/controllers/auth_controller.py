from fastapi import APIRouter, Depends, HTTPException
from app.models import (
    LoginRequest,
    LoginResponse,
    EmailOtpRequest,
    EmailOtpVerifyRequest,
    EmailOtpRequestResponse,
)
from app.services.auth_service import (
    get_current_user,
    request_email_code,
    verify_email_code,
)


router = APIRouter(tags=["Authentication"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    raise HTTPException(status_code=404, detail="Use POST /auth/login on the main app")


@router.post("/auth/email/request", response_model=EmailOtpRequestResponse)
async def request_email_login(request: EmailOtpRequest) -> EmailOtpRequestResponse:
    request_email_code(request.email)
    return EmailOtpRequestResponse(message="Verification code sent")


@router.post("/auth/email/verify", response_model=LoginResponse)
async def verify_email_login(request: EmailOtpVerifyRequest) -> LoginResponse:
    raise HTTPException(status_code=404, detail="Use POST /auth/email/verify on the main app")


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user
