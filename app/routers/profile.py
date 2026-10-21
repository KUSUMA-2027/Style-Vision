"""
StyleVision — User Profile & Settings Router
Provides endpoints for retrieving and updating the authenticated user's profile.
JWT-protected; all data is scoped to the token's user.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models.user import UpdateProfileRequest
from app.utils.security import get_current_user
from app.database import get_database

router = APIRouter(prefix="/api/v1/profile", tags=["User Profile"])


class FullProfileResponse(BaseModel):
    user_id: str
    name: str
    email: str
    profile_photo: Optional[str] = None
    created_at: datetime
    saved_looks_count: int
    tryons_count: int


async def _load_full_profile(user_id: str) -> FullProfileResponse:
    db = get_database()
    users_col = db["users"]
    looks_col = db["saved_looks"]
    tryons_col = db["tryons"]

    user_doc = await users_col.find_one({"user_id": user_id})
    if not user_doc:
        raise LookupError("User account not found.")

    saved_count = await looks_col.count_documents({"user_id": user_id})
    tryons_count = await tryons_col.count_documents({"user_id": user_id})

    return FullProfileResponse(
        user_id=user_doc["user_id"],
        name=user_doc.get("name", "User"),
        email=user_doc.get("email", ""),
        profile_photo=user_doc.get("profile_photo"),
        created_at=user_doc.get("created_at", datetime.now(timezone.utc)),
        saved_looks_count=saved_count,
        tryons_count=tryons_count,
    )


@router.get(
    "",
    response_model=FullProfileResponse,
    summary="Get user profile and statistics",
)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Retrieve the authenticated user's profile and live try-on metrics from MongoDB."""
    try:
        return await _load_full_profile(current_user["sub"])
    except LookupError as exc:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "",
    response_model=FullProfileResponse,
    summary="Update user profile",
)
async def update_profile(request: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    """Update the authenticated user's profile name and personal details in MongoDB."""
    db = get_database()
    users_col = db["users"]

    if request.name:
        await users_col.update_one(
            {"user_id": current_user["sub"]},
            {"$set": {"name": request.name}},
        )

    try:
        return await _load_full_profile(current_user["sub"])
    except LookupError as exc:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(exc))
