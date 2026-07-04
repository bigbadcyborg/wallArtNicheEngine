"""qualityControlAgent (SRS §7.5): automated checks before human review.

Automated pass sets qualityStatus to passed/failed; a human reviewer must still
approve (qualityStatus=approved) before publishing — the gate chain enforces it.
"""
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from ..models import DesignAsset
from .assets import RATIO_EXPORTS
from . import compliance

MIN_MASTER_PIXELS = 2000 * 2000     # smallest master we accept for print work
RATIO_TOLERANCE = 0.02


def run_checks(db: Session, asset: DesignAsset) -> DesignAsset:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # master resolution
    with Image.open(asset.filePath) as img:
        w, h = img.size
    check("masterResolution", w * h >= MIN_MASTER_PIXELS,
          f"master is {w}x{h}px (minimum {MIN_MASTER_PIXELS:,} total pixels)")

    # all required ratios exported, with correct aspect ratio
    for label, (tw, th) in RATIO_EXPORTS.items():
        path = (asset.exports or {}).get(label)
        if not path or not Path(path).exists():
            check(f"export:{label}", False, "missing export")
            continue
        with Image.open(path) as img:
            ew, eh = img.size
        ok = abs((ew / eh) - (tw / th)) <= RATIO_TOLERANCE
        check(f"export:{label}", ok, f"{ew}x{eh}px")

    # clean file names (SRS §7.5 acceptance criteria)
    names = [Path(asset.filePath).name] + [Path(p).name for p in (asset.exports or {}).values()]
    clean = all(" " not in n and n == n.lower() for n in names)
    check("fileNames", clean, "lowercase, no spaces" if clean else f"unclean names: {names}")

    # filename-level IP scan (brand names sneaking in via upload name)
    scan = compliance.scan_text(*names)
    check("ipTermsInFilenames", not scan.blocked,
          "no blocked terms" if not scan.blocked else str(scan.flags))

    passed = all(c["ok"] for c in checks)
    asset.qualityReport = {"checks": checks, "passed": passed,
                           "note": "Automated pass only — human approval still required (gate4)."}
    asset.qualityStatus = "passed" if passed else "failed"
    db.commit()
    db.refresh(asset)
    return asset
