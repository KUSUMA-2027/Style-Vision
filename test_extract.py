import os
import time
import cv2
import numpy as np
from PIL import Image
from app.utils.face_utils import detect_face_landmarks

def extract_garment_from_person(img_pil: Image.Image) -> Image.Image:
    """
    Extracts the garment from a photo of a person wearing it.
    Masks out the head, face, bare skin (arms/shoulders), and background.
    """
    t0 = time.time()
    orig_w, orig_h = img_pil.size
    
    # 1. Downsample for fast processing
    max_dim = 600
    scale = min(1.0, max_dim / max(orig_w, orig_h))
    sw, sh = max(10, int(orig_w * scale)), max(10, int(orig_h * scale))
    
    small_pil = img_pil.resize((sw, sh), Image.Resampling.BILINEAR)
    small_rgb = np.array(small_pil.convert("RGB"))
    small_bgr = cv2.cvtColor(small_rgb, cv2.COLOR_RGB2BGR)
    
    # 2. Detect face landmarks
    landmarks = detect_face_landmarks(small_rgb)
    if not landmarks:
        from app.services.tryon_service import _clean_garment_background
        return _clean_garment_background(img_pil)
        
    p_chin = landmarks[152]
    p_forehead = landmarks[10]
    p_left_ear = landmarks[234]
    p_right_ear = landmarks[454]
    
    face_h = float(np.linalg.norm(p_chin - p_forehead))
    face_w = float(np.linalg.norm(p_right_ear - p_left_ear))
    cx = float((p_left_ear[0] + p_right_ear[0]) / 2.0)
    chin_y = float(p_chin[1])
    neck_y = int(chin_y + face_h * 0.16)
    
    # 3. Setup GrabCut mask
    mask = np.zeros((sh, sw), np.uint8)
    
    # Definite background: entire head, hair, and face above neck
    mask[:neck_y, :] = cv2.GC_BGD
    
    # Estimate body column: from neck down
    body_half_w = max(int(face_w * 2.3), int(sw * 0.35))
    x1 = max(0, int(cx - body_half_w))
    x2 = min(sw, int(cx + body_half_w))
    mask[neck_y:, x1:x2] = cv2.GC_PR_FGD
    
    # Outer margins are definite background
    b_w = max(2, int(sw * 0.08))
    b_h = max(2, int(sh * 0.04))
    mask[:, :b_w] = cv2.GC_BGD
    mask[:, sw-b_w:] = cv2.GC_BGD
    mask[:b_h, :] = cv2.GC_BGD
    mask[sh-b_h:, :] = cv2.GC_BGD
    
    # Detect background color from top corners and borders
    corners = np.vstack([
        small_rgb[:b_h, :b_w].reshape(-1, 3),
        small_rgb[:b_h, -b_w:].reshape(-1, 3),
        small_rgb[-b_h:, :b_w].reshape(-1, 3),
        small_rgb[-b_h:, -b_w:].reshape(-1, 3),
    ])
    bg_median = np.median(corners, axis=0)
    color_diff = np.sqrt(np.sum((small_rgb.astype(np.float32) - bg_median) ** 2, axis=-1))
    
    # Pixels very close to background color are definite background
    mask[color_diff < 25.0] = cv2.GC_BGD
    
    # Run GrabCut
    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)
    rect = (x1, neck_y, max(1, x2 - x1), max(1, sh - neck_y - 1))
    
    try:
        cv2.grabCut(small_bgr, mask, rect, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_MASK)
        fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except Exception as e:
        fg_mask = np.zeros((sh, sw), np.uint8)
        fg_mask[neck_y:, x1:x2] = 255

    # Enforce strictly no pixels above neck_y
    fg_mask[:neck_y, :] = 0
    
    # Morphology cleaning
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    fg_mask = cv2.GaussianBlur(fg_mask, (7, 7), 2)
    
    # Upsample mask to original resolution
    full_mask = cv2.resize(fg_mask, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
    
    # Crop to garment bounds
    coords = cv2.findNonZero((full_mask > 25).astype(np.uint8))
    full_rgba = np.array(img_pil.convert("RGBA"))
    full_rgba[:, :, 3] = full_mask
    
    if coords is not None:
        bx, by, bw, bh = cv2.boundingRect(coords)
        if bw > 30 and bh > 30:
            full_rgba = full_rgba[by:by+bh, bx:bx+bw]
            
    res_pil = Image.fromarray(full_rgba, mode="RGBA")
    print(f"Extraction completed in {time.time() - t0:.2f}s, size: {res_pil.size}")
    return res_pil

if __name__ == "__main__":
    img_path = r"uploads\wardrobe\garment_user_100e0ec9f69843b48cecd162d4a6a637.jpg"
    img = Image.open(img_path)
    res = extract_garment_from_person(img)
    os.makedirs(r"uploads\test", exist_ok=True)
    res.save(r"uploads\test\extracted_garment_v2.png")
