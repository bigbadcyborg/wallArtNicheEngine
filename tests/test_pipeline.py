"""End-to-end pipeline: keyword -> niche -> brief -> asset -> listing -> gates."""
import io

import pytest
from PIL import Image

from app.gates import check_publish_ready
from app.models import Keyword
from app.modules import (assets as assets_mod, briefs as briefs_mod,
                         listings as listings_mod, publisher, quality,
                         research, scoring)


def _master_png(w=3000, h=3000) -> bytes:
    img = Image.new("RGB", (w, h), (212, 180, 140))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def approved_listing(db):
    kw = Keyword(phrase="minimalist desert landscape")
    db.add(kw)
    db.commit()
    research.run_research(db, kw)
    niche = scoring.score_keyword(db, kw)
    niche.status = "approved"
    db.commit()

    briefs = briefs_mod.generate_for_niche(db, niche, count=2)
    brief = briefs[0]
    brief.status = "approved"
    db.commit()

    asset = assets_mod.create_asset(db, brief, _master_png(), "design.png", is_ai_assisted=True)
    assets_mod.export_ratios(db, asset)
    assets_mod.build_bundle(db, asset)
    quality.run_checks(db, asset)
    assert asset.qualityStatus == "passed", asset.qualityReport
    asset.qualityStatus = "approved"
    asset.complianceStatus = "approved"
    db.commit()

    listing = listings_mod.generate_for_asset(db, asset)
    return db, listing


def test_briefs_require_approved_niche(db):
    kw = Keyword(phrase="calm ocean print")
    db.add(kw)
    db.commit()
    research.run_research(db, kw)
    niche = scoring.score_keyword(db, kw)  # status pending, not approved
    with pytest.raises(ValueError):
        briefs_mod.generate_for_niche(db, niche)


def test_asset_exports_all_required_ratios(approved_listing):
    db, listing = approved_listing
    from app.models import DesignAsset
    asset = db.get(DesignAsset, listing.assetId)
    assert set(asset.exports) == set(assets_mod.RATIO_EXPORTS)
    assert asset.bundlePath and asset.bundlePath.endswith(".zip")


def test_ai_assisted_listing_carries_disclosure(approved_listing):
    db, listing = approved_listing
    assert listing.aiDisclosure
    assert listing.aiDisclosure in listing.description
    assert len(listing.tags) == 13
    assert all(len(t) <= 20 for t in listing.tags)


def test_gates_block_unapproved_listing(approved_listing):
    db, listing = approved_listing  # listing status is draft, not approved
    result = check_publish_ready(db, listing)
    assert not result.passed
    assert any("gate6" in f for f in result.failures)
    with pytest.raises(publisher.GateError):
        publisher.create_etsy_draft(db, listing)


def test_full_gate_chain_then_dry_run_draft(approved_listing):
    db, listing = approved_listing
    listing.status = "approved"
    db.commit()
    assert check_publish_ready(db, listing).passed

    listing = publisher.create_etsy_draft(db, listing)  # dry-run (no Etsy keys)
    assert listing.status == "draftCreated"
    assert listing.externalListingId is None
    assert listing.publishPayload["title"] == listing.title

    # gate7 still required for final publish
    assert not check_publish_ready(db, listing, final_publish=True).passed
    listing = publisher.approve_final_publish(db, listing)
    assert listing.status == "publishApproved"
    assert check_publish_ready(db, listing, final_publish=True).passed


def test_gate_regression_upstream_revocation(approved_listing):
    """Revoking an upstream gate re-blocks publishing (no gate may be skipped)."""
    db, listing = approved_listing
    listing.status = "approved"
    from app.models import DesignAsset
    asset = db.get(DesignAsset, listing.assetId)
    asset.complianceStatus = "needsRevision"
    db.commit()
    result = check_publish_ready(db, listing)
    assert not result.passed
    assert any("gate5" in f for f in result.failures)


def test_merch_package_is_manual_only(approved_listing):
    db, listing = approved_listing
    listing.status = "approved"
    db.commit()
    path = publisher.build_amazon_merch_package(db, listing)
    assert path.endswith(".zip")
    # the publisher module must expose no Merch upload function at all
    assert not any("upload" in name and "merch" in name.lower()
                   for name in dir(publisher))
