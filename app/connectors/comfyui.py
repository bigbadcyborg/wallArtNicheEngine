"""ComfyUI prompt helpers.

Keeps provider-specific prompt wiring in one place so API routes can expose
ComfyUI-ready fields without duplicating business or compliance wording.
"""

STANDARD_NEGATIVE_PROMPT = (
    "text, letters, words, numbers, watermark, signature, logo, brand name, "
    "trademark, copyrighted character, celebrity likeness, frame, mockup, "
    "room scene, low resolution, blurry, jpeg artifacts, distorted anatomy, "
    "malformed hands, extra fingers, cropped subject, neon colors"
)


def build_prompt_pair(positive_prompt: str) -> dict[str, str]:
    """Return ComfyUI-ready positive and negative prompts."""
    return {
        "positivePrompt": positive_prompt,
        "negativePrompt": STANDARD_NEGATIVE_PROMPT,
    }
