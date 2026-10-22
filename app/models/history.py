"""
StyleVision — Upload & Saved Look Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.catalogue import TryOnCategory


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadedImageResponse(BaseModel):
    image_id: str
    filename: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    url: str
    uploaded_at: datetime
    suitability_note: Optional[str] = None
    quality_score: Optional[str] = "good"


# ── Saved Looks / History ──────────────────────────────────────────────────────

class SaveLookRequest(BaseModel):
    tryon_id: str = Field(..., description="ID of a completed try-on result")
    title: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, description="Optional category: outfit | accessories | makeup | hairstyle | complete")
    base_image_id: Optional[str] = Field(None, description="Original portrait that seeded the styling session")
    final_image_id: Optional[str] = Field(None, description="Latest chained image id of the complete look")
    stages: Optional[List[dict]] = Field(None, description="Per-stage metadata: [{stage, tryon_id, result_image_url, ...}]")


class UpdateLookRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)


class SavedLookResponse(BaseModel):
    look_id: str
    user_id: str
    title: str
    category: TryOnCategory
    original_image_url: str
    result_image_url: str
    style_item_name: str
    base_image_id: Optional[str] = None
    final_image_id: Optional[str] = None
    stages: List[dict] = []
    created_at: datetime


class HistoryListResponse(BaseModel):
    looks: List[SavedLookResponse]
    total: int


class DeleteResponse(BaseModel):
    message: str
    deleted_id: str
