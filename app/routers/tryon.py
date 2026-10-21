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
)
from app.config import get_settings
from app.utils.security import get_current_user
from app.services.tryon_service import (
    synthesize_outfit_tryon,
    resolve_person_image_for_user,
    _get_or_create_person_image,
)
from app.services.image_registry import (
    register_stage_result,
    get_chain,
    get_session_stages,
    resolve_stage_replay,
    load_image_from_doc,
)
from app.services.stage_replay import (
    ops_from_docs,
    execute_replay_ops,
    save_stage_composite,
)
from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tryon", tags=["Virtual Try-On"])
settings = get_settings()


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
    replay_docs: list = []
    dropped = False
    try:
        source_doc, replay_docs, dropped = await resolve_stage_replay(
            user_id, request.person_image_id, stage="outfit", replace_all=True,
        )
        if source_doc is not None:
            person_img, _url = load_image_from_doc(source_doc)
    except Exception as exc:
        logger.warning("[Outfit] replay resolution failed: %s", exc)

    if dropped and person_img is not None:
        # Rebuild: new outfit first, then replay preserved stages on top
        intermediate = await synthesize_outfit_tryon(
            person_image_id="replay",
            garment_id=garment_id,
            source=request.source,
            garment_color=garment_color,
            garment_name=garment_name,
            garment_image_path=garment_image_path,
            garment_category=garment_category,
            explicit_cloth_type=request.cloth_type,
            user_id=None,
            person_image_override=person_img,
            register_result=False,
        )
        composite = intermediate.get("composite_image")
        if composite is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Outfit synthesis failed during rebuild.",
            )
        final_img = await execute_replay_ops(composite, ops_from_docs(replay_docs))

        from app.services.stage_replay import save_stage_composite
        tryon_id = f"tryon-outfit-{uuid.uuid4().hex[:10]}"
        result_url = save_stage_composite(final_img, tryon_id)
        now = datetime.now(timezone.utc)
        result = {
            "tryon_id": tryon_id,
            "status": TryOnStatus.completed,
            "mode": intermediate.get("mode", TryOnMode.prototype),
            "source": request.source,
            "parent_image_id": request.person_image_id,
            "result_image_id": tryon_id,
            "original_image_url": intermediate.get("original_image_url") or "",
            "garment_image_url": intermediate.get("garment_image_url"),
            "result_image_url": result_url,
            "processing_note": intermediate.get("processing_note"),
            "created_at": now,
        }
        try:
            await register_stage_result(
                user_id=user_id,
                image_id=tryon_id,
                stage="outfit",
                parent_image_id=request.person_image_id,
                tryon_id=tryon_id,
                url=result_url,
                metadata={
                    "garment_id": garment_id,
                    "garment_name": garment_name,
                    "source": request.source,
                    "cloth_type": request.cloth_type,
                    "mode": str(intermediate.get("mode", "prototype")),
                    "processing_note": intermediate.get("processing_note"),
                    "parent_url": intermediate.get("original_image_url") or "",
                    "replayed": [d.get("image_id") for d in replay_docs],
                },
            )
        except Exception as reg_err:
            logger.warning("[Outfit] Failed to register replayed result: %s", reg_err)
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

    job_record = {**result, "user_id": user_id, "garment_name": garment_name}
    await _save_job(job_record)
    return OutfitTryOnResponse(**result)


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
            # Rebuild: apply preserved items + the new accessory onto the pre-replacement source
            ops = ops_from_docs(replay_docs)
            ops.append({
                "stage": "accessories",
                "params": {
                    "style_item_id": request.style_item_id,
                    "subcategory": request.subcategory,
                    "custom_url": custom_url,
                },
            })
            composite = await execute_replay_ops(person_img, ops)
            landmark = "Replay Rebuild (replacement)"
            result_url = save_stage_composite(composite, tryon_id)
        else:
            composite, landmark, result_url, closeup_result_url, closeup_orig_url = synthesize_accessory_tryon(
                person_img=person_img,
                style_item_id=request.style_item_id,
                subcategory=request.subcategory,
                custom_image_url=custom_url,
                override_x=request.position_x,
                override_y=request.position_y,
                override_scale=request.scale,
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
            # Rebuild: preserved items + the new makeup look onto the pre-replacement source
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
            composite = await execute_replay_ops(person_img, ops)
            landmark_summary = "Replay Rebuild (replacement)"
            result_url = save_stage_composite(composite, f"tryon-mu-{uuid.uuid4().hex[:10]}")
            import os as _os
            tryon_id = _os.path.splitext(_os.path.basename(result_url))[0]
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
            # Rebuild: preserved items + the new hairstyle onto the pre-replacement source
            ops = ops_from_docs(replay_docs)
            ops.append({
                "stage": "hairstyle",
                "params": {
                    "style_item_id": request.style_item_id,
                    "color_hex": request.color_hex,
                    "style_name": style_name,
                },
            })
            composite = await execute_replay_ops(person_img, ops)
            result_url = save_stage_composite(composite, f"tryon-hair-{uuid.uuid4().hex[:10]}")
            import os as _os
            tryon_id = _os.path.splitext(_os.path.basename(result_url))[0]
        else:
            res_pil, landmark_desc, result_url, closeup_result_url, closeup_orig_url = synthesize_hairstyle_tryon(
                person_img=person_img,
                style_item_id=request.style_item_id,
                color_hex=request.color_hex,
                subcategory=subcategory,
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
