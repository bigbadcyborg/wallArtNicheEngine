"""Gemini image generation connector ("Nano Banana", gemini-2.5-flash-image).

Every call is a single stateless generateContent request containing only the
prompt — a brand-new context each time, no conversation history is ever sent.

Without GEMINI_API_KEY a labeled placeholder image is produced so the rest of
the pipeline (attach -> exports -> QC) stays testable offline.
"""
import base64
import io
import logging
import textwrap

import httpx
from PIL import Image, ImageDraw

from ..config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return (image_bytes, model_label, is_placeholder)."""
    if not settings.gemini_api_key:
        return _placeholder(prompt, aspect_ratio), "placeholder", True

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


_PLACEHOLDER_SIZES = {"2:3": (4000, 6000), "3:4": (3900, 5200), "4:5": (4000, 5000),
                      "1:1": (4200, 4200), "9:16": (2880, 5120)}


def _placeholder(prompt: str, aspect_ratio: str) -> bytes:
    w, h = _PLACEHOLDER_SIZES.get(aspect_ratio, (4000, 5000))
    img = Image.new("RGB", (w, h))
    top, bottom = (216, 196, 166), (140, 111, 78)
    for y in range(h):  # simple vertical gradient
        t = y / h
        img.paste(tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)), (0, y, w, y + 1))
    draw = ImageDraw.Draw(img)
    lines = ["PLACEHOLDER IMAGE", "set GEMINI_API_KEY for real generation", "", "prompt:"]
    lines += textwrap.wrap(prompt, width=48)[:14]
    draw.multiline_text((w * 0.08, h * 0.30), "\n".join(lines), fill=(40, 30, 20),
                        font_size=int(w * 0.028), spacing=int(w * 0.014))
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(300, 300))
    return buf.getvalue()
