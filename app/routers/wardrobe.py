"""
StyleVision — Wardrobe Router ("My Digital Closet")
Allows users to upload photos of their own clothes/dresses, view their private
wardrobe collection, and delete garments. Backed by MongoDB 'outfits' collection.
"""
from datetime import datetime, timezone
import io
import os
import uuid
from typing import Optional
from PIL import Image
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status

from app.models.outfit import (
    WardrobeCategory,
    WardrobeItemResponse,
    WardrobeListResponse,
    WardrobeItemDeleteResponse,
)
from app.utils.file_utils import (
    validate_and_read_upload,
    generate_safe_filename,
    save_upload_to_disk,
    delete_file_safe,
)
from app.utils.security import get_current_user
from app.config import get_settings
from app.database import get_database

router = APIRouter(prefix="/api/v1/wardrobe", tags=["Digital Wardrobe"])
settings = get_settings()

WARDROBE_DIR = os.path.join(settings.upload_dir, "wardrobe")


@router.post(
    "/upload",
    response_model=WardrobeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a photo of your own dress to your digital wardrobe",
)
async def upload_wardrobe_dress(
    file: UploadFile = File(...),
    name: str = Form("My Garment"),
    category: WardrobeCategory = Form(WardrobeCategory.top),
    color: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    User photographs a dress from their own closet:
    - Validates image file type, size, and readability
    - Saves image safely in /uploads/wardrobe/
    - Stores metadata in MongoDB 'outfits' collection tied to the authenticated user
    """
    user_id = current_user["sub"]
    os.makedirs(WARDROBE_DIR, exist_ok=True)
    raw_bytes, extension = await validate_and_read_upload(file)

    # Verify and extract dimensions
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            width, height = img.size
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read garment image: {exc}",
        ) from exc

    if width < 150 or height < 150:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garment image is too small. Please take a clearer photo of your clothing item.",
        )

    outfit_id = f"outfit-{uuid.uuid4().hex[:10]}"
    safe_filename = generate_safe_filename(
        user_id=user_id,
        prefix="garment",
        extension=extension,
    )

    save_upload_to_disk(
        raw_bytes=raw_bytes,
        directory=WARDROBE_DIR,
        filename=safe_filename,
    )

    image_url = f"/uploads/wardrobe/{safe_filename}"
    now = datetime.now(timezone.utc)

    db = get_database()
    col = db["outfits"]

    doc = {
        "outfit_id": outfit_id,
        "user_id": user_id,
        "name": name.strip(),
        "category": category.value,
        "outfit_image": image_url,
        "color": color or "#7C4DFF",
        "uploaded_at": now,
        "try_on_result": None,
    }
    await col.insert_one(doc)

    return WardrobeItemResponse(
        outfit_id=doc["outfit_id"],
        user_id=doc["user_id"],
        name=doc["name"],
        category=WardrobeCategory(doc["category"]),
        outfit_image=doc["outfit_image"],
        uploaded_at=doc["uploaded_at"],
        try_on_result=doc.get("try_on_result"),
        color=doc.get("color"),
    )


@router.get(
    "",
    response_model=WardrobeListResponse,
    summary="List user's digital wardrobe items",
)
async def list_wardrobe_items(current_user: dict = Depends(get_current_user)):
    """Retrieve the authenticated user's clothing items from MongoDB."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["outfits"]

    cursor = col.find({"user_id": user_id}).sort("uploaded_at", -1)
    results = []
    async for doc in cursor:
        results.append(
            WardrobeItemResponse(
                outfit_id=doc["outfit_id"],
                user_id=doc.get("user_id", user_id),
                name=doc["name"],
                category=WardrobeCategory(doc["category"]),
                outfit_image=doc["outfit_image"],
                uploaded_at=doc["uploaded_at"],
                try_on_result=doc.get("try_on_result"),
                color=doc.get("color"),
            )
        )

    return WardrobeListResponse(items=results, total=len(results))


@router.delete(
    "/{outfit_id}",
    response_model=WardrobeItemDeleteResponse,
    summary="Delete a clothing item from wardrobe",
)
async def delete_wardrobe_item(outfit_id: str, current_user: dict = Depends(get_current_user)):
    """Delete the authenticated user's garment from MongoDB and remove file from disk."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["outfits"]

    doc = await col.find_one({"outfit_id": outfit_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Garment '{outfit_id}' not found in your wardrobe.",
        )

    # Clean up file on disk if local
    image_rel = doc.get("outfit_image", "").lstrip("/")
    if image_rel.startswith("uploads"):
        delete_file_safe(image_rel)

    await col.delete_one({"outfit_id": outfit_id})

    return WardrobeItemDeleteResponse(
        message="Garment successfully removed from your digital wardrobe.",
        deleted_id=outfit_id,
    )
