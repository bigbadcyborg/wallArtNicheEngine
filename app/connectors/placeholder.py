"""Deterministic placeholder image generation for offline/test image flows."""
import io
import textwrap

from PIL import Image, ImageDraw

_PLACEHOLDER_SIZES = {
    "2:3": (4000, 6000),
    "3:4": (3900, 5200),
    "4:5": (4000, 5000),
    "1:1": (4200, 4200),
    "9:16": (2880, 5120),
}


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return deterministic placeholder bytes using the image connector tuple contract."""
    return generate_placeholder_image(prompt, aspect_ratio), "placeholder", True


def generate_placeholder_image(prompt: str, aspect_ratio: str) -> bytes:
    """Create a labeled print-sized PNG placeholder for local development and tests."""
    w, h = _PLACEHOLDER_SIZES.get(aspect_ratio, (4000, 5000))
    img = Image.new("RGB", (w, h))
    top, bottom = (216, 196, 166), (140, 111, 78)
    for y in range(h):  # simple vertical gradient
        t = y / h
        img.paste(tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)), (0, y, w, y + 1))
    draw = ImageDraw.Draw(img)
    lines = ["PLACEHOLDER IMAGE", "configure an image provider for real generation", "", "prompt:"]
    lines += textwrap.wrap(prompt, width=48)[:14]
    draw.multiline_text((w * 0.08, h * 0.30), "\n".join(lines), fill=(40, 30, 20),
                        font_size=int(w * 0.028), spacing=int(w * 0.014))
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(300, 300))
    return buf.getvalue()
