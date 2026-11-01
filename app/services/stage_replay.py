"""
StyleVision — Stage Replay Executor
When a user replaces or removes an item in the styling chain (e.g. swaps
glasses while keeping earrings), the chain is REBUILT: every preserved item
is re-applied sequentially and REGISTERED as its own chain document, so the
items list stays accurate and future replacements/removals keep working.
"""
import logging
import os
import uuid
from typing import List, Optional, Tuple
from PIL import Image

from app.services.image_registry import (
    STAGE_ORDER,
    register_stage_result,
    load_image_from_doc,
)
from app.config import get_settings
from app.database import get_database

logger = logging.getLogger(__name__)
settings = get_settings()

_ID_PREFIX = {
    "outfit": "tryon-outfit-",
    "accessories": "tryon-acc-",
    "makeup": "tryon-mu-",
    "hairstyle": "tryon-hair-",
}


def save_stage_composite(img: Image.Image, tryon_id: str) -> str:
    """Save a replayed composite to the try-on output dir; returns its serving URL."""
    out_dir = os.path.join(settings.upload_dir, "tryon")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{tryon_id}.png"
    path = os.path.join(out_dir, filename)
    img.convert("RGBA").save(path, format="PNG")
    return f"/uploads/tryon/{filename}"


def sort_ops(ops: List[dict]) -> List[dict]:
    """Order ops by pipeline stage (outfit → accessories → makeup → hairstyle),
    preserving the original application order within the same stage."""
    return sorted(
        ops,
        key=lambda op: STAGE_ORDER.index(op["stage"]) if op["stage"] in STAGE_ORDER else 99,
    )


def ops_from_docs(docs: List[dict]) -> List[dict]:
    """Convert registry stage-result docs into executable replay ops."""
    ops: List[dict] = []
    for doc in docs:
        meta = doc.get("metadata") or {}
        stage = doc.get("stage")
        if stage == "accessories":
            if not meta.get("style_item_id"):
                logger.warning("[Replay] accessory doc %s missing style_item_id — skipping", doc.get("image_id"))
                continue
            ops.append(
                {
                    "stage": "accessories",
                    "doc_id": doc.get("image_id"),
                    "params": {
                        "style_item_id": meta.get("style_item_id"),
                        "subcategory": meta.get("subcategory"),
                        "custom_url": meta.get("custom_url"),
                    },
                }
            )
        elif stage == "makeup":
            ops.append(
                {
                    "stage": "makeup",
                    "doc_id": doc.get("image_id"),
                    "params": {
                        "makeup_type": meta.get("makeup_type") or "full_transfer",
                        "color_hex": meta.get("color_hex") or "#BA000D",
                        "intensity": meta.get("intensity", 0.7),
                        "finish": meta.get("finish") or "satin",
                    },
                }
            )
        elif stage == "hairstyle":
            ops.append(
                {
                    "stage": "hairstyle",
                    "doc_id": doc.get("image_id"),
                    "params": {
                        "style_item_id": meta.get("style_item_id"),
                        "color_hex": meta.get("color_hex"),
                        "style_name": meta.get("style_name"),
                    },
                }
            )
        elif stage == "outfit":
            if not meta.get("garment_id"):
                logger.warning("[Replay] outfit doc %s missing garment_id — skipping", doc.get("image_id"))
                continue
            ops.append(
                {
                    "stage": "outfit",
                    "doc_id": doc.get("image_id"),
                    "params": {
                        "garment_id": meta.get("garment_id"),
                        "source": meta.get("source") or "catalogue",
                        "cloth_type": meta.get("cloth_type"),
                    },
                }
            )
    return ops


async def _resolve_garment_info(garment_id: str, source: str) -> dict:
    """Re-resolve garment colour/name/image path from catalogue or wardrobe."""
    db = get_database()
    try:
        if source == "wardrobe":
            doc = await db["outfits"].find_one({"outfit_id": garment_id})
            if doc:
                return {
                    "color": doc.get("color"),
                    "name": doc.get("name"),
                    "image_path": doc.get("outfit_image"),
                    "category": doc.get("category"),
                }
        else:
            doc = await db["catalogue"].find_one({"item_id": garment_id})
            if doc:
                return {
                    "color": doc.get("color"),
                    "name": doc.get("name"),
                    "image_path": doc.get("thumbnail"),
                    "category": doc.get("subcategory") or doc.get("category"),
                }
    except Exception as exc:
        logger.warning("[Replay] garment lookup failed for %s: %s", garment_id, exc)
    return {}


async def execute_single_op(current_img: Image.Image, op: dict) -> Optional[Image.Image]:
    """Apply ONE replay op onto the given image. Returns the composite or None on failure."""
    from app.services.accessory_service import synthesize_accessory_tryon
    from app.services.makeup_service import synthesize_makeup_tryon
    from app.services.hairstyle_service import synthesize_hairstyle_tryon
    from app.services.tryon_service import synthesize_outfit_tryon

    stage = op["stage"]
    params = op["params"]
    try:
        if stage == "accessories":
            custom_url = params.get("custom_url")
            if not custom_url:
                try:
                    db = get_database()
                    cat_doc = await db["catalogue"].find_one({"item_id": params["style_item_id"]})
                    if cat_doc and cat_doc.get("thumbnail"):
                        custom_url = cat_doc.get("thumbnail")
                except Exception:
                    pass
            return synthesize_accessory_tryon(
                person_img=current_img,
                style_item_id=params["style_item_id"],
                subcategory=params.get("subcategory") or "glasses",
                custom_image_url=custom_url,
            )[0]
        if stage == "makeup":
            m_type = params.get("makeup_type") or "full_transfer"
            intensity = float(params.get("intensity", 0.7))
            finish = params.get("finish") or "satin"
            color_hex = params.get("color_hex") or "#BA000D"
            if m_type == "full_transfer":
                # Complete look = lipstick → eyeshadow → blush (same as the router)
                res_pil = synthesize_makeup_tryon(
                    current_img, "lipstick", color_hex, intensity, finish
                )[0]
                res_pil = synthesize_makeup_tryon(
                    res_pil, "eyeshadow", "#37474F", intensity * 0.8, finish
                )[0]
                return synthesize_makeup_tryon(
                    res_pil, "blush", "#F48FB1", intensity * 0.7, finish
                )[0]
            return synthesize_makeup_tryon(
                current_img, m_type, color_hex, intensity, finish
            )[0]
        if stage == "hairstyle":
            style_name = params.get("style_name")
            subcategory = None
            if not style_name:
                try:
                    db = get_database()
                    style_doc = await db["catalogue"].find_one({"item_id": params["style_item_id"]})
                    if style_doc:
                        style_name = style_doc.get("name")
                        subcategory = style_doc.get("subcategory")
                except Exception:
                    pass
            return synthesize_hairstyle_tryon(
                person_img=current_img,
                style_item_id=params["style_item_id"],
                color_hex=params.get("color_hex"),
                subcategory=subcategory,
            )[0]
        if stage == "outfit":
            info = await _resolve_garment_info(params["garment_id"], params.get("source") or "catalogue")
            result = await synthesize_outfit_tryon(
                person_image_id="replay",
                garment_id=params["garment_id"],
                source=params.get("source") or "catalogue",
                garment_color=info.get("color"),
                garment_name=info.get("name"),
                garment_image_path=info.get("image_path"),
                garment_category=info.get("category"),
                explicit_cloth_type=params.get("cloth_type"),
                user_id=None,
                person_image_override=current_img,
                register_result=False,
            )
            return result.get("composite_image")
    except Exception as exc:
        # A replay failure must never fail the whole request — skip the op
        logger.error("[Replay] op %s (%s) failed: %s", op.get("doc_id"), stage, exc)
    return None


async def execute_replay_ops(source_img: Image.Image, ops: List[dict]) -> Image.Image:
    """Apply replay ops in-memory without registering (kept for simple reuse)."""
    current = source_img
    for op in sort_ops(ops):
        composite = await execute_single_op(current, op)
        if composite is not None:
            current = composite
    return current


async def rebuild_and_register_chain(
    user_id: str,
    source_doc: dict,
    ops: List[dict],
    final_image_id: Optional[str] = None,
) -> Tuple[Optional[Image.Image], Optional[str], Optional[str]]:
    """
    Sequentially apply ops starting from source_doc's image, SAVING and
    REGISTERING each intermediate as its own chain document (preserving item
    metadata). This keeps the live-items view and future removals correct.

    Returns (final_image, final_image_id, final_url).
    - final_image_id: id of the last registered doc (or source_doc's id when
      no ops produced a composite).
    """
    img, url = load_image_from_doc(source_doc)
    if img is None:
        return None, None, None

    current = img
    parent_id = source_doc["image_id"]
    last_id = parent_id
    last_url = url
    ops_sorted = sort_ops(ops)
    total = len(ops_sorted)

    for idx, op in enumerate(ops_sorted):
        composite = await execute_single_op(current, op)
        if composite is None:
            continue
        is_last = idx == total - 1
        stage = op["stage"]
        image_id = (
            final_image_id
            if (is_last and final_image_id)
            else f"{_ID_PREFIX.get(stage, 'tryon-rm-')}{uuid.uuid4().hex[:10]}"
        )
        result_url = save_stage_composite(composite, image_id)
        try:
            await register_stage_result(
                user_id=user_id,
                image_id=image_id,
                stage=stage,
                parent_image_id=parent_id,
                tryon_id=image_id,
                url=result_url,
                metadata={
                    **op["params"],
                    "mode": op.get("params", {}).get("mode") or ("catvton" if stage == "outfit" else "local"),
                    "replayed_from": op.get("doc_id"),
                    "parent_url": last_url,
                },
            )
        except Exception as reg_err:
            logger.warning("[Replay] Failed to register rebuilt doc %s: %s", image_id, reg_err)
        current = composite
        parent_id = image_id
        last_id = image_id
        last_url = result_url

    return current, last_id, last_url
