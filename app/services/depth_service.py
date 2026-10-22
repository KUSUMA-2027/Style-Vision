"""
StyleVision — Depth-Aware 2.5D Tilt Service
Applies depth-based parallax tilt to create a slight 3D effect from 2D images.
"""
import logging
import os
import numpy as np
import cv2
from PIL import Image
from typing import Tuple, Optional

from app.utils.depth_utils import estimate_depth, depth_to_visual

logger = logging.getLogger(__name__)


def apply_depth_tilt(
    image: Image.Image,
    angle_deg: float = 8.0,
    intensity: float = 0.12,
    model_type: str = "MiDaS_small",
) -> Tuple[Image.Image, Image.Image]:
    """
    Apply a depth-aware tilt to create a pseudo-3D effect.
    Closer regions shift more than farther regions, creating parallax.

    Returns:
        (tilted_image, depth_map_visual)
    """
    try:
        img_rgba = image.convert("RGBA")
        img_rgba_np = np.array(img_rgba)
        h, w = img_rgba_np.shape[:2]
        img_rgb = img_rgba_np[:, :, :3]

        depth = estimate_depth(Image.fromarray(img_rgb), model_type=model_type)
        depth_norm = depth

        cx, cy = w / 2.0, h / 2.0
        yy, xx = np.mgrid[0:h, 0:w]

        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        max_dist = np.sqrt(cx ** 2 + cy ** 2)
        falloff = 1.0 - (dist / max_dist) * 0.3

        angle_rad = np.radians(angle_deg)
        shift_x = (depth_norm - 0.5) * np.sin(angle_rad) * intensity * w * falloff
        shift_y = (depth_norm - 0.5) * np.sin(angle_rad * 0.6) * intensity * h * falloff

        map_x = (xx + shift_x).astype(np.float32)
        map_y = (yy + shift_y).astype(np.float32)

        tilted = cv2.remap(
            img_rgba_np,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )

        tilted_pil = Image.fromarray(tilted, mode="RGBA")
        depth_vis = depth_to_visual(depth_norm)

        return tilted_pil, depth_vis
    except Exception as exc:
        logger.warning("[Depth] Depth tilt failed, returning original image: %s", exc)
        return image.convert("RGBA"), Image.new("L", image.size, 128)


def save_tilt_result(tilted_img: Image.Image, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tilted_img.convert("RGB").save(output_path, format="PNG")
