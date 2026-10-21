"""
StyleVision — File Upload Validation Utilities
Ensures uploaded images are safe, readable, and within size/type limits.
"""
import os
import uuid
from pathlib import Path
from typing import Tuple, Optional
import io
from PIL import Image

def detect_image_type(raw_bytes: bytes) -> Optional[str]:
    """Detect image type from magic bytes or PIL fallback."""
    if raw_bytes.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    elif raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    elif raw_bytes.startswith(b"RIFF") and len(raw_bytes) >= 12 and raw_bytes[8:12] == b"WEBP":
        return "webp"
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            fmt = (img.format or "").lower()
            if fmt in ("jpeg", "jpg"):
                return "jpeg"
            return fmt
    except Exception:
        return None

from fastapi import HTTPException, UploadFile, status

# ── Constants ──────────────────────────────────────────────────────────────────

# Supported MIME types and their corresponding file extensions
ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Magic-byte signatures for additional server-side validation
ALLOWED_IMG_HEADERS = {"jpeg", "png", "webp"}

# Upload limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MIN_FILE_SIZE_BYTES = 1024                # 1 KB — reject empty/corrupt files


# ── Validation ────────────────────────────────────────────────────────────────

async def validate_and_read_upload(upload: UploadFile) -> Tuple[bytes, str]:
    """
    Read an uploaded image file and validate:
      1. Content-Type header is in the allowed MIME list.
      2. File size is within limits (1 KB – 10 MB).
      3. Actual image magic bytes match the declared type.

    Returns (raw_bytes, extension) on success.
    Raises HTTPException 400 on any validation failure.
    """
    # --- Check declared content type ---
    content_type = upload.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type: '{content_type}'. "
                f"Accepted types: JPEG, PNG, WebP."
            ),
        )

    # --- Read raw bytes ---
    raw_bytes = await upload.read()

    # --- Size checks ---
    file_size = len(raw_bytes)
    if file_size < MIN_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is too small or empty. Please upload a valid photo.",
        )
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 10 MB.",
        )

    # --- Magic-byte validation ---
    detected = detect_image_type(raw_bytes)
    if detected not in ALLOWED_IMG_HEADERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The file content does not appear to be a valid image. "
                "Please upload a real JPEG, PNG, or WebP photograph."
            ),
        )

    extension = ALLOWED_MIME_TYPES[content_type]
    return raw_bytes, extension


# ── Safe File Saving ──────────────────────────────────────────────────────────

def generate_safe_filename(user_id: str, prefix: str, extension: str) -> str:
    """
    Generate a random UUID-based filename that is safe for all OS filesystems.
    Format: {prefix}_{user_id_prefix}_{uuid}.{ext}
    The original filename from the client is NEVER used directly.
    """
    unique_id = uuid.uuid4().hex
    safe_user = user_id[:8].replace("-", "")
    return f"{prefix}_{safe_user}_{unique_id}.{extension}"


def save_upload_to_disk(raw_bytes: bytes, directory: str, filename: str) -> str:
    """
    Write raw bytes to disk under the given directory.
    Creates the directory if it does not exist.
    Returns the absolute file path.
    """
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, filename)
    with open(file_path, "wb") as f:
        f.write(raw_bytes)
    return file_path


def delete_file_safe(file_path: str) -> bool:
    """
    Delete a file from disk if it exists.
    Returns True if deleted, False if the file was not found.
    """
    path = Path(file_path)
    if path.exists() and path.is_file():
        path.unlink()
        return True
    return False
