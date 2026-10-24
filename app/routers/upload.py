"""
StyleVision — Photo Upload Router
Handles secure multipart image uploads with validation, image suitability checks,
safe storage, and MongoDB tracking. JWT-protected and user-scoped.
"""
from datetime import datetime, timezone
import io
from typing import Optional
from PIL import Image
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status

from app.models.history import UploadedImageResponse
from app.utils.file_utils import (
    validate_and_read_upload,
    generate_safe_filename,
    save_upload_to_disk,
)
from app.utils.security import get_current_user
from app.services.image_registry import register_original_image
from app.config import get_settings
from app.database import get_database

router = APIRouter(prefix="/api/v1/upload", tags=["Photo Upload"])
settings = get_settings()

MIN_DIMENSION_PX = 256
RECOMMENDED_DIMENSION_PX = 512


@router.post(
    "/photo",
    response_model=UploadedImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a person photograph",
)
async def upload_photo(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    Upload a user portrait photograph for virtual try-on:
    - Validates file type (JPEG, PNG, WebP), size, real image data, and suitability
    - Saves with a safe randomized UUID filename
    - Records upload metadata in MongoDB AND registers it in the unified image
      registry (kind='original') as the base of the styling session chain
    - Returns URL, dimensions, and suitability analysis
    """
    user_id = current_user["sub"]
    raw_bytes, extension = await validate_and_read_upload(file)

    # Read, orient, and inspect image using Pillow
    try:
        from PIL import ImageOps
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Auto-orient based on EXIF camera tag
            img = ImageOps.exif_transpose(img) or img
            width, height = img.size
            format_name = img.format or extension.upper()

            # Downscale if excessively large (> 1600px on longest edge)
            # This makes all try-on pipelines and mobile display significantly faster
            if max(width, height) > 1600:
                scale = 1600.0 / max(width, height)
                new_w, new_h = max(256, int(width * scale)), max(256, int(height * scale))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                width, height = new_w, new_h
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
                raw_bytes = buf.getvalue()
                extension = "jpg"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image decoding failed: {exc}",
        ) from exc

    # Resolution suitability validation
    if width < MIN_DIMENSION_PX or height < MIN_DIMENSION_PX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Image resolution too low ({width}x{height} px). "
                f"A minimum of {MIN_DIMENSION_PX}x{MIN_DIMENSION_PX} pixels is required "
                f"for accurate landmark alignment and clothing fitting."
            ),
        )

    # Aspect ratio check
    ratio = width / height
    if ratio < 0.35 or ratio > 2.8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image proportions (aspect ratio {ratio:.2f}). "
                "Please upload a standard portrait or upper-body photograph."
            ),
        )

    # Quality classification
    if width >= RECOMMENDED_DIMENSION_PX and height >= RECOMMENDED_DIMENSION_PX:
        quality_score = "high"
        suitability_note = f"High-resolution {format_name} portrait ({width}x{height} px) suitable for all AI studios."
    else:
        quality_score = "medium"
        suitability_note = f"Standard resolution ({width}x{height} px) detected. Suitable for prototype styling."

    # Generate safe random filename
    safe_filename = generate_safe_filename(
        user_id=user_id,
        prefix="person",
        extension=extension,
    )

    # Save to uploads directory
    save_upload_to_disk(
        raw_bytes=raw_bytes,
        directory=settings.upload_dir,
        filename=safe_filename,
    )

    image_id = f"img-{safe_filename.split('.')[0]}"
    image_url = f"/uploads/{safe_filename}"
    now = datetime.now(timezone.utc)

    # Persist record in MongoDB
    db = get_database()
    upload_doc = {
        "image_id": image_id,
        "user_id": user_id,
        "filename": safe_filename,
        "size_bytes": len(raw_bytes),
        "width": width,
        "height": height,
        "url": image_url,
        "quality_score": quality_score,
        "suitability_note": suitability_note,
        "uploaded_at": now,
    }
    await db["uploads"].insert_one(upload_doc)

    # Register in unified image registry as the styling session base
    try:
        await register_original_image(
            user_id=user_id,
            image_id=image_id,
            filename=safe_filename,
            url=image_url,
            width=width,
            height=height,
            size_bytes=len(raw_bytes),
            quality_score=quality_score,
        )
    except Exception as reg_err:
        # Non-fatal: legacy resolution still works
        print(f"[StyleVision Upload] Registry registration skipped: {reg_err}")

    return UploadedImageResponse(
        image_id=image_id,
        filename=safe_filename,
        size_bytes=len(raw_bytes),
        width=width,
        height=height,
        url=image_url,
        uploaded_at=now,
        quality_score=quality_score,
        suitability_note=suitability_note,
    )


@router.get(
    "/latest",
    response_model=Optional[UploadedImageResponse],
    summary="Get user's most recent uploaded portrait",
)
async def get_latest_upload(current_user: dict = Depends(get_current_user)):
    """Retrieve metadata of the current user's most recent portrait upload (user-scoped)."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["uploads"]
    doc = await col.find_one({"user_id": user_id}, sort=[("uploaded_at", -1)])

    # Fallback to unified registry (covers portraits registered after a restart or import)
    if not doc:
        reg_doc = await db["images"].find_one(
            {"user_id": user_id, "kind": "original"}, sort=[("created_at", -1)]
        )
        if reg_doc:
            doc = {
                "image_id": reg_doc.get("image_id"),
                "filename": reg_doc.get("filename"),
                "size_bytes": reg_doc.get("size_bytes", 0),
                "width": reg_doc.get("width"),
                "height": reg_doc.get("height"),
                "url": reg_doc.get("url"),
                "uploaded_at": reg_doc.get("created_at"),
                "quality_score": reg_doc.get("quality_score", "good"),
            }

    if not doc:
        return None
    return UploadedImageResponse(
        image_id=doc["image_id"],
        filename=doc.get("filename", ""),
        size_bytes=doc.get("size_bytes", 0),
        width=doc.get("width"),
        height=doc.get("height"),
        url=doc["url"],
        uploaded_at=doc.get("uploaded_at", datetime.now(timezone.utc)),
        quality_score=doc.get("quality_score", "good"),
        suitability_note=doc.get("suitability_note"),
    )


@router.delete(
    "/reset",
    summary="Undo everything: delete user's uploaded portrait and all styling session history",
)
async def reset_user_portrait_and_session(current_user: dict = Depends(get_current_user)):
    """
    Completely deletes the user's active portrait, registered images, and active try-on session.
    Allows user to start completely fresh with zero lingering portrait or styling state.
    """
    user_id = current_user["sub"]
    db = get_database()

    # 1. Delete user uploads
    await db["uploads"].delete_many({"user_id": user_id})

    # 2. Delete unified image registry records
    await db["images"].delete_many({"user_id": user_id})

    # 3. Clean active try-on jobs (keep saved looks in 'looks' collection safe in lookbook)
    await db["tryons"].delete_many({"user_id": user_id})
    await db["tryon_jobs"].delete_many({"user_id": user_id})

    return {"status": "ok", "message": "All portrait and session data deleted successfully."}
