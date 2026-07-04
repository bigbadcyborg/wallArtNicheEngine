"""ComfyUI image generation connector.

This module owns the ComfyUI provider boundary used by the API router. The
actual ComfyUI workflow integration can be configured/extended here without
changing route response shape or API persistence code.
"""


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return (image_bytes, model_label, is_placeholder) for ComfyUI generation."""
    raise RuntimeError(
        "ComfyUI image provider is selected, but the ComfyUI connector is not configured. "
        "Set IMAGE_PROVIDER=placeholder for offline placeholders or IMAGE_PROVIDER=gemini "
        "with GEMINI_API_KEY for Gemini generation."
    )
