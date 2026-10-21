"""
StyleVision — Unified Image Registry Service

Implements the critical "continuous styling workflow" requirement:
every original portrait upload AND every try-on stage result is registered in a
single `images` collection, so any stage can start from the LATEST generated
image of a previous stage instead of repeatedly from the original photo.

Every image document records:
- image_id          : unique id (upload id or try-on result id)
- user_id           : owner (strict user isolation)
- kind              : "original" | "stage_result"
- stage             : "outfit" | "accessories" | "makeup" | "hairstyle" (results only)
- parent_image_id   : the image this one was generated FROM (chain linkage)
- root_image_id     : the original portrait at the head of the chain
- tryon_id          : try-on job that produced it (results only)
- url               : relative static URL for serving the image
"""
import os
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from PIL import Image

from app.config import get_settings
from app.database import get_database

settings = get_settings()

STAGE_ORDER = ("outfit", "accessories", "makeup", "hairstyle")


def _disk_path_from_url(url: Optional[str]) -> Optional[str]:
    """Map a relative static URL (e.g. /uploads/tryon/x.png) to a local file path."""
    if not url:
        return None
    rel = url.lstrip("/").split("?")[0].replace("/", os.sep)
    path = os.path.join(os.getcwd(), rel)
    return path if os.path.isfile(path) else None


def _image_id_from_url(url: Optional[str]) -> Optional[str]:
    """Derive a stable image id from a result URL (filename without extension)."""
    if not url:
        return None
    stem = os.path.splitext(os.path.basename(url))[0]
    return stem or None


async def register_original_image(
    user_id: str,
    image_id: str,
    filename: str,
    url: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    size_bytes: Optional[int] = None,
    quality_score: Optional[str] = None,
) -> None:
    """Register a freshly uploaded original portrait in the unified registry."""
    now = datetime.now(timezone.utc)
    doc = {
        "image_id": image_id,
        "user_id": user_id,
        "kind": "original",
        "stage": None,
        "parent_image_id": None,
        "root_image_id": image_id,
        "tryon_id": None,
        "filename": filename,
        "url": url,
        "width": width,
        "height": height,
        "size_bytes": size_bytes,
        "quality_score": quality_score,
        "created_at": now,
    }
    db = get_database()
    await db["images"].update_one({"image_id": image_id}, {"$set": doc}, upsert=True)


async def register_stage_result(
    user_id: str,
    image_id: str,
    stage: str,
    parent_image_id: Optional[str],
    tryon_id: str,
    url: str,
    metadata: Optional[dict] = None,
) -> str:
    """
    Register a try-on stage result so the next stage can chain from it.
    `parent_image_id` is the image the result was generated from.
    Returns the registered image_id.
    """
    now = datetime.now(timezone.utc)
    parent_image_id = parent_image_id or image_id

    root_image_id = parent_image_id
    if parent_image_id != image_id:
        parent_doc = await db_get_image(user_id, parent_image_id)
        if parent_doc:
            root_image_id = parent_doc.get("root_image_id") or parent_doc.get("image_id")

    doc = {
        "image_id": image_id,
        "user_id": user_id,
        "kind": "stage_result",
        "stage": stage,
        "parent_image_id": parent_image_id,
        "root_image_id": root_image_id,
        "tryon_id": tryon_id,
        "filename": os.path.basename(url or ""),
        "url": url,
        "metadata": metadata or {},
        "created_at": now,
    }
    db = get_database()
    await db["images"].update_one({"image_id": image_id}, {"$set": doc}, upsert=True)
    return image_id


async def db_get_image(user_id: str, image_id: str) -> Optional[dict]:
    """Fetch one registry document owned by the user (image_id or tryon_id match)."""
    if not image_id:
        return None
    db = get_database()
    ref = str(image_id).strip()
    return await db["images"].find_one(
        {"user_id": user_id, "$or": [{"image_id": ref}, {"tryon_id": ref}]}
    )


def _load_pil_from_doc(doc: dict) -> Optional[Tuple[Image.Image, str]]:
    path = _disk_path_from_url(doc.get("url"))
    if not path:
        return None
    try:
        img = Image.open(path).convert("RGBA")
        return img, doc.get("url")
    except Exception:
        return None


def load_image_from_doc(doc: dict) -> Tuple[Optional[Image.Image], Optional[str]]:
    """Public wrapper: load a registry doc's image from disk. Returns (img, url) or (None, None)."""
    result = _load_pil_from_doc(doc)
    if result is None:
        return None, None
    return result


async def resolve_person_image(
    user_id: str,
    image_ref: Optional[str],
) -> Tuple[Optional[Image.Image], Optional[str], Optional[str]]:
    """
    Resolve ANY image reference into a loadable PIL image for the next stage.

    Resolution order (user-scoped at every step):
      1. Unified registry by exact image_id / tryon_id  → includes ALL stage results,
         which is what makes stage chaining work.
      2. Legacy `uploads` collection doc by image_id (pre-registry uploads).
      3. User's latest ORIGINAL portrait from the registry.
      4. User's latest portrait from the legacy `uploads` collection.
      5. None — caller falls back to the demo portrait generator.
    """
    # 1. Unified registry (originals + stage results)
    doc = await db_get_image(user_id, image_ref or "")
    if doc:
        loaded = _load_pil_from_doc(doc)
        if loaded:
            img, url = loaded
            return img, url, doc.get("image_id")

    # 2. Legacy uploads collection by image_id
    if image_ref:
        db = get_database()
        legacy = await db["uploads"].find_one(
            {"$or": [{"image_id": image_ref}, {"filename": image_ref}]}
        )
        if legacy:
            loaded = _load_pil_from_doc({"url": legacy.get("url")})
            if loaded:
                img, url = loaded
                return img, url, legacy.get("image_id")

    # 3. Latest original from registry
    db = get_database()
    latest = await db["images"].find_one(
        {"user_id": user_id, "kind": "original"}, sort=[("created_at", -1)]
    )
    if latest:
        loaded = _load_pil_from_doc(latest)
        if loaded:
            img, url = loaded
            return img, url, latest.get("image_id")

    # 4. Legacy latest upload
    legacy_latest = await db["uploads"].find_one(sort=[("uploaded_at", -1)])
    if legacy_latest:
        loaded = _load_pil_from_doc({"url": legacy_latest.get("url")})
        if loaded:
            img, url = loaded
            return img, url, legacy_latest.get("image_id")

    return None, None, None


async def get_chain(user_id: str, image_id: str) -> List[dict]:
    """
    Walk the parent linkage from an image back to the base portrait.
    Returns the chain ordered base → latest (each item: image_id, stage, url, tryon_id).
    """
    chain: List[dict] = []
    seen = set()
    current_id = image_id
    db = get_database()

    while current_id and current_id not in seen and len(seen) < 25:
        seen.add(current_id)
        doc = await db["images"].find_one({"user_id": user_id, "image_id": current_id})
        if not doc:
            break
        chain.append(
            {
                "image_id": doc.get("image_id"),
                "kind": doc.get("kind"),
                "stage": doc.get("stage"),
                "url": doc.get("url"),
                "tryon_id": doc.get("tryon_id"),
                "created_at": doc.get("created_at"),
            }
        )
        current_id = doc.get("parent_image_id")

    chain.reverse()
    return chain


async def get_chain_docs(user_id: str, image_ref: Optional[str]) -> List[dict]:
    """
    Full registry documents for the chain that produced `image_ref`,
    ordered ROOT (original portrait) → TIP (requested image).
    Empty list if the reference is not registered.
    """
    docs: List[dict] = []
    seen = set()
    current_id = image_ref
    db = get_database()

    while current_id and current_id not in seen and len(seen) < 25:
        seen.add(current_id)
        doc = await db["images"].find_one(
            {"user_id": user_id, "$or": [{"image_id": current_id}, {"tryon_id": current_id}]}
        )
        if not doc:
            break
        docs.append(doc)
        current_id = doc.get("parent_image_id")

    docs.reverse()
    return docs


def _slot_of_doc(stage: str, doc: dict) -> Optional[str]:
    """The replaceable slot value of a stage-result document (e.g. accessory subcategory)."""
    meta = doc.get("metadata") or {}
    if stage == "accessories":
        return meta.get("subcategory")
    if stage == "makeup":
        return meta.get("makeup_type")
    return None


async def resolve_stage_replay(
    user_id: str,
    image_ref: Optional[str],
    stage: str,
    replace_all: bool = False,
    slot_key: Optional[str] = None,
    slot_value: Optional[str] = None,
) -> Tuple[Optional[dict], List[dict], bool]:
    """
    Replacement-aware source resolution for stage chaining.

    When the user re-applies a slot that already exists in the chain (e.g. new
    glasses over old glasses), the old result must NOT be composited over.
    Instead:
      - the dropped docs (same stage + same slot, or ALL docs of the stage when
        replace_all=True) are stripped from the chain,
      - the source becomes the image BEFORE the first dropped doc,
      - every KEPT doc that was applied after that point is returned as a
        replay list so the caller can re-apply them on top of the new item.

    Returns (source_doc, replay_docs, dropped_any):
      source_doc : registry doc whose image the caller should composite onto
                   (None → caller falls back to legacy resolution)
      replay_docs: kept stage-result docs (root→tip order) to re-apply after
                   the new item is composited
      dropped_any: True when a replacement strip occurred
    """
    chain = await get_chain_docs(user_id, image_ref)
    if not chain:
        return None, [], False

    def _is_dropped(doc: dict) -> bool:
        if doc.get("kind") != "stage_result" or doc.get("stage") != stage:
            return False
        if replace_all:
            return True
        if slot_value is None:
            return True
        return _slot_of_doc(stage, doc) == slot_value

    first_drop_idx = next((i for i, d in enumerate(chain) if _is_dropped(d)), None)
    if first_drop_idx is None:
        # Nothing to replace — the requested image itself is the correct source
        return chain[-1], [], False

    source_doc = chain[first_drop_idx - 1] if first_drop_idx > 0 else None
    if source_doc is None:
        # The dropped doc starts the chain (no original registered) — treat
        # the original slot of that doc as the source anyway (should not happen)
        return None, [], True

    replay_docs = [
        d for d in chain[first_drop_idx + 1:]
        if d.get("kind") == "stage_result" and not _is_dropped(d)
    ]
    return source_doc, replay_docs, True


async def get_session_stages(user_id: str, base_image_id: str) -> dict:
    """
    Latest applied result per styling stage for a styling session rooted at
    `base_image_id`, plus the true CURRENT image of the session (the latest
    stage result overall — critical when items were re-applied out of order).
    Powers the Complete Look screen and session restore.
    """
    db = get_database()
    stages: dict = {}
    current_doc = None
    for stage in STAGE_ORDER:
        doc = await db["images"].find_one(
            {
                "user_id": user_id,
                "kind": "stage_result",
                "stage": stage,
                "root_image_id": base_image_id,
            },
            sort=[("created_at", -1)],
        )
        if doc:
            stages[stage] = {
                "image_id": doc.get("image_id"),
                "tryon_id": doc.get("tryon_id"),
                "url": doc.get("url"),
                "created_at": doc.get("created_at"),
                "metadata": doc.get("metadata", {}),
            }
            if current_doc is None or (doc.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)) > (current_doc.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)):
                current_doc = doc

    current_image = None
    if current_doc:
        current_image = {
            "image_id": current_doc.get("image_id"),
            "url": current_doc.get("url"),
            "stage": current_doc.get("stage"),
            "created_at": current_doc.get("created_at"),
        }
    return {"stages": stages, "current_image": current_image}
