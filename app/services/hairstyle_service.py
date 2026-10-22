"""
StyleVision — Virtual Hairstyle Studio Service
=============================================
Uses MediaPipe FaceMesh / FaceDetection to estimate head orientation (yaw, roll),
forehead anchor, and cranial scale, then overlays and color-tints hairstyle assets.

Key landmarks used:
  #10  — Forehead top / hairline center anchor
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
from app.utils.face_utils import detect_face_landmarks

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

HAIRSTYLE_PROFILES = {
    "beach_waves.png":          {"top_y": 141, "cx": 389.0, "cw": 464.0, "margin": 1.15, "y_adj": 10},
    "classic_french_bob.png":   {"top_y": 330, "cx": 383.5, "cw": 462.5, "margin": 1.12, "y_adj": -15},
    "platinum_blonde_shag.png": {"top_y": 271, "cx": 524.2, "cw": 523.0, "margin": 1.18, "y_adj": -10},
    "sleek_high_ponytail.png":  {"top_y": 330, "cx": 199.5, "cw": 304.0, "margin": 1.10, "y_adj": 20},
    "soft_curls.png":           {"top_y": 141, "cx": 389.0, "cw": 464.0, "margin": 1.15, "y_adj": 10},
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
                return Image.open(asset_path).convert("RGBA")
            except Exception as e:
                logger.warning("Could not read hair asset %s: %s", asset_path, e)

    # If no file on disk, create procedural hairstyle template
    return _generate_procedural_hair(filename)


def _generate_procedural_hair(style_name: str) -> Image.Image:
    """Generates an aesthetic stylized hairstyle overlay with alpha transparency."""
    width, height = 600, 650
    img = np.zeros((height, width, 4), dtype=np.uint8)

    # Center crown at (300, 260)
    # Hair silhouette drawing based on style
    if "bob" in style_name or "short" in style_name:
        # Chic bob: rounded cap over head + sleek jawline sides
        cv2.ellipse(img, (300, 250), (220, 200), 0, 0, 360, (40, 35, 35, 240), -1)
        cv2.rectangle(img, (80, 220), (520, 390), (40, 35, 35, 240), -1)
        # Soften edges
        cv2.circle(img, (140, 390), 50, (40, 35, 35, 240), -1)
        cv2.circle(img, (460, 390), 50, (40, 35, 35, 240), -1)
        # Hollow out face window
        face_pts = np.array([
            [170, 210], [430, 210], [400, 420], [300, 470], [200, 420]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    elif "updo" in style_name or "ponytail" in style_name:
        # Sleek high ponytail: high bun/tail + sleek pulled back crown
        cv2.circle(img, (300, 110), 90, (30, 28, 28, 250), -1)  # Ponytail bulb
        cv2.ellipse(img, (300, 240), (200, 160), 0, 0, 360, (35, 30, 30, 245), -1)
        # Face cutout
        face_pts = np.array([
            [175, 200], [425, 200], [390, 400], [300, 440], [210, 400]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    elif "curls" in style_name or "medium" in style_name:
        # Voluminous curls
        cv2.ellipse(img, (300, 250), (240, 210), 0, 0, 360, (55, 42, 38, 245), -1)
        cv2.rectangle(img, (70, 220), (530, 480), (55, 42, 38, 245), -1)
        for cx in range(80, 530, 45):
            cv2.circle(img, (cx, 470), 38, (55, 42, 38, 245), -1)
        # Face cutout
        face_pts = np.array([
            [175, 205], [425, 205], [395, 410], [300, 460], [205, 410]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))
    else:
        # Beach waves (long cascading waves)
        cv2.ellipse(img, (300, 240), (235, 195), 0, 0, 360, (48, 38, 32, 245), -1)
        cv2.rectangle(img, (65, 220), (535, 590), (48, 38, 32, 245), -1)
        # Bottom strand waves
        for cx in range(80, 530, 50):
            cv2.circle(img, (cx, 580), 45, (48, 38, 32, 245), -1)
        # Face cutout
        face_pts = np.array([
            [180, 210], [420, 210], [390, 420], [300, 470], [210, 420]
        ], np.int32)
        cv2.fillPoly(img, [face_pts], (0, 0, 0, 0))

    # Apply soft Gaussian blur to smooth the hair silhouette
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
    tr, tg, tb = int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)

    # Convert target color to HSV
    target_bgr = np.uint8([[[tb, tg, tr]]])
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0, 0]
    target_h, target_s = target_hsv[0], target_hsv[1]

    # Convert hair rgb to HSV
    hair_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    hair_hsv = cv2.cvtColor(hair_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Modulate Hue and Saturation
    hair_hsv[:, :, 0] = target_h
    hair_hsv[:, :, 1] = np.clip(hair_hsv[:, :, 1] * 0.4 + target_s * 0.7, 0, 255)

    tinted_bgr = cv2.cvtColor(hair_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    tinted_rgb = cv2.cvtColor(tinted_bgr, cv2.COLOR_BGR2RGB)

    np_rgba[:, :, :3] = tinted_rgb
    np_rgba[:, :, 3] = alpha
    return Image.fromarray(np_rgba, mode="RGBA")



def _call_cloud_hairstyle_sync(
    endpoint: str,
    person_img: Image.Image,
    hair_img: Image.Image,
    hairstyle_name: str,
    color_hex: Optional[str] = None,
    timeout_secs: float = 35.0,
) -> Optional[Image.Image]:
    import httpx, io
    clean_endpoint = endpoint.strip().rstrip("/")
    url = f"{clean_endpoint}/tryon-hair"

    p_buf = io.BytesIO()
    person_img.convert("RGB").save(p_buf, format="JPEG", quality=95)
    h_buf = io.BytesIO()
    hair_img.convert("RGB").save(h_buf, format="JPEG", quality=95)

    files = {
        "person_image": ("person.jpg", p_buf.getvalue(), "image/jpeg"),
        "hair_image": ("hair.jpg", h_buf.getvalue(), "image/jpeg"),
    }
    data = {
        "hairstyle_name": hairstyle_name,
        "color_hex": color_hex or ""
    }
    try:
        with httpx.Client(timeout=timeout_secs) as client:
            resp = client.post(url, files=files, data=data)
            if resp.status_code == 200:
                logger.info("Cloud neural hairstyle tryon successful via %s", url)
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        logger.warning("Cloud hairstyle endpoint %s unreachable or skipped (%s)", url, exc)
    return None


def synthesize_hairstyle_tryon(
    person_img: Image.Image,
    style_item_id: str,
    color_hex: Optional[str] = None,
    subcategory: Optional[str] = None,
    offset_x: Optional[float] = None,
    offset_y: Optional[float] = None,
    scale_override: Optional[float] = None,
) -> Tuple[Image.Image, str, str]:
    """
    Fit hairstyle matched to head orientation and forehead anchor.

    Returns:
        (result_pil, landmark_summary, result_url)
    """
    np_rgb = np.array(person_img.convert("RGB"))
    h, w, _ = np_rgb.shape

    pts = _detect_landmarks_two_stage(np_rgb)
    if pts is None or 10 not in pts or 234 not in pts or 454 not in pts:
        logger.warning("[Hairstyle] Landmark detection failed, using proportional head placement.")
        forehead_pt = np.array([w * 0.5, h * 0.28])
        face_w = w * 0.35
        face_h = h * 0.25
        angle_deg = 0.0
        landmark_summary = "Proportional head-crown estimate"
    else:
        p_forehead = pts[10]   # Top of forehead
        p_left_ear = pts[234]  # Left tragus
        p_right_ear = pts[454] # Right tragus
        p_chin = pts[152]

        face_w = float(np.linalg.norm(p_right_ear - p_left_ear))
        face_h = float(np.linalg.norm(p_chin - p_forehead))
        
        dx = p_right_ear[0] - p_left_ear[0]
        dy = p_right_ear[1] - p_left_ear[1]
        angle_deg = math.degrees(math.atan2(dy, dx))
        # Hair anchor: slightly above forehead (#10) so hair sits on head, not eyes
        forehead_pt = np.array([p_forehead[0], p_forehead[1] - face_h * 0.08])
        landmark_summary = f"Forehead anchor #10, Ear span #234 <-> #454 (roll={angle_deg:.1f} deg)"

    # 1. Load hairstyle asset
    hair_asset_pil = _get_or_create_hair_asset(style_item_id, subcategory)

    # 2. Apply color tint if provided
    hair_asset_pil = _apply_hair_color(hair_asset_pil, color_hex)
    hair_rgba = np.array(hair_asset_pil)

    cloud_neural_used = False
    if settings.catvton_endpoint:
        try:
            cloud_res = _call_cloud_hairstyle_sync(
                endpoint=settings.catvton_endpoint,
                person_img=person_img,
                hair_img=hair_asset_pil,
                hairstyle_name=style_item_id or (subcategory or "hairstyle"),
                color_hex=color_hex
            )
            if cloud_res:
                final_pil = cloud_res.resize((w, h), Image.Resampling.LANCZOS)
                landmark_summary = "Neural Diffusion (IP-Adapter on GPU)"
                cloud_neural_used = True
        except Exception as exc:
            logger.warning("[Hairstyle] Cloud neural try-on failed (%s), using landmark overlay", exc)

    if not cloud_neural_used:
        # 3. Determine style-specific geometry profile
        filename = (
            HAIRSTYLE_ASSET_MAP.get(style_item_id)
            or (HAIRSTYLE_ASSET_MAP.get(subcategory.lower()) if subcategory else None)
            or "beach_waves.png"
        )
        prof = HAIRSTYLE_PROFILES.get(filename, {"top_y": 141, "cx": 389.0, "cw": 464.0, "margin": 1.15, "y_adj": 10})

        # 4. Scale hairstyle to head dimensions
        ah, aw = hair_rgba.shape[:2]
        base_scale = (face_w * prof["margin"]) / prof["cw"]
        # Constrain by face height so hair covers head properly
        h_scale = (face_h * 1.15) / ah
        final_scale = min(base_scale, h_scale)
        # Ensure minimum visible size relative to image width
        min_scale = (w * 0.25) / aw
        final_scale = max(final_scale, min_scale)
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

        if pts is not None and 234 in pts and 454 in pts:
            face_center_x = (pts[234][0] + pts[454][0]) / 2.0
        else:
            face_center_x = forehead_pt[0]

        paste_x = int(face_center_x - (prof["cx"] * final_scale))
        paste_y = int(forehead_pt[1] - (prof["top_y"] * final_scale) + prof["y_adj"])
        # Shift hair slightly upward to sit better on crown
        paste_y -= int(final_scale * 10)

        # Apply manual offsets
        if offset_x is not None:
            paste_x += int(offset_x)
        if offset_y is not None:
            paste_y += int(offset_y)

        # 6. Clean Alpha Composition
        hair_pil = Image.fromarray(hair_transformed, "RGBA")
        canvas_pil = person_img.convert("RGBA")
        W, H = person_img.size

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

    # 7. Generate Close-up Portrait Crop (Head & Hair Zoom)
    closeup_result_url = None
    closeup_orig_url = None
    if pts is not None and 10 in pts and 152 in pts and 234 in pts and 454 in pts:
        try:
            p_forehead = pts[10]
            p_chin = pts[152]
            p_left_ear = pts[234]
            p_right_ear = pts[454]

            face_w = max(40, int(abs(p_right_ear[0] - p_left_ear[0])))
            face_h = max(50, int(abs(p_chin[1] - p_forehead[1])))
            cx = (p_left_ear[0] + p_right_ear[0]) / 2.0

            crop_w = int(face_w * 2.4)
            crop_h = int(face_h * 2.6)

            x1 = max(0, int(cx - crop_w / 2))
            x2 = min(w, int(cx + crop_w / 2))
            y1 = max(0, int(p_forehead[1] - face_h * 0.70))
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
