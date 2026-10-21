import os
import cv2
import numpy as np
from PIL import Image
from app.utils.face_utils import detect_face_landmarks

def extract_hair_wig(img_path: str, out_path: str):
    img = Image.open(img_path).convert("RGB")
    rgb = np.array(img)
    h, w = rgb.shape[:2]
    
    landmarks = detect_face_landmarks(rgb)
    if not landmarks:
        print("No landmarks for hair extraction")
        return
        
    # Face perimeter landmarks
    # Chin to jaw to temples to eyebrows
    face_contour_indices = [
        10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
        148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
    ]
    
    face_pts = np.array([landmarks[idx] for idx in face_contour_indices if idx in landmarks], dtype=np.int32)
    
    # 1. Background removal
    # Sample 4 corners
    b = 10
    corners = np.vstack([
        rgb[:b, :b].reshape(-1, 3),
        rgb[:b, -b:].reshape(-1, 3),
        rgb[-b:, :b].reshape(-1, 3),
        rgb[-b:, -b:].reshape(-1, 3),
    ])
    bg_median = np.median(corners, axis=0)
    diff = np.sqrt(np.sum((rgb.astype(np.float32) - bg_median) ** 2, axis=-1))
    
    # Hair mask: diff > threshold
    hair_mask = np.where(diff > 32.0, 255, 0).astype(np.uint8)
    
    # 2. Hollow out the face window
    cv2.fillPoly(hair_mask, [face_pts], 0)
    
    # 3. Hollow out the neck / chest area below chin
    p_chin = landmarks[152]
    p_left_ear = landmarks[234]
    p_right_ear = landmarks[454]
    chin_y = int(p_chin[1])
    
    neck_box = np.array([
        [int(p_left_ear[0] + 40), chin_y],
        [int(p_right_ear[0] - 40), chin_y],
        [int(p_right_ear[0] - 30), h],
        [int(p_left_ear[0] + 30), h]
    ], dtype=np.int32)
    cv2.fillPoly(hair_mask, [neck_box], 0)
    
    # Smooth alpha edges
    hair_mask = cv2.GaussianBlur(hair_mask, (5, 5), 1.5)
    
    # Create RGBA
    rgba = np.dstack([rgb, hair_mask])
    
    # Tight crop
    coords = cv2.findNonZero((hair_mask > 20).astype(np.uint8))
    if coords is not None:
        bx, by, bw, bh = cv2.boundingRect(coords)
        rgba = rgba[by:by+bh, bx:bx+bw]
        
    res_img = Image.fromarray(rgba, "RGBA")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    res_img.save(out_path)
    print("Saved hair wig:", out_path, "size:", res_img.size)

if __name__ == "__main__":
    extract_hair_wig(r"catalogue\hairstyles\hairstyles1.jpg", r"catalogue\hairstyles\beach_waves.png")
    extract_hair_wig(r"catalogue\hairstyles\hairstyles2.jpg", r"catalogue\hairstyles\classic_french_bob.png")
    extract_hair_wig(r"catalogue\hairstyles\hairstyles3.jpg", r"catalogue\hairstyles\sleek_high_ponytail.png")
    extract_hair_wig(r"catalogue\hairstyles\hairstyles4.jpg", r"catalogue\hairstyles\soft_curls.png")
    extract_hair_wig(r"catalogue\hairstyles\hairstyles5.jpg", r"catalogue\hairstyles\platinum_blonde_shag.png")
