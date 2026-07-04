"""designGenerator / asset manager (SRS §7.4): master upload -> print-ready exports.

Accepts a manually uploaded master image (or AI-generated import), exports it to
every required ratio at print resolution, and zips a digital-download bundle.
"""
import re
import zipfile
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DesignAsset, DesignBrief

# Target pixel sizes: 300 DPI at common max print size for each ratio family.
RATIO_EXPORTS: dict[str, tuple[int, int]] = {
    "2x3":     (7200, 10800),   # up to 24x36 in
    "3x4":     (5400, 7200),    # up to 18x24 in
    "4x5":     (4800, 6000),    # up to 16x20 in
    "11x14":   (3300, 4200),
    "A-series": (7016, 9933),   # A1 at 300 DPI; scales down to A5 losslessly
}

MAX_UPSCALE = 2.0  # refuse to blow a master up more than 2x (quality floor)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "design"


def create_asset(db: Session, brief: DesignBrief, master_bytes: bytes,
                 original_name: str, *, is_ai_assisted: bool) -> DesignAsset:
    if brief.status != "approved":
        raise ValueError("gate2: brief must be approved before design assets are created")

    asset_dir = settings.storage_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(original_name).suffix.lower() or ".png"
    slug = _slug(brief.nicheName)

    asset = DesignAsset(briefId=brief.briefId, fileType=ext.lstrip("."),
                        isAiAssisted=is_ai_assisted, filePath="")
    db.add(asset)
    db.flush()

    master_path = asset_dir / f"{slug}-{asset.assetId[:8]}-master{ext}"
    master_path.write_bytes(master_bytes)
    asset.filePath = str(master_path)
    db.commit()
    db.refresh(asset)
    return asset


def export_ratios(db: Session, asset: DesignAsset) -> DesignAsset:
    """Center-crop the master to each required ratio and save print-ready PNGs."""
    master = Image.open(asset.filePath).convert("RGB")
    out_dir = settings.storage_dir / "assets" / f"{asset.assetId[:8]}-exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    base = _slug(Path(asset.filePath).stem)

    exports: dict[str, str] = {}
    for label, (tw, th) in RATIO_EXPORTS.items():
        img = _crop_to_ratio(master, tw / th)
        scale = min(MAX_UPSCALE, tw / img.width)
        target = (min(tw, int(img.width * scale)), min(th, int(img.height * scale)))
        img = img.resize(target, Image.LANCZOS)
        path = out_dir / f"{base}-{label.lower()}.png"
        img.save(path, "PNG", dpi=(300, 300))
        exports[label] = str(path)

    asset.exports = exports
    db.commit()
    db.refresh(asset)
    return asset


def _crop_to_ratio(img: Image.Image, target_ratio: float) -> Image.Image:
    w, h = img.size
    current = w / h
    if abs(current - target_ratio) < 1e-3:
        return img.copy()
    if current > target_ratio:  # too wide -> crop sides
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = int(w / target_ratio)  # too tall -> crop top/bottom
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def build_bundle(db: Session, asset: DesignAsset) -> DesignAsset:
    """ZIP the ratio exports for Etsy digital-download delivery (SRS iteration 5)."""
    if not asset.exports:
        raise ValueError("export ratios before bundling")
    bundle_dir = settings.storage_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"{_slug(Path(asset.filePath).stem)}-bundle.zip"

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for label, path in asset.exports.items():
            zf.write(path, arcname=f"{label}/{Path(path).name}")
        zf.writestr(
            "READ-ME-printing-guide.txt",
            "Thank you for your purchase!\n\n"
            "Each folder contains the artwork in a different aspect ratio:\n"
            "  2x3  -> 4x6, 8x12, 12x18, 16x24, 20x30, 24x36 in\n"
            "  3x4  -> 6x8, 9x12, 12x16, 18x24 in\n"
            "  4x5  -> 4x5, 8x10, 16x20 in\n"
            "  11x14 -> 11x14 in\n"
            "  A-series -> A1, A2, A3, A4, A5\n\n"
            "All files are 300 DPI PNG. Print at home or through any print service.\n"
            "For personal use only. Do not resell or redistribute the files.\n",
        )

    asset.bundlePath = str(bundle_path)
    db.commit()
    db.refresh(asset)
    return asset
