"""listingGenerator (SRS §7.7): marketplace-ready metadata for an approved asset."""
from sqlalchemy.orm import Session

from ..connectors import ai_provider
from ..models import DesignAsset, DesignBrief, Listing
from . import compliance


def generate_for_asset(db: Session, asset: DesignAsset) -> Listing:
    brief: DesignBrief = db.get(DesignBrief, asset.briefId)
    brief_dict = {
        "nicheName": brief.nicheName,
        "targetBuyer": brief.targetBuyer,
        "roomContext": brief.roomContext,
        "styleDirection": brief.styleDirection,
        "colorPalette": brief.colorPalette,
        "subjectMatter": brief.subjectMatter,
        "productFormat": brief.productFormat,
    }
    data, generated_by = ai_provider.generate_listing(brief_dict, is_ai_assisted=asset.isAiAssisted)

    scan = compliance.scan_text(data["title"], data["description"], *data["tags"])
    listing = Listing(
        assetId=asset.assetId,
        marketplace="etsy",
        title=data["title"][:140],
        description=data["description"],
        tags=data["tags"],
        seoKeywords=data.get("seoKeywords", []),
        price=data.get("priceSuggestion"),
        aiDisclosure=data.get("aiDisclosure", ""),
        complianceFlags=scan.flags,
        generatedBy=generated_by,
        status="blocked" if scan.blocked else "draft",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing
