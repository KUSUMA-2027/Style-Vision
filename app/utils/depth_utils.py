"""
StyleVision — Depth Estimation Utility (MiDaS)
Lightweight 2.5D depth mapping for pseudo-3D tilt effects.
"""
import logging
from typing import Optional, Tuple
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_midas_model = None
_midas_transform = None
_midas_device = None


def _get_device():
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_midas(model_type: str = "MiDaS_small"):
    """Load MiDaS depth model via torch hub (downloads weights on first run)."""
    global _midas_model, _midas_transform, _midas_device
    if _midas_model is not None:
        return _midas_model, _midas_transform, _midas_device

    import torch
    _midas_device = _get_device()
    logger.info(f"[Depth] Loading MiDaS ({model_type}) on {_midas_device}...")

    _midas_model = torch.hub.load("intel-isl/MiDaS", model_type, trust_repo=True)
    _midas_model.to(_midas_device)
    _midas_model.eval()

    midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
    if model_type == "MiDaS_small":
        _midas_transform = midas_transforms.small_transform
    else:
        _midas_transform = midas_transforms.default_transform

    logger.info("[Depth] MiDaS loaded successfully.")
    return _midas_model, _midas_transform, _midas_device


def estimate_depth(image: Image.Image, model_type: str = "MiDaS_small") -> np.ndarray:
    """
    Estimate depth map from a PIL image.
    Returns: numpy array (H, W) float32, higher = closer to camera.
    """
    model, transform, device = load_midas(model_type)
    import torch

    img = np.array(image.convert("RGB"))
    input_batch = transform(img).to(device)

    with torch.no_grad():
        prediction = model(input_batch)
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=img.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

    depth = prediction.cpu().numpy()
    depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-6)
    return depth.astype(np.float32)


def depth_to_visual(depth: np.ndarray) -> Image.Image:
    """Convert depth map to a visualizable grayscale PIL image."""
    depth_vis = (depth * 255).astype(np.uint8)
    return Image.fromarray(depth_vis, mode="L")
