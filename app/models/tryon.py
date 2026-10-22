"""
StyleVision — Try-On Request / Response Pydantic Schemas
Covers outfit (CatVTON), accessories, makeup, and hairstyle.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class TryOnStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TryOnMode(str, Enum):
    prototype = "prototype"   # CPU overlay — clearly labelled
    catvton = "catvton"       # Real GPU diffusion inference
    replicate = "replicate"   # Serverless Cloud SOTA Diffusion (IDM-VTON)


# ── Outfit Try-On ─────────────────────────────────────────────────────────────

class OutfitTryOnRequest(BaseModel):
    person_image_id: str = Field(..., description="ID or URL of the person photograph")
    style_item_id: Optional[str] = Field(None, description="Catalogue item ID if choosing from catalogue")
    outfit_id: Optional[str] = Field(None, description="Wardrobe outfit ID if choosing from user's closet")
    source: str = Field("catalogue", description="'wardrobe' | 'catalogue'")
    category: Optional[str] = Field(None, description="'top' | 'bottom' | 'overall' | 'outerwear'")
    cloth_type: Optional[str] = Field(None, description="Explicit cloth type: 'upper' | 'lower' | 'overall'")


class OutfitTryOnResponse(BaseModel):
    tryon_id: str
    status: TryOnStatus
    mode: TryOnMode
    source: str = "catalogue"
    parent_image_id: Optional[str] = None
    result_image_id: Optional[str] = None
    original_image_url: str
    garment_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    processing_note: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


# ── Accessory Try-On ──────────────────────────────────────────────────────────

class AccessoryTryOnRequest(BaseModel):
    person_image_id: str
    style_item_id: str
    subcategory: str = Field(..., description="e.g. glasses, earrings, necklace, nose_pin")
    custom_image_url: Optional[str] = Field(None, description="Custom uploaded accessory image URL or path")
    position_x: Optional[float] = Field(None, description="Manual X offset override (0-1 normalised)")
    position_y: Optional[float] = Field(None, description="Manual Y offset override (0-1 normalised)")
    scale: Optional[float] = Field(None, ge=0.1, le=5.0, description="Manual scale override")
    offset_x: Optional[float] = Field(None, description="Manual X offset in pixels")
    offset_y: Optional[float] = Field(None, description="Manual Y offset in pixels")


class AccessoryTryOnResponse(BaseModel):
    tryon_id: str
    status: TryOnStatus
    subcategory: str
    landmark_used: Optional[str] = None    # e.g. "Eye Bridge #168"
    parent_image_id: Optional[str] = None
    result_image_id: Optional[str] = None
    original_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    tilted_image_url: Optional[str] = None
    depth_map_url: Optional[str] = None
    closeup_original_image_url: Optional[str] = None
    closeup_result_image_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


# ── Makeup Try-On ─────────────────────────────────────────────────────────────

class MakeupTryOnRequest(BaseModel):
    person_image_id: str
    reference_image_id: Optional[str] = Field(None, description="Catalogue reference look ID (e.g. item-mu-look-1)")
    custom_reference_image_url: Optional[str] = Field(None, description="Custom uploaded reference makeup photo URL")
    makeup_type: Optional[str] = Field("full_transfer", description="full_transfer | lipstick | eyeshadow | blush")
    color_hex: Optional[str] = Field(None, description="Optional hex color override")
    intensity: float = Field(0.7, ge=0.0, le=1.0)
    finish: str = Field("satin", description="matte | satin | glossy")


class MakeupTryOnResponse(BaseModel):
    tryon_id: str
    status: TryOnStatus
    makeup_type: str = "full_transfer"
    style_name: Optional[str] = "Complete Reference Makeup Transfer"
    reference_image_url: Optional[str] = None
    parent_image_id: Optional[str] = None
    result_image_id: Optional[str] = None
    original_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    tilted_image_url: Optional[str] = None
    depth_map_url: Optional[str] = None
    closeup_original_image_url: Optional[str] = None
    closeup_result_image_url: Optional[str] = None
    color_hex: Optional[str] = None
    intensity: float = 0.7
    finish: str = "satin"
    error: Optional[str] = None
    created_at: datetime


# ── Hairstyle Try-On ──────────────────────────────────────────────────────────

class HairstyleTryOnRequest(BaseModel):
    person_image_id: str
    style_item_id: str
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    offset_x: Optional[float] = Field(None, description="Manual X offset in pixels")
    offset_y: Optional[float] = Field(None, description="Manual Y offset in pixels")
    scale: Optional[float] = Field(None, ge=0.5, le=2.0, description="Manual scale multiplier")


class HairstyleTryOnResponse(BaseModel):
    tryon_id: str
    status: TryOnStatus
    style_name: str
    color_hex: Optional[str] = None
    parent_image_id: Optional[str] = None
    result_image_id: Optional[str] = None
    original_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    tilted_image_url: Optional[str] = None
    depth_map_url: Optional[str] = None
    closeup_original_image_url: Optional[str] = None
    closeup_result_image_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


# ── Generic Try-On Error ──────────────────────────────────────────────────────

class TryOnErrorResponse(BaseModel):
    error: str
    code: str
    detail: Optional[str] = None


# ── Remove Applied Item ───────────────────────────────────────────────────────

class RemoveItemRequest(BaseModel):
    person_image_id: str = Field(..., description="Current tip image id of the styling session")
    stage: str = Field(..., description="Stage of the item to remove: outfit | accessories | makeup | hairstyle")
    slot_value: Optional[str] = Field(
        None,
        description="Slot to remove, e.g. accessory subcategory (glasses) or makeup type (lipstick). "
                    "Omit for outfit/hairstyle (single-slot stages).",
    )


class RemoveItemResponse(BaseModel):
    status: TryOnStatus
    removed_stage: str
    removed_slot: Optional[str] = None
    result_image_id: Optional[str] = None
    result_image_url: Optional[str] = None
    current_image_id: Optional[str] = None
    remaining_items: List[dict] = []
    error: Optional[str] = None
