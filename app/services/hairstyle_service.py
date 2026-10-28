"""
StyleVision — Virtual Hairstyle Studio Service
=============================================
Uses MediaPipe FaceMesh / FaceDetection to estimate head orientation (yaw, roll),
forehead anchor, and cranial scale, then overlays and color-tints hairstyle assets.

Key landmarks used:
  #10  — Forehead top / hairline center anchor
  #70  — Left eyebrow inner/mid
  #336 — Right eyebrow inner/mid
  #234 — Left ear / tragus
  #454 — Right ear / tragus
  #152 — Chin bottom
  #1   — Nose tip center
"""
import os
import uuid
import logging
import math
from typing import Tuple, Optional, Dict

import numpy as np
from PIL import Image, ImageOps
import cv2
from app.utils.face_utils import detect_face_landmarks, detect_pose_landmarks

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

HAIRSTYLE_ASSET_MAP = {
    "item-hair-1": "beach_waves.png",
    "item-hair-2": "classic_french_bob.png",
    "item-hair-3": "sleek_high_ponytail.png",
    "item-hair-4": "soft_curls.png",
    "item-hair-5": "platinum_blonde_shag.png",
    "beach_waves.png": "beach_waves.png",
    "classic_french_bob.png": "classic_french_bob.png",
    "sleek_high_ponytail.png": "sleek_high_ponytail.png",
    "soft_curls.png": "soft_curls.png",
    "platinum_blonde_shag.png": "platinum_blonde_shag.png",
    "beach waves": "beach_waves.png",
    "classic french bob": "classic_french_bob.png",
    "sleek high ponytail": "sleek_high_ponytail.png",
    "soft curls": "soft_curls.png",
    "platinum blonde shag": "platinum_blonde_shag.png",
    "long": "beach_waves.png",
    "short": "classic_french_bob.png",
    "updo": "sleek_high_ponytail.png",
    "medium": "soft_curls.png",
    "shag": "platinum_blonde_shag.png",
    "ponytail": "sleek_high_ponytail.png",
    "bob": "classic_french_bob.png",
    "waves": "beach_waves.png",
    "curls": "soft_curls.png",
}

# Calibrated cranial profiles based on anatomical proportions
HAIRSTYLE_PROFILES = {
    "beach_waves.png":          {"top_y": 140, "cx": 385.0, "cw": 385.0, "anchor": "hairline", "y_shift": -4},
    "classic_french_bob.png":   {"top_y": 370, "cx": 383.0, "cw": 440.0, "anchor": "bangs",    "y_shift": -8},
    "sleek_high_ponytail.png":  {"top_y": 340, "cx": 200.0, "cw": 310.0, "anchor": "hairline", "y_shift": -4},
    "soft_curls.png":           {"top_y": 140, "cx": 385.0, "cw": 385.0, "anchor": "hairline", "y_shift": -4},
    "platinum_blonde_shag.png": {"top_y": 260, "cx": 513.0, "cw": 390.0, "anchor": "hairline", "y_shift": -4},
}


def _detect_landmarks_two_stage(np_rgb: np.ndarray) -> Optional[Dict[int, np.ndarray]]:
    """Detect 478 face landmarks on image using MediaPipe / OpenCV geometric projection."""
    return detect_face_landmarks(np_rgb)


def _clean_hairstyle_background(img: Image.Image) -> Image.Image:
    """
    Cleans background and hollows face window from user-uploaded hairstyle photo.
    Works for:
    1. Already transparent PNG wigs (> 2% transparent alpha).
    2. Portrait or model photo wearing the desired hairstyle (face/neck hollowed out).
    3. Flat-lay wig or mannequin photo (background subtracted, central face oval hollowed).
    """
    img_rgba = img.convert("RGBA")
    arr = np.array(img_rgba, dtype=np.float32)
    h, w = arr.shape[:2]

    # 1. Existing transparency
    if (arr[:, :, 3] < 240).sum() > (h * w * 0.02):
        coords = cv2.findNonZero((arr[:, :, 3] > 20).astype(np.uint8))
        if coords is not None:
            bx, by, bw, bh = cv2.boundingRect(coords)
            pad = 2
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(w, bx + bw + pad)
            y2 = min(h, by + bh + pad)
            return img_rgba.crop((x1, y1, x2, y2))
        return img_rgba

    # 2. Try face landmark detection
    rgb = np.array(img.convert("RGB"))
    landmarks = detect_face_landmarks(rgb)

    if landmarks:
        # Perimeter indices along jawline and forehead
        face_contour_indices = [
            10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
            148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
        ]
        face_pts = np.array([landmarks[idx] for idx in face_contour_indices if idx in landmarks], dtype=np.int32)

        # Background detection via perimeter edge sampling
        edge_pixels = []
        step_w = max(1, w // 40)
        step_h = max(1, h // 40)
        for x in range(0, w, step_w):
            edge_pixels.extend([rgb[0, x], rgb[1, x], rgb[-1, x], rgb[-2, x]])
        for y in range(0, h, step_h):
            edge_pixels.extend([rgb[y, 0], rgb[y, 1], rgb[y, -1], rgb[y, -2]])

        edge_arr = np.array(edge_pixels)
        bg_median = np.median(edge_arr, axis=0)
        diff = np.sqrt(np.sum((rgb.astype(np.float32) - bg_median) ** 2, axis=-1))

        hair_mask = np.where(diff > 25.0, 255, 0).astype(np.uint8)

        # Hollow out face window
        if len(face_pts) > 5:
            cv2.fillPoly(hair_mask, [face_pts], 0)

        # Hollow out neck / chest below chin
        p_chin = landmarks.get(152)
        p_left_ear = landmarks.get(234)
        p_right_ear = landmarks.get(454)
        if p_chin is not None and p_left_ear is not None and p_right_ear is not None:
            chin_y = int(p_chin[1])
            neck_box = np.array([
                [int(p_left_ear[0] + 35), chin_y],
                [int(p_right_ear[0] - 35), chin_y],
                [int(p_right_ear[0] - 20), h],
                [int(p_left_ear[0] + 20), h]
            ], dtype=np.int32)
            cv2.fillPoly(hair_mask, [neck_box], 0)

        hair_mask = cv2.GaussianBlur(hair_mask, (5, 5), 1.5)
        arr[:, :, 3] = hair_mask
    else:
        # No face detected (e.g. mannequin wig): perimeter edge subtraction
        edge_pixels = []
        step_w = max(1, w // 40)
        step_h = max(1, h // 40)
        for x in range(0, w, step_w):
            edge_pixels.extend([rgb[0, x], rgb[1, x], rgb[-1, x], rgb[-2, x]])
        for y in range(0, h, step_h):
            edge_pixels.extend([rgb[y, 0], rgb[y, 1], rgb[y, -1], rgb[y, -2]])

        edge_arr = np.array(edge_pixels)
        bg_median = np.median(edge_arr, axis=0)
        diff = np.sqrt(np.sum((rgb.astype(np.float32) - bg_median) ** 2, axis=-1))

        hair_mask = np.where(diff > 28.0, 255, 0).astype(np.uint8)

        # Hollow central face oval
        center_x = w // 2
        center_y = int(h * 0.45)
        oval_w = int(w * 0.22)
        oval_h = int(h * 0.28)
        cv2.ellipse(hair_mask, (center_x, center_y), (oval_w, oval_h), 0, 0, 360, 0, -1)

        hair_mask = cv2.GaussianBlur(hair_mask, (5, 5), 1.5)
        arr[:, :, 3] = hair_mask

    cleaned = Image.fromarray(arr.astype(np.uint8), "RGBA")
    coords = cv2.findNonZero((arr[:, :, 3] > 20).astype(np.uint8))
    if coords is not None:
        bx, by, bw, bh = cv2.boundingRect(coords)
        pad = 2
        x1 = max(0, bx - pad)
        y1 = max(0, by - pad)
        x2 = min(w, bx + bw + pad)
        y2 = min(h, by + bh + pad)
        cleaned = cleaned.crop((x1, y1, x2, y2))

    return cleaned


def _get_or_create_hair_asset(
    style_item_id: str,
    subcategory: Optional[str] = None,
    custom_image_url: Optional[str] = None,
) -> Image.Image:
    """Retrieve hairstyle PNG asset or generate a procedural hairstyle alpha silhouette."""
    # 1. Custom image url provided directly
    if custom_image_url:
        clean_path = custom_image_url.lstrip("/").replace("/", os.sep)
        for cand in [
            clean_path,
            os.path.join(settings.upload_dir, os.path.basename(clean_path)),
            os.path.join(settings.upload_dir, "hairstyles", os.path.basename(clean_path)),
            os.path.join("uploads", "hairstyles", os.path.basename(clean_path)),
        ]:
            if os.path.exists(cand):
                try:
                    img = Image.open(cand)
                    return _clean_hairstyle_background(img)
                except Exception as exc:
                    logger.warning("Failed to open custom hairstyle %s: %s", cand, exc)

    # 2. Check if style_item_id is in uploads/hairstyles
    hair_upload_dir = os.path.join(settings.upload_dir, "hairstyles")
    if os.path.exists(hair_upload_dir):
        for f in os.listdir(hair_upload_dir):
            if style_item_id in f:
                try:
                    img = Image.open(os.path.join(hair_upload_dir, f))
                    return _clean_hairstyle_background(img)
                except Exception:
                    pass

    # 3. Check catalogue assets
    filename = (
        HAIRSTYLE_ASSET_MAP.get(style_item_id)
        or (HAIRSTYLE_ASSET_MAP.get(subcategory.lower()) if subcategory else None)
        or "beach_waves.png"
    )

    for base in [settings.catalogue_dir, os.path.join("backend", "catalogue")]:
        asset_path = os.path.join(base, "hairstyles", filename)
        if os.path.exists(asset_path):
            try:
                img = Image.open(asset_path).convert("RGBA")
                if filename in ("sleek_high_ponytail.png", "classic_french_bob.png"):
                    arr = np.array(img)
                    r = arr[:, :, 0]
                    g = arr[:, :, 1]
                    b = arr[:, :, 2]
                    skin_fringe = (r > 165) & (g > 125) & (b > 105) & (r >= g) & (g >= b)
                    arr[skin_fringe, 3] = 0
                    img = Image.fromarray(arr, "RGBA")
                return img
            except Exception as e:
                logger.warning("Could not read hair asset %s: %s", asset_path, e)

    # If no file on disk, create procedural hairstyle template
    return _generate_procedural_hair(filename)


def _generate_procedural_hair(style_name: str) -> Image.Image:
    """Generates an aesthetic stylized hairstyle overlay with alpha transparency."""
    width, height = 600, 650
    img = np.zeros((height, width, 4), dtype=np.uint8)

    # Center crown at (300, 260)
    if "bob" in style_name or "short" in style_name:
        cv2.ellipse(img, (300, 250), (220, 200), 0, 0, 360, (40, 35, 35, 240), -1)
        cv2.rectangle(img, (80, 220), (520, 390), (40, 35, 35, 240), -1)
        cv2.circle(img, (140, 390), 50, (40, 35, 35, 240), -1)
        cv2.circle(img, (460, 390), 50, (40, 35, 35, 240), -1)
        face_pts = np.array([
            [170, 210], [430, 210], [400, 420], [300, 470], [200, 420]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    elif "updo" in style_name or "ponytail" in style_name:
        cv2.circle(img, (300, 110), 90, (30, 28, 28, 250), -1)
        cv2.ellipse(img, (300, 240), (200, 160), 0, 0, 360, (35, 30, 30, 245), -1)
        face_pts = np.array([
            [175, 200], [425, 200], [390, 400], [300, 440], [210, 400]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    elif "curls" in style_name or "medium" in style_name:
        cv2.ellipse(img, (300, 250), (240, 210), 0, 0, 360, (55, 42, 38, 245), -1)
        cv2.rectangle(img, (70, 220), (530, 480), (55, 42, 38, 245), -1)
        for cx in range(80, 530, 45):
            cv2.circle(img, (cx, 470), 38, (55, 42, 38, 245), -1)
        face_pts = np.array([
            [175, 205], [425, 205], [395, 410], [300, 460], [205, 410]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    else:
        cv2.ellipse(img, (300, 240), (235, 195), 0, 0, 360, (48, 38, 32, 245), -1)
        cv2.rectangle(img, (65, 220), (535, 590), (48, 38, 32, 245), -1)
        for cx in range(80, 530, 50):
            cv2.circle(img, (cx, 580), 45, (48, 38, 32, 245), -1)
        face_pts = np.array([
            [180, 210], [420, 210], [390, 420], [300, 470], [210, 420]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))

    alpha = img[:, :, 3]
    alpha_blurred = cv2.GaussianBlur(alpha, (9, 9), 3)
    img[:, :, 3] = alpha_blurred

    return Image.fromarray(img, mode="RGBA")


def _apply_hair_color(hair_rgba: Image.Image, color_hex: Optional[str]) -> Image.Image:
    """Modulates the hairstyle color using HSV channel replacement while keeping texture/shading."""
    if not color_hex:
        return hair_rgba

    np_rgba = np.array(hair_rgba)
    rgb = np_rgba[:, :, :3]
    alpha = np_rgba[:, :, 3]

    clean_hex = color_hex.lstrip("#")
    if len(clean_hex) != 6:
        return hair_rgba

    tr, tg, tb = int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)

    # Convert target color to HSV
    target_bgr = np.uint8([[[tb, tg, tr]]])
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0, 0]
    target_h, target_s, target_v = float(target_hsv[0]), float(target_hsv[1]), float(target_hsv[2])

    # Convert hair rgb to HSV
    hair_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    hair_hsv = cv2.cvtColor(hair_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Modulate Hue and Saturation
    hair_hsv[:, :, 0] = target_h
    hair_hsv[:, :, 1] = np.clip(hair_hsv[:, :, 1] * 0.4 + target_s * 0.7, 0, 255)

    # Modulate Value (luminance) so black/dark hair stays rich and doesn't leave bright white edges
    target_lum = target_v / 255.0
    hair_hsv[:, :, 2] = np.clip(hair_hsv[:, :, 2] * (0.35 + 0.65 * target_lum), 0, 255)

    tinted_bgr = cv2.cvtColor(hair_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    tinted_rgb = cv2.cvtColor(tinted_bgr, cv2.COLOR_BGR2RGB)

    np_rgba[:, :, :3] = tinted_rgb
    np_rgba[:, :, 3] = alpha
    return Image.fromarray(np_rgba, mode="RGBA")



def _suppress_original_hair(
    person_img: Image.Image,
    pts: Optional[Dict[int, np.ndarray]],
    hair_transformed: np.ndarray,
    paste_x: int,
    paste_y: int,
    hairstyle_filename: Optional[str] = None,
) -> Image.Image:
    """
    Leaves the original photo's real background, lighting, and environment 100% untouched
    without any artificial inpainting or background color distortion.
    """
    return person_img.convert("RGBA")


def synthesize_hairstyle_tryon(
    person_img: Image.Image,
    style_item_id: str,
    color_hex: Optional[str] = None,
    subcategory: Optional[str] = None,
    offset_x: Optional[float] = None,
    offset_y: Optional[float] = None,
    scale_override: Optional[float] = None,
    custom_image_url: Optional[str] = None,
) -> Tuple[Image.Image, str, str, Optional[str], Optional[str]]:
    """
    Fit hairstyle matched to head orientation, skull proportions, and forehead/eyebrow anchor.

    Returns:
        (result_pil, landmark_summary, result_url, closeup_result_url, closeup_orig_url)
    """
    np_rgb = np.array(person_img.convert("RGB"))
    h, w, _ = np_rgb.shape

    pts = _detect_landmarks_two_stage(np_rgb)
    if pts is None or 10 not in pts or 234 not in pts or 454 not in pts:
        logger.warning("[Hairstyle] Landmark detection failed, using proportional head placement.")
        forehead_pt = np.array([w * 0.5, h * 0.28])
        face_cx = float(w * 0.5)
        face_w = float(w * 0.35)
        face_h = float(h * 0.25)
        model_cranial_width = face_w
        eyebrow_y = float(forehead_pt[1] + face_h * 0.2)
        angle_deg = 0.0
        ear_span = face_w
        p_chin = np.array([w * 0.5, h * 0.45])
        landmark_summary = "Proportional head-crown estimate"
    else:
        p_forehead = pts[10]   # Top of forehead hairline
        p_left_ear = pts[234]  # Left tragus
        p_right_ear = pts[454] # Right tragus
        p_chin = pts[152]

        p_l_eyebrow = pts.get(70, p_forehead)
        p_r_eyebrow = pts.get(336, p_forehead)
        eyebrow_y = float(min(p_l_eyebrow[1], p_r_eyebrow[1]))

        # Dynamic Multi-Point Cranial Measurements
        ear_span = float(np.linalg.norm(p_right_ear - p_left_ear))
        zygo_span = float(np.linalg.norm(pts[356] - pts[127])) if 127 in pts and 356 in pts else ear_span
        temple_span = float(np.linalg.norm(pts[284] - pts[54])) if 54 in pts and 284 in pts else ear_span
        model_cranial_width = max(ear_span, zygo_span, temple_span * 1.05)

        face_h = float(np.linalg.norm(p_chin - p_forehead))
        face_cx = float((p_left_ear[0] + p_right_ear[0]) / 2.0)

        dx = p_right_ear[0] - p_left_ear[0]
        dy = p_right_ear[1] - p_left_ear[1]
        angle_deg = float(math.degrees(math.atan2(dy, dx)))

        forehead_pt = p_forehead
        landmark_summary = (
            f"Dynamic Head Fit: width={model_cranial_width:.0f}px, height={face_h:.0f}px "
            f"(roll={angle_deg:.1f}°)"
        )

    # 1. Load hairstyle asset
    hair_asset_pil = _get_or_create_hair_asset(style_item_id, subcategory, custom_image_url)

    # 2. Apply color tint if provided
    hair_asset_pil = _apply_hair_color(hair_asset_pil, color_hex)
    hair_rgba = np.array(hair_asset_pil)

    # 3. Determine style-specific geometry profile
    is_custom = bool(custom_image_url or "custom" in style_item_id)
    if is_custom:
        alpha = hair_rgba[:, :, 3]
        ys, xs = np.where(alpha > 30)
        ah, aw = hair_rgba.shape[:2]
        if len(xs) > 100:
            top_y = float(np.min(ys))
            cx = float(np.median(xs))
            cw = float(np.max(xs) - np.min(xs)) * 0.75
            prof = {"top_y": top_y, "cx": cx, "cw": max(150.0, cw), "anchor": "hairline", "y_shift": -10}
        else:
            prof = {"top_y": int(ah * 0.15), "cx": aw * 0.5, "cw": max(150.0, aw * 0.7), "anchor": "hairline", "y_shift": -10}
        filename = "custom_hair.png"
    else:
        filename = (
            HAIRSTYLE_ASSET_MAP.get(style_item_id)
            or (HAIRSTYLE_ASSET_MAP.get(subcategory.lower()) if subcategory else None)
            or "beach_waves.png"
        )
        prof = HAIRSTYLE_PROFILES.get(
            filename,
            {"top_y": 354, "cx": 792.0, "cw": 420.0, "anchor": "hairline", "y_shift": -14}
        )

    # 4. Scale hairstyle dynamically to model's head cranial width
    ah, aw = hair_rgba.shape[:2]
    scale = model_cranial_width / prof["cw"]
    if scale_override is not None:
        scale = scale * scale_override

    target_w = max(60, int(aw * scale))
    target_h = max(60, int(ah * scale))
    # INTER_AREA downsamples cleanly without sinc-filter ringing or boundary speckles
    hair_resized = cv2.resize(hair_rgba, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # 5. Rotate by head roll angle
    if abs(angle_deg) > 0.5:
        M_rot = cv2.getRotationMatrix2D((target_w / 2, target_h / 2), angle_deg, 1.0)
        cos = np.abs(M_rot[0, 0])
        sin = np.abs(M_rot[0, 1])
        nW = int((target_h * sin) + (target_w * cos))
        nH = int((target_h * cos) + (target_w * sin))
        M_rot[0, 2] += (nW / 2) - target_w / 2
        M_rot[1, 2] += (nH / 2) - target_h / 2
        hair_transformed = cv2.warpAffine(
            hair_resized, M_rot, (nW, nH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
        )
    else:
        hair_transformed = hair_resized

    tw, th = hair_transformed.shape[1], hair_transformed.shape[0]

    # Target anchor y
    if prof.get("anchor") == "bangs":
        anchor_y = eyebrow_y
    else:
        anchor_y = forehead_pt[1]

    paste_x = int(face_cx - (prof["cx"] * scale))
    paste_y = int(anchor_y - (prof["top_y"] * scale) + prof.get("y_shift", 0))

    # Apply manual user offsets if provided
    if offset_x is not None:
        paste_x += int(offset_x)
    if offset_y is not None:
        paste_y += int(offset_y)

    canvas_pil = person_img.convert("RGBA")
    W, H = canvas_pil.size

    # Clean Alpha Composition of New Hairstyle
    hair_pil = Image.fromarray(hair_transformed, "RGBA")

    canvas_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas_overlay.paste(hair_pil, (paste_x, paste_y), mask=hair_pil)

    # 6. Dynamic Face Protection Mask
    # Ensures eyes, nose, mouth, and chin remain 100% natural and never covered by stray overlay
    if pts is not None:
        jaw_indices = [234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323, 454]
        face_poly_pts = [pts[i] for i in jaw_indices if i in pts]
        if 336 in pts and 70 in pts:
            face_poly_pts.append(pts[336])
            face_poly_pts.append(pts[70])

        if len(face_poly_pts) >= 5:
            model_face_mask = np.zeros((H, W), dtype=np.uint8)
            cv2.fillPoly(model_face_mask, [np.array(face_poly_pts, dtype=np.int32)], 255)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            model_face_mask = cv2.erode(model_face_mask, kernel, iterations=1)

            protect_mask = model_face_mask.copy()
            if prof.get("anchor") == "bangs":
                # For fringe bangs, protect only from eyebrows down so bangs stay visible
                protect_mask[0:int(eyebrow_y - 2), :] = 0

            # For ponytail/updo styles, protect the central neck/throat area so ponytail falls over the shoulder
            if "ponytail" in filename or "updo" in filename:
                throat_y = p_chin[1] + face_h * 0.40
                neck_half_w = ear_span * 0.30
                throat_poly = np.array([
                    [face_cx - neck_half_w, p_chin[1] - 4],
                    [face_cx + neck_half_w, p_chin[1] - 4],
                    [face_cx + neck_half_w * 1.15, throat_y],
                    [face_cx - neck_half_w * 1.15, throat_y],
                ], dtype=np.int32)
                throat_mask = np.zeros((H, W), dtype=np.uint8)
                cv2.fillPoly(throat_mask, [throat_poly], 255)
                protect_mask = np.maximum(protect_mask, throat_mask)

            protect_float = cv2.GaussianBlur(protect_mask.astype(np.float32) / 255.0, (11, 11), 4)
            overlay_arr = np.array(canvas_overlay)
            overlay_arr[:, :, 3] = (overlay_arr[:, :, 3].astype(np.float32) * (1.0 - protect_float)).astype(np.uint8)
            canvas_overlay = Image.fromarray(overlay_arr, "RGBA")

    composited = Image.alpha_composite(canvas_pil, canvas_overlay)
    final_pil = composited.convert("RGB")

    # 7. Save output
    tryon_id = f"tryon-hair-{uuid.uuid4().hex[:10]}"
    out_dir = os.path.join(settings.upload_dir, "tryon")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{tryon_id}.png")
    final_pil.save(out_path, "PNG")

    result_url = f"/uploads/tryon/{tryon_id}.png"

    # 8. Generate Close-up Portrait Crop (Head & Hair Zoom)
    closeup_result_url = None
    closeup_orig_url = None
    if pts is not None and 10 in pts and 152 in pts and 234 in pts and 454 in pts:
        try:
            p_forehead = pts[10]
            p_chin = pts[152]
            p_left_ear = pts[234]
            p_right_ear = pts[454]

            crop_face_w = max(40, int(abs(p_right_ear[0] - p_left_ear[0])))
            crop_face_h = max(50, int(abs(p_chin[1] - p_forehead[1])))
            cx = (p_left_ear[0] + p_right_ear[0]) / 2.0

            crop_w = int(crop_face_w * 2.4)
            crop_h = int(crop_face_h * 2.6)

            x1 = max(0, int(cx - crop_w / 2))
            x2 = min(w, int(cx + crop_w / 2))
            y1 = max(0, int(p_forehead[1] - crop_face_h * 0.70))
            y2 = min(h, int(y1 + crop_h))

            if (x2 - x1) > 40 and (y2 - y1) > 40:
                crop_res = final_pil.crop((x1, y1, x2, y2))
                crop_orig = person_img.convert("RGB").crop((x1, y1, x2, y2))

                closeup_filename = f"{tryon_id}_closeup.png"
                closeup_orig_filename = f"{tryon_id}_orig_closeup.png"

                crop_res.save(os.path.join(out_dir, closeup_filename), format="PNG")
                crop_orig.save(os.path.join(out_dir, closeup_orig_filename), format="PNG")

                closeup_result_url = f"/uploads/tryon/{closeup_filename}"
                closeup_orig_url = f"/uploads/tryon/{closeup_orig_filename}"
        except Exception as e:
            logger.warning("Failed to generate hairstyle closeup: %s", e)

    logger.info("[Hairstyle] Try-on completed for %s -> %s (closeup: %s)", style_item_id, result_url, closeup_result_url)
    return final_pil, landmark_summary, result_url, closeup_result_url, closeup_orig_url
