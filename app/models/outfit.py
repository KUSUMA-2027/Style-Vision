"""
StyleVision — Outfit & Wardrobe Pydantic Schemas
Directly implements the OUTFIT entity from the PPT specification:
- outfit_id
- user_id
- outfit_image
- uploaded_at
- try_on_result
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class WardrobeCategory(str, Enum):
    top = "top"
    bottom = "bottom"
    overall = "overall"
    outerwear = "outerwear"

    @classmethod
    def _missing_(cls, value):
        val = str(value).lower()
        if val in ("dress", "ethnic", "suit", "traditional", "gown", "other"):
            return cls.overall
        if val in ("upper", "shirt", "kurti", "t-shirt", "tee", "blouse", "tops"):
            return cls.top
        if val in ("lower", "pant", "pants", "jeans", "skirt", "trouser", "shorts", "bottoms"):
            return cls.bottom
        if val in ("jacket", "coat", "blazer", "hoodie", "sweater"):
            return cls.outerwear
        return cls.top


# ── Response for User's Uploaded Garment ───────────────────────────────────────

class WardrobeItemResponse(BaseModel):
    outfit_id: str
    user_id: str
    name: str
    category: WardrobeCategory
    outfit_image: str             # URL / path to user's uploaded dress
    uploaded_at: datetime
    try_on_result: Optional[str] = None
    color: Optional[str] = None
    notes: Optional[str] = None


class WardrobeListResponse(BaseModel):
    items: List[WardrobeItemResponse]
    total: int


class WardrobeItemDeleteResponse(BaseModel):
    message: str
    deleted_id: str
