"""nicheScorer (SRS §7.2): turn stored research listings into a scored niche report.

All sub-scores are on a 0-100 scale; weights live in config/scoring.yaml so an
admin can retune without code changes (SRS §8.4).
"""
import statistics

from sqlalchemy.orm import Session

from ..config import scoring_config
from ..models import Keyword, NicheReport, ResearchListing
from . import compliance


def _demand_score(listings: list[ResearchListing]) -> tuple[float, str]:
    reviews = [l.reviewCount or 0 for l in listings]
    total = sum(reviews)
    # log-ish banding: 0 reviews -> 0, ~10k+ cumulative reviews across top results -> 100
    score = min(100.0, (total / 10000.0) * 100.0)
    return score, f"{total} cumulative reviews across {len(listings)} sampled listings"


def _competition_score(listings: list[ResearchListing]) -> tuple[float, str]:
    cfg = scoring_config()["competition"]
    n = len(listings)
    # research batches are samples; scale sample size into the configured band
    est = n * 100  # rough extrapolation from sample to marketplace
    if est <= cfg["low"]:
        score = 20.0
    elif est >= cfg["high"]:
        score = 90.0
    else:
        score = 20.0 + 70.0 * (est - cfg["low"]) / (cfg["high"] - cfg["low"])
    return score, f"~{est} estimated competing listings (sample of {n})"


def _price_score(listings: list[ResearchListing]) -> tuple[float, str]:
    cfg = scoring_config()["price"]
    prices = [l.price for l in listings if l.price]
    if not prices:
        return 40.0, "no price data; neutral score"
    median = statistics.median(prices)
    if median < cfg["floor"]:
        score = 10.0
    elif cfg["sweet_low"] <= median <= cfg["sweet_high"]:
        score = 90.0
    elif median > cfg["ceiling"]:
        score = 50.0
    else:
        score = 60.0
    return score, f"median price ${median:.2f} (sweet spot ${cfg['sweet_low']}-${cfg['sweet_high']})"


def _trend_score(listings: list[ResearchListing]) -> tuple[float, str]:
    ratings = [l.rating for l in listings if l.rating]
    if not ratings:
        return 50.0, "no rating data; neutral trend score"
    avg = sum(ratings) / len(ratings)
    score = max(0.0, min(100.0, (avg - 3.0) / 2.0 * 100.0))
    return score, f"avg rating {avg:.2f} used as buyer-satisfaction trend proxy"


def _visual_gap_score(listings: list[ResearchListing]) -> tuple[float, str]:
    styles = [l.detectedStyle for l in listings if l.detectedStyle]
    if not styles:
        return 50.0, "no style data; neutral visual gap score"
    unique_ratio = len(set(styles)) / len(styles)
    # low style diversity = repetitive market = bigger gap for something original
    score = max(0.0, min(100.0, (1.0 - unique_ratio) * 100.0 + 20.0))
    dominant = max(set(styles), key=styles.count)
    return score, f"dominant style '{dominant}' ({len(set(styles))} styles across {len(styles)} listings)"


def score_keyword(db: Session, keyword: Keyword) -> NicheReport:
    listings = db.query(ResearchListing).filter_by(keywordId=keyword.keywordId).all()
    cfg = scoring_config()
    weights, thresholds = cfg["weights"], cfg["thresholds"]

    demand, demand_why = _demand_score(listings)
    competition, comp_why = _competition_score(listings)
    price, price_why = _price_score(listings)
    trend, trend_why = _trend_score(listings)
    gap, gap_why = _visual_gap_score(listings)

    titles = [l.listingTitle for l in listings]
    comp_result = compliance.scan_text(keyword.phrase, *titles)
    ip_risk = comp_result.risk_score

    niche_score = (
        demand * weights["demandScore"]
        + price * weights["priceScore"]
        + trend * weights["trendScore"]
        + gap * weights["visualGapScore"]
        - competition * weights["competitionScore"]
        - ip_risk * weights["ipRiskScore"]
    )

    if comp_result.blocked or ip_risk >= thresholds["block_ip_risk"]:
        status = "blocked"
    elif niche_score < thresholds["min_niche_score"]:
        status = "needsReview"
    else:
        status = "pending"

    report = NicheReport(
        keywordId=keyword.keywordId,
        demandScore=round(demand, 1),
        competitionScore=round(competition, 1),
        priceScore=round(price, 1),
        trendScore=round(trend, 1),
        visualGapScore=round(gap, 1),
        ipRiskScore=round(ip_risk, 1),
        nicheScore=round(niche_score, 1),
        status=status,
        riskFlags=comp_result.flags,
        explanation={
            "demandScore": demand_why,
            "competitionScore": comp_why,
            "priceScore": price_why,
            "trendScore": trend_why,
            "visualGapScore": gap_why,
            "ipRiskScore": f"{len(comp_result.flags)} compliance flags",
        },
    )
    db.add(report)
    keyword.status = "blocked" if status == "blocked" else "researched"
    db.commit()
    db.refresh(report)
    return report
