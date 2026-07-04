"""Gemini image generation connector ("Nano Banana", gemini-2.5-flash-image).

Every call is a single stateless generateContent request containing only the
prompt — a brand-new context each time, no conversation history is ever sent.

Without GEMINI_API_KEY a labeled placeholder image is produced so the rest of
the pipeline (attach -> exports -> QC) stays testable offline.
"""
import base64
import logging

import httpx

from ..config import settings
from .placeholder import generate_placeholder_image

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return (image_bytes, model_label, is_placeholder)."""
    if not settings.gemini_api_key:
        return generate_placeholder_image(prompt, aspect_ratio), "placeholder", True

    url = f"{API_BASE}/{settings.gemini_image_model}:generateContent"
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    # Newest config first; older model versions reject fields they don't know,
    # so degrade gracefully: 2K size -> aspect ratio only -> bare request.
    generation_configs = [
        {"imageConfig": {"aspectRatio": aspect_ratio, "imageSize": "2K"}},
        {"imageConfig": {"aspectRatio": aspect_ratio}},
        None,
    ]
    for gc in generation_configs:
        body: dict = {"contents": [{"parts": [{"text": prompt}]}]}  # fresh context every call
        if gc:
            body["generationConfig"] = gc
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=120)
        except httpx.HTTPError as e:
            raise RuntimeError(f"Gemini request failed: {e}")
        if resp.status_code == 400 and gc is not None:
            logger.info("Gemini rejected generationConfig %s; retrying with simpler config", gc)
            continue  # config field not supported by this model version
        if resp.status_code == 429:
            if "limit: 0" in resp.text:
                raise RuntimeError(
                    "Your Google project has no quota for this image model (free tier "
                    "limit is 0 — image generation isn't included in the free tier). "
                    "Enable billing on the project at https://aistudio.google.com and retry."
                )
            raise RuntimeError(
                "Gemini rate limit hit (429). Wait a minute and try again, or check "
                "your API quota at https://aistudio.google.com."
            )
        if resp.is_error:
            raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text[:300]}")
        image = _extract_image(resp.json())
        if image is None:
            raise RuntimeError("Gemini returned no image (prompt may have been safety-blocked)")
        return image, settings.gemini_image_model, False
    raise RuntimeError("Gemini rejected all generationConfig variants")


def _extract_image(data: dict) -> bytes | None:
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    return None

