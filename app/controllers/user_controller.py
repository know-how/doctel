from fastapi import APIRouter, Depends
from app.services.history_service import get_chat_history
from app.services.summary_history_service import get_summary_history
from app.services.auth_service import get_current_user


router = APIRouter(tags=["Users"])


@router.get("/users/me/history")
async def get_user_history(user: dict = Depends(get_current_user)):
    ec_number = user["ec_number"]
    history = get_chat_history(ec_number)
    return {"ec_number": ec_number, "history": history}


@router.get("/users/me/summary-history")
async def get_user_summary_history(user: dict = Depends(get_current_user)):
    ec_number = user["ec_number"]
    history = get_summary_history(ec_number)
    return {"ec_number": ec_number, "history": history}
