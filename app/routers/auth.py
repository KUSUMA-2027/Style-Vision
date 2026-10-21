"""
StyleVision — Authentication Router
Endpoints for user registration, login, and token identity backed by MongoDB.
"""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from pymongo.errors import DuplicateKeyError

from app.models.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserPublic,
    AuthTokenResponse,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.config import get_settings
from app.database import get_database

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register_user(request: UserRegisterRequest):
    """
    Register a new user document in MongoDB:
    - Enforces unique email check via unique index
    - Hashes password with bcrypt
    - Never stores or logs plain-text passwords
    - Returns signed JWT access token and safe UserPublic profile
    """
    db = get_database()
    users_col = db["users"]
    email_key = request.email.lower()

    existing = await users_col.find_one({"email": email_key})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    user_id = f"usr-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    user_doc = {
        "user_id": user_id,
        "name": request.name,
        "email": email_key,
        "password_hash": hash_password(request.password),
        "profile_photo": None,
        "is_admin": False,
        "created_at": now,
    }

    try:
        await users_col.insert_one(user_doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    access_token = create_access_token(
        user_id=user_id,
        email=email_key,
        is_admin=False,
    )

    user_public = UserPublic(
        user_id=user_id,
        name=request.name,
        email=email_key,
        profile_photo=None,
        created_at=now,
        is_admin=False,
    )

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=user_public,
    )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="Sign in to obtain access token",
)
async def login_user(request: UserLoginRequest):
    """
    Authenticate against MongoDB:
    - Look up user document by lowercase email
    - Verify plain password against stored bcrypt hash
    - Returns signed JWT on success, 401 on bad credentials
    """
    db = get_database()
    users_col = db["users"]
    email_key = request.email.lower()

    user_doc = await users_col.find_one({"email": email_key})
    if not user_doc or not verify_password(request.password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user_doc["user_id"],
        email=email_key,
        is_admin=user_doc.get("is_admin", False),
    )

    user_public = UserPublic(
        user_id=user_doc["user_id"],
        name=user_doc["name"],
        email=user_doc["email"],
        profile_photo=user_doc.get("profile_photo"),
        created_at=user_doc["created_at"],
        is_admin=user_doc.get("is_admin", False),
    )

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=user_public,
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Retrieve user record from MongoDB based on JWT token sub (user_id)."""
    db = get_database()
    users_col = db["users"]
    user_id = current_user.get("sub")

    user_doc = await users_col.find_one({"user_id": user_id})
    if not user_doc:
        # Try finding by email if sub didn't match
        email = current_user.get("email")
        if email:
            user_doc = await users_col.find_one({"email": email})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    return UserPublic(
        user_id=user_doc["user_id"],
        name=user_doc["name"],
        email=user_doc["email"],
        profile_photo=user_doc.get("profile_photo"),
        created_at=user_doc["created_at"],
        is_admin=user_doc.get("is_admin", False),
    )
