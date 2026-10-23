"""
StyleVision — Facial Landmarks & Pose Utility
Two-stage face detection and landmarking:
1. Haar Cascade / multi-crop face localizer to locate the head region even in 4K full-body portraits.
2. MediaPipe Tasks Vision FaceLandmarker (478 sub-pixel landmarks with iris & contour precision).
3. Robust anatomical geometric fallback anchored to detected face bounding box.
"""
import os
import math
import logging
from typing import Optional, Dict, Tuple, Any
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Model paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_BIN_DIR = os.path.join(BASE_DIR, "models_bin")
TASK_MODEL_PATH = os.path.join(MODELS_BIN_DIR, "face_landmarker.task")
POSE_TASK_MODEL_PATH = os.path.join(MODELS_BIN_DIR, "pose_landmarker.task")
HAND_TASK_MODEL_PATH = os.path.join(MODELS_BIN_DIR, "hand_landmarker.task")
HAAR_CASCADE_PATH = os.path.join(MODELS_BIN_DIR, "haarcascade_frontalface_default.xml")

# Cached detector instances
_cached_face_landmarker = None
_cached_pose_landmarker = None
_cached_hand_landmarker = None
_cached_haar_cascade = None


def get_mediapipe_pose_landmarker():
    """Retrieve or initialize the MediaPipe Tasks PoseLandmarker singleton."""
    global _cached_pose_landmarker
    if _cached_pose_landmarker is not None:
        return _cached_pose_landmarker

    if not os.path.exists(POSE_TASK_MODEL_PATH):
        logger.warning("MediaPipe pose_landmarker.task not found at %s", POSE_TASK_MODEL_PATH)
        return None

    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=POSE_TASK_MODEL_PATH)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            min_pose_detection_confidence=0.25,
            min_pose_presence_confidence=0.25,
            min_tracking_confidence=0.25,
            num_poses=1,
        )
        _cached_pose_landmarker = vision.PoseLandmarker.create_from_options(options)
        logger.info("MediaPipe PoseLandmarker task loaded successfully from %s", POSE_TASK_MODEL_PATH)
        return _cached_pose_landmarker
    except Exception as e:
        logger.warning("Failed to initialize MediaPipe PoseLandmarker: %s", e)
        return None


def get_haar_cascade() -> Optional[cv2.CascadeClassifier]:
    """Retrieve or initialize the Haar Cascade face detector."""
    global _cached_haar_cascade
    if _cached_haar_cascade is not None:
        return _cached_haar_cascade

    paths_to_try = [
        HAAR_CASCADE_PATH,
        os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml") if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades") else "",
    ]
    for p in paths_to_try:
        if p and os.path.exists(p):
            try:
                cascade = cv2.CascadeClassifier(p)
                if not cascade.empty():
                    _cached_haar_cascade = cascade
                    logger.info("Loaded Haar Cascade face detector from %s", p)
                    return _cached_haar_cascade
            except Exception as e:
                logger.warning("Could not load Haar cascade from %s: %s", p, e)
    return None


def get_mediapipe_landmarker():
    """Retrieve or initialize the MediaPipe Tasks FaceLandmarker singleton."""
    global _cached_face_landmarker
    if _cached_face_landmarker is not None:
        return _cached_face_landmarker

    if not os.path.exists(TASK_MODEL_PATH):
        logger.warning("MediaPipe face_landmarker.task not found at %s", TASK_MODEL_PATH)
        return None

    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=TASK_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            min_face_detection_confidence=0.1,
            min_face_presence_confidence=0.1,
        )
        _cached_face_landmarker = vision.FaceLandmarker.create_from_options(options)
        logger.info("MediaPipe FaceLandmarker task loaded successfully from %s", TASK_MODEL_PATH)
        return _cached_face_landmarker
    except Exception as e:
        logger.warning("Failed to initialize MediaPipe FaceLandmarker: %s", e)
        return None


def detect_face_bbox_opencv(np_rgb: np.ndarray, allow_default_crop: bool = False) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect primary face bounding box (x, y, w, h) using Haar Cascade or upper-quadrant contour analysis.
    Guaranteed to anchor to the head and never select torso / waist / hands.
    If allow_default_crop is False, returns None when no real face is detected.
    """
    h, w = np_rgb.shape[:2]

    # 1. Try Haar Cascade first
    cascade = get_haar_cascade()
    if cascade is not None:
        try:
            gray = cv2.cvtColor(np_rgb, cv2.COLOR_RGB2GRAY)
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(int(min(w, h) * 0.05), int(min(w, h) * 0.05)),
            )
            if len(faces) > 0:
                # Filter faces to upper 65% of image (head is never at the bottom of portrait)
                valid_faces = [f for f in faces if f[1] < h * 0.65]
                if valid_faces:
                    valid_faces.sort(key=lambda f: f[2] * f[3], reverse=True)
                    return tuple(valid_faces[0])
                else:
                    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                    return tuple(faces[0])
        except Exception as e:
            logger.warning("OpenCV Haar cascade detection error: %s", e)

    # 2. Skin / contour analysis restricted ONLY to the upper 40% of the image
    upper_limit = int(h * 0.40)
    upper_slice = np_rgb[0:upper_limit, :]
    hsv = cv2.cvtColor(upper_slice, cv2.COLOR_RGB2HSV)
    lower_skin = np.array([0, 25, 60], dtype=np.uint8)
    upper_skin = np.array([25, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_skin, upper_skin)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > (w * upper_limit * 0.02):
                x, y, cw, ch = cv2.boundingRect(c)
                # Head aspect ratio check (roughly 0.7 to 1.6)
                ratio = ch / max(1, cw)
                if 0.6 <= ratio <= 2.2:
                    candidates.append((area, (x, y, cw, ch)))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]

    # 3. Standard anatomical upper-center portrait heuristic (ONLY if explicitly enabled for person portraits)
    if allow_default_crop:
        fw = int(w * 0.32)
        fh = int(fw * 1.30)
        fx = int((w - fw) / 2)
        fy = int(h * 0.06)
        return (fx, fy, fw, fh)

    return None


def generate_geometric_landmarks(bbox: Tuple[int, int, int, int], img_w: int, img_h: int) -> Dict[int, np.ndarray]:
    """
    Synthesize the core MediaPipe FaceMesh landmark dictionary from face bounding box coordinates.
    Covers all indices needed by accessory_service, makeup_service, and hairstyle_service.
    """
    x, y, fw, fh = bbox
    cx = x + fw / 2.0

    landmarks = {}

    # Forehead top / hairline center (#10)
    landmarks[10] = np.array([cx, max(0.0, y - fh * 0.05)])

    # Eye bridge / nasion (#168)
    landmarks[168] = np.array([cx, y + fh * 0.35])

    # Nose tip center (#1)
    landmarks[1] = np.array([cx, y + fh * 0.56])

    # Chin bottom (#152)
    landmarks[152] = np.array([cx, min(float(img_h), y + fh * 0.98)])

    # Left & Right outer eye corners (#33, #263)
    landmarks[33] = np.array([x + fw * 0.22, y + fh * 0.36])
    landmarks[263] = np.array([x + fw * 0.78, y + fh * 0.36])

    # Left & Right inner eye corners (#133, #362)
    landmarks[133] = np.array([x + fw * 0.38, y + fh * 0.36])
    landmarks[362] = np.array([x + fw * 0.62, y + fh * 0.36])

    # Left & Right earlobes / tragus (#234, #454)
    landmarks[234] = np.array([max(0.0, x - fw * 0.08), y + fh * 0.46])
    landmarks[454] = np.array([min(float(img_w), x + fw * 1.08), y + fh * 0.46])

    # Left & Right nostrils (#48, #278)
    landmarks[48] = np.array([cx - fw * 0.10, y + fh * 0.58])
    landmarks[278] = np.array([cx + fw * 0.10, y + fh * 0.58])

    # Mouth corners & lips
    landmarks[61] = np.array([cx - fw * 0.18, y + fh * 0.74])
    landmarks[291] = np.array([cx + fw * 0.18, y + fh * 0.74])
    landmarks[0] = np.array([cx, y + fh * 0.70])
    landmarks[17] = np.array([cx, y + fh * 0.80])
    landmarks[13] = np.array([cx, y + fh * 0.73])
    landmarks[14] = np.array([cx, y + fh * 0.76])

    # Outer lip ring points
    outer_indices = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
    for i, idx in enumerate(outer_indices):
        theta = (2.0 * math.pi * i) / len(outer_indices)
        px = cx + (fw * 0.18) * math.cos(theta)
        py = (y + fh * 0.75) + (fh * 0.07) * math.sin(theta)
        landmarks[idx] = np.array([px, py])

    # Inner lip ring points
    inner_indices = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
    for i, idx in enumerate(inner_indices):
        theta = (2.0 * math.pi * i) / len(inner_indices)
        px = cx + (fw * 0.12) * math.cos(theta)
        py = (y + fh * 0.75) + (fh * 0.04) * math.sin(theta)
        landmarks[idx] = np.array([px, py])

    # Left & Right eyeshadow regions
    left_shadow = [226, 247, 30, 29, 27, 28, 56, 190, 243, 112, 26, 22, 23, 24, 110, 25]
    for i, idx in enumerate(left_shadow):
        landmarks[idx] = np.array([x + fw * (0.20 + (i % 4) * 0.04), y + fh * (0.30 + (i // 4) * 0.02)])

    right_shadow = [463, 414, 286, 258, 257, 259, 260, 467, 446, 255, 339, 254, 253, 252, 256, 341]
    for i, idx in enumerate(right_shadow):
        landmarks[idx] = np.array([x + fw * (0.64 + (i % 4) * 0.04), y + fh * (0.30 + (i // 4) * 0.02)])

    # Left & Right cheek blush clusters
    left_cheek = [116, 123, 147, 213, 192, 214, 212, 202, 210, 169, 136, 135]
    for i, idx in enumerate(left_cheek):
        landmarks[idx] = np.array([x + fw * (0.22 + (i % 3) * 0.04), y + fh * (0.50 + (i // 3) * 0.03)])

    right_cheek = [340, 349, 376, 433, 434, 416, 432, 422, 430, 394, 365, 364]
    for i, idx in enumerate(right_cheek):
        landmarks[idx] = np.array([x + fw * (0.68 + (i % 3) * 0.04), y + fh * (0.50 + (i // 3) * 0.03)])

    return landmarks


def detect_face_landmarks(np_rgb: np.ndarray, allow_fallback: bool = True) -> Optional[Dict[int, np.ndarray]]:
    """
    Detect face landmarks on image using high-precision multi-stage pipeline:
    1. Stage 1: OpenCV Haar Cascade localized face bbox with padding -> MediaPipe FaceLandmarker.
    2. Stage 2: MediaPipe FaceLandmarker directly on full image.
    3. Stage 3: Multi-crop upper region scan (35%, 50%, 25%, 55% center) with MediaPipe.
    4. Stage 4: Geometric anatomical fallback anchored to face bbox (only when allow_fallback=True).
    Returns: Dict mapping landmark index -> np.array([x, y]) in full-image pixel coordinates.
    """
    h, w = np_rgb.shape[:2]
    landmarker = get_mediapipe_landmarker()

    # ── STAGE 1: Haar Cascade Face Localizer + MediaPipe on Face Crop ─────────
    cascade = get_haar_cascade()
    haar_bbox = None
    if cascade is not None:
        try:
            gray = cv2.cvtColor(np_rgb, cv2.COLOR_RGB2GRAY)
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(int(min(w, h) * 0.04), int(min(w, h) * 0.04)),
            )
            if len(faces) > 0:
                valid_faces = [f for f in faces if f[1] < h * 0.65]
                chosen = valid_faces if valid_faces else faces
                chosen = sorted(chosen, key=lambda f: f[2] * f[3], reverse=True)
                fx, fy, fw, fh = chosen[0]
                haar_bbox = (fx, fy, fw, fh)

                if landmarker:
                    import mediapipe as mp
                    # Pad face region generously (45% horizontally, 55% vertically)
                    px = int(fw * 0.45)
                    py = int(fh * 0.55)
                    x1 = max(0, fx - px)
                    y1 = max(0, fy - py)
                    x2 = min(w, fx + fw + px)
                    y2 = min(h, fy + fh + py)

                    face_crop = np.ascontiguousarray(np_rgb[y1:y2, x1:x2])
                    if face_crop.shape[0] >= 20 and face_crop.shape[1] >= 20:
                        mp_crop = mp.Image(image_format=mp.ImageFormat.SRGB, data=face_crop)
                        res = landmarker.detect(mp_crop)
                        if res.face_landmarks:
                            crop_w = x2 - x1
                            crop_h = y2 - y1
                            pts = {}
                            for idx, lm in enumerate(res.face_landmarks[0]):
                                pts[idx] = np.array([x1 + lm.x * crop_w, y1 + lm.y * crop_h])
                            logger.info("[FaceUtils] Stage 1 success: Haar crop + MediaPipe (478 landmarks).")
                            return pts
        except Exception as e:
            logger.warning("[FaceUtils] Stage 1 error: %s", e)

    # ── STAGE 2: Direct MediaPipe on Full Image ──────────────────────────────
    if landmarker:
        try:
            import mediapipe as mp
            mp_full = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(np_rgb))
            res_full = landmarker.detect(mp_full)
            if res_full.face_landmarks:
                pts = {}
                for idx, lm in enumerate(res_full.face_landmarks[0]):
                    pts[idx] = np.array([lm.x * w, lm.y * h])
                logger.info("[FaceUtils] Stage 2 success: Direct full-image MediaPipe (478 landmarks).")
                return pts
        except Exception as e:
            logger.warning("[FaceUtils] Stage 2 error: %s", e)

    # ── STAGE 3: Multi-Crop Upper Region Scan with MediaPipe ───────────────────
    if landmarker:
        import mediapipe as mp
        crop_configs = [
            (0, int(h * 0.35), 0, w),                           # Upper 35% (standing body)
            (0, int(h * 0.50), 0, w),                           # Upper 50% (half body)
            (0, int(h * 0.25), 0, w),                           # Upper 25% (tall full body)
            (0, int(h * 0.55), int(w * 0.15), int(w * 0.85)),   # Upper-center 55%
        ]
        for y1, y2, x1, x2 in crop_configs:
            crop = np.ascontiguousarray(np_rgb[y1:y2, x1:x2])
            if crop.shape[0] < 20 or crop.shape[1] < 20:
                continue
            try:
                mp_crop = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop)
                res_crop = landmarker.detect(mp_crop)
                if res_crop.face_landmarks:
                    crop_w = x2 - x1
                    crop_h = y2 - y1
                    pts = {}
                    for idx, lm in enumerate(res_crop.face_landmarks[0]):
                        pts[idx] = np.array([x1 + lm.x * crop_w, y1 + lm.y * crop_h])
                    logger.info("[FaceUtils] Stage 3 success: Multi-crop MediaPipe at [%d:%d, %d:%d].", y1, y2, x1, x2)
                    return pts
            except Exception as e:
                logger.debug("[FaceUtils] Crop scan [%d:%d] exception: %s", y1, y2, e)

    # ── STAGE 4: Anatomical Geometric Projection from Detected Bbox ───────────
    if allow_fallback:
        bbox = haar_bbox or detect_face_bbox_opencv(np_rgb, allow_default_crop=True)
        if bbox:
            logger.info("[FaceUtils] Stage 4: Geometric anatomical fallback anchored to bbox %s", bbox)
            return generate_geometric_landmarks(bbox, w, h)

    logger.warning("[FaceUtils] Face detection completely failed.")
    return None


def detect_pose_landmarks(np_rgb: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    Detect 33 full-body pose landmarks using MediaPipe PoseLandmarker task.
    Returns dictionary with sub-pixel coordinates for:
    - Shoulders: 'left_shoulder' (#11), 'right_shoulder' (#12), 'shoulder_center', 'shoulder_span'
    - Arms & Wrists: 'left_elbow' (#13), 'right_elbow' (#14), 'left_wrist' (#15), 'right_wrist' (#16)
    - Hands & Fingers: 'left_index' (#19), 'right_index' (#20), 'left_pinky' (#17), 'right_pinky' (#18)
    - Lower Body: 'left_hip' (#23), 'right_hip' (#24), 'hip_center', 'hip_span', 'torso_height'
    - Legs & Feet: 'left_knee' (#25), 'right_knee' (#26), 'left_ankle' (#27), 'right_ankle' (#28)
    - 'raw': dict mapping 0..32 -> np.ndarray([x, y])
    - 'has_pose': bool (True if detected by PoseLandmarker, False if anatomically synthesized from face)
    """
    h, w = np_rgb.shape[:2]
    landmarker = get_mediapipe_pose_landmarker()

    if landmarker:
        try:
            import mediapipe as mp
            mp_full = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(np_rgb))
            res = landmarker.detect(mp_full)
            if res.pose_landmarks and len(res.pose_landmarks) > 0:
                lms = res.pose_landmarks[0]
                raw = {}
                for idx, lm in enumerate(lms):
                    raw[idx] = np.array([lm.x * w, lm.y * h])

                p_l_shoulder = raw[11]
                p_r_shoulder = raw[12]
                p_l_hip = raw[23]
                p_r_hip = raw[24]
                shoulder_center = (p_l_shoulder + p_r_shoulder) / 2.0
                shoulder_span = float(np.linalg.norm(p_l_shoulder - p_r_shoulder))
                hip_center = (p_l_hip + p_r_hip) / 2.0
                hip_span = float(np.linalg.norm(p_l_hip - p_r_hip))
                torso_height = float(np.linalg.norm(shoulder_center - hip_center))

                return {
                    "raw": raw,
                    "has_pose": True,
                    "left_shoulder": p_l_shoulder,
                    "right_shoulder": p_r_shoulder,
                    "shoulder_center": shoulder_center,
                    "shoulder_span": shoulder_span,
                    "left_elbow": raw[13],
                    "right_elbow": raw[14],
                    "left_wrist": raw[15],
                    "right_wrist": raw[16],
                    "left_pinky": raw[17],
                    "right_pinky": raw[18],
                    "left_index": raw[19],
                    "right_index": raw[20],
                    "left_hip": p_l_hip,
                    "right_hip": p_r_hip,
                    "hip_center": hip_center,
                    "hip_span": hip_span,
                    "torso_height": torso_height,
                    "left_knee": raw[25],
                    "right_knee": raw[26],
                    "left_ankle": raw[27],
                    "right_ankle": raw[28],
                }
        except Exception as e:
            logger.warning("[PoseUtils] Direct pose landmarker error: %s", e)

    # Fallback to synthesizing anatomical pose from face landmarks (for close-up portraits)
    face_lms = detect_face_landmarks(np_rgb, allow_fallback=True)
    if face_lms and 152 in face_lms and 10 in face_lms and 234 in face_lms and 454 in face_lms:
        p_chin = face_lms[152]
        p_forehead = face_lms[10]
        p_left_ear = face_lms[234]
        p_right_ear = face_lms[454]
        face_w = float(np.linalg.norm(p_right_ear - p_left_ear))
        face_h = float(np.linalg.norm(p_chin - p_forehead))
        cx = float((p_left_ear[0] + p_right_ear[0]) / 2.0)
        chin_y = float(p_chin[1])

        shoulder_span = face_w * 2.3
        shoulder_y = chin_y + face_h * 0.45
        p_l_shoulder = np.array([cx + shoulder_span / 2.0, shoulder_y])
        p_r_shoulder = np.array([cx - shoulder_span / 2.0, shoulder_y])
        shoulder_center = np.array([cx, shoulder_y])

        hip_span = shoulder_span * 0.90
        hip_y = chin_y + face_h * 2.5
        p_l_hip = np.array([cx + hip_span / 2.0, hip_y])
        p_r_hip = np.array([cx - hip_span / 2.0, hip_y])
        hip_center = np.array([cx, hip_y])
        torso_height = float(hip_y - shoulder_y)

        # Approximate wrist and hand locations at hips/flanks
        p_l_wrist = np.array([cx + shoulder_span * 0.65, hip_y])
        p_r_wrist = np.array([cx - shoulder_span * 0.65, hip_y])
        p_l_index = np.array([cx + shoulder_span * 0.68, hip_y + face_h * 0.3])
        p_r_index = np.array([cx - shoulder_span * 0.68, hip_y + face_h * 0.3])

        return {
            "raw": {},
            "has_pose": False,
            "left_shoulder": p_l_shoulder,
            "right_shoulder": p_r_shoulder,
            "shoulder_center": shoulder_center,
            "shoulder_span": shoulder_span,
            "left_elbow": np.array([cx + shoulder_span * 0.60, shoulder_y + torso_height * 0.5]),
            "right_elbow": np.array([cx - shoulder_span * 0.60, shoulder_y + torso_height * 0.5]),
            "left_wrist": p_l_wrist,
            "right_wrist": p_r_wrist,
            "left_pinky": p_l_wrist,
            "right_pinky": p_r_wrist,
            "left_index": p_l_index,
            "right_index": p_r_index,
            "left_hip": p_l_hip,
            "right_hip": p_r_hip,
            "hip_center": hip_center,
            "hip_span": hip_span,
            "torso_height": torso_height,
            "left_knee": np.array([cx + hip_span * 0.45, min(float(h), hip_y + face_h * 2.0)]),
            "right_knee": np.array([cx - hip_span * 0.45, min(float(h), hip_y + face_h * 2.0)]),
            "left_ankle": np.array([cx + hip_span * 0.45, float(h)]),
            "right_ankle": np.array([cx - hip_span * 0.45, float(h)]),
        }

    return None



def get_mediapipe_hand_landmarker():
    """Retrieve or initialize the MediaPipe Tasks HandLandmarker singleton for 21-joint 3D hand tracking."""
    global _cached_hand_landmarker
    if _cached_hand_landmarker is not None:
        return _cached_hand_landmarker

    if not os.path.exists(HAND_TASK_MODEL_PATH):
        logger.warning("MediaPipe hand_landmarker.task not found at %s", HAND_TASK_MODEL_PATH)
        return None

    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=HAND_TASK_MODEL_PATH)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=2,
            min_hand_detection_confidence=0.20,
            min_hand_presence_confidence=0.20,
            min_tracking_confidence=0.20,
        )
        _cached_hand_landmarker = vision.HandLandmarker.create_from_options(options)
        logger.info("MediaPipe HandLandmarker task loaded successfully from %s", HAND_TASK_MODEL_PATH)
        return _cached_hand_landmarker
    except Exception as e:
        logger.warning("Failed to initialize MediaPipe HandLandmarker: %s", e)
        return None


def detect_hand_landmarks(
    np_rgb: np.ndarray,
    pose_hint: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Detect 21 3D hand landmarks for high-precision virtual ring placement and finger geometry.
    Two-stage detection:
    1. Direct full-image HandLandmarker (best for hand photos, upper-body shots, selfies).
    2. Multi-crop around wrist coordinates if pose_hint is provided (handles full-body portraits).
    3. Anatomical fallback anchored to wrists or waist if hand is obscured.
    """
    detector = get_mediapipe_hand_landmarker()
    if detector is None or np_rgb is None:
        return None

    h, w = np_rgb.shape[:2]
    import mediapipe as mp

    def _parse_hand(lms, handedness_str="Right", offset_x=0.0, offset_y=0.0, scale_x=1.0, scale_y=1.0):
        raw = {}
        xs, ys = [], []
        for idx, lm in enumerate(lms):
            px = float(lm.x * scale_x + offset_x)
            py = float(lm.y * scale_y + offset_y)
            pz = float(lm.z * scale_x)
            raw[idx] = np.array([px, py, pz])
            xs.append(px)
            ys.append(py)

        # Key finger coordinates (Ring finger is MCP 13 -> PIP 14 -> DIP 15 -> TIP 16)
        p_ring_mcp = raw[13][:2]  # base knuckle
        p_ring_pip = raw[14][:2]  # proximal interphalangeal joint
        p_ring_dip = raw[15][:2]
        p_ring_tip = raw[16][:2]

        p_middle_mcp = raw[9][:2]   # adjacent medial finger
        p_middle_pip = raw[10][:2]
        p_pinky_mcp = raw[17][:2]    # adjacent lateral finger
        p_pinky_pip = raw[18][:2]

        # Vector along proximal phalanx (from knuckle to mid joint)
        finger_vec = p_ring_pip - p_ring_mcp
        phalanx_len = float(np.linalg.norm(finger_vec))
        if phalanx_len < 2.0:
            finger_vec = np.array([0.0, -10.0])
            phalanx_len = 10.0

        finger_dir = finger_vec / phalanx_len
        angle_rad = math.atan2(finger_dir[1], finger_dir[0])
        angle_deg = math.degrees(angle_rad)

        # Caliber (thickness) between adjacent fingers (middle and pinky)
        d_middle = float(np.linalg.norm(p_ring_mcp - p_middle_mcp))
        d_pinky = float(np.linalg.norm(p_ring_mcp - p_pinky_mcp))
        valid_ds = [d for d in [d_middle, d_pinky] if d > 5.0]
        interdigital_width = float(min(valid_ds) * 0.95) if valid_ds else max(16.0, phalanx_len * 0.45)

        # Center point sits on the proximal phalanx, ~38% along the joint from knuckle
        ring_center = p_ring_mcp + finger_vec * 0.38

        # Hand bounding box for zooming / closeup
        pad = int(max(xs) - min(xs)) * 0.2
        hand_bbox = (
            max(0, int(min(xs) - pad)),
            max(0, int(min(ys) - pad)),
            min(w, int(max(xs) + pad)),
            min(h, int(max(ys) + pad)),
        )

        return {
            "has_hand": True,
            "raw": raw,
            "handedness": handedness_str,
            "ring_mcp": p_ring_mcp,
            "ring_pip": p_ring_pip,
            "ring_dip": p_ring_dip,
            "ring_tip": p_ring_tip,
            "middle_mcp": p_middle_mcp,
            "pinky_mcp": p_pinky_mcp,
            "wrist": raw[0][:2],
            "ring_center": ring_center,
            "finger_dir": finger_dir,
            "angle_deg": angle_deg,
            "phalanx_length": phalanx_len,
            "interdigital_width": interdigital_width,
            "hand_bbox": hand_bbox,
        }

    # Stage 1: Direct full image inference
    try:
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(np_rgb))
        res = detector.detect(mp_img)
        if res and res.hand_landmarks and len(res.hand_landmarks) > 0:
            lms = res.hand_landmarks[0]
            hand_label = "Right"
            if res.handedness and len(res.handedness) > 0 and len(res.handedness[0]) > 0:
                hand_label = res.handedness[0][0].category_name
            logger.info("[HandUtils] Direct HandLandmarker success: %s hand with 21 landmarks", hand_label)
            return _parse_hand(lms, hand_label, offset_x=0.0, offset_y=0.0, scale_x=float(w), scale_y=float(h))
    except Exception as e:
        logger.warning("[HandUtils] Direct hand detection error: %s", e)

    # Stage 2: Crop around wrists if pose_hint is available (for full-body portraits)
    if pose_hint:
        for wrist_key in ["left_wrist", "right_wrist"]:
            if wrist_key in pose_hint:
                w_pt = pose_hint[wrist_key]
                wx, wy = int(w_pt[0]), int(w_pt[1])
                crop_size = int(max(w, h) * 0.22)
                x1 = max(0, wx - crop_size // 2)
                y1 = max(0, wy - crop_size // 2)
                x2 = min(w, x1 + crop_size)
                y2 = min(h, y1 + crop_size)
                x1 = max(0, x2 - crop_size)
                y1 = max(0, y2 - crop_size)

                crop = np_rgb[y1:y2, x1:x2]
                ch, cw = crop.shape[:2]
                if ch > 40 and cw > 40:
                    try:
                        mp_crop = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop))
                        c_res = detector.detect(mp_crop)
                        if c_res and c_res.hand_landmarks and len(c_res.hand_landmarks) > 0:
                            lms = c_res.hand_landmarks[0]
                            hand_label = "Left" if "left" in wrist_key else "Right"
                            logger.info("[HandUtils] Wrist crop HandLandmarker success for %s: %s hand", wrist_key, hand_label)
                            return _parse_hand(
                                lms,
                                hand_label,
                                offset_x=float(x1),
                                offset_y=float(y1),
                                scale_x=float(cw),
                                scale_y=float(ch),
                            )
                    except Exception as e:
                        logger.debug("[HandUtils] Crop detection error for %s: %s", wrist_key, e)

    return None
