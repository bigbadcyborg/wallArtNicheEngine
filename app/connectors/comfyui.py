"""ComfyUI image generation connector.

Submits a small text-to-image workflow to ComfyUI's HTTP API and returns the
first generated image. Tests can mock the HTTP calls; no local ComfyUI server is
required for unit coverage.
"""
import io
import logging
from typing import Any

import httpx
from PIL import Image

from ..config import settings

logger = logging.getLogger(__name__)

MODEL_LABEL = "comfyui"

_ASPECT_RATIO_SIZES = {
    "2:3": (1024, 1536),
    "3:4": (1024, 1365),
    "4:5": (1024, 1280),
    "11x14": (1024, 1303),
    "A-series": (1024, 1448),
    "1:1": (1024, 1024),
    "9:16": (1024, 1820),
}


def dimensions_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    """Return ComfyUI generation dimensions for a supported aspect ratio."""
    return _ASPECT_RATIO_SIZES.get(aspect_ratio, _ASPECT_RATIO_SIZES["4:5"])


def build_workflow(prompt: str, aspect_ratio: str = "4:5") -> dict[str, Any]:
    """Build a minimal ComfyUI workflow that includes prompt and dimensions."""
    width, height = dimensions_for_aspect_ratio(aspect_ratio)
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "default.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "text, watermark, logo", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "wallart", "images": ["8", 0]}},
    }


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return (image_bytes, model_label, is_placeholder) from ComfyUI."""
    base_url = str(settings.comfyui_base_url).rstrip("/")
    workflow = build_workflow(prompt, aspect_ratio)
    try:
        submit = httpx.post(f"{base_url}/prompt", json={"prompt": workflow}, timeout=30)
        if submit.is_error:
            raise RuntimeError(f"ComfyUI error {submit.status_code}: {submit.text[:300]}")
        prompt_id = submit.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI returned no prompt_id")

        history = httpx.get(f"{base_url}/history/{prompt_id}", timeout=120)
        if history.is_error:
            raise RuntimeError(f"ComfyUI history error {history.status_code}: {history.text[:300]}")
        image_info = _first_image(history.json(), prompt_id)
        if not image_info:
            raise RuntimeError("ComfyUI returned no image")

        image = httpx.get(f"{base_url}/view", params=image_info, timeout=120)
        if image.is_error:
            raise RuntimeError(f"ComfyUI image fetch error {image.status_code}: {image.text[:300]}")
        return image.content, MODEL_LABEL, False
    except httpx.HTTPError as e:
        raise RuntimeError(f"ComfyUI request failed: {e}") from e
    except RuntimeError:
        if settings.comfyui_placeholder_on_failure:
            logger.exception("ComfyUI generation failed; using configured placeholder fallback")
            return _placeholder(prompt, aspect_ratio), "comfyui-placeholder", True
        raise


def _first_image(history: dict[str, Any], prompt_id: str) -> dict[str, str] | None:
    outputs = history.get(prompt_id, history).get("outputs", {})
    for output in outputs.values():
        images = output.get("images") or []
        if images:
            img = images[0]
            return {
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            }
    return None


def _placeholder(prompt: str, aspect_ratio: str) -> bytes:
    width, height = dimensions_for_aspect_ratio(aspect_ratio)
    img = Image.new("RGB", (width, height), (185, 170, 150))
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(300, 300))
    return buf.getvalue()
