"""analyticsAgent (SRS §7.9): performance tracking + niche feedback loop."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (DesignAsset, DesignBrief, Listing, NicheReport,
                      PerformanceRecord)


def record(db: Session, listing: Listing, views: int, favorites: int,
           sales: int, revenue: float) -> PerformanceRecord:
    rec = PerformanceRecord(listingId=listing.listingId, views=views,
                            favorites=favorites, sales=sales, revenue=revenue)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def niche_performance(db: Session) -> list[dict]:
    """Compare predicted nicheScore against actual sales per niche."""
    rows = (
        db.query(
            NicheReport,
            func.coalesce(func.sum(PerformanceRecord.views), 0),
            func.coalesce(func.sum(PerformanceRecord.favorites), 0),
            func.coalesce(func.sum(PerformanceRecord.sales), 0),
            func.coalesce(func.sum(PerformanceRecord.revenue), 0.0),
        )
        .join(DesignBrief, DesignBrief.nicheId == NicheReport.nicheId)
        .join(DesignAsset, DesignAsset.briefId == DesignBrief.briefId)
        .join(Listing, Listing.assetId == DesignAsset.assetId)
        .outerjoin(PerformanceRecord, PerformanceRecord.listingId == Listing.listingId)
        .group_by(NicheReport.nicheId)
        .all()
    )
    out = []
    for niche, views, favorites, sales, revenue in rows:
        if sales >= 3:
            recommendation = "expand: generate new design variants for this winning niche"
        elif views and sales == 0 and views > 200:
            recommendation = "revise: traffic without sales — review pricing and mockups"
        elif views == 0 and sales == 0:
            recommendation = "wait: not enough data yet"
        else:
            recommendation = "monitor"
        out.append({
            "nicheId": niche.nicheId,
            "predictedScore": niche.nicheScore,
            "views": int(views), "favorites": int(favorites),
            "sales": int(sales), "revenue": float(revenue),
            "recommendation": recommendation,
        })
    return out
