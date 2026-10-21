"""
StyleVision — Admin Router
Allows administrators to manage the MongoDB catalogue of virtual try-on style items.
"""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.catalogue import (
    CreateStyleItemRequest,
    UpdateStyleItemRequest,
    StyleItemResponse,
)
from app.utils.security import get_current_admin
from app.database import get_database
from app.routers.catalogue import _doc_to_response

router = APIRouter(prefix="/api/v1/admin", tags=["Administrator Management"], dependencies=[Depends(get_current_admin)])


@router.post(
    "/catalogue",
    response_model=StyleItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new style item to the catalogue",
)
async def create_catalogue_item(request: CreateStyleItemRequest):
    """Admin endpoint to add a new outfit, accessory, makeup, or hairstyle to MongoDB."""
    db = get_database()
    col = db["catalogue"]

    item_id = f"item-{request.category.value}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    item_doc = {
        "item_id": item_id,
        "name": request.name,
        "category": request.category.value,
        "subcategory": request.subcategory,
        "description": request.description,
        "thumbnail": None,
        "tags": request.tags or [],
        "color": request.color,
        "is_active": request.is_active,
        "created_at": now,
        "updated_at": now,
    }
    await col.insert_one(item_doc)
    return _doc_to_response(item_doc)


@router.put(
    "/catalogue/{item_id}",
    response_model=StyleItemResponse,
    summary="Update an existing style item",
)
async def update_catalogue_item(item_id: str, request: UpdateStyleItemRequest):
    """Admin endpoint to update style item details or toggle its active status."""
    db = get_database()
    col = db["catalogue"]

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    if request.name is not None:
        update_fields["name"] = request.name
    if request.description is not None:
        update_fields["description"] = request.description
    if request.tags is not None:
        update_fields["tags"] = request.tags
    if request.color is not None:
        update_fields["color"] = request.color
    if request.is_active is not None:
        update_fields["is_active"] = request.is_active

    result = await col.find_one_and_update(
        {"item_id": item_id},
        {"$set": update_fields},
        return_document=True,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Style item '{item_id}' not found.",
        )
    return _doc_to_response(result)


@router.delete(
    "/catalogue/{item_id}",
    summary="Remove a style item from the catalogue",
)
async def delete_catalogue_item(item_id: str):
    """Admin endpoint to permanently remove an item from MongoDB catalogue."""
    db = get_database()
    col = db["catalogue"]

    result = await col.delete_one({"item_id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Style item '{item_id}' not found.",
        )
    return {
        "message": f"Style item '{item_id}' successfully removed from catalogue.",
        "deleted_id": item_id,
    }
