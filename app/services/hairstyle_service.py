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
    "long": "beach_waves.png",
    "short": "classic_french_bob.png",
    "updo": "sleek_high_ponytail.png",
    "medium": "soft_curls.png",
    "shag": "platinum_blonde_shag.png",
    "ponytail": "sleek_high_ponytail.png",
    "bob": "classic_french_bob.png",
    "waves": "beach_waves.png",
}

# Calibrated cranial profiles based on anatomical proportions
HAIRSTYLE_PROFILES = {
    "beach_waves.png":          {"top_y": 140, "cx": 384.5, "cw": 385.0, "margin": 1.18, "anchor": "forehead", "y_shift": -4},
    "soft_curls.png":           {"top_y": 140, "cx": 384.5, "cw": 385.0, "margin": 1.18, "anchor": "forehead", "y_shift": -4},
    "sleek_high_ponytail.png":  {"top_y": 330, "cx": 220.0, "cw": 424.0, "margin": 1.24, "anchor": "forehead", "y_shift": -6},
    "classic_french_bob.png":   {"top_y": 368, "cx": 381.0, "cw": 448.0, "margin": 1.24, "anchor": "eyebrow",  "y_shift": -8},
    "platinum_blonde_shag.png": {"top_y": 254, "cx": 510.0, "cw": 423.0, "margin": 1.20, "anchor": "forehead", "y_shift": 0},
}


def _detect_landmarks_two_stage(np_rgb: np.ndarray) -> Optional[Dict[int, np.ndarray]]:
    """Detect 478 face landmarks on image using MediaPipe / OpenCV geometric projection."""
    return detect_face_landmarks(np_rgb)


def _get_or_create_hair_asset(style_item_id: str, subcategory: Optional[str] = None) -> Image.Image:
    """Retrieve hairstyle PNG asset or generate a procedural hairstyle alpha silhouette."""
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
                # Clean inner hairline fringe (for ponytail and bob styles to prevent cyan/white edge artifacts)
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
) -> Image.Image:
    """
    Trims and hides the person's natural original hair in the background that falls outside
    the new hairstyle silhouette (especially for updos, sleek high ponytails, or short bobs).
    Guarantees:
      - Face (forehead, brows, eyes, nose, cheeks, mouth, jaw, chin) is 100% PROTECTED.
      - Ears, neck column, shoulders, and clothes remain 100% intact.
      - Original hair outside the new hairstyle is smoothly blended into the portrait background.
    """
    orig_bgr = cv2.cvtColor(np.array(person_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    h, w = orig_bgr.shape[:2]

    # 1. Background Reconstruction (Horizontal Studio Gradient)
    strip_w = max(10, int(w * 0.05))
    col_left = cv2.medianBlur(orig_bgr[:, 0:strip_w], 15).mean(axis=1)
    col_right = cv2.medianBlur(orig_bgr[:, max(0, w - strip_w):w], 15).mean(axis=1)
    xs = np.linspace(0, 1, w).reshape(1, w, 1)
    bg_canvas = (1.0 - xs) * col_left.reshape(h, 1, 3) + xs * col_right.reshape(h, 1, 3)
    bg_canvas = np.clip(bg_canvas, 0, 255).astype(np.uint8)

    # 2. Construct Anatomical Protection Mask (Never Modified)
    protected = np.zeros((h, w), dtype=np.uint8)

    if pts is not None and 10 in pts and 152 in pts and 234 in pts and 454 in pts:
        # 2a. Face Oval: 36 standard MediaPipe FaceMesh contour points
        face_oval_idx = [
            10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379,
            378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127,
            162, 21, 54, 103, 67, 109
        ]
        face_pts = [pts[i] for i in face_oval_idx if i in pts]
        if len(face_pts) >= 10:
            face_poly = np.array(face_pts, dtype=np.int32)
            cv2.fillPoly(protected, [face_poly], 255)

        p_forehead = pts[10]
        p_chin = pts[152]
        p_l_ear = pts[234]
        p_r_ear = pts[454]
        face_w = float(np.linalg.norm(p_r_ear - p_l_ear))
        face_h = float(np.linalg.norm(p_chin - p_forehead))
        face_cx = float((p_l_ear[0] + p_r_ear[0]) / 2.0)

        # 2b. Ears
        ear_r = int(face_w * 0.16)
        cv2.circle(protected, (int(p_l_ear[0]), int(p_l_ear[1])), ear_r, 255, -1)
        cv2.circle(protected, (int(p_r_ear[0]), int(p_r_ear[1])), ear_r, 255, -1)

        # 2c. Neck & Torso Protection
        p_l_jaw = pts.get(172, p_l_ear)
        p_r_jaw = pts.get(397, p_r_ear)

        pose = detect_pose_landmarks(cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB))
        if pose and pose.get("has_pose"):
            sh_left = pose["left_shoulder"]
            sh_right = pose["right_shoulder"]
            shoulder_y = float(min(sh_left[1], sh_right[1]))
        else:
            shoulder_y = float(p_chin[1] + face_h * 0.55)

        neck_base_l = [face_cx - face_w * 0.38, shoulder_y]
        neck_base_r = [face_cx + face_w * 0.38, shoulder_y]

        neck_poly = np.array([
            p_l_jaw, p_chin, p_r_jaw, neck_base_r, neck_base_l
        ], dtype=np.int32)
        cv2.fillPoly(protected, [neck_poly], 255)

        # Torso and clothing below shoulder line
        cv2.rectangle(protected, (0, int(shoulder_y)), (w, h), 255, -1)
    else:
        # Fallback when landmarks unavailable
        face_cx = float(w * 0.5)
        face_w = float(w * 0.35)
        shoulder_y = float(h * 0.45)
        cv2.ellipse(protected, (int(w * 0.5), int(h * 0.30)), (int(w * 0.18), int(h * 0.22)), 0, 0, 360, 255, -1)
        cv2.rectangle(protected, (0, int(h * 0.45)), (w, h), 255, -1)

    # 3. New Hairstyle Silhouette
    th, tw = hair_transformed.shape[:2]
    hair_mask = np.zeros((h, w), dtype=np.uint8)
    alpha = hair_transformed[:, :, 3]

    y1 = max(0, paste_y)
    y2 = min(h, paste_y + th)
    x1 = max(0, paste_x)
    x2 = min(w, paste_x + tw)

    ay1 = max(0, -paste_y)
    ay2 = ay1 + (y2 - y1)
    ax1 = max(0, -paste_x)
    ax2 = ax1 + (x2 - x1)

    if y2 > y1 and x2 > x1:
        hair_mask[y1:y2, x1:x2] = alpha[ay1:ay2, ax1:ax2]

    # Dilate new hair silhouette slightly so new hair naturally overlaps the background
    hair_mask_dilated = cv2.dilate(
        hair_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)), iterations=1
    )

    # 4. Candidate Trim Region (Lateral to head/neck, above shoulders)
    head_bbox_mask = np.zeros((h, w), dtype=np.uint8)
    ymin = max(0, paste_y - 35)
    ymax = min(h, int(shoulder_y + 10))
    xmin = max(0, int(face_cx - face_w * 2.2))
    xmax = min(w, int(face_cx + face_w * 2.2))
    head_bbox_mask[ymin:ymax, xmin:xmax] = 255

    # Any pixel in candidate box that is outside protected face/body and outside new hair
    trim_mask = cv2.bitwise_and(head_bbox_mask, cv2.bitwise_not(protected))
    trim_mask = cv2.bitwise_and(trim_mask, cv2.bitwise_not(hair_mask_dilated))

    # 5. Soft feathering for seamless blending
    trim_mask_feathered = cv2.GaussianBlur(trim_mask.astype(np.float32) / 255.0, (17, 17), 5)
    trim_mask_3d = trim_mask_feathered[:, :, np.newaxis]

    # 6. Clean canvas: blend original with background in trim region
    cleaned_bgr = (
        orig_bgr.astype(np.float32) * (1.0 - trim_mask_3d)
        + bg_canvas.astype(np.float32) * trim_mask_3d
    ).astype(np.uint8)

    cleaned_rgba = cv2.cvtColor(cleaned_bgr, cv2.COLOR_BGR2RGBA)
    return Image.fromarray(cleaned_rgba, mode="RGBA")


def synthesize_hairstyle_tryon(
    person_img: Image.Image,
    style_item_id: str,
    color_hex: Optional[str] = None,
    subcategory: Optional[str] = None,
    offset_x: Optional[float] = None,
    offset_y: Optional[float] = None,
    scale_override: Optional[float] = None,
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
        eyebrow_y = float(forehead_pt[1] + face_h * 0.2)
        angle_deg = 0.0
        landmark_summary = "Proportional head-crown estimate"
    else:
        p_forehead = pts[10]   # Top of forehead hairline
        p_left_ear = pts[234]  # Left tragus
        p_right_ear = pts[454] # Right tragus
        p_chin = pts[152]

        p_l_eyebrow = pts.get(70, p_forehead)
        p_r_eyebrow = pts.get(336, p_forehead)
        eyebrow_y = float(min(p_l_eyebrow[1], p_r_eyebrow[1]))

        face_w = float(np.linalg.norm(p_right_ear - p_left_ear))
        face_h = float(np.linalg.norm(p_chin - p_forehead))
        face_cx = float((p_left_ear[0] + p_right_ear[0]) / 2.0)

        dx = p_right_ear[0] - p_left_ear[0]
        dy = p_right_ear[1] - p_left_ear[1]
        angle_deg = float(math.degrees(math.atan2(dy, dx)))

        forehead_pt = p_forehead
        landmark_summary = f"Forehead anchor #10, Ear span #234 <-> #454 (roll={angle_deg:.1f} deg)"

    # 1. Load hairstyle asset
    hair_asset_pil = _get_or_create_hair_asset(style_item_id, subcategory)

    # 2. Apply color tint if provided
    hair_asset_pil = _apply_hair_color(hair_asset_pil, color_hex)
    hair_rgba = np.array(hair_asset_pil)

    # 3. Determine style-specific geometry profile
    filename = (
        HAIRSTYLE_ASSET_MAP.get(style_item_id)
        or (HAIRSTYLE_ASSET_MAP.get(subcategory.lower()) if subcategory else None)
        or "beach_waves.png"
    )
    prof = HAIRSTYLE_PROFILES.get(
        filename,
        {"top_y": 140, "cx": 384.5, "cw": 385.0, "margin": 1.18, "anchor": "forehead", "y_shift": -4}
    )

    # 4. Scale hairstyle to head cranial dimensions
    ah, aw = hair_rgba.shape[:2]
    final_scale = (face_w * prof["margin"]) / prof["cw"]
    if scale_override is not None:
        final_scale = final_scale * scale_override

    target_w = max(60, int(aw * final_scale))
    target_h = max(60, int(ah * final_scale))
    hair_resized = cv2.resize(hair_rgba, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

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
    if prof.get("anchor") == "eyebrow":
        anchor_y = eyebrow_y
    else:
        anchor_y = forehead_pt[1]

    paste_x = int(face_cx - (prof["cx"] * final_scale))
    paste_y = int(anchor_y - (prof["top_y"] * final_scale) + prof.get("y_shift", 0))

    # Apply manual user offsets if provided
    if offset_x is not None:
        paste_x += int(offset_x)
    if offset_y is not None:
        paste_y += int(offset_y)

    # 6. Suppress Original Background Hair
    # Clean/trim any natural hair that falls outside the new hairstyle silhouette,
    # keeping face, ears, neck, shoulders, and clothing 100% untouched.
    canvas_pil = _suppress_original_hair(person_img, pts, hair_transformed, paste_x, paste_y)
    W, H = canvas_pil.size

    # Clean Alpha Composition of New Hairstyle
    hair_pil = Image.fromarray(hair_transformed, "RGBA")

    px = max(-tw + 10, min(W - 10, paste_x))
    py = max(-th + 10, min(H - 10, paste_y))

    canvas_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas_overlay.paste(hair_pil, (px, py), mask=hair_pil)
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
