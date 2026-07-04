"""Etsy Open API v3 connector (SRS §14.1).

Draft-only by design: createDraftListing creates listings in draft state and this
client exposes no "activate listing" call — final publish is a manual step the
adminUser performs in Etsy after gate7 approval.

Runs in dry-run mode (returns the payload instead of calling Etsy) until
ETSY_API_KEY / ETSY_SHOP_ID / ETSY_ACCESS_TOKEN are configured.
"""
import logging
from pathlib import Path

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.etsy.com/v3/application"


class EtsyClient:
    def __init__(self):
        self.dry_run = not settings.etsy_configured

    def _headers(self) -> dict:
        return {
            "x-api-key": settings.etsy_api_key or "",
            "Authorization": f"Bearer {settings.etsy_access_token or ''}",
        }

    # ------------------------------------------------------------ research
    def search_listings(self, keyword: str, limit: int = 25) -> list[dict] | None:
        """findAllListingsActive. Returns None in dry-run mode (caller uses sample data)."""
        if self.dry_run:
            return None
        resp = httpx.get(
            f"{API_BASE}/listings/active",
            params={"keywords": keyword, "limit": limit, "sort_on": "score"},
            headers={"x-api-key": settings.etsy_api_key},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    # ------------------------------------------------------------ publishing
    def create_draft_listing(self, payload: dict) -> dict:
        """createDraftListing — the listing is created in Etsy's draft state."""
        if self.dry_run:
            logger.info("[dry-run] would create Etsy draft listing: %s", payload.get("title"))
            return {"dry_run": True, "listing_id": None, "payload": payload}
        resp = httpx.post(
            f"{API_BASE}/shops/{settings.etsy_shop_id}/listings",
            data=payload,
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"dry_run": False, "listing_id": str(data["listing_id"]), "payload": payload}

    def upload_listing_image(self, listing_id: str, image_path: str) -> dict:
        if self.dry_run:
            return {"dry_run": True, "image": image_path}
        with open(image_path, "rb") as f:
            resp = httpx.post(
                f"{API_BASE}/shops/{settings.etsy_shop_id}/listings/{listing_id}/images",
                files={"image": (Path(image_path).name, f)},
                headers=self._headers(),
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json()

    def upload_listing_file(self, listing_id: str, file_path: str) -> dict:
        """Attach the digital-download file (ZIP bundle) to a digital listing."""
        if self.dry_run:
            return {"dry_run": True, "file": file_path}
        with open(file_path, "rb") as f:
            resp = httpx.post(
                f"{API_BASE}/shops/{settings.etsy_shop_id}/listings/{listing_id}/files",
                files={"file": (Path(file_path).name, f)},
                data={"name": Path(file_path).name},
                headers=self._headers(),
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()


def build_draft_payload(listing, bundle_name: str | None) -> dict:
    """Map our Listing model onto Etsy createDraftListing fields (SRS §7.7)."""
    return {
        "quantity": 999,
        "title": listing.title,
        "description": listing.description,
        "price": listing.price or 8.99,
        "who_made": "i_did",
        "when_made": "2020_2026",
        "taxonomy_id": 2078,  # Art & Collectibles > Prints > Digital Prints
        "is_supply": False,
        "type": "download",
        "tags": ",".join(listing.tags or []),
        "should_auto_renew": False,
        # audit fields (stripped client-side by Etsy; kept for the dry-run record)
        "_aiDisclosure": listing.aiDisclosure,
        "_digitalBundle": bundle_name,
    }
