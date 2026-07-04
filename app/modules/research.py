"""researchAgent (SRS §7.1): collect marketplace signals for a seed keyword.

Uses the Etsy Open API when configured; otherwise generates clearly-labeled
deterministic sample data (isSampleData=True) so scoring and the rest of the
pipeline can be exercised offline. No scraping — API routes only (SRS §3.2).
"""
import hashlib
import random

from sqlalchemy.orm import Session

from ..connectors.etsy import EtsyClient
from ..models import Keyword, ResearchListing

_STYLES = ["minimalist", "boho", "vintage", "watercolor", "line art", "abstract", "botanical"]
_AUDIENCES = ["new parents", "renters", "office workers", "students", "homeowners"]


def run_research(db: Session, keyword: Keyword, limit: int = 25) -> list[ResearchListing]:
    client = EtsyClient()
    raw = client.search_listings(keyword.phrase, limit=limit)

    rows: list[ResearchListing] = []
    if raw is not None:
        for item in raw:
            price_data = item.get("price") or {}
            amount = price_data.get("amount")
            divisor = price_data.get("divisor") or 100
            rows.append(ResearchListing(
                keywordId=keyword.keywordId,
                marketplace="etsy",
                listingTitle=item.get("title", ""),
                price=(amount / divisor) if amount else None,
                reviewCount=item.get("num_favorers"),
                rating=None,
                listingUrl=item.get("url"),
                shopName=str(item.get("shop_id", "")),
                isSampleData=False,
            ))
    else:
        rows = _sample_listings(keyword, limit)

    db.add_all(rows)
    db.commit()
    return rows


def _sample_listings(keyword: Keyword, limit: int) -> list[ResearchListing]:
    """Deterministic per-keyword sample data for offline mode."""
    seed = int(hashlib.sha256(keyword.phrase.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    rows = []
    for i in range(limit):
        style = rng.choice(_STYLES)
        rows.append(ResearchListing(
            keywordId=keyword.keywordId,
            marketplace="etsy",
            listingTitle=f"{style.title()} {keyword.phrase.title()} Print Set of {rng.randint(1, 3)} [SAMPLE DATA]",
            price=round(rng.uniform(3.5, 24.0), 2),
            reviewCount=rng.randint(0, 1500),
            rating=round(rng.uniform(3.8, 5.0), 2),
            category="Digital Prints",
            listingUrl=None,
            shopName=f"sampleShop{rng.randint(1, 8)}",
            detectedStyle=style,
            detectedAudience=rng.choice(_AUDIENCES),
            isSampleData=True,
        ))
    return rows
