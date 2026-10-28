"""
StyleVision — Catalogue Router
Reads style items from MongoDB catalogue collection with optional category filtering.
"""
from datetime import datetime, timezone
from typing import Optional
import uuid
import os
import io
from PIL import Image
from fastapi import APIRouter, HTTPException, Query, status, UploadFile, File, Form

from app.models.catalogue import (
    TryOnCategory,
    StyleItemResponse,
    CatalogueListResponse,
)
from app.database import get_database
from app.config import get_settings
from app.utils.file_utils import validate_and_read_upload
from app.services.accessory_service import _clean_accessory_background

router = APIRouter(prefix="/api/v1/catalogue", tags=["Style Catalogue"])
settings = get_settings()


def _doc_to_response(doc: dict) -> StyleItemResponse:
    """Convert a MongoDB document to StyleItemResponse, safely."""
    cat = doc.get("category")
    if isinstance(cat, str):
        cat = TryOnCategory(cat)
    return StyleItemResponse(
        item_id=doc["item_id"],
        name=doc["name"],
        category=cat,
        subcategory=doc.get("subcategory"),
        description=doc.get("description"),
        thumbnail=doc.get("thumbnail"),
        tags=doc.get("tags", []),
        color=doc.get("color"),
        is_active=doc.get("is_active", True),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=doc.get("updated_at"),
    )


@router.get(
    "",
    response_model=CatalogueListResponse,
    summary="List available catalogue style items",
)
async def list_catalogue(
    category: Optional[TryOnCategory] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only return active items"),
):
    """Retrieve style items from MongoDB with optional category filtering."""
    db = get_database()
    col = db["catalogue"]

    query: dict = {}
    if active_only:
        query["is_active"] = True
    if category:
        query["category"] = category.value

    cursor = col.find(query).sort("name", 1)
    results = []
    async for doc in cursor:
        results.append(_doc_to_response(doc))

    # If MongoDB catalogue is empty or missing thumbnails, seed/update them
    if not results or not any(getattr(d, "thumbnail", None) for d in results):
        await _seed_catalogue(col)
        cursor2 = col.find(query).sort("name", 1)
        results = []
        async for doc in cursor2:
            results.append(_doc_to_response(doc))

    return CatalogueListResponse(items=results, total=len(results), category=category)


@router.get(
    "/{item_id}",
    response_model=StyleItemResponse,
    summary="Get style item by ID",
)
async def get_catalogue_item(item_id: str):
    """Fetch details of a specific style item from MongoDB."""
    db = get_database()
    col = db["catalogue"]

    doc = await col.find_one({"item_id": item_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Style item '{item_id}' not found.",
        )
    return _doc_to_response(doc)


@router.post(
    "/upload-accessory",
    response_model=StyleItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload your own accessory photograph",
)
async def upload_custom_accessory(
    file: UploadFile = File(...),
    name: str = Form("My Accessory"),
    subcategory: str = Form("glasses"),
    color: Optional[str] = Form(None),
):
    """
    Upload a photo of your own accessory (sunglasses, earrings, necklace, nose pin).
    Automatically validates image, cleans background for transparency, and adds to catalogue.
    """
    raw_bytes, extension = await validate_and_read_upload(file)
    acc_dir = os.path.join(settings.upload_dir, "accessories")
    os.makedirs(acc_dir, exist_ok=True)

    try:
        raw_img = Image.open(io.BytesIO(raw_bytes))
        clean_img = _clean_accessory_background(raw_img)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to process accessory image: {exc}",
        )

    safe_name = f"acc_{uuid.uuid4().hex[:10]}.png"
    save_path = os.path.join(acc_dir, safe_name)
    clean_img.save(save_path, format="PNG")
    image_url = f"/uploads/accessories/{safe_name}"

    item_id = f"item-acc-custom-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    sub = subcategory.lower().strip()
    if sub not in ("glasses", "earrings", "necklace", "nose_pin", "bags"):
        sub = "glasses"

    doc = {
        "item_id": item_id,
        "name": name.strip(),
        "category": "accessories",
        "subcategory": sub,
        "description": f"Custom user-uploaded {sub}",
        "thumbnail": image_url,
        "tags": ["custom", sub],
        "color": color or "#FFD700",
        "is_active": True,
        "is_custom": True,
        "created_at": now,
        "updated_at": None,
    }
    db = get_database()
    await db["catalogue"].insert_one(doc)

    return _doc_to_response(doc)


@router.delete(
    "/{item_id}",
    summary="Remove a style item from the catalogue",
)
async def delete_catalogue_item(item_id: str):
    """Permanently remove an item from MongoDB catalogue and disk."""
    db = get_database()
    col = db["catalogue"]
    item = await col.find_one({"item_id": item_id})
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Style item '{item_id}' not found.",
        )
    thumb = item.get("thumbnail")
    if thumb and "uploads" in thumb:
        file_path = os.path.join(settings.upload_dir, "accessories", os.path.basename(thumb))
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
    await col.delete_one({"item_id": item_id})
    return {
        "message": f"Style item '{item_id}' successfully removed from catalogue.",
        "deleted_id": item_id,
    }


async def _seed_catalogue(col):
    """Seed the MongoDB catalogue with the initial style items."""
    now = datetime.now(timezone.utc)
    items = [
        # ── Outfits ────────────────────────────────────────────────────────────
        {
            "item_id": "item-outfit-1",
            "name": "Slim-Fit Velvet Blazer",
            "category": "outfit",
            "subcategory": "Formal",
            "description": "Tailored midnight blue velvet evening blazer with satin lapels.",
            "thumbnail": "/catalogue/outfits/velvet_blazer.png",
            "tags": ["formal", "blazer", "evening", "velvet"],
            "color": "#1A237E",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-outfit-2",
            "name": "Silk Evening Gown",
            "category": "outfit",
            "subcategory": "Evening",
            "description": "Floor-length burgundy mulberry silk gown with pleated accents.",
            "thumbnail": "/catalogue/outfits/crimson_silk_gown.png",
            "tags": ["evening", "dress", "silk", "burgundy"],
            "color": "#880E4F",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-outfit-3",
            "name": "Casual Denim Jacket",
            "category": "outfit",
            "subcategory": "Streetwear",
            "description": "Stonewashed classic blue denim trucker jacket.",
            "thumbnail": "/catalogue/outfits/denim_jacket.png",
            "tags": ["casual", "streetwear", "denim"],
            "color": "#1565C0",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-outfit-4",
            "name": "Traditional Embroidered Kurta",
            "category": "outfit",
            "subcategory": "Ethnic",
            "description": "Intricately embroidered Indian kurta in rich crimson silk.",
            "thumbnail": "/catalogue/outfits/embroidered_kurta.png",
            "tags": ["ethnic", "traditional", "kurta", "indian"],
            "color": "#B71C1C",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-outfit-6",
            "name": "Puffer Winter Coat",
            "category": "outfit",
            "subcategory": "Outerwear",
            "description": "Quilted matte-black puffer coat with hood.",
            "thumbnail": None,
            "tags": ["outerwear", "winter", "puffer"],
            "color": "#212121",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-outfit-7",
            "name": "Classic Blue Denim Jeans",
            "category": "outfit",
            "subcategory": "Bottom",
            "description": "High-waisted straight leg classic indigo blue denim jeans.",
            "thumbnail": "/catalogue/outfits/classic_blue_jeans.png",
            "tags": ["bottom", "jeans", "denim", "pants"],
            "color": "#283593",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        # ── Accessories ────────────────────────────────────────────────────────
        {
            "item_id": "item-acc-1",
            "name": "Aviator Sunglasses",
            "category": "accessories",
            "subcategory": "glasses",
            "description": "Classic metallic frame sunglasses with polarized UV400 lenses.",
            "thumbnail": "/catalogue/accessories/aviator_sunglasses.png",
            "tags": ["glasses", "sunglasses", "aviator"],
            "color": "#212121",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-acc-2",
            "name": "Emerald Chandelier Earrings",
            "category": "accessories",
            "subcategory": "earrings",
            "description": "Art-deco chandelier drop earrings with emerald crystals.",
            "thumbnail": "/catalogue/accessories/chandelier_earring.png",
            "tags": ["jewelry", "earrings", "emerald"],
            "color": "#004D40",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-acc-3",
            "name": "Layered Gold Necklace",
            "category": "accessories",
            "subcategory": "necklace",
            "description": "18k gold vermeil triple-layer chain necklace.",
            "thumbnail": "/catalogue/accessories/gold_necklace.png",
            "tags": ["jewelry", "necklace", "gold"],
            "color": "#FFD700",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-acc-4",
            "name": "Crystal Nose Pin",
            "category": "accessories",
            "subcategory": "nose_pin",
            "description": "Delicate clear crystal stud nose pin, titanium post.",
            "thumbnail": "/catalogue/accessories/diamond_nose_pin.png",
            "tags": ["nose pin", "stud", "crystal"],
            "color": "#FFFFFF",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-acc-7",
            "name": "Structured Tote Bag",
            "category": "accessories",
            "subcategory": "bags",
            "description": "Minimalist structured vegan leather tote in camel.",
            "thumbnail": "/catalogue/accessories/structured_tote_bag.png",
            "tags": ["bags", "tote", "leather", "camel"],
            "color": "#C19A6B",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        # ── Makeup ─────────────────────────────────────────────────────────────
        {
            "item_id": "item-mu-1",
            "name": "Ruby Velvet Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Bold true-red lipstick with creamy satin finish.",
            "thumbnail": None,
            "tags": ["lipstick", "red", "satin"],
            "color": "#BA000D",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-2",
            "name": "Smoky Charcoal Eyeshadow",
            "category": "makeup",
            "subcategory": "eyeshadow",
            "description": "Intense matte charcoal eyeshadow for smoky eye looks.",
            "thumbnail": None,
            "tags": ["eyeshadow", "smoky", "charcoal"],
            "color": "#37474F",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-3",
            "name": "Rosy Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Sheer pink shimmer blush for a natural flush.",
            "thumbnail": None,
            "tags": ["blush", "pink", "shimmer"],
            "color": "#F48FB1",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-4",
            "name": "Dusty Rose Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Muted rose-mauve matte lipstick for an everyday look.",
            "thumbnail": None,
            "tags": ["lipstick", "rose", "matte"],
            "color": "#C2818A",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-5",
            "name": "Amethyst Eyeshadow",
            "category": "makeup",
            "subcategory": "eyeshadow",
            "description": "Rich purple metallic eyeshadow for evening glam.",
            "thumbnail": None,
            "tags": ["eyeshadow", "purple", "metallic"],
            "color": "#7B1FA2",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-6",
            "name": "Champagne Gold Shimmer",
            "category": "makeup",
            "subcategory": "eyeshadow",
            "description": "Luminous warm champagne gold eyeshadow with delicate metallic micro-sparkle.",
            "thumbnail": None,
            "tags": ["eyeshadow", "gold", "shimmer", "metallic"],
            "color": "#D4AF37",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-7",
            "name": "Rose Gold Sunset",
            "category": "makeup",
            "subcategory": "eyeshadow",
            "description": "Romantic rose gold pearlescent eyeshadow for natural daytime elegance.",
            "thumbnail": None,
            "tags": ["eyeshadow", "rose gold", "shimmer", "pink"],
            "color": "#B76E79",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-8",
            "name": "Burgundy Merlot Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Deep sultry merlot wine lipstick with rich satin intensity.",
            "thumbnail": None,
            "tags": ['lipstick', 'wine', 'burgundy', 'satin'],
            "color": "#6A1B29",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-9",
            "name": "Warm Peach Nude Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Velvety soft warm peachy-nude lipstick for natural everyday elegance.",
            "thumbnail": None,
            "tags": ['lipstick', 'peach', 'nude', 'matte'],
            "color": "#C58369",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-10",
            "name": "Sunset Coral Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Vibrant fiery warm coral orange lipstick with luminous shine.",
            "thumbnail": None,
            "tags": ['lipstick', 'coral', 'orange', 'glossy'],
            "color": "#E64A19",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-11",
            "name": "Plum Noir Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Bold gothic mulberry plum matte lipstick with dramatic depth.",
            "thumbnail": None,
            "tags": ['lipstick', 'plum', 'dark', 'matte'],
            "color": "#4A154B",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-12",
            "name": "Terracotta Spice Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Warm earthy cinnamon brick-red lipstick with smooth satin finish.",
            "thumbnail": None,
            "tags": ['lipstick', 'terracotta', 'spice', 'satin'],
            "color": "#A04030",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-13",
            "name": "Hot Fuchsia Glam Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Electric radiant berry fuchsia lipstick with brilliant luster.",
            "thumbnail": None,
            "tags": ['lipstick', 'fuchsia', 'pink', 'glossy'],
            "color": "#D81B60",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-14",
            "name": "Chocolate Mocha Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Rich 90s-inspired warm toffee chocolate brown matte lipstick.",
            "thumbnail": None,
            "tags": ['lipstick', 'brown', 'mocha', 'matte'],
            "color": "#7B3F28",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-15",
            "name": "Petal Pink Sheer Lipstick",
            "category": "makeup",
            "subcategory": "lipstick",
            "description": "Romantic fresh cherry blossom pink sheer satin lipstick.",
            "thumbnail": None,
            "tags": ['lipstick', 'pink', 'petal', 'satin'],
            "color": "#F06292",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-16",
            "name": "Golden Peach Nectar Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Warm luminous sun-kissed golden peach blush with delicate radiance.",
            "thumbnail": None,
            "tags": ['blush', 'peach', 'golden', 'satin'],
            "color": "#FF8A65",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-17",
            "name": "Tropical Coral Flush Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Fresh vibrant tropical coral blush for an energetic awake look.",
            "thumbnail": None,
            "tags": ['blush', 'coral', 'matte'],
            "color": "#FA6E59",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-18",
            "name": "Spiced Berry Flush Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Deep contouring mulberry berry flush for sultry cheekbone definition.",
            "thumbnail": None,
            "tags": ['blush', 'berry', 'plum', 'satin'],
            "color": "#AD1457",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-19",
            "name": "Luminous Apricot Glow Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Soft champagne golden apricot blush with glass-skin dewy finish.",
            "thumbnail": None,
            "tags": ['blush', 'apricot', 'glow', 'glossy'],
            "color": "#FFB74D",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-20",
            "name": "Dusty Mauve Orchid Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Sophisticated cool-toned muted rose-mauve blush.",
            "thumbnail": None,
            "tags": ['blush', 'mauve', 'rose', 'matte'],
            "color": "#BA68C8",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-21",
            "name": "Sunkissed Bronze Glow Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "Warm terracotta bronzing blush combining contour warmth and cheek glow.",
            "thumbnail": None,
            "tags": ['blush', 'bronze', 'terracotta', 'satin'],
            "color": "#C26D45",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-22",
            "name": "Crimson Apple Flushed Blush",
            "category": "makeup",
            "subcategory": "blush",
            "description": "High-fashion flushed rosy apple cheek tint for an editorial finish.",
            "thumbnail": None,
            "tags": ['blush', 'crimson', 'apple', 'matte'],
            "color": "#D32F2F",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-23",
            "name": "Jet Black Volume Lashes",
            "category": "makeup",
            "subcategory": "eyelashes",
            "description": "Dense volumizing carbon black false lashes with curved fiber definition.",
            "thumbnail": None,
            "tags": ['eyelashes', 'lashes', 'mascara', 'black', 'volume'],
            "color": "#0D0D0D",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-24",
            "name": "Wispy Charcoal Flutter Lashes",
            "category": "makeup",
            "subcategory": "eyelashes",
            "description": "Soft feathery natural daytime lash fringe with gentle winged curl.",
            "thumbnail": None,
            "tags": ['eyelashes', 'charcoal', 'wispy', 'natural'],
            "color": "#2B2B2B",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-25",
            "name": "Espresso Brown Soft Lashes",
            "category": "makeup",
            "subcategory": "eyelashes",
            "description": "Warm chocolate espresso brown lashes for effortless natural beauty.",
            "thumbnail": None,
            "tags": ['eyelashes', 'brown', 'espresso', 'natural'],
            "color": "#3B2219",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-26",
            "name": "Midnight Blue Accent Lashes",
            "category": "makeup",
            "subcategory": "eyelashes",
            "description": "Deep midnight indigo accent lashes with subtle metallic eye-brightening sheen.",
            "thumbnail": None,
            "tags": ['eyelashes', 'blue', 'indigo', 'accent'],
            "color": "#101C38",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-27",
            "name": "Burgundy Plum Dramatic Lashes",
            "category": "makeup",
            "subcategory": "eyelashes",
            "description": "Rich dark wine-tinted evening falsies for sultry eye glam.",
            "thumbnail": None,
            "tags": ['eyelashes', 'plum', 'burgundy', 'dramatic'],
            "color": "#3E1226",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-28",
            "name": "Smoky Cat-Eye Wing Lashes",
            "category": "makeup",
            "subcategory": "eyelashes",
            "description": "Flirty elongated winged outer cat-eye lashes with defined tightline base.",
            "thumbnail": None,
            "tags": ['eyelashes', 'cat-eye', 'winged', 'falsies'],
            "color": "#1A1817",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-29",
            "name": "Emerald Jewel Eyeshadow",
            "category": "makeup",
            "subcategory": "eyeshadow",
            "description": "Deep metallic emerald jewel eyeshadow with rich chromatic depth.",
            "thumbnail": None,
            "tags": ['eyeshadow', 'green', 'emerald', 'metallic'],
            "color": "#004D40",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-mu-30",
            "name": "Bronze Goddess Eyeshadow",
            "category": "makeup",
            "subcategory": "eyeshadow",
            "description": "Warm radiant copper bronze shimmer eyeshadow for sunlit glamour.",
            "thumbnail": None,
            "tags": ['eyeshadow', 'bronze', 'copper', 'metallic'],
            "color": "#8D6E63",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        # ── Hairstyles ─────────────────────────────────────────────────────────
        {
            "item_id": "item-hair-1",
            "name": "Beach Waves",
            "category": "hairstyle",
            "subcategory": "long",
            "description": "Cascading textured beach waves with natural volume.",
            "thumbnail": "/catalogue/hairstyles/beach_waves.png",
            "tags": ["hair", "waves", "long"],
            "color": "#4E342E",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-2",
            "name": "Classic French Bob",
            "category": "hairstyle",
            "subcategory": "short",
            "description": "Jawline-grazing chic bob cut with soft bevelled ends.",
            "thumbnail": "/catalogue/hairstyles/classic_french_bob.png",
            "tags": ["hair", "bob", "short"],
            "color": "#1C1C1E",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-3",
            "name": "Sleek High Ponytail",
            "category": "hairstyle",
            "subcategory": "updo",
            "description": "Polished high ponytail with flat-ironed roots.",
            "thumbnail": "/catalogue/hairstyles/sleek_high_ponytail.png",
            "tags": ["hair", "ponytail", "updo"],
            "color": "#212121",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-4",
            "name": "Soft Curls",
            "category": "hairstyle",
            "subcategory": "medium",
            "description": "Defined barrel-curl ringlets with medium length.",
            "thumbnail": "/catalogue/hairstyles/soft_curls.png",
            "tags": ["hair", "curls", "medium"],
            "color": "#6D4C41",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-5",
            "name": "Platinum Blonde Shag",
            "category": "hairstyle",
            "subcategory": "medium",
            "description": "Textured shag cut in platinum blonde with curtain bangs.",
            "thumbnail": "/catalogue/hairstyles/platinum_blonde_shag.png",
            "tags": ["hair", "blonde", "shag", "bangs"],
            "color": "#F5F5DC",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-6",
            "name": "Voluminous Curls",
            "category": "hairstyle",
            "subcategory": "medium",
            "description": "Bouncy cascading corkscrew curls with full crown volume.",
            "thumbnail": "/catalogue/hairstyles/voluminous_curls.png",
            "tags": ['hair', 'curls', 'medium', 'volume'],
            "color": "#3B2A22",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-7",
            "name": "Curtain Bangs Lob",
            "category": "hairstyle",
            "subcategory": "medium",
            "description": "Long layered bob featuring face-framing curtain bangs.",
            "thumbnail": "/catalogue/hairstyles/curtain_bangs_lob.png",
            "tags": ['hair', 'bangs', 'lob', 'medium'],
            "color": "#4A3B32",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-8",
            "name": "Textured Pixie Cut",
            "category": "hairstyle",
            "subcategory": "short",
            "description": "Chic tapered pixie cut with piecey textured crown layers.",
            "thumbnail": "/catalogue/hairstyles/textured_pixie_cut.png",
            "tags": ['hair', 'pixie', 'short', 'chic'],
            "color": "#2C201C",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-9",
            "name": "Hollywood Glamour Waves",
            "category": "hairstyle",
            "subcategory": "long",
            "description": "Vintage red-carpet sculpted S-waves with lustrous shine.",
            "thumbnail": "/catalogue/hairstyles/glamour_hollywood_waves.png",
            "tags": ['hair', 'waves', 'long', 'glamour', 'vintage'],
            "color": "#8D5B4C",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-10",
            "name": "Messy High Bun Updo",
            "category": "hairstyle",
            "subcategory": "updo",
            "description": "Effortlessly chic textured topknot with soft tendril flyaways.",
            "thumbnail": "/catalogue/hairstyles/messy_bun_updo.png",
            "tags": ['hair', 'updo', 'bun', 'messy'],
            "color": "#2A2421",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-11",
            "name": "Caramel Balayage Layers",
            "category": "hairstyle",
            "subcategory": "long",
            "description": "Sun-drenched long cascading layers with warm caramel dimension.",
            "thumbnail": "/catalogue/hairstyles/caramel_balayage_layers.png",
            "tags": ['hair', 'balayage', 'long', 'layers', 'caramel'],
            "color": "#8F5D3A",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-12",
            "name": "Blunt Cut Bob",
            "category": "hairstyle",
            "subcategory": "short",
            "description": "Precision razor-sharp chin-length bob with clean geometric edges.",
            "thumbnail": "/catalogue/hairstyles/blunt_cut_bob.png",
            "tags": ['hair', 'bob', 'short', 'blunt'],
            "color": "#1B1715",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-13",
            "name": "Sleek Silk Straight",
            "category": "hairstyle",
            "subcategory": "long",
            "description": "Ultra-glossy waist-length flat-ironed silk straight hair.",
            "thumbnail": "/catalogue/hairstyles/sleek_straight_long.png",
            "tags": ['hair', 'straight', 'long', 'sleek', 'glossy'],
            "color": "#1C1918",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-14",
            "name": "Afro Volume Coils",
            "category": "hairstyle",
            "subcategory": "medium",
            "description": "Defined springy natural coils celebrating glorious spherical volume.",
            "thumbnail": "/catalogue/hairstyles/afro_volume_coils.png",
            "tags": ['hair', 'afro', 'coils', 'natural', 'volume'],
            "color": "#201A18",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
        {
            "item_id": "item-hair-15",
            "name": "Boho Crown Braid",
            "category": "hairstyle",
            "subcategory": "updo",
            "description": "Romantic halo crown milkmaid braid with soft ethereal texture.",
            "thumbnail": "/catalogue/hairstyles/boho_crown_braid.png",
            "tags": ['hair', 'braid', 'updo', 'boho', 'crown'],
            "color": "#3D2E24",
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        },
    ]

    for item in items:
        await col.update_one({"item_id": item["item_id"]}, {"$set": item}, upsert=True)

    print(f"[StyleVision DB] Seeded/updated {len(items)} catalogue items into MongoDB.")
