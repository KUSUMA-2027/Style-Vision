"""
StyleVision — Virtual Makeup Studio Service
============================================
Uses MediaPipe FaceMesh 478 landmarks + OpenCV colour-space alpha blending
to apply cosmetics onto user portrait photos.

Supported makeup types:
  lipstick  — lips polygon fill  (landmarks #61, #291, #0, #17 + inner lip ring)
  eyeshadow — upper eyelid area  (per-eye: #33,#133,#362,#263 + brow / orbital zone)
  blush     — cheek polygon      (medial cheek cluster per side)

Finish modes modulate final blend opacity and saturation:
  matte   → lower alpha, fully desaturated overlay (flat pigment)
  satin   → medium alpha, slight saturation boost
  glossy  → higher alpha, strong saturation, additive specular highlight

Output is always saved to:
  <uploads_dir>/tryon/tryon-mu-<id>.png
"""
import os
import uuid
import logging
import math
from typing import Tuple, Optional, List

import numpy as np
from PIL import Image
import cv2
from app.utils.face_utils import detect_face_landmarks

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── FaceMesh landmark index groups ────────────────────────────────────────────
# Outer lip ring  (clockwise from left corner)
OUTER_LIP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405,
              314, 17, 84, 181, 91, 146, 61]
# Inner lip ring  (used to make lips hollow = only colour the visible surface)
INNER_LIP = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318,
             402, 317, 14, 87, 178, 88, 95, 78]

# Upper eyelid / eyeshadow zone — left eye
LEFT_EYE_SHADOW = [226, 247, 30, 29, 27, 28, 56, 190,  # above crease
                   243, 112, 26, 22, 23, 24, 110, 25]
# Upper eyelid / eyeshadow zone — right eye
RIGHT_EYE_SHADOW = [463, 414, 286, 258, 257, 259, 260, 467,
                    446, 255, 339, 254, 253, 252, 256, 341]

# Blush regions — left cheek (medial) and right cheek
LEFT_CHEEK = [116, 123, 147, 213, 192, 214, 212, 202, 210, 169, 136, 135, 192]
RIGHT_CHEEK = [340, 349, 376, 433, 434, 416, 432, 422, 430, 394, 365, 364, 416]


# ── Two-stage MediaPipe face detection (same approach as accessory_service) ───

def _get_landmarks_on_full_image(
    img_rgb: np.ndarray,
) -> Optional[List[Tuple[int, int]]]:
    """
    Two-stage landmark detection using MediaPipe FaceMesh / OpenCV geometric projection.
    Returns list of (px, py) for all 478 landmarks, or None on failure.
    """
    lm_dict = detect_face_landmarks(img_rgb)
    if not lm_dict:
        logger.warning("[Makeup] No facial landmarks detected.")
        return None

    max_idx = max(500, max(lm_dict.keys()) + 1)
    pts: List[Tuple[int, int]] = [(0, 0)] * max_idx
    for idx, pt in lm_dict.items():
        if idx < max_idx:
            pts[idx] = (int(pt[0]), int(pt[1]))
    return pts


# ── Colour helpers ─────────────────────────────────────────────────────────────

def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    """Convert #RRGGBB → (B, G, R) for OpenCV."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def _adjust_saturation(bgr: np.ndarray, factor: float) -> np.ndarray:
    """Multiply saturation channel of a BGR image by factor (HSV space)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


# ── Per-makeup-type blend functions ───────────────────────────────────────────

# Left Eye Upper Eyelid & Eyeball Landmarks
LEFT_EYE_LID = [33, 246, 161, 160, 159, 158, 157, 173, 133, 243, 190, 56, 28, 27, 29, 30, 247]
LEFT_EYEBALL = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]

# Right Eye Upper Eyelid & Eyeball Landmarks
RIGHT_EYE_LID = [362, 398, 384, 385, 386, 387, 388, 466, 263, 467, 260, 259, 257, 258, 286, 414, 463]
RIGHT_EYEBALL = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]


def _apply_lipstick(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """Apply high-precision cosmetic lipstick with lip texture and crease preservation."""
    outer = np.array([pts[i] for i in OUTER_LIP], dtype=np.int32)
    inner = np.array([pts[i] for i in INNER_LIP], dtype=np.int32)

    lip_mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
    cv2.fillPoly(lip_mask, [outer], 255)
    # Hollow out teeth / tongue cavity
    cv2.fillPoly(lip_mask, [inner], 0)

    # Multi-stage edge feathering
    lip_mask = cv2.GaussianBlur(lip_mask, (7, 7), 2)

    # Realistic texture preservation using HSV skin tinting
    hsv_canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2HSV).astype(np.float32)
    target_bgr = np.uint8([[[bgr_color[0], bgr_color[1], bgr_color[2]]]])
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0, 0]

    tinted_hsv = hsv_canvas.copy()
    tinted_hsv[:, :, 0] = target_hsv[0]

    if finish == "matte":
        alpha = 0.55 * intensity
        tinted_hsv[:, :, 1] = np.clip(target_hsv[1] * 0.9, 0, 255)
        tinted_hsv[:, :, 2] = np.clip(hsv_canvas[:, :, 2] * 0.95, 0, 255)
    elif finish == "glossy":
        alpha = 0.72 * intensity
        tinted_hsv[:, :, 1] = np.clip(target_hsv[1] * 1.25, 0, 255)
        tinted_hsv[:, :, 2] = np.clip(hsv_canvas[:, :, 2] * 1.15, 0, 255)
    else:  # satin
        alpha = 0.62 * intensity
        tinted_hsv[:, :, 1] = np.clip(target_hsv[1] * 1.05, 0, 255)

    tinted_bgr = cv2.cvtColor(tinted_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)

    # Specular highlight for glossy finish
    if finish == "glossy":
        cx, cy = pts[0]  # cupid's bow
        cv2.ellipse(tinted_bgr, (cx, cy + 3), (8, 3), 0, 0, 360, (235, 235, 235), -1)

    alpha_mask = (lip_mask / 255.0 * alpha)[:, :, np.newaxis].astype(np.float32)
    result = canvas.astype(np.float32) * (1.0 - alpha_mask) + tinted_bgr * alpha_mask
    return np.clip(result, 0, 255).astype(np.uint8)


def _apply_eyeshadow(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """
    Apply photorealistic, anatomically-mapped eyeshadow:
    - Layer 1: Mobile Eyelid (high pigment saturation from lash line to crease)
    - Layer 2: Crease & Transition Blend (gradient falloff upward toward orbital bone)
    - Eyeball / Cornea / Sclera Protection (dilated exclusion to guarantee zero bleeding)
    - Upper Lash Line Tightlining (keeps eyelashes jet-black, crisp, and high-definition)
    - Finish Shading: Matte (velvety pigment), Satin (luminous apex glow), Glossy/Metallic (faceted shimmer)
    """
    h, w = canvas.shape[:2]

    # Anatomical landmark loops:
    # Screen Left Eye (Model's Right Eye):
    # Lash line (inner to outer): [33, 246, 161, 160, 159, 158, 157, 173, 133]
    # Crease line (inner to outer): [243, 190, 56, 28, 27, 29, 30, 247]
    # Upper crease / orbital blend: [226, 113, 225, 224, 223, 222, 221, 189]
    l_lash = [33, 246, 161, 160, 159, 158, 157, 173, 133]
    l_crease = [243, 190, 56, 28, 27, 29, 30, 247]
    l_upper_crease = [226, 113, 225, 224, 223, 222, 221, 189]

    # Screen Right Eye (Model's Left Eye):
    # Lash line (inner to outer): [362, 398, 384, 385, 386, 387, 388, 466, 263]
    # Crease line (inner to outer): [463, 414, 286, 258, 257, 259, 260, 467]
    # Upper crease / orbital blend: [446, 342, 445, 444, 443, 442, 441, 413]
    r_lash = [362, 398, 384, 385, 386, 387, 388, 466, 263]
    r_crease = [463, 414, 286, 258, 257, 259, 260, 467]
    r_upper_crease = [446, 342, 445, 444, 443, 442, 441, 413]

    l_lash_pts = np.array([pts[i] for i in l_lash if i < len(pts)], dtype=np.int32)
    l_crease_pts = np.array([pts[i] for i in l_crease if i < len(pts)], dtype=np.int32)
    l_upper_pts = np.array([pts[i] for i in l_upper_crease if i < len(pts)], dtype=np.int32)

    r_lash_pts = np.array([pts[i] for i in r_lash if i < len(pts)], dtype=np.int32)
    r_crease_pts = np.array([pts[i] for i in r_crease if i < len(pts)], dtype=np.int32)
    r_upper_pts = np.array([pts[i] for i in r_upper_crease if i < len(pts)], dtype=np.int32)

    # 1. Base Density Mask (Floating point for seamless multi-tier shading)
    density_mask = np.zeros((h, w), dtype=np.float32)

    # Left eye polygons
    if len(l_lash_pts) > 2 and len(l_crease_pts) > 2:
        poly_l_mobile = np.vstack([l_lash_pts, l_crease_pts[::-1]])
        cv2.fillPoly(density_mask, [poly_l_mobile], 1.0)
    if len(l_crease_pts) > 2 and len(l_upper_pts) > 2:
        poly_l_trans = np.vstack([l_crease_pts, l_upper_pts[::-1]])
        cv2.fillPoly(density_mask, [poly_l_trans], 0.45)

    # Right eye polygons
    if len(r_lash_pts) > 2 and len(r_crease_pts) > 2:
        poly_r_mobile = np.vstack([r_lash_pts, r_crease_pts[::-1]])
        cv2.fillPoly(density_mask, [poly_r_mobile], 1.0)
    if len(r_crease_pts) > 2 and len(r_upper_pts) > 2:
        poly_r_trans = np.vstack([r_crease_pts, r_upper_pts[::-1]])
        cv2.fillPoly(density_mask, [poly_r_trans], 0.45)

    # Fallback if specific crease landmarks were out of range
    if np.max(density_mask) == 0.0:
        p_left_lid = np.array([pts[i] for i in LEFT_EYE_LID if i < len(pts)], dtype=np.int32)
        p_right_lid = np.array([pts[i] for i in RIGHT_EYE_LID if i < len(pts)], dtype=np.int32)
        if len(p_left_lid) > 2:
            cv2.fillPoly(density_mask, [p_left_lid], 1.0)
        if len(p_right_lid) > 2:
            cv2.fillPoly(density_mask, [p_right_lid], 1.0)

    # 2. Complete Eyeball / Cornea / Sclera Exclusion Mask
    eyeball_mask = np.zeros((h, w), dtype=np.uint8)
    p_left_eye = np.array([pts[i] for i in LEFT_EYEBALL if i < len(pts)], dtype=np.int32)
    p_right_eye = np.array([pts[i] for i in RIGHT_EYEBALL if i < len(pts)], dtype=np.int32)
    if len(p_left_eye) > 2:
        cv2.fillPoly(eyeball_mask, [p_left_eye], 255)
    if len(p_right_eye) > 2:
        cv2.fillPoly(eyeball_mask, [p_right_eye], 255)

    # Dilate eyeball slightly to ensure crisp zero-bleed boundary at the lid-eye junction
    kernel_eye = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ball_dilated = cv2.dilate(eyeball_mask, kernel_eye, iterations=1)
    density_mask[ball_dilated > 0] = 0.0

    # 3. Soft Optical Gaussian Feathering (preserves opacity while smoothing crease transition)
    feathered = cv2.GaussianBlur(density_mask, (9, 9), 2.2)
    feathered[ball_dilated > 0] = 0.0

    # 4. Luminance-Preserving High-Fidelity Color Engine
    canvas_f = canvas.astype(np.float32)
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32)
    norm_lum = gray / 255.0  # Skin highlights & creases modulate pigment depth

    b_t, g_t, r_t = float(bgr_color[0]), float(bgr_color[1]), float(bgr_color[2])
    target_vec = np.array([b_t, g_t, r_t], dtype=np.float32)

    # Shaded pigment retains skin fold luminance for natural realism rather than flat paint
    shaded_pigment = np.zeros_like(canvas_f)
    for c in range(3):
        shaded_pigment[:, :, c] = target_vec[c] * (0.50 + 0.50 * norm_lum)

    # 5. Finish Shimmer / Highlight Processing
    if finish in ["satin", "glossy", "metallic"] and len(pts) > 467:
        shimmer_map = np.zeros((h, w), dtype=np.float32)
        p_l_apex = pts[159]
        p_r_apex = pts[386]
        eye_w_l = max(4, int(np.linalg.norm(np.array(pts[33]) - np.array(pts[133])) * 0.18))
        eye_w_r = max(4, int(np.linalg.norm(np.array(pts[362]) - np.array(pts[263])) * 0.18))

        cv2.ellipse(shimmer_map, p_l_apex, (eye_w_l, 2), 0, 0, 360, 1.0, -1)
        cv2.ellipse(shimmer_map, p_r_apex, (eye_w_r, 2), 0, 0, 360, 1.0, -1)
        shimmer_map = cv2.GaussianBlur(shimmer_map, (9, 9), 2.5)
        shimmer_map[ball_dilated > 0] = 0.0

        shimmer_strength = 35.0 if finish in ["metallic", "glossy"] else 20.0
        shaded_pigment = shaded_pigment + (shimmer_map[:, :, None] * shimmer_strength)

    # 6. Alpha Composition
    alpha_mult = float(np.clip(intensity * (0.75 if finish == "matte" else 0.82), 0.0, 1.0))
    final_alpha = (feathered * alpha_mult)[:, :, None]

    composited = canvas_f * (1.0 - final_alpha) + shaded_pigment * final_alpha

    # 7. Eyelash Line Tightlining
    # Restores deep contrast along the lash root for crisp, high-definition eye expression
    if len(l_lash_pts) > 2 and len(r_lash_pts) > 2:
        lash_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.polylines(lash_mask, [l_lash_pts, r_lash_pts], False, 255, 1, cv2.LINE_AA)
        lash_feather = cv2.GaussianBlur(lash_mask, (3, 3), 0.8) / 255.0
        lash_alpha = (lash_feather * 0.55)[:, :, None]

        lash_bgr = np.array([18.0, 15.0, 16.0], dtype=np.float32)
        composited = composited * (1.0 - lash_alpha) + lash_bgr * lash_alpha

    return np.clip(composited, 0, 255).astype(np.uint8)


def _apply_blush(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """Apply soft radial airbrush blush onto cheek apples with seamless gradient falloff."""
    h, w = canvas.shape[:2]
    blush_mask = np.zeros((h, w), dtype=np.uint8)

    # Anatomical cheek apple centers
    # Left cheek: around #116 / #123 / #187
    p_left_ear = np.array(pts[234])
    p_right_ear = np.array(pts[454])
    p_chin = np.array(pts[152])
    p_forehead = np.array(pts[10])

    face_w = float(np.linalg.norm(p_right_ear - p_left_ear))
    face_h = float(np.linalg.norm(p_chin - p_forehead))

    rx = max(15, int(face_w * 0.15))
    ry = max(10, int(face_h * 0.09))

    # Left cheek center: blend of landmarks 116, 123, 50
    lc_x = int((pts[116][0] * 0.4 + pts[123][0] * 0.3 + pts[50][0] * 0.3))
    lc_y = int((pts[116][1] * 0.4 + pts[123][1] * 0.3 + pts[50][1] * 0.3))
    cv2.ellipse(blush_mask, (lc_x, lc_y), (rx, ry), -15, 0, 360, 255, -1)

    # Right cheek center: blend of landmarks 345, 352, 280
    rc_x = int((pts[345][0] * 0.4 + pts[352][0] * 0.3 + pts[280][0] * 0.3))
    rc_y = int((pts[345][1] * 0.4 + pts[352][1] * 0.3 + pts[280][1] * 0.3))
    cv2.ellipse(blush_mask, (rc_x, rc_y), (rx, ry), 15, 0, 360, 255, -1)

    # Ultra-soft Gaussian feathering for Snapchat-level airbrushed diffusion
    blush_mask = cv2.GaussianBlur(blush_mask, (45, 45), 18)

    # Texture-preserving tinting
    hsv_canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2HSV).astype(np.float32)
    target_bgr = np.uint8([[[bgr_color[0], bgr_color[1], bgr_color[2]]]])
    target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0, 0]

    tinted_hsv = hsv_canvas.copy()
    tinted_hsv[:, :, 0] = target_hsv[0]
    tinted_hsv[:, :, 1] = np.clip(target_hsv[1] * 0.75 + hsv_canvas[:, :, 1] * 0.25, 0, 255)

    alpha = 0.35 * intensity
    if finish == "matte":
        alpha = 0.28 * intensity
    elif finish == "glossy":
        alpha = 0.42 * intensity
        tinted_hsv[:, :, 2] = np.clip(hsv_canvas[:, :, 2] * 1.05, 0, 255)

    tinted_bgr = cv2.cvtColor(tinted_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    alpha_mask = (blush_mask / 255.0 * alpha)[:, :, np.newaxis].astype(np.float32)

    result = canvas.astype(np.float32) * (1.0 - alpha_mask) + tinted_bgr * alpha_mask
    return np.clip(result, 0, 255).astype(np.uint8)


# ── Main public function ───────────────────────────────────────────────────────


def _apply_eyelashes(
    canvas: np.ndarray,
    pts: List[Tuple[int, int]],
    bgr_color: Tuple[int, int, int],
    intensity: float,
    finish: str,
) -> np.ndarray:
    """
    Apply photorealistic volumetric eyelashes & tightline eyeliner:
    - Base Eyeliner: Anti-aliased lash root tightline with subtle outer wing.
    - Curled Lash Fibers: Upward and temple-curling lash wisps with natural length progression
      from inner canthus to outer lateral corner.
    - Sclera / Cornea Protection: Zero bleed into the eyeball.
    - Finish Styles: Matte (rich carbon ink), Satin (natural fiber sheen), Glossy (wet-look lacquer).
    """
    h, w = canvas.shape[:2]
    canvas_f = canvas.astype(np.float32)

    # Landmark loops ordered strictly from INNER (canthus near nose) to OUTER (lateral near temple):
    # Screen Left Eye (Model's Right Eye): inner #133 -> outer #33
    l_lash_indices = [133, 173, 157, 158, 159, 160, 161, 246, 33]
    # Screen Right Eye (Model's Left Eye): inner #362 -> outer #263
    r_lash_indices = [362, 398, 384, 385, 386, 387, 388, 466, 263]

    l_pts = [pts[i] for i in l_lash_indices if i < len(pts)]
    r_pts = [pts[i] for i in r_lash_indices if i < len(pts)]

    if len(l_pts) < 4 or len(r_pts) < 4:
        return canvas

    # Eyeball exclusion mask
    eyeball_mask = np.zeros((h, w), dtype=np.uint8)
    p_left_eye = np.array([pts[i] for i in LEFT_EYEBALL if i < len(pts)], dtype=np.int32)
    p_right_eye = np.array([pts[i] for i in RIGHT_EYEBALL if i < len(pts)], dtype=np.int32)
    if len(p_left_eye) > 2:
        cv2.fillPoly(eyeball_mask, [p_left_eye], 255)
    if len(p_right_eye) > 2:
        cv2.fillPoly(eyeball_mask, [p_right_eye], 255)

    eye_w_l = np.linalg.norm(np.array(pts[33]) - np.array(pts[133]))
    eye_w_r = np.linalg.norm(np.array(pts[362]) - np.array(pts[263]))
    avg_eye_w = float((eye_w_l + eye_w_r) / 2.0)

    # Scale max lash length to ~22% of eye width (typically 5 to 10 pixels for portraits)
    max_lash_len = max(4.0, avg_eye_w * 0.22)

    lash_alpha = np.zeros((h, w), dtype=np.float32)
    bgr_f = np.array(bgr_color, dtype=np.float32)

    def draw_eye_fringe(lash_pts, temple_dir_x):
        nonlocal lash_alpha
        pts_arr = np.array(lash_pts, dtype=np.int32)
        n = len(lash_pts)

        # 1. Dark Tightline / Mascara Base
        tight_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.polylines(tight_mask, [pts_arr], False, 255, 2, cv2.LINE_AA)

        # Subtle winged extension at the outer temple corner
        p_outer = pts_arr[-1]
        p_prev = pts_arr[-2]
        wing_vec = (p_outer - p_prev).astype(np.float32)
        norm_w = np.linalg.norm(wing_vec)
        if norm_w > 0:
            wing_dir = wing_vec / norm_w
            wing_p2 = (p_outer + wing_dir * max_lash_len * 0.6 + np.array([0, -max_lash_len * 0.35])).astype(np.int32)
            cv2.line(tight_mask, tuple(p_outer), tuple(wing_p2), 255, 1, cv2.LINE_AA)

        tight_feather = cv2.GaussianBlur(tight_mask, (3, 3), 0.5) / 255.0
        lash_alpha = np.maximum(lash_alpha, tight_feather * 0.90)

        # 2. Curled Lash Fibers
        dense_points = []
        for i in range(n - 1):
            p1 = np.array(lash_pts[i], dtype=np.float32)
            p2 = np.array(lash_pts[i + 1], dtype=np.float32)
            dist = np.linalg.norm(p2 - p1)
            steps = max(2, int(dist * 1.2))
            for s in range(steps):
                t = s / steps
                dense_points.append((p1 * (1.0 - t) + p2 * t, (i + t) / (n - 1)))

        fiber_mask = np.zeros((h, w), dtype=np.uint8)

        for root, progress in dense_points:
            # progress: 0.0 (inner eye) -> 1.0 (outer eye near temple)
            length_mult = 0.25 + 0.75 * (progress ** 0.8)
            cur_len = max_lash_len * length_mult

            outward_amount = temple_dir_x * (0.20 + 0.80 * progress)
            upward_amount = -1.0

            dir_norm = np.sqrt(outward_amount**2 + upward_amount**2)
            dx = outward_amount / dir_norm
            dy = upward_amount / dir_norm

            root_pt = (int(root[0]), int(root[1]))
            mid_pt = (
                int(root[0] + dx * cur_len * 0.55),
                int(root[1] + dy * cur_len * 0.55),
            )
            tip_pt = (
                int(root[0] + dx * cur_len + temple_dir_x * cur_len * 0.35),
                int(root[1] + dy * cur_len * 0.85),
            )

            cv2.line(fiber_mask, root_pt, mid_pt, 255, 1, cv2.LINE_AA)
            cv2.line(fiber_mask, mid_pt, tip_pt, 210, 1, cv2.LINE_AA)

            # Volume lash adds a sister fiber
            if progress > 0.25 and (int(root[0] * 7 + root[1]) % 2 == 0):
                tip_pt_2 = (
                    int(root[0] + dx * cur_len * 0.9 + temple_dir_x * cur_len * 0.2),
                    int(root[1] + dy * cur_len * 0.95),
                )
                cv2.line(fiber_mask, root_pt, tip_pt_2, 175, 1, cv2.LINE_AA)

        fiber_feather = cv2.GaussianBlur(fiber_mask, (3, 3), 0.4) / 255.0
        lash_alpha = np.maximum(lash_alpha, fiber_feather * 0.85)

    # Left eye: temple is in -x direction (-1.0)
    draw_eye_fringe(l_pts, temple_dir_x=-1.0)
    # Right eye: temple is in +x direction (+1.0)
    draw_eye_fringe(r_pts, temple_dir_x=1.0)

    # Exclude eyeballs
    lash_alpha[eyeball_mask > 0] = 0.0

    # Build color layer
    lash_layer = np.zeros_like(canvas_f)
    for c in range(3):
        lash_layer[:, :, c] = bgr_f[c]

    eff_alpha = np.clip(lash_alpha * intensity, 0.0, 1.0)[:, :, None]
    result = canvas_f * (1.0 - eff_alpha) + lash_layer * eff_alpha
    return np.clip(result, 0, 255).astype(np.uint8)


def synthesize_makeup_tryon(
    person_img: Image.Image,
    makeup_type: str,
    color_hex: str,
    intensity: float,
    finish: str,
) -> Tuple[Image.Image, str, str]:
    """
    Apply virtual makeup to person_img.

    Args:
        person_img  : PIL Image (RGB) of the person.
        makeup_type : 'lipstick' | 'eyeshadow' | 'blush'
        color_hex   : '#RRGGBB'
        intensity   : 0.0 – 1.0 (blend strength multiplier)
        finish      : 'matte' | 'satin' | 'glossy'

    Returns:
        (result_pil, landmark_summary, result_url)
    """
    # ── 1. Prepare BGR canvas ────────────────────────────────────────
    img_rgb = np.array(person_img.convert("RGB"))
    canvas_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    # ── 2. Detect landmarks ─────────────────────────────────────────
    pts = _get_landmarks_on_full_image(img_rgb)
    if pts is None:
        raise ValueError(
            "No face detected in the uploaded photo. "
            "Please use a well-lit, front-facing portrait."
        )

    # ── 3. Apply makeup ─────────────────────────────────────────────
    bgr_color = _hex_to_bgr(color_hex)
    makeup_type_lower = makeup_type.lower()

    if makeup_type_lower == "lipstick":
        result_bgr = _apply_lipstick(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = f"Lips mesh ({len(OUTER_LIP)}-pt polygon, landmark #0 centroid)"
    elif makeup_type_lower == "eyeshadow":
        result_bgr = _apply_eyeshadow(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = "Upper eyelid convex hull (L: #33-#133, R: #362-#263)"
    elif makeup_type_lower == "blush":
        result_bgr = _apply_blush(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = "Medial cheek clusters (L: #116-#213, R: #340-#433)"
    elif makeup_type_lower in ("eyelashes", "eyelash", "lashes", "mascara"):
        result_bgr = _apply_eyelashes(canvas_bgr, pts, bgr_color, intensity, finish)
        landmark_summary = "Upper lash lines with feathered volumetric winged fibers"
    else:
        raise ValueError(f"Unknown makeup_type: '{makeup_type}'. Use lipstick|eyeshadow|blush|eyelashes.")

    # ── 4. Save result ──────────────────────────────────────────────
    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(result_rgb)

    tryon_id = f"tryon-mu-{uuid.uuid4().hex[:10]}"
    out_dir = os.path.join(settings.upload_dir, "tryon")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{tryon_id}.png")
    result_pil.save(out_path, "PNG")

    result_url = f"/uploads/tryon/{tryon_id}.png"

    # ── 5. Generate Close-up Portrait Crop (Face & Cosmetics Zoom) ───
    closeup_result_url = None
    closeup_orig_url = None
    if pts is not None and len(pts) > 454:
        try:
            p_forehead = pts[10]
            p_chin = pts[152]
            p_left_ear = pts[234]
            p_right_ear = pts[454]

            face_w = max(40, int(abs(p_right_ear[0] - p_left_ear[0])))
            face_h = max(50, int(abs(p_chin[1] - p_forehead[1])))
            cx = (p_left_ear[0] + p_right_ear[0]) / 2.0
            cy = (p_forehead[1] + p_chin[1]) / 2.0

            crop_w = int(face_w * 1.6)
            crop_h = int(face_h * 1.6)

            pw, ph = person_img.size
            x1 = max(0, int(cx - crop_w / 2))
            x2 = min(pw, int(cx + crop_w / 2))
            y1 = max(0, int(cy - crop_h / 2))
            y2 = min(ph, int(cy + crop_h / 2))

            if (x2 - x1) > 40 and (y2 - y1) > 40:
                crop_res = result_pil.crop((x1, y1, x2, y2))
                crop_orig = person_img.convert("RGB").crop((x1, y1, x2, y2))

                closeup_filename = f"{tryon_id}_closeup.png"
                closeup_orig_filename = f"{tryon_id}_orig_closeup.png"

                crop_res.save(os.path.join(out_dir, closeup_filename), format="PNG")
                crop_orig.save(os.path.join(out_dir, closeup_orig_filename), format="PNG")

                closeup_result_url = f"/uploads/tryon/{closeup_filename}"
                closeup_orig_url = f"/uploads/tryon/{closeup_orig_filename}"
        except Exception as e:
            logger.warning("Failed to generate makeup closeup: %s", e)

    logger.info(
        "[Makeup] %s applied (%s, intensity=%.2f, finish=%s) -> %s (closeup: %s)",
        makeup_type, color_hex, intensity, finish, result_url, closeup_result_url,
    )
    return result_pil, landmark_summary, result_url, closeup_result_url, closeup_orig_url
