"""
StyleVision — Catalogue & Style Item Pydantic Schemas
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class TryOnCategory(str, Enum):
    outfit = "outfit"
    accessories = "accessories"
    makeup = "makeup"
    hairstyle = "hairstyle"


class AccessorySubcategory(str, Enum):
    glasses = "glasses"
    earrings = "earrings"
    necklace = "necklace"
    bracelet = "bracelet"
    rings = "rings"
    nose_pin = "nose_pin"
    bags = "bags"


class MakeupSubcategory(str, Enum):
    lipstick = "lipstick"
    eyeshadow = "eyeshadow"
    blush = "blush"
    foundation = "foundation"


# ── Request Bodies ────────────────────────────────────────────────────────────

class CreateStyleItemRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    category: TryOnCategory
    subcategory: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(default_factory=list)
    color: Optional[str] = Field(None, max_length=50)
    is_active: bool = True


class UpdateStyleItemRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    color: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


# ── Response Payloads ─────────────────────────────────────────────────────────

class StyleItemResponse(BaseModel):
    item_id: str
    name: str
    category: TryOnCategory
    subcategory: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None     # URL to catalogue image
    tags: List[str] = []
    color: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class CatalogueListResponse(BaseModel):
    items: List[StyleItemResponse]
    total: int
    category: Optional[TryOnCategory] = None
