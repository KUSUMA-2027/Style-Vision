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
import io
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
    # Bags
    "item-acc-7": "structured_tote_bag.png",
    "bags": "structured_tote_bag.png",
    "bag": "structured_tote_bag.png",
    "tote": "structured_tote_bag.png",
    "handbag": "structured_tote_bag.png",
}


def _trim_to_alpha_bbox(img: Image.Image) -> Image.Image:
    """Crops transparent padding around the accessory so (0,0)-(w,h) tightly bounds the object."""
    arr = np.array(img)
    if arr.ndim != 3 or arr.shape[2] != 4:
        return img
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 15)
    if len(xs) > 0 and len(ys) > 0:
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        w, h = img.size
        x1 = max(0, x1 - 1)
        y1 = max(0, y1 - 1)
        x2 = min(w, x2 + 2)
        y2 = min(h, y2 + 2)
        return img.crop((x1, y1, x2, y2))
    return img


def _detect_glasses_geometry(acc_img: Image.Image) -> Tuple[float, float, float]:
    """
    Scans the eyewear asset to calculate:
    - lens_spacing (distance between left and right optical centers)
    - optical_center_y_ratio (fractional Y position of the optical line, default ~0.46)
    - optical_center_x_ratio (fractional X position of the bridge, default ~0.50)
    """
    arr = np.array(acc_img)
    alpha = arr[:, :, 3]
    h, w = alpha.shape
    
    left_alpha = alpha[:, :w // 2]
    right_alpha = alpha[:, w // 2:]
    
    ly, lx = np.where(left_alpha > 40)
    ry, rx = np.where(right_alpha > 40)
    
    if len(lx) > 20 and len(rx) > 20:
        rx = rx + (w // 2)
        left_lens_x = float(np.mean(lx))
        left_lens_y = float(np.mean(ly))
        right_lens_x = float(np.mean(rx))
        right_lens_y = float(np.mean(ry))
        
        lens_spacing = right_lens_x - left_lens_x
        opt_y = (left_lens_y + right_lens_y) / (2.0 * h)
        opt_x = (left_lens_x + right_lens_x) / (2.0 * w)
        return lens_spacing, opt_y, opt_x
    
    return float(w * 0.512), 0.46, 0.50


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
    cleaned = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return _trim_to_alpha_bbox(cleaned)


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
                raw_asset = Image.open(asset_path).convert("RGBA")
                return _trim_to_alpha_bbox(raw_asset)

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



    def pt(idx: int) -> np.ndarray:
        if landmarks and idx in landmarks:
            return landmarks[idx]
        return np.array([pw * 0.5, ph * 0.5], dtype=np.float32)

    if landmarks:

        # ── 1. GLASSES & SUNGLASSES ──────────────────────────────────────────
        if "glass" in subcat or subcat == "glasses":
            # Pupil & Eye Landmarks: #468 (left pupil), #473 (right pupil), #33/#133, #263/#362
            # Bridge Landmarks: #168 (nasion bridge)
            p_pupil_l = pt(468) if 468 in landmarks else (pt(33) + pt(133)) / 2.0
            p_pupil_r = pt(473) if 473 in landmarks else (pt(263) + pt(362)) / 2.0
            p_bridge = pt(168)
            
            # Midpoint between the two eyes/pupils
            mid_eye = (p_pupil_l + p_pupil_r) / 2.0
            
            dx = p_pupil_r[0] - p_pupil_l[0]
            dy = p_pupil_r[1] - p_pupil_l[1]
            angle_deg = -math.degrees(math.atan2(dy, dx))
            ipd = math.hypot(dx, dy)
            
            # Detect optical geometry of the eyewear asset
            lens_dist, opt_y_ratio, opt_x_ratio = _detect_glasses_geometry(acc_img)
            acc_w, acc_h = acc_img.size
            
            scale_factor = override_scale if override_scale else 1.0
            # Scale glasses so distance between lens centers matches user's inter-pupillary distance
            target_w = int((ipd * (acc_w / max(10.0, lens_dist))) * scale_factor)
            target_h = int(target_w * (acc_h / acc_w))
            
            resized = acc_img.resize((max(10, target_w), max(10, target_h)), Image.Resampling.LANCZOS)
            rotated = resized.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
            
            # Sub-pixel alignment: map optical center of eyewear directly onto mid_eye
            opt_x = opt_x_ratio * target_w
            opt_y = opt_y_ratio * target_h
            dx_opt = opt_x - (target_w / 2.0)
            dy_opt = opt_y - (target_h / 2.0)
            
            rad = -math.radians(angle_deg)
            rot_opt_x = (rotated.width / 2.0) + (dx_opt * math.cos(rad) - dy_opt * math.sin(rad))
            rot_opt_y = (rotated.height / 2.0) + (dx_opt * math.sin(rad) + dy_opt * math.cos(rad))
            
            cx = mid_eye[0]
            cy = mid_eye[1]
            if override_x is not None:
                cx = override_x * pw
            if override_y is not None:
                cy = override_y * ph
            if override_x is None and offset_x is not None:
                cx += offset_x
            if override_y is None and offset_y is not None:
                cy += offset_y
                
            paste_x = int(cx - rot_opt_x)
            paste_y = int(cy - rot_opt_y)
            canvas.alpha_composite(rotated, (paste_x, paste_y))
            landmark_desc = f"Pupil & Eye Bridge Alignment (IPD {ipd:.1f}px, angle {angle_deg:.1f} deg)"

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
            
            # Hook anchors precisely at the bottom of the earlobe (1.5% face_h below earlobe landmark)
            left_ear_y = int(p_left_ear[1] + (face_h * 0.015))
            right_ear_y = int(p_right_ear[1] + (face_h * 0.015))
            
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
            # Anchor at the throat contour right below chin, embracing the neck with NO extra gap
            p_chin = pt(152)
            p_forehead = pt(10)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            
            # Scan neck and shoulder width
            scale_factor = override_scale if override_scale else 1.0
            sh_span = pose.get("shoulder_span") if (pose and pose.get("has_pose")) else int(face_w * 2.8)
            shoulder_center = pose.get("shoulder_center") if (pose and pose.get("has_pose")) else None
            
            # Natural necklace width: spans across the clavicles / inner collarbones
            target_w = int(min(face_w * 1.18, sh_span * 0.50) * scale_factor)
            target_h = int(target_w * (acc_img.height / acc_img.width))
            
            resized_neck = acc_img.resize((max(20, target_w), max(20, target_h)), Image.Resampling.LANCZOS)
            
            # Angle following the head and neck tilt
            dx = p_right_ear[0] - p_left_ear[0]
            dy = p_right_ear[1] - p_left_ear[1]
            angle_deg = -math.degrees(math.atan2(dy, dx))
            
            if pose and pose.get("has_pose"):
                p_ls = pose.get("left_shoulder")
                p_rs = pose.get("right_shoulder")
                if p_ls is not None and p_rs is not None:
                    dx_sh = p_ls[0] - p_rs[0]
                    dy_sh = p_ls[1] - p_rs[1]
                    angle_sh = -math.degrees(math.atan2(dy_sh, dx_sh))
                    # Natural gravitational hang blending head tilt and torso orientation
                    angle_deg = 0.65 * angle_deg + 0.35 * angle_sh
                    
            rotated_neck = resized_neck.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
            
            # X center follows the midline of the neck between chin and sternum
            cx = p_chin[0]
            if shoulder_center is not None:
                cx = float(p_chin[0] * 0.40 + shoulder_center[0] * 0.60)
                
            # Y position: top of the chain begins right at the throat contour below chin (3.5% of face height)
            # This completely eliminates any floating gap between the chin/neck and the necklace!
            neck_top_y = p_chin[1] + (face_h * 0.035)
            
            if override_x is not None:
                cx = override_x * pw
            if override_y is not None:
                neck_top_y = override_y * ph
            if override_x is None and offset_x is not None:
                cx += offset_x
            if override_y is None and offset_y is not None:
                neck_top_y += offset_y
                
            paste_x = int(cx - (rotated_neck.width / 2.0))
            paste_y = int(neck_top_y)
            canvas.alpha_composite(rotated_neck, (paste_x, paste_y))
            landmark_desc = f"Anatomical Neck & Clavicle Fit (Zero-Gap, angle {angle_deg:.1f} deg)"

        # ── 4. NOSE PIN ──────────────────────────────────────────────────────
        elif "nose" in subcat:
            p_tip = pt(1)
            p_bridge = pt(168)
            p_eye_left = pt(33)   # viewer's left / model's right eye
            p_eye_right = pt(263) # viewer's right / model's left eye
            
            nose_len = math.hypot(p_tip[0] - p_bridge[0], p_tip[1] - p_bridge[1])
            scale_factor = override_scale if override_scale else 1.0
            # Natural diamond nose stud scale: 12% of nose length (subtle, delicate, realistic)
            pin_size = max(8, int(nose_len * 0.12 * scale_factor))
            
            # Scan face yaw / orientation to place pin on the camera-facing nostril
            dist_l = abs(p_tip[0] - p_eye_left[0])
            dist_r = abs(p_tip[0] - p_eye_right[0])
            
            if dist_l < dist_r * 0.65:
                # Head turned towards model's left (viewer's right) -> model's right nostril is prominent
                p_crease = pt(48)
                p_lobule = pt(240) if 240 in landmarks else p_crease
                pierce_x = p_lobule[0] * 0.70 + p_tip[0] * 0.30
                pierce_y = p_lobule[1] * 0.55 + p_crease[1] * 0.45
                nostril_name = "Right Nostril Alar Curve"
            else:
                # Default / model facing forward or turned right -> model's left nostril (#278 / #460)
                p_crease = pt(278)
                p_lobule = pt(460) if 460 in landmarks else p_crease
                pierce_x = p_lobule[0] * 0.70 + p_tip[0] * 0.30
                pierce_y = p_lobule[1] * 0.55 + p_crease[1] * 0.45
                nostril_name = "Left Nostril Alar Curve"
                
            if override_x is not None:
                pierce_x = override_x * pw
            if override_y is not None:
                pierce_y = override_y * ph
            if override_x is None and offset_x is not None:
                pierce_x += offset_x
            if override_y is None and offset_y is not None:
                pierce_y += offset_y
                
            resized_pin = acc_img.resize((pin_size, pin_size), Image.Resampling.LANCZOS)
            paste_x = int(pierce_x - (resized_pin.width / 2.0))
            paste_y = int(pierce_y - (resized_pin.height / 2.0))
            canvas.alpha_composite(resized_pin, (paste_x, paste_y))
            landmark_desc = f"{nostril_name} (Mesh Precision Placement)"

        # ── 7. BAGS (TOTE BAG — HAND-HELD GRIP & HANG) ──────────────────────
        elif any(k in subcat for k in ["bag", "tote", "handbag", "purse"]):
            p_chin = pt(152)
            p_forehead = pt(10)
            p_left_ear = pt(234)
            p_right_ear = pt(454)
            face_h = math.hypot(p_chin[0] - p_forehead[0], p_chin[1] - p_forehead[1])
            face_w = math.hypot(p_right_ear[0] - p_left_ear[0], p_right_ear[1] - p_left_ear[1])
            scale_factor = override_scale if override_scale else 1.0

            # Clean any studio floor artifacts from bag asset
            bag_arr = np.array(acc_img)
            bh = bag_arr.shape[0]
            is_floor = (
                (bag_arr[:, :, 0] > 195)
                & (bag_arr[:, :, 1] > 195)
                & (bag_arr[:, :, 2] > 190)
                & (np.arange(bh)[:, None] > int(bh * 0.88))
            )
            bag_arr[is_floor, 3] = 0
            clean_acc_img = Image.fromarray(bag_arr, "RGBA")

            # Proportion to shoulder span (72% of shoulder span for natural tote fit)
            sh_span = pose.get("shoulder_span", int(face_w * 2.8)) if pose else int(face_w * 2.8)
            target_w = int(sh_span * 0.72 * scale_factor)
            target_h = int(target_w * (clean_acc_img.height / clean_acc_img.width))
            resized_bag = clean_acc_img.resize((max(30, target_w), max(30, target_h)), Image.Resampling.LANCZOS)

            # Choose hand: prefer right_wrist/right_index if on-screen, else left_wrist/left_index
            placed_in_hand = False
            hand_ref_x, hand_ref_y = float(pw * 0.35), float(ph * 0.60)
            if pose and pose.get("has_pose"):
                rw = pose.get("right_wrist")
                ri = pose.get("right_index", rw)
                lw = pose.get("left_wrist")
                li = pose.get("left_index", lw)

                if rw is not None and 0 <= rw[0] <= pw and 0 <= rw[1] <= ph * 0.92:
                    grip_x = float(rw[0] * 0.5 + ri[0] * 0.5) if ri is not None else float(rw[0])
                    grip_y = float(rw[1] * 0.4 + ri[1] * 0.6) if ri is not None else float(rw[1])
                    paste_x = int(grip_x - target_w * 0.45)
                    paste_y = int(grip_y - target_h * 0.05)
                    hand_ref_x, hand_ref_y = grip_x, grip_y
                    placed_in_hand = True
                    landmark_desc = "Right Hand Holding Handle"
                elif lw is not None and 0 <= lw[0] <= pw and 0 <= lw[1] <= ph * 0.92:
                    grip_x = float(lw[0] * 0.5 + li[0] * 0.5) if li is not None else float(lw[0])
                    grip_y = float(lw[1] * 0.4 + li[1] * 0.6) if li is not None else float(lw[1])
                    paste_x = int(grip_x - target_w * 0.55)
                    paste_y = int(grip_y - target_h * 0.05)
                    hand_ref_x, hand_ref_y = grip_x, grip_y
                    placed_in_hand = True
                    landmark_desc = "Left Hand Holding Handle"

            if not placed_in_hand:
                # Hip / Torso side placement for upper-body/bust portraits
                paste_x = min(pw - target_w - 20, int(p_right_ear[0] + face_w * 0.40))
                paste_y = max(0, ph - target_h - 20)
                landmark_desc = "Hand / Hip Bag Placement"

            # Bound inside canvas
            paste_x = max(0, min(pw - target_w, paste_x))
            paste_y = max(0, min(ph - target_h, paste_y))

            # Composite bag onto canvas
            canvas.alpha_composite(resized_bag, (paste_x, paste_y))

            # If placed in hand, blend hand and curled fingers OVER handle strap so she genuinely holds it
            if placed_in_hand:
                try:
                    hx1 = max(0, int(hand_ref_x - face_w * 0.22))
                    hx2 = min(pw, int(hand_ref_x + face_w * 0.22))
                    hy1 = max(0, int(hand_ref_y - face_h * 0.20))
                    hy2 = min(ph, int(hand_ref_y + face_h * 0.20))

                    if (hx2 - hx1) > 10 and (hy2 - hy1) > 10:
                        hand_crop = person_img.convert("RGBA").crop((hx1, hy1, hx2, hy2))
                        hand_mask = Image.new("L", (hx2 - hx1, hy2 - hy1), 0)
                        hm_arr = np.array(hand_mask)
                        cx_h = (hx2 - hx1) // 2
                        cy_h = int((hy2 - hy1) * 0.55)
                        rx = int((hx2 - hx1) * 0.38)
                        ry = int((hy2 - hy1) * 0.38)
                        cv2.ellipse(hm_arr, (cx_h, cy_h), (rx, ry), 0, 0, 360, 255, -1)
                        hm_blurred = cv2.GaussianBlur(hm_arr, (11, 11), 4)
                        canvas.paste(hand_crop, (hx1, hy1), mask=Image.fromarray(hm_blurred, "L"))
                except Exception as e:
                    logger.warning("Hand layering over handle strap skipped: %s", e)

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

    # Generate Close-up Crop: Head & Neck zoom for facial jewelry only
    # Do NOT generate face close-up for bags so the user sees the complete look with bag in hand!
    closeup_result_url = None
    closeup_orig_url = None
    is_bag = any(k in subcat for k in ["bag", "tote", "handbag", "purse"])
    if landmarks and not is_bag:
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
