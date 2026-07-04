"""Compliance gates (SRS §15 / SOUL.md workflowGates).

No product moves forward unless every upstream gate is approved. The publisher
calls check_publish_ready() and refuses to create even a *draft* listing until
gates 1-6 pass; final publish additionally requires gate 7 (publishApproved).
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .models import DesignAsset, DesignBrief, Listing, NicheReport


@dataclass
class GateResult:
    passed: bool = True
    failures: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.passed = False
        self.failures.append(message)


def check_publish_ready(db: Session, listing: Listing, *, final_publish: bool = False) -> GateResult:
    result = GateResult()

    asset: DesignAsset | None = db.get(DesignAsset, listing.assetId)
    if asset is None:
        result.fail("asset missing")
        return result
    brief: DesignBrief | None = db.get(DesignBrief, asset.briefId)
    niche: NicheReport | None = db.get(NicheReport, brief.nicheId) if brief else None

    if niche is None or niche.status != "approved":
        result.fail("gate1 nicheApproved: niche is not approved")
    if brief is None or brief.status != "approved":
        result.fail("gate2 briefApproved: brief is not approved")
    if asset.qualityStatus != "approved":
        result.fail("gate3/4 designApproved+qualityApproved: asset quality not human-approved")
    if asset.complianceStatus != "approved":
        result.fail("gate5 complianceApproved: asset compliance not approved")
    if listing.status not in ("approved", "publishApproved", "draftCreated"):
        result.fail("gate6 listingApproved: listing is not approved")
    if final_publish and listing.status != "publishApproved":
        result.fail("gate7 publishApproved: final publish not approved by adminUser")

    return result
