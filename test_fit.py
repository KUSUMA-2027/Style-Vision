import os
import cv2
import numpy as np
from PIL import Image
from app.utils.face_utils import detect_face_landmarks

def tryon_garment_test(person_path: str, garment_path: str, out_path: str):
    person_img = Image.open(person_path).convert("RGBA")
    pw, ph = person_img.size
    
    garment_img = Image.open(garment_path).convert("RGBA")
    gw, gh = garment_img.size
    aspect = gh / max(1, gw)
    
    landmarks = detect_face_landmarks(np.array(person_img.convert("RGB")))
    if not landmarks:
        print("No face landmarks")
        return
        
    p_chin = landmarks[152]
    p_forehead = landmarks[10]
    p_left_ear = landmarks[234]
    p_right_ear = landmarks[454]
    
    face_h = float(np.linalg.norm(p_chin - p_forehead))
    face_w = float(np.linalg.norm(p_right_ear - p_left_ear))
    cx = float((p_left_ear[0] + p_right_ear[0]) / 2.0)
    chin_y = float(p_chin[1])
    neck_y = int(chin_y + face_h * 0.16)
    
    # Target width scaled to match human shoulder span
    target_width = min(int(pw * 0.96), max(int(pw * 0.65), int(face_w * 3.8)))
    target_height = int(target_width * aspect)
    
    resized_garment = garment_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    paste_x = int(cx - (target_width / 2))
    paste_y = max(0, int(neck_y - target_height * 0.03))
    
    composite = person_img.copy()
    
    # Clip if goes beyond bottom of person image
    if paste_y + target_height > ph:
        visible_h = ph - paste_y
        cropped_garment = resized_garment.crop((0, 0, target_width, visible_h))
        composite.alpha_composite(cropped_garment, (paste_x, paste_y))
    else:
        composite.alpha_composite(resized_garment, (paste_x, paste_y))
        
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    composite.convert("RGB").save(out_path, format="JPEG", quality=95)
    print("Saved:", out_path)

if __name__ == "__main__":
    p_medium = r"uploads\person_user_30ad2e4b6fcc4826b76ca3d493425124.jpg"
    p_full = r"uploads\person_user_b79826f394394c47a05805d9748b9db2.jpg"
    
    g_saree = r"uploads\test\extracted_garment_v2.png"
    g_gown = r"..\catalogue\outfits\gown1.webp" if os.path.exists(r"..\catalogue\outfits\gown1.webp") else r"catalogue\outfits\gown1.webp"
    
    tryon_garment_test(p_medium, g_saree, r"uploads\test\result_medium_saree.jpg")
    tryon_garment_test(p_full, g_saree, r"uploads\test\result_full_saree.jpg")
    tryon_garment_test(p_medium, g_gown, r"uploads\test\result_medium_gown.jpg")
    tryon_garment_test(p_full, g_gown, r"uploads\test\result_full_gown.jpg")
