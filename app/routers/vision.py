"""Vision / image analysis endpoint."""

import json

from fastapi import APIRouter

from app.routers.deps import (
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException,
    User,
    get_current_user,
    settings,
    uuid,
    analyze_image,
)

router = APIRouter(tags=["vision"])


@router.post("/api/vision/ask")
async def ask_vision(
    image: UploadFile = File(...),
    user_query: str = Form(...),
    user: User = Depends(get_current_user),
):
    temp_path = settings.uploads_dir / f"vision_{uuid.uuid4().hex}_{image.filename}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await image.read())
        result = await analyze_image(str(temp_path), user_query)
        return {"answer": result}
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
