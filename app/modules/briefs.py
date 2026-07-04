"""designBriefGenerator (SRS §7.3): approved niches -> original design briefs."""
from sqlalchemy.orm import Session

from ..connectors import ai_provider
from ..models import DesignBrief, Keyword, NicheReport
from . import compliance


def generate_for_niche(db: Session, niche: NicheReport, count: int = 5) -> list[DesignBrief]:
    if niche.status != "approved":
        raise ValueError("gate1: niche must be approved before briefs are generated")

    keyword = db.get(Keyword, niche.keywordId)
    context = {
        "phrase": keyword.phrase,
        "nicheScore": niche.nicheScore,
        "visualGap": niche.explanation.get("visualGapScore"),
        "styles": niche.explanation.get("visualGapScore"),
        "riskFlags": [f["term"] for f in niche.riskFlags] or "none",
    }
    raw_briefs, generated_by = ai_provider.generate_briefs(context, count)

    saved: list[DesignBrief] = []
    for raw in raw_briefs:
        # briefs are scanned too: an AI or template slip-up must not pass silently
        scan = compliance.scan_text(*(str(v) for v in raw.values()))
        brief = DesignBrief(
            nicheId=niche.nicheId,
            nicheName=raw.get("nicheName", keyword.phrase),
            targetBuyer=raw.get("targetBuyer", ""),
            roomContext=raw.get("roomContext", ""),
            styleDirection=raw.get("styleDirection", ""),
            colorPalette=raw.get("colorPalette", ""),
            subjectMatter=raw.get("subjectMatter", ""),
            composition=raw.get("composition", ""),
            ratios=raw.get("ratios", ai_provider.REQUIRED_RATIOS),
            productFormat=raw.get("productFormat", "digital download bundle"),
            negativePrompt=raw.get("negativePrompt", ""),
            ipSafetyNotes=raw.get("ipSafetyNotes", ""),
            generatedBy=generated_by,
            status="rejected" if scan.blocked else "draft",
        )
        db.add(brief)
        saved.append(brief)
    db.commit()
    return saved
