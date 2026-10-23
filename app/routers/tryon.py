"""
StyleVision — Try-On Router
Handles virtual try-on pipelines for clothing, accessories, makeup, and hairstyles.
Implements the client's critical requirements:
- STAGE CHAINING: every stage resolves the latest generated image (previous stage
  result) via the unified image registry instead of repeatedly using the original photo.
- PERSISTENCE: try-on job records are stored in MongoDB (survive restarts).
- HONEST ERRORS: processing failures return status="failed" with the reason —
  never a fake completed result.
- AUTH: every endpoint is JWT-protected and strictly user-scoped.
"""
from datetime import datetime, timezone
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.tryon import (
    TryOnStatus,
    TryOnMode,
    OutfitTryOnRequest,
    OutfitTryOnResponse,
    AccessoryTryOnRequest,
    AccessoryTryOnResponse,
    MakeupTryOnRequest,
    MakeupTryOnResponse,
    HairstyleTryOnRequest,
    HairstyleTryOnResponse,
    RemoveItemRequest,
    RemoveItemResponse,
)
from app.config import get_settings
from app.utils.security import get_current_user
from app.services.tryon_service import (
    synthesize_outfit_tryon,
    resolve_person_image_for_user,
    _get_or_create_person_image,
    generate_depth_variants,
)
from app.services.image_registry import (
    _disk_path_from_url,
    register_stage_result,
    get_chain,
    get_session_stages,
    resolve_stage_replay,
    load_image_from_doc,
    user_has_portrait,
    get_live_items,
    STAGE_ORDER,
)
from app.services.stage_replay import (
    ops_from_docs,
    rebuild_and_register_chain,
)
from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tryon", tags=["Virtual Try-On"])
settings = get_settings()

PORTRAIT_REQUIRED_DETAIL = (
    "No portrait photo found for your account. Please upload your photo first — "
    "styles can only be applied to your own picture."
)


async def _enforce_portrait(user_id: str) -> None:
    """Reject styling requests from users who have not uploaded a portrait."""
    if not await user_has_portrait(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=PORTRAIT_REQUIRED_DETAIL,
        )


# ── Try-on job persistence (Mongo) ────────────────────────────────────────────

async def _save_job(record: dict) -> None:
    try:
        db = get_database()
        await db["tryons"].update_one(
            {"tryon_id": record["tryon_id"]}, {"$set": record}, upsert=True
        )
    except Exception as exc:
        logger.warning("[TryOn] Failed to persist job record: %s", exc)


async def _get_job(tryon_id: str, user_id: str) -> Optional[dict]:
    db = get_database()
    return await db["tryons"].find_one({"tryon_id": tryon_id, "user_id": user_id})


def _result_image_id_from_url(result_url: Optional[str]) -> Optional[str]:
    if not result_url:
        return None
    import os as _os
    stem = _os.path.splitext(_os.path.basename(result_url))[0]
    return stem or None


# ── Outfit ────────────────────────────────────────────────────────────────────

@router.post(
    "/outfit",
    response_model=OutfitTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Run clothing virtual try-on (chains from the latest generated image)",
)
async def tryon_outfit(request: OutfitTryOnRequest, current_user: dict = Depends(get_current_user)):
    """
    Synthesize clothing try-on onto the user's latest styled image.
    Supports garments from both the Digital Wardrobe ('wardrobe') and Catalogue ('catalogue').
    REPLACEMENT-AWARE: a new outfit REPLACES the previous outfit while
    re-applying (replaying) all preserved accessory/makeup/hairstyle stages on top.
    """
    user_id = current_user["sub"]
    await _enforce_portrait(user_id)
    db = get_database()
    garment_id = request.outfit_id if request.source == "wardrobe" else request.style_item_id
    if not garment_id:
        garment_id = request.style_item_id or request.outfit_id or "item-outfit-1"

    garment_color = None
    garment_name = None
    garment_image_path = None
    garment_category = request.category

    try:
        if request.source == "wardrobe":
            doc = await db["outfits"].find_one({"outfit_id": garment_id, "user_id": user_id})
            if doc:
                garment_color = doc.get("color")
                garment_name = doc.get("name")
                garment_image_path = doc.get("outfit_image")
                if not garment_category:
                    garment_category = doc.get("category")
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Garment not found in your wardrobe.",
                )
        else:
            doc = await db["catalogue"].find_one({"item_id": garment_id})
            if doc:
                garment_color = doc.get("color")
                garment_name = doc.get("name")
                garment_image_path = doc.get("thumbnail")
                if not garment_category:
                    garment_category = doc.get("subcategory") or doc.get("category")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("[Outfit] DB lookup skipped: %s", exc)

    # Replacement-aware source resolution (one outfit at a time)
    person_img = None
    source_url: Optional[str] = None
    source_doc_id: Optional[str] = None
    replay_docs: list = []
    dropped = False
    try:
        source_doc, replay_docs, dropped = await resolve_stage_replay(
            user_id, request.person_image_id, stage="outfit", replace_all=True,
        )
        if source_doc is not None:
            person_img, source_url = load_image_from_doc(source_doc)
            source_doc_id = source_doc.get("image_id")
    except Exception as exc:
        logger.warning("[Outfit] replay resolution failed: %s", exc)

    if dropped and person_img is not None:
        # Rebuild: new outfit first, then replay preserved stages on top.
        # Every rebuilt layer is registered as its own chain doc so removals
        # and future replacements keep working.
        tryon_id = f"tryon-outfit-{uuid.uuid4().hex[:10]}"
        ops = [{"stage": "outfit", "params": {
            "garment_id": garment_id,
            "source": request.source,
            "cloth_type": request.cloth_type,
            "garment_name": garment_name,
        }}]
        ops.extend(ops_from_docs(replay_docs))
        final_img, final_id, result_url = await rebuild_and_register_chain(
            user_id, source_doc, ops, final_image_id=tryon_id,
        )
        if final_img is None or not result_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Outfit rebuild failed — could not reconstruct your look.",
            )
        now = datetime.now(timezone.utc)
        from app.config import get_settings as _get_settings
        _st = _get_settings()
        _mode = TryOnMode.catvton if _st.tryon_mode == "catvton" else TryOnMode.prototype
        result = {
            "tryon_id": tryon_id,
            "status": TryOnStatus.completed,
            "mode": _mode,
            "source": request.source,
            "parent_image_id": source_doc_id or request.person_image_id,
            "result_image_id": final_id or tryon_id,
            "original_image_url": source_url or "",
            "garment_image_url": None,
            "result_image_url": result_url,
            "processing_note": f"Rebuilt look: new outfit applied, {len(replay_docs)} preserved stage(s) replayed.",
            "created_at": now,
        }
        await _save_job({**result, "user_id": user_id, "garment_name": garment_name})
        return OutfitTryOnResponse(**result)

    result = await synthesize_outfit_tryon(
        person_image_id=request.person_image_id,
        garment_id=garment_id,
        source=request.source,
        garment_color=garment_color,
        garment_name=garment_name,
        garment_image_path=garment_image_path,
        garment_category=garment_category,
        explicit_cloth_type=request.cloth_type,
        user_id=user_id,
    )

    # Auto-generate depth tilt variant for the result
    tilted_url = None
    depth_url = None
    effective_image_id = result.get("result_image_id") or result.get("tryon_id")
    effective_tryon_id = result.get("tryon_id")
    if result.get("status") == TryOnStatus.completed and result.get("result_image_url"):
        result_path = _disk_path_from_url(result.get("result_image_url"))
        if result_path and os.path.isfile(result_path):
            tilted_url, depth_url = await generate_depth_variants(
                result_image_path=result_path,
                user_id=user_id,
                image_id=effective_image_id,
                tryon_id=effective_tryon_id,
            )

    job_record = {
        **result,
        "user_id": user_id,
        "garment_name": garment_name,
        "tilted_image_url": tilted_url,
        "depth_map_url": depth_url,
    }
    await _save_job(job_record)
    return OutfitTryOnResponse(**job_record)


# ── Accessories ───────────────────────────────────────────────────────────────

from app.services.accessory_service import synthesize_accessory_tryon


@router.post(
    "/accessories",
    response_model=AccessoryTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Fit accessory or jewelry using MediaPipe facial/pose landmarks",
)
async def tryon_accessory(request: AccessoryTryOnRequest, current_user: dict = Depends(get_current_user)):
    """
    Anchor accessory to face or body using computer vision landmarks.
    REPLACEMENT-AWARE: applying an accessory of a subcategory already present
    in the chain REPLACES it (old one stripped) while all other accessories and
    earlier styling are preserved via replay.
    """
    user_id = current_user["sub"]
    await _enforce_portrait(user_id)

    custom_url = request.custom_image_url
    if not custom_url:
        try:
            db = get_database()
            cat_doc = await db["catalogue"].find_one({"item_id": request.style_item_id})
            if cat_doc and cat_doc.get("thumbnail"):
                custom_url = cat_doc.get("thumbnail")
        except Exception as exc:
            logger.warning("[Accessory] DB lookup skipped: %s", exc)

    # Replacement-aware source resolution
    person_img: Optional[object] = None
    source_url: Optional[str] = None
    parent_image_id: Optional[str] = None
    replay_docs: list = []
    dropped = False

    try:
        source_doc, replay_docs, dropped = await resolve_stage_replay(
            user_id, request.person_image_id, stage="accessories",
            replace_all=False, slot_value=request.subcategory,
        )
        if source_doc is not None:
            img, url = load_image_from_doc(source_doc)
            if img is not None:
                person_img, source_url, parent_image_id = img, url, source_doc["image_id"]
    except Exception as exc:
        logger.warning("[Accessory] replay resolution failed: %s", exc)

    if person_img is None:
        person_img, source_url, parent_image_id = await resolve_person_image_for_user(
            user_id, request.person_image_id
        )
        if person_img is None:
            person_img, source_url = _get_or_create_person_image(request.person_image_id)
            parent_image_id = request.person_image_id

    created_at = datetime.now(timezone.utc)
    tryon_id = f"tryon-acc-{uuid.uuid4().hex[:10]}"
    closeup_result_url = None
    closeup_orig_url = None

    try:
        if dropped:
            # Rebuild: preserved items + the new accessory, each registered as
            # its own chain doc so removals and future replacements keep working
            ops = ops_from_docs(replay_docs)
            ops.append({
                "stage": "accessories",
                "params": {
                    "style_item_id": request.style_item_id,
                    "subcategory": request.subcategory,
                    "custom_url": custom_url,
                },
            })
            composite, final_id, result_url = await rebuild_and_register_chain(
                user_id, source_doc, ops, final_image_id=tryon_id,
            )
            if composite is None or not result_url:
                raise RuntimeError("Rebuild failed — could not reconstruct your look.")
            landmark = "Replay Rebuild (replacement)"
            result_image_id = final_id or tryon_id
        else:
            composite, landmark, result_url, closeup_result_url, closeup_orig_url = synthesize_accessory_tryon(
                person_img=person_img,
                style_item_id=request.style_item_id,
                subcategory=request.subcategory,
                custom_image_url=custom_url,
                override_x=request.position_x,
                override_y=request.position_y,
                override_scale=request.scale,
                offset_x=request.offset_x,
                offset_y=request.offset_y,
            )
    except Exception as exc:
        # Honest failure: no fake "completed" result pointing at the original photo
        logger.error("[Accessory] tryon failed: %s", exc)
        record = {
            "tryon_id": tryon_id,
            "user_id": user_id,
            "category": "accessories",
            "status": TryOnStatus.failed,
            "subcategory": request.subcategory,
            "parent_image_id": parent_image_id,
            "original_image_url": source_url,
            "result_image_url": None,
            "error": f"Accessory fitting failed: {exc}",
            "created_at": created_at,
        }
        await _save_job(record)
        return AccessoryTryOnResponse(
            tryon_id=tryon_id,
            status=TryOnStatus.failed,
            subcategory=request.subcategory,
            parent_image_id=parent_image_id,
            original_image_url=source_url,
            result_image_url=None,
            error=record["error"],
            created_at=created_at,
        )

    if not dropped:
        result_image_id = _result_image_id_from_url(result_url) or tryon_id
        try:
            await register_stage_result(
                user_id=user_id,
                image_id=result_image_id,
                stage="accessories",
                parent_image_id=parent_image_id,
                tryon_id=tryon_id,
                url=result_url,
                metadata={
                    "subcategory": request.subcategory,
                    "style_item_id": request.style_item_id,
                    "landmark_used": landmark,
                    "custom_url": custom_url,
                    "parent_url": source_url,
                },
            )
        except Exception as reg_err:
            logger.warning("[Accessory] Failed to register result image: %s", reg_err)
    else:
        result_image_id = _result_image_id_from_url(result_url) or tryon_id

    # Auto-generate depth tilt variant for the result
    tilted_url = None
    depth_url = None
    if result_url:
        result_path = _disk_path_from_url(result_url)
        if result_path and os.path.isfile(result_path):
            tilted_url, depth_url = await generate_depth_variants(
                result_image_path=result_path,
                user_id=user_id,
                image_id=result_image_id,
                tryon_id=tryon_id,
            )

    job_record = {
        "tryon_id": tryon_id,
        "user_id": user_id,
        "category": "accessories",
        "status": TryOnStatus.completed,
        "subcategory": request.subcategory,
        "landmark_used": landmark,
        "parent_image_id": parent_image_id,
        "result_image_id": result_image_id,
        "original_image_url": source_url,
        "result_image_url": result_url,
        "tilted_image_url": tilted_url,
        "depth_map_url": depth_url,
        "closeup_original_image_url": closeup_orig_url,
        "closeup_result_image_url": closeup_result_url,
        "created_at": created_at,
    }
    await _save_job(job_record)

    return AccessoryTryOnResponse(
        tryon_id=tryon_id,
        status=TryOnStatus.completed,
        subcategory=request.subcategory,
        landmark_used=landmark,
        parent_image_id=parent_image_id,
        result_image_id=result_image_id,
        original_image_url=source_url,
        result_image_url=result_url,
        tilted_image_url=tilted_url,
        depth_map_url=depth_url,
        closeup_original_image_url=closeup_orig_url,
        closeup_result_image_url=closeup_result_url,
        created_at=created_at,
    )


# ── Makeup & Hairstyle ────────────────────────────────────────────────────────

from app.services.makeup_service import synthesize_makeup_tryon
from app.services.hairstyle_service import synthesize_hairstyle_tryon


@router.post(
    "/makeup",
    response_model=MakeupTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply reference-based or multi-zone makeup style",
)
async def tryon_makeup(request: MakeupTryOnRequest, current_user: dict = Depends(get_current_user)):
    """
    Apply virtual makeup using MediaPipe landmark segmentation
    and OpenCV color space alpha blending, on the LATEST generated image.
    REPLACEMENT-AWARE: re-applying the same makeup type replaces it; a
    full-transfer look replaces ALL previously applied makeup.
    """
    user_id = current_user["sub"]
    await _enforce_portrait(user_id)

    # Replacement-aware source resolution
    person_img: Optional[object] = None
    source_url: Optional[str] = None
    parent_image_id: Optional[str] = None
    replay_docs: list = []
    dropped = False

    m_type = request.makeup_type or "full_transfer"
    color_hex = request.color_hex or "#BA000D"

    try:
        source_doc, replay_docs, dropped = await resolve_stage_replay(
            user_id, request.person_image_id, stage="makeup",
            replace_all=(m_type == "full_transfer"), slot_value=None if m_type == "full_transfer" else m_type,
        )
        if source_doc is not None:
            img, url = load_image_from_doc(source_doc)
            if img is not None:
                person_img, source_url, parent_image_id = img, url, source_doc["image_id"]
    except Exception as exc:
        logger.warning("[Makeup] replay resolution failed: %s", exc)

    if person_img is None:
        person_img, source_url, parent_image_id = await resolve_person_image_for_user(
            user_id, request.person_image_id
        )
        if person_img is None:
            person_img, source_url = _get_or_create_person_image(request.person_image_id)
            parent_image_id = request.person_image_id

    created_at = datetime.now(timezone.utc)
    closeup_result_url = None
    closeup_orig_url = None

    try:
        if dropped:
            # Rebuild: preserved items + the new makeup look, chain-registered
            ops = ops_from_docs(replay_docs)
            ops.append({
                "stage": "makeup",
                "params": {
                    "makeup_type": m_type,
                    "color_hex": color_hex,
                    "intensity": request.intensity,
                    "finish": request.finish,
                },
            })
            composite, final_id, result_url = await rebuild_and_register_chain(
                user_id, source_doc, ops,
            )
            if composite is None or not result_url:
                raise RuntimeError("Rebuild failed — could not reconstruct your look.")
            landmark_summary = "Replay Rebuild (replacement)"
            tryon_id = final_id
        elif m_type == "full_transfer":
            # Complete reference/holistic look transfer: combines lips, eyelids, and cheeks
            res_pil, _, _ = synthesize_makeup_tryon(
                person_img, "lipstick", color_hex, request.intensity, request.finish
            )[:3]
            res_pil, _, _ = synthesize_makeup_tryon(
                res_pil, "eyeshadow", "#37474F", request.intensity * 0.8, request.finish
            )[:3]
            res_pil, landmark_summary, result_url, closeup_result_url, closeup_orig_url = synthesize_makeup_tryon(
                res_pil, "blush", "#F48FB1", request.intensity * 0.7, request.finish
            )
            import os as _os
            tryon_id = _os.path.splitext(_os.path.basename(result_url))[0]
        else:
            res_pil, landmark_summary, result_url, closeup_result_url, closeup_orig_url = synthesize_makeup_tryon(
                person_img, m_type, color_hex, request.intensity, request.finish
            )
            import os as _os
            tryon_id = _os.path.splitext(_os.path.basename(result_url))[0]
    except Exception as exc:
        # Honest failure
        logger.error("[Makeup] tryon failed: %s", exc)
        tryon_id = f"tryon-mu-{uuid.uuid4().hex[:10]}"
        record = {
            "tryon_id": tryon_id,
            "user_id": user_id,
            "category": "makeup",
            "status": TryOnStatus.failed,
            "makeup_type": m_type,
            "parent_image_id": parent_image_id,
            "original_image_url": source_url,
            "result_image_url": None,
            "error": f"Makeup application failed: {exc}",
            "created_at": created_at,
        }
        await _save_job(record)
        return MakeupTryOnResponse(
            tryon_id=tryon_id,
            status=TryOnStatus.failed,
            makeup_type=m_type,
            parent_image_id=parent_image_id,
            original_image_url=source_url,
            result_image_url=None,
            error=record["error"],
            color_hex=color_hex,
            intensity=request.intensity,
            finish=request.finish,
            created_at=created_at,
        )

    result_image_id = _result_image_id_from_url(result_url) or tryon_id
    if not dropped:
        try:
            await register_stage_result(
                user_id=user_id,
                image_id=result_image_id,
                stage="makeup",
                parent_image_id=parent_image_id,
                tryon_id=tryon_id,
                url=result_url,
                metadata={
                    "makeup_type": m_type,
                    "color_hex": color_hex,
                    "intensity": request.intensity,
                    "finish": request.finish,
                    "parent_url": source_url,
                },
            )
        except Exception as reg_err:
            logger.warning("[Makeup] Failed to register result image: %s", reg_err)

    # Auto-generate depth tilt variant for the result
    tilted_url = None
    depth_url = None
    if result_url:
        result_path = _disk_path_from_url(result_url)
        if result_path and os.path.isfile(result_path):
            tilted_url, depth_url = await generate_depth_variants(
                result_image_path=result_path,
                user_id=user_id,
                image_id=result_image_id,
                tryon_id=tryon_id,
            )

    job_record = {
        "tryon_id": tryon_id,
        "user_id": user_id,
        "category": "makeup",
        "status": TryOnStatus.completed,
        "makeup_type": m_type,
        "style_name": "Complete Reference Makeup Transfer" if m_type == "full_transfer" else f"Virtual {m_type.capitalize()}",
        "color_hex": color_hex,
        "intensity": request.intensity,
        "finish": request.finish,
        "parent_image_id": parent_image_id,
        "result_image_id": result_image_id,
        "original_image_url": source_url,
        "result_image_url": result_url,
        "tilted_image_url": tilted_url,
        "depth_map_url": depth_url,
        "closeup_original_image_url": closeup_orig_url,
        "closeup_result_image_url": closeup_result_url,
        "created_at": created_at,
    }
    await _save_job(job_record)

    return MakeupTryOnResponse(**job_record)


@router.post(
    "/hairstyle",
    response_model=HairstyleTryOnResponse,
    status_code=status.HTTP_200_OK,
    summary="Fit hairstyle matched to head orientation",
)
async def tryon_hairstyle(request: HairstyleTryOnRequest, current_user: dict = Depends(get_current_user)):
    """
    Fit haircut style using head pose estimation (yaw/pitch) and forehead anchor,
    on the LATEST generated image. REPLACEMENT-AWARE: a new hairstyle REPLACES
    any previously applied hairstyle while preserving all other styling.
    """
    user_id = current_user["sub"]
    await _enforce_portrait(user_id)

    # Replacement-aware source resolution (only one hairstyle at a time)
    person_img: Optional[object] = None
    source_url: Optional[str] = None
    parent_image_id: Optional[str] = None
    replay_docs: list = []
    dropped = False

    try:
        source_doc, replay_docs, dropped = await resolve_stage_replay(
            user_id, request.person_image_id, stage="hairstyle", replace_all=True,
        )
        if source_doc is not None:
            img, url = load_image_from_doc(source_doc)
            if img is not None:
                person_img, source_url, parent_image_id = img, url, source_doc["image_id"]
    except Exception as exc:
        logger.warning("[Hairstyle] replay resolution failed: %s", exc)

    if person_img is None:
        person_img, source_url, parent_image_id = await resolve_person_image_for_user(
            user_id, request.person_image_id
        )
        if person_img is None:
            person_img, source_url = _get_or_create_person_image(request.person_image_id)
            parent_image_id = request.person_image_id

    created_at = datetime.now(timezone.utc)

    style_name = "Hairstyle Style Fit"
    subcategory = None
    try:
        db = get_database()
        style_doc = await db["catalogue"].find_one({"item_id": request.style_item_id})
        if style_doc:
            style_name = style_doc.get("name") or style_name
            subcategory = style_doc.get("subcategory")
    except Exception as exc:
        logger.warning("[Hairstyle] DB lookup skipped: %s", exc)

    closeup_result_url = None
    closeup_orig_url = None

    try:
        if dropped:
            # Rebuild: preserved items + the new hairstyle, chain-registered
            ops = ops_from_docs(replay_docs)
            ops.append({
                "stage": "hairstyle",
                "params": {
                    "style_item_id": request.style_item_id,
                    "color_hex": request.color_hex,
                    "style_name": style_name,
                },
            })
            composite, final_id, result_url = await rebuild_and_register_chain(
                user_id, source_doc, ops,
            )
            if composite is None or not result_url:
                raise RuntimeError("Rebuild failed — could not reconstruct your look.")
            result_image_id = final_id
            tryon_id = final_id
        else:
            res_pil, landmark_desc, result_url, closeup_result_url, closeup_orig_url = synthesize_hairstyle_tryon(
                person_img=person_img,
                style_item_id=request.style_item_id,
                color_hex=request.color_hex,
                subcategory=subcategory,
                offset_x=request.offset_x,
                offset_y=request.offset_y,
                scale_override=request.scale,
            )
            import os as _os
            tryon_id = _os.path.splitext(_os.path.basename(result_url))[0]
    except Exception as exc:
        # Honest failure
        logger.error("[Hairstyle] tryon failed: %s", exc)
        tryon_id = f"tryon-hair-{uuid.uuid4().hex[:10]}"
        record = {
            "tryon_id": tryon_id,
            "user_id": user_id,
            "category": "hairstyle",
            "status": TryOnStatus.failed,
            "style_name": style_name,
            "parent_image_id": parent_image_id,
            "original_image_url": source_url,
            "result_image_url": None,
            "error": f"Hairstyle fitting failed: {exc}",
            "created_at": created_at,
        }
        await _save_job(record)
        return HairstyleTryOnResponse(
            tryon_id=tryon_id,
            status=TryOnStatus.failed,
            style_name=style_name,
            parent_image_id=parent_image_id,
            original_image_url=source_url,
            result_image_url=None,
            error=record["error"],
            created_at=created_at,
        )

    result_image_id = _result_image_id_from_url(result_url) or tryon_id
    if not dropped:
        try:
            await register_stage_result(
                user_id=user_id,
                image_id=result_image_id,
                stage="hairstyle",
                parent_image_id=parent_image_id,
                tryon_id=tryon_id,
                url=result_url,
                metadata={
                    "style_item_id": request.style_item_id,
                    "style_name": style_name,
                    "color_hex": request.color_hex,
                    "parent_url": source_url,
                },
            )
        except Exception as reg_err:
            logger.warning("[Hairstyle] Failed to register result image: %s", reg_err)

    # Auto-generate depth tilt variant for the result
    tilted_url = None
    depth_url = None
    if result_url:
        result_path = _disk_path_from_url(result_url)
        if result_path and os.path.isfile(result_path):
            tilted_url, depth_url = await generate_depth_variants(
                result_image_path=result_path,
                user_id=user_id,
                image_id=result_image_id,
                tryon_id=tryon_id,
            )

    job_record = {
        "tryon_id": tryon_id,
        "user_id": user_id,
        "category": "hairstyle",
        "status": TryOnStatus.completed,
        "style_name": style_name,
        "color_hex": request.color_hex,
        "parent_image_id": parent_image_id,
        "result_image_id": result_image_id,
        "original_image_url": source_url,
        "result_image_url": result_url,
        "tilted_image_url": tilted_url,
        "depth_map_url": depth_url,
        "closeup_original_image_url": closeup_orig_url,
        "closeup_result_image_url": closeup_result_url,
        "created_at": created_at,
    }
    await _save_job(job_record)

    return HairstyleTryOnResponse(**job_record)


# ── Stage chaining introspection ──────────────────────────────────────────────

@router.get(
    "/chain/{image_id}",
    summary="Get the full stage chain that produced an image (base → latest)",
)
async def get_image_chain(image_id: str, current_user: dict = Depends(get_current_user)):
    """Returns the ordered chain of styling stages applied to produce this image."""
    user_id = current_user["sub"]
    chain = await get_chain(user_id, image_id)
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image '{image_id}' not found.",
        )
    return {"image_id": image_id, "chain": chain, "length": len(chain)}


@router.get(
    "/session/{base_image_id}/stages",
    summary="Get the latest applied result per stage for a styling session",
)
async def get_styling_session_stages(base_image_id: str, current_user: dict = Depends(get_current_user)):
    """Powers the Complete Look screen: latest result of each stage rooted at the base portrait."""
    user_id = current_user["sub"]
    session_data = await get_session_stages(user_id, base_image_id)
    return {"base_image_id": base_image_id, **session_data}


@router.post(
    "/remove",
    response_model=RemoveItemResponse,
    summary="Remove an applied item (accessory, makeup, outfit, or hairstyle) from the current look",
)
async def remove_tryon_item(request: RemoveItemRequest, current_user: dict = Depends(get_current_user)):
    """
    Strip a previously applied item from the styling chain and rebuild the
    image WITHOUT it — while re-applying (replaying) every other preserved
    item on top. Unlike replacement, no new item is composited afterwards.
    """
    user_id = current_user["sub"]
    await _enforce_portrait(user_id)

    stage = (request.stage or "").strip().lower()
    if stage not in STAGE_ORDER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage '{request.stage}'. Must be one of: {', '.join(STAGE_ORDER)}.",
        )

    # Slot semantics: outfit/hairstyle are single-slot (whole-stage removal);
    # accessories/makeup remove by slot; without a slot removes ALL items in that stage.
    replace_all = False
    slot = request.slot_value
    if stage in ("outfit", "hairstyle"):
        replace_all = True
        slot = None
    elif stage in ("makeup", "accessories") and not slot:
        replace_all = True
    elif not slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'slot_value' is required to remove an item from the {stage} stage.",
        )

    source_doc, replay_docs, dropped = await resolve_stage_replay(
        user_id, request.person_image_id, stage=stage,
        replace_all=replace_all, slot_value=slot,
    )
    if not dropped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That item is not part of your current look.",
        )

    person_img, source_url = load_image_from_doc(source_doc)
    if person_img is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the underlying image for rebuild.",
        )

    created_at = datetime.now(timezone.utc)
    tryon_id = f"tryon-rm-{uuid.uuid4().hex[:10]}"
    try:
        # Rebuild the chain WITHOUT the removed item: each preserved item is
        # re-applied and registered as its own chain doc
        final_img, final_id, result_url = await rebuild_and_register_chain(
            user_id, source_doc, ops_from_docs(replay_docs),
        )
        if final_img is None or not final_id or not result_url:
            raise RuntimeError("Could not load the underlying image for rebuild.")
    except Exception as exc:
        logger.error("[Remove] rebuild failed: %s", exc)
        return RemoveItemResponse(
            status=TryOnStatus.failed,
            removed_stage=stage,
            removed_slot=slot,
            error=f"Could not rebuild the look without this item: {exc}",
        )

    try:
        await register_stage_result(
            user_id=user_id,
            image_id=tryon_id,
            stage=stage,
            parent_image_id=final_id,
            tryon_id=tryon_id,
            url=result_url,
            metadata={
                "removed": True,
                "removed_slot": slot,
                "removed_stage": stage,
                "parent_url": result_url,
                "replayed": [d.get("image_id") for d in replay_docs],
            },
        )
    except Exception as reg_err:
        logger.warning("[Remove] Failed to register removal result: %s", reg_err)

    remaining = await get_live_items(user_id, tryon_id)
    return RemoveItemResponse(
        status=TryOnStatus.completed,
        removed_stage=stage,
        removed_slot=slot,
        result_image_id=tryon_id,
        result_image_url=result_url,
        current_image_id=tryon_id,
        remaining_items=remaining,
    )


@router.get(
    "/{tryon_id}",
    summary="Get try-on job status and result",
)
async def get_tryon_status(tryon_id: str, current_user: dict = Depends(get_current_user)):
    """Check the status and retrieve result image URL for any try-on job (user-scoped)."""
    job = await _get_job(tryon_id, current_user["sub"])
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Try-on job '{tryon_id}' not found.",
        )
    job.pop("_id", None)
    return job
