"""
StyleVision — Virtual Accessory & Jewelry Fitting Service
Uses MediaPipe Face Detection (model_selection=1 for full-body range)
+ MediaPipe Face Mesh (478 landmarks with iris refinement)
+ OpenCV affine transformations for high-precision placement of:
- Glasses & Sunglasses (Eye bridge #168, eye corners #33, #263)
- Earrings (Left earlobe #234, Right earlobe #454)
- Necklaces (Suprasternal notch / neck below chin #152)
- Nose Pins (Nostril ala #278 / #48)
"""
import os
import math
import uuid
import logging
from typing import Tuple, Optional, Dict
import numpy as np
from PIL import Image, ImageOps, ImageDraw
import cv2
from app.utils.face_utils import detect_face_landmarks, detect_pose_landmarks

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ACCESSORY_ASSET_MAP = {
    # Glasses
    "item-acc-1": "aviator_sunglasses.png",
    "glasses_aviator": "aviator_sunglasses.png",
    "glasses_wayfarer": "wayfarer_glasses.png",
    "glasses": "aviator_sunglasses.png",
    # Earrings
    "item-acc-2": "chandelier_earring.png",
    "earrings_chandelier": "chandelier_earring.png",
    "earrings_hoop": "gold_hoop.png",
    "earrings": "chandelier_earring.png",
    # Necklace
    "item-acc-3": "gold_necklace.png",
    "necklace_gold": "gold_necklace.png",
    "necklace": "gold_necklace.png",
    # Nose Pin
    "item-acc-4": "diamond_nose_pin.png",
    "nose_pin": "diamond_nose_pin.png",
    # Bracelet
    "item-acc-5": "tennis_bracelet.png",
    "bracelet": "tennis_bracelet.png",
    "bracelets": "tennis_bracelet.png",
    "tennis_bracelet": "tennis_bracelet.png",
    "bangle": "tennis_bracelet.png",
    "wrist": "tennis_bracelet.png",
    # Ring
    "item-acc-6": "solitaire_diamond_ring.png",
    "rings": "solitaire_diamond_ring.png",
    "ring": "solitaire_diamond_ring.png",
    "diamond_ring": "solitaire_diamond_ring.png",
    "solitaire_ring": "solitaire_diamond_ring.png",
    # Bags
    "item-acc-7": "structured_tote_bag.png",
    "bags": "structured_tote_bag.png",
    "bag": "structured_tote_bag.png",
    "tote": "structured_tote_bag.png",
    "handbag": "structured_tote_bag.png",
}


def _clean_accessory_background(img: Image.Image) -> Image.Image:
    """If image is not already transparent RGBA, remove white/solid background."""
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba, dtype=np.float32)
    h, w = arr.shape[:2]
    # Sample 4 corners
    corners = [arr[0, 0, :3], arr[0, w - 1, :3], arr[h - 1, 0, :3], arr[h - 1, w - 1, :3]]
    bg = np.median(corners, axis=0)
    diff = np.sqrt(np.sum((arr[:, :, :3] - bg) ** 2, axis=-1))
    mask = diff > 28.0
    arr[:, :, 3] = np.where(mask, 255.0, 0.0)
    # Zero out edge pixels (3px borders and 4px bottom) to prevent any border cropping artifacts
    arr[:3, :, 3] = 0.0
    arr[-4:, :, 3] = 0.0
    arr[:, :3, 3] = 0.0
    arr[:, -3:, 3] = 0.0
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _get_accessory_image(
    style_item_id: str,
    subcategory: str,
    custom_image_url: Optional[str] = None,
) -> Optional[Image.Image]:
    """Retrieve or load the accessory RGBA transparent PNG from catalogue or user upload."""
    # 1. Custom image url provided directly
    if custom_image_url:
        clean_path = custom_image_url.lstrip("/").replace("/", os.sep)
        for cand in [
            clean_path,
            os.path.join(settings.upload_dir, os.path.basename(clean_path)),
            os.path.join(settings.upload_dir, "accessories", os.path.basename(clean_path)),
        ]:
            if os.path.exists(cand):
                try:
                    img = Image.open(cand)
                    return _clean_accessory_background(img)
                except Exception as exc:
                    logger.warning("Failed to open custom accessory %s: %s", cand, exc)

    # 2. Check if style_item_id is in uploads/accessories
    acc_upload_dir = os.path.join(settings.upload_dir, "accessories")
    if os.path.exists(acc_upload_dir):
        for f in os.listdir(acc_upload_dir):
            if style_item_id in f:
                try:
                    img = Image.open(os.path.join(acc_upload_dir, f))
                    return _clean_accessory_background(img)
                except Exception:
                    pass

    # 3. Check catalogue assets
    filename = (
        ACCESSORY_ASSET_MAP.get(style_item_id)
        or ACCESSORY_ASSET_MAP.get(subcategory.lower())
    )
    if not filename:
        sub = subcategory.lower()
        if "glass" in sub:
            filename = "aviator_sunglasses.png"
        elif "ear" in sub:
            filename = "chandelier_earring.png"
        elif "neck" in sub:
            filename = "gold_necklace.png"
        elif "nose" in sub:
            filename = "diamond_nose_pin.png"
        elif any(k in sub for k in ["bracelet", "bangle", "wrist", "watch"]):
            filename = "tennis_bracelet.png"
        elif any(k in sub for k in ["ring", "rings"]):
            filename = "solitaire_diamond_ring.png"
        elif any(k in sub for k in ["bag", "tote", "handbag", "purse"]):
            filename = "structured_tote_bag.png"

    if filename:
        for base in [settings.catalogue_dir, os.path.join("backend", "catalogue")]:
            asset_path = os.path.join(base, "accessories", filename)
            if os.path.exists(asset_path):
                return Image.open(asset_path).convert("RGBA")

    logger.warning("Accessory asset '%s' not found for subcategory '%s'.", filename, subcategory)
    return None


def _detect_landmarks_two_stage(np_rgb: np.ndarray) -> Optional[Dict[int, np.ndarray]]:
    """
    Detects 478 face landmarks on both close-up and full-body images using robust
    MediaPipe / OpenCV two-stage geometric projection.
    """
    return detect_face_landmarks(np_rgb)



def synthesize_accessory_tryon(
    person_img: Image.Image,
    style_item_id: str,
    subcategory: str,
    custom_image_url: Optional[str] = None,
    override_x: Optional[float] = None,
    override_y: Optional[float] = None,
    override_scale: Optional[float] = None,
    offset_x: Optional[float] = None,
    offset_y: Optional[float] = None,
) -> Tuple[Image.Image, str, str, Optional[str], Optional[str]]:
    """
    Fits glasses, earrings, necklace, nose pin, bracelet, or tote bag using precision landmarks.
    Returns: (final_rgb, landmark_desc, result_url, closeup_result_url, closeup_orig_url)
    """
    pw, ph = person_img.size
    np_img = np.array(person_img.convert("RGB"))
    subcat = subcategory.lower()
    canvas = person_img.convert("RGBA")
    
    acc_img = _get_accessory_image(style_item_id, subcat, custom_image_url)
    if acc_img is None:
        tryon_id = f"tryon-acc-{uuid.uuid4().hex[:10]}"
        output_filename = f"{tryon_id}.png"
        output_path = os.path.join(settings.upload_dir, "tryon", output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_rgb = canvas.convert("RGB")
        final_rgb.save(output_path, format="PNG")
        return final_rgb, "Fallback", f"/uploads/tryon/{output_filename}", None, None

    landmarks = _detect_landmarks_two_stage(np_img)
    pose = detect_pose_landmarks(np_img)
    landmark_desc = "Facial Landmark Anchor"

    if landmarks:
        def pt(idx):
            return landmarks[idx]

        # ── 1. GLASSES & SUNGLASSES ──────────────────────────────────────────
        if "glass" in subcat or subcat == "glasses":
            # Landmarks: #33 (left outer eye), #263 (right outer eye), #168 (nasion bridge)
            p_left = pt(33)
            p_right = pt(263)
            p_bridge = pt(168)
            
            dx = p_right[0] - p_left[0]
            dy = p_right[1] - p_left[1]
            angle_deg = -math.degrees(math.atan2(dy, dx))
            eye_dist = math.hypot(dx, dy)
            
            scale_factor = override_scale if override_scale else 1.0
            # Width spans across temple-to-temple naturally (calibrated to orbital eye distance)
            target_w = int(eye_dist * 1.62 * scale_factor)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            
            resized = acc_img.resize((max(10, target_w), max(10, target_h)), Image.Resampling.LANCZOS)
            rotated = resized.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
            
            # The bridge saddle sits centered right on the nasion #168
            # Anchor vertical center at the nose bridge so glasses sit at eye level
            cx = p_bridge[0]
            cy = p_bridge[1]
            if override_x is not None:
                cx = override_x * pw
            if override_y is not None:
                cy = override_y * ph
            # Apply manual pixel offsets (only if no normalized override)
            if override_x is None and offset_x is not None:
                cx += offset_x
            if override_y is None and offset_y is not None:
                cy += offset_y
                
            paste_x = int(cx - (rotated.width / 2))
            paste_y = int(cy - (rotated.height / 2))
            canvas.alpha_composite(rotated, (paste_x, paste_y))
            landmark_desc = f"Eye Bridge (Mesh #168, angle {angle_deg:.1f} deg)"

        # ── 2. EARRINGS ──────────────────────────────────────────────────────
        elif "earring" in subcat or subcat == "earrings":
            # Left earlobe #234, Right earlobe #454
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            p_chin = pt(152)
            p_forehead = pt(10)
            
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            scale_factor = override_scale if override_scale else 1.0
            earring_h = int(face_h * 0.32 * scale_factor)
            earring_w = int(earring_h * (acc_img.width / acc_img.height))
            
            resized_earring = acc_img.resize((max(8, earring_w), max(8, earring_h)), Image.Resampling.LANCZOS)
            
            # Hook anchors at the bottom of the earlobe
            left_ear_y = int(p_left_ear[1] + (face_h * 0.04))
            right_ear_y = int(p_right_ear[1] + (face_h * 0.04))
            
            # Left Earring
            lx = int(p_left_ear[0] - (earring_w * 0.5))
            ly = int(left_ear_y)
            canvas.alpha_composite(resized_earring, (lx, ly))
            
            # Right Earring (Mirrored for natural 3D symmetry)
            right_earring = ImageOps.mirror(resized_earring)
            rx = int(p_right_ear[0] - (right_earring.width * 0.5))
            ry = int(right_ear_y)
            canvas.alpha_composite(right_earring, (rx, ry))
            
            landmark_desc = "Earlobes (Mesh #234 & #454)"

        # ── 3. NECKLACE ──────────────────────────────────────────────────────
        elif "necklace" in subcat:
            # Anchor at suprasternal notch / collarbone hollow right below chin
            p_chin = pt(152)
            p_forehead = pt(10)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            
            scale_factor = override_scale if override_scale else 1.0
            # Width spans naturally across collarbones (1.15x face width, not 1.85x)
            target_w = int(face_w * 1.15 * scale_factor)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            
            resized_neck = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)
            
            dx = p_right_ear[0] - p_left_ear[0]
            dy = p_right_ear[1] - p_left_ear[1]
            angle_deg = -math.degrees(math.atan2(dy, dx))
            rotated_neck = resized_neck.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
            
            cx = p_chin[0]
            # Collarbone anchor sits naturally at the suprasternal notch (32% face height below chin)
            cy = p_chin[1] + (face_h * 0.32)
            if override_x is not None:
                cx = override_x * pw
            if override_y is not None:
                cy = override_y * ph
                
            paste_x = int(cx - (rotated_neck.width / 2))
            paste_y = int(cy)
            canvas.alpha_composite(rotated_neck, (paste_x, paste_y))
            landmark_desc = f"Collarbone Notch (Suprasternal #152, angle {angle_deg:.1f} deg)"

        # ── 4. NOSE PIN ──────────────────────────────────────────────────────
        elif "nose" in subcat:
            p_nostril = pt(278) # Left nostril ala
            p_bridge = pt(168)
            p_tip = pt(1)
            
            nose_len = math.hypot(p_tip[0] - p_bridge[0], p_tip[1] - p_bridge[1])
            scale_factor = override_scale if override_scale else 1.0
            pin_size = max(10, int(nose_len * 0.24 * scale_factor))
            
            resized_pin = acc_img.resize((pin_size, pin_size), Image.Resampling.LANCZOS)
            paste_x = int(p_nostril[0] - (resized_pin.width / 2))
            paste_y = int(p_nostril[1] - (resized_pin.height / 2))
            canvas.alpha_composite(resized_pin, (paste_x, paste_y))
            landmark_desc = "Left Nostril Ala (Mesh #278)"

        # ── 5. BRACELET ──────────────────────────────────────────────────────
        elif any(k in subcat for k in ["bracelet", "bangle", "wrist", "watch"]):
            p_chin = pt(152)
            p_forehead = pt(10)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            scale_factor = override_scale if override_scale else 1.0

            if pose and pose.get("has_pose"):
                wrist = pose["left_wrist"]
                elbow = pose["left_elbow"]
                # Compute angle along the forearm
                fdx = wrist[0] - elbow[0]
                fdy = wrist[1] - elbow[1]
                angle_deg = -math.degrees(math.atan2(fdy, fdx)) + 90.0
                
                target_w = int(face_w * 0.36 * scale_factor)
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_br = acc_img.resize((max(15, target_w), max(10, target_h)), Image.Resampling.LANCZOS)
                rotated_br = resized_br.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)

                paste_x = int(wrist[0] - (rotated_br.width / 2))
                paste_y = int(wrist[1] - (rotated_br.height / 2))
                canvas.alpha_composite(rotated_br, (max(0, paste_x), max(0, paste_y)))
                landmark_desc = f"Wrist Anatomy (Pose Landmark #15, angle {angle_deg:.1f} deg)"
            else:
                # Elegant luxury jewelry inset for close-up portraits
                badge_w = min(220, int(pw * 0.32))
                badge_h = int(badge_w * 0.85)
                badge = Image.new("RGBA", (badge_w, badge_h), (18, 14, 28, 220))
                b_draw = ImageDraw.Draw(badge)
                b_draw.rectangle([0, 0, badge_w - 1, badge_h - 1], outline=(218, 165, 32, 230), width=2)
                br_preview = acc_img.resize((int(badge_w * 0.82), int(badge_w * 0.82 * (acc_img.height / acc_img.width))), Image.Resampling.LANCZOS)
                badge.alpha_composite(br_preview, ((badge_w - br_preview.width) // 2, (badge_h - br_preview.height) // 2 - 8))
                canvas.alpha_composite(badge, (pw - badge_w - 24, ph - badge_h - 44))
                landmark_desc = "Luxury Wrist Jewelry Preview"

        # ── 6. RING (SOLITAIRE DIAMOND RING) ─────────────────────────────────
        elif any(k in subcat for k in ["ring", "rings"]):
            p_chin = pt(152)
            p_forehead = pt(10)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            scale_factor = override_scale if override_scale else 1.0

            if pose and pose.get("has_pose"):
                finger = pose["left_index"]
                target_w = max(16, int(face_w * 0.25 * scale_factor))
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_ring = acc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                paste_x = int(finger[0] - (resized_ring.width / 2))
                paste_y = int(finger[1] - (resized_ring.height / 2))
                canvas.alpha_composite(resized_ring, (max(0, paste_x), max(0, paste_y)))

                # Add luxury macro preview badge in bottom-right so the user can see diamond facets
                badge_size = min(220, int(pw * 0.28))
                badge = Image.new("RGBA", (badge_size, badge_size), (18, 14, 28, 225))
                b_draw = ImageDraw.Draw(badge)
                b_draw.rectangle([0, 0, badge_size - 1, badge_size - 1], outline=(218, 165, 32, 230), width=2)
                macro_ring = acc_img.resize((int(badge_size * 0.80), int(badge_size * 0.80 * (acc_img.height / acc_img.width))), Image.Resampling.LANCZOS)
                badge.alpha_composite(macro_ring, ((badge_size - macro_ring.width) // 2, (badge_size - macro_ring.height) // 2 - 8))
                canvas.alpha_composite(badge, (pw - badge_size - 24, ph - badge_size - 44))
                landmark_desc = "Hand & Index Finger (Pose Landmark #19 + Solitaire Macro)"
            else:
                # Portrait macro showcase
                badge_size = min(240, int(pw * 0.35))
                badge = Image.new("RGBA", (badge_size, badge_size), (18, 14, 28, 225))
                b_draw = ImageDraw.Draw(badge)
                b_draw.rectangle([0, 0, badge_size - 1, badge_size - 1], outline=(218, 165, 32, 230), width=2)
                macro_ring = acc_img.resize((int(badge_size * 0.80), int(badge_size * 0.80 * (acc_img.height / acc_img.width))), Image.Resampling.LANCZOS)
                badge.alpha_composite(macro_ring, ((badge_size - macro_ring.width) // 2, (badge_size - macro_ring.height) // 2 - 8))
                canvas.alpha_composite(badge, (pw - badge_size - 24, ph - badge_size - 44))
                landmark_desc = "Solitaire Diamond Macro Showcase"

        # ── 7. BAGS (TOTE BAG) ───────────────────────────────────────────────
        elif any(k in subcat for k in ["bag", "tote", "handbag", "purse"]):
            p_chin = pt(152)
            p_forehead = pt(10)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            scale_factor = override_scale if override_scale else 1.0

            if pose and pose.get("has_pose"):
                # Anatomically proportioned to body shoulder span (approx 70% shoulder span)
                sh_span = pose.get("shoulder_span", int(face_w * 2.8))
                target_w = int(sh_span * 0.70 * scale_factor)
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_bag = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)

                # Hang naturally from the wrist/hand alongside thigh
                wrist = pose["right_wrist"]
                paste_x = int(wrist[0] - (target_w * 0.45))
                paste_y = int(wrist[1] - (target_h * 0.15))
                paste_x = max(0, min(pw - target_w, paste_x))
                paste_y = max(0, min(ph - target_h, paste_y))
                canvas.alpha_composite(resized_bag, (paste_x, paste_y))
                landmark_desc = "Hand / Wrist Hang (Pose Landmark #16)"
            else:
                target_w = int(face_w * 2.2 * scale_factor)
                target_h = int(target_w * (acc_img.height / acc_img.width))
                resized_bag = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)
                paste_x = min(pw - target_w - 20, int(p_right_ear[0] + face_w * 0.40))
                paste_y = max(0, ph - target_h - 30)
                canvas.alpha_composite(resized_bag, (max(0, paste_x), max(0, paste_y)))
                landmark_desc = "Hand / Hip Bag Placement"

        else:
            # Torso / Generic fallback
            target_w = int(pw * 0.35)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            resized_bag = acc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            canvas.alpha_composite(resized_bag, (int(pw * 0.65), int(ph * 0.55)))
            landmark_desc = "Torso / Hip Anchor"

    else:
        logger.warning("No face detected by two-stage MediaPipe. Using anatomical estimate.")
        target_w = int(pw * 0.45)
        target_h = int(target_w * (acc_img.height / acc_img.width))
        resized = acc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, (int(pw * 0.28), int(ph * 0.22)))
        landmark_desc = "Anatomical Head Estimate"

    # Save output
    os.makedirs(os.path.join(settings.upload_dir, "tryon"), exist_ok=True)
    tryon_id = f"tryon-acc-{uuid.uuid4().hex[:10]}"
    output_filename = f"{tryon_id}.png"
    output_path = os.path.join(settings.upload_dir, "tryon", output_filename)
    
    final_rgb = canvas.convert("RGB")
    final_rgb.save(output_path, format="PNG")
    result_url = f"/uploads/tryon/{output_filename}"

    # Generate Close-up Portrait Crop (Head & Neck Zoom)
    closeup_result_url = None
    closeup_orig_url = None
    if landmarks:
        try:
            p_forehead = pt(10)
            p_chin = pt(152)
            p_left_ear = pt(234)
            p_right_ear = pt(454)

            face_w = max(40, int(abs(p_right_ear[0] - p_left_ear[0])))
            face_h = max(50, int(abs(p_chin[1] - p_forehead[1])))
            cx = (p_left_ear[0] + p_right_ear[0]) / 2.0

            # Crop width covers beyond both ears (~2.2x face width)
            crop_w = int(face_w * 2.2)
            # Crop height covers hair top down through collarbones (~2.5x face height)
            crop_h = int(face_h * 2.5)

            x1 = max(0, int(cx - crop_w / 2))
            x2 = min(pw, int(cx + crop_w / 2))
            y1 = max(0, int(p_forehead[1] - face_h * 0.35))
            y2 = min(ph, int(y1 + crop_h))

            if (x2 - x1) > 40 and (y2 - y1) > 40:
                crop_res = final_rgb.crop((x1, y1, x2, y2))
                crop_orig = person_img.convert("RGB").crop((x1, y1, x2, y2))

                closeup_filename = f"{tryon_id}_closeup.png"
                closeup_orig_filename = f"{tryon_id}_orig_closeup.png"

                crop_res.save(os.path.join(settings.upload_dir, "tryon", closeup_filename), format="PNG")
                crop_orig.save(os.path.join(settings.upload_dir, "tryon", closeup_orig_filename), format="PNG")

                closeup_result_url = f"/uploads/tryon/{closeup_filename}"
                closeup_orig_url = f"/uploads/tryon/{closeup_orig_filename}"
        except Exception as e:
            logger.warning("Failed to generate closeup crop: %s", e)
    
    logger.info("Accessory try-on completed: %s -> %s (closeup: %s)", landmark_desc, result_url, closeup_result_url)
    return final_rgb, landmark_desc, result_url, closeup_result_url, closeup_orig_url
