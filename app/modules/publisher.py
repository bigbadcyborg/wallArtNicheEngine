"""publisherAgent (SRS §7.8): create Etsy drafts, prepare Amazon packages.

Hard rules enforced here:
- Etsy listings are created in DRAFT state only; there is no auto-publish path.
- Amazon Merch: manual upload package only. There is deliberately no code path
  that uploads to Merch (SRS §5.2 / SOUL.md forbiddenActions).
- Every publish action passes through the gate chain (app/gates.py) first.
"""
import json
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..connectors.etsy import EtsyClient, build_draft_payload
from ..gates import check_publish_ready
from ..models import DesignAsset, Listing


class GateError(Exception):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("; ".join(failures))


def create_etsy_draft(db: Session, listing: Listing) -> Listing:
    gates = check_publish_ready(db, listing)
    if not gates.passed:
        raise GateError(gates.failures)

    asset: DesignAsset = db.get(DesignAsset, listing.assetId)
    client = EtsyClient()
    payload = build_draft_payload(listing, Path(asset.bundlePath).name if asset.bundlePath else None)
    result = client.create_draft_listing(payload)

    listing.publishPayload = payload
    if result["listing_id"]:
        listing.externalListingId = result["listing_id"]
        # attach preview image (first export) and the digital bundle
        first_export = next(iter((asset.exports or {}).values()), None)
        if first_export:
            client.upload_listing_image(result["listing_id"], first_export)
        if asset.bundlePath:
            client.upload_listing_file(result["listing_id"], asset.bundlePath)
    listing.status = "draftCreated"
    db.commit()
    db.refresh(listing)
    return listing


def build_amazon_merch_package(db: Session, listing: Listing) -> str:
    """Manual-upload package ONLY — never uploaded programmatically."""
    gates = check_publish_ready(db, listing)
    if not gates.passed:
        raise GateError(gates.failures)

    asset: DesignAsset = db.get(DesignAsset, listing.assetId)
    out_dir = settings.storage_dir / "amazon-merch-manual"
    out_dir.mkdir(parents=True, exist_ok=True)
    package_path = out_dir / f"merch-manual-{listing.listingId[:8]}.zip"

    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.txt", (
            "AMAZON MERCH ON DEMAND — MANUAL UPLOAD PACKAGE\n"
            "Amazon prohibits scripted bulk uploads. Upload this content by hand.\n\n"
            f"Title: {listing.title}\n\nDescription:\n{listing.description}\n\n"
            f"Suggested price: ${listing.price}\n"
        ))
        for label, path in (asset.exports or {}).items():
            if Path(path).exists():
                zf.write(path, arcname=f"art/{Path(path).name}")

    return str(package_path)


def build_amazon_seller_payload(db: Session, listing: Listing) -> dict:
    """SP-API Listings Items payload prep (SRS §14.2) — prepared, not submitted, in MVP."""
    gates = check_publish_ready(db, listing)
    if not gates.passed:
        raise GateError(gates.failures)
    return {
        "productType": "WALL_ART",
        "requirements": "LISTING",
        "attributes": {
            "item_name": [{"value": listing.title}],
            "product_description": [{"value": listing.description}],
            "list_price": [{"value": {"Amount": listing.price, "CurrencyCode": "USD"}}],
            "generic_keyword": [{"value": kw} for kw in (listing.seoKeywords or [])[:5]],
        },
        "_note": "Prepared payload only. Submission via SP-API is a phase-two integration.",
    }


def approve_final_publish(db: Session, listing: Listing) -> Listing:
    """gate7: adminUser signs off; actual activation is done by hand in Etsy."""
    gates = check_publish_ready(db, listing)
    if not gates.passed:
        raise GateError(gates.failures)
    listing.status = "publishApproved"
    db.commit()
    db.refresh(listing)
    return listing
