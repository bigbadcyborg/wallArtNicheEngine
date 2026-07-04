from app.models import Keyword
from app.modules import research, scoring


def _research_keyword(db, phrase: str) -> Keyword:
    kw = Keyword(phrase=phrase)
    db.add(kw)
    db.commit()
    research.run_research(db, kw)  # offline sample data (no Etsy keys in tests)
    return kw


def test_score_keyword_produces_report(db):
    kw = _research_keyword(db, "neutral boho bedroom")
    report = scoring.score_keyword(db, kw)
    assert report.nicheScore != 0
    for field in ("demandScore", "competitionScore", "priceScore",
                  "trendScore", "visualGapScore"):
        assert 0 <= getattr(report, field) <= 100
    assert report.status in ("pending", "needsReview")
    assert set(report.explanation) >= {"demandScore", "priceScore"}


def test_ip_risky_keyword_blocked(db):
    kw = _research_keyword(db, "disney princess nursery")
    report = scoring.score_keyword(db, kw)
    assert report.status == "blocked"
    assert report.ipRiskScore == 100.0
    assert kw.status == "blocked"


def test_weights_come_from_config(db):
    from app.config import scoring_config
    weights = scoring_config()["weights"]
    assert abs(weights["demandScore"] - 0.25) < 1e-9  # SRS §7.2 draft formula
