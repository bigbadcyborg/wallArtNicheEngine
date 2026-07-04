"""Provider-neutral generation dimensions for portrait wall-art ratios."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationDimensions:
    """Pixel dimensions for an image generation request."""

    width: int
    height: int

    def as_tuple(self) -> tuple[int, int]:
        return self.width, self.height


_GENERATION_DIMENSIONS: dict[str, GenerationDimensions] = {
    "2:3": GenerationDimensions(1536, 2304),
    "3:4": GenerationDimensions(1536, 2048),
    "4:5": GenerationDimensions(1600, 2000),
    "11:14": GenerationDimensions(1760, 2240),
    "A-series": GenerationDimensions(1664, 2352),
}

_RATIO_ALIASES: dict[str, str] = {
    "2x3": "2:3",
    "3x4": "3:4",
    "4x5": "4:5",
    "11x14": "11:14",
    "a-series": "A-series",
    "aseries": "A-series",
    "a series": "A-series",
}


def generation_dimensions_for(aspect_ratio: str) -> GenerationDimensions:
    """Return safe portrait generation dimensions for a supported wall-art ratio.

    Accepts the API aspect-ratio labels and export-ratio aliases while keeping all
    returned dimensions portrait-oriented.
    """
    key = _normalize_ratio(aspect_ratio)
    try:
        return _GENERATION_DIMENSIONS[key]
    except KeyError as exc:
        supported = ", ".join(_GENERATION_DIMENSIONS)
        raise ValueError(f"Unsupported aspect ratio '{aspect_ratio}'. Supported ratios: {supported}") from exc


def _normalize_ratio(aspect_ratio: str) -> str:
    ratio = aspect_ratio.strip()
    return _RATIO_ALIASES.get(ratio, _RATIO_ALIASES.get(ratio.lower(), ratio))
