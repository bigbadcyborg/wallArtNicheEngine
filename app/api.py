"""REST API covering the SRS user flow (§12) and key screens (§13)."""
import csv
import io
import subprocess
import sys
from pathlib import Path

from PIL import Image

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .connectors import ai_provider, comfyui, gemini
from .models import (DesignAsset, DesignBrief, GeneratedImage, Keyword,
                     Listing, NicheReport, PerformanceRecord, ResearchListing,
                     ReviewLog)
from .modules import (analytics, assets as assets_mod, briefs as briefs_mod,
                      listings as listings_mod, publisher, quality,
                      research, scoring)

router = APIRouter(prefix="/api")


def _log_review(db: Session, entity_type: str, entity_id: str,
                decision: str, reviewer: str, notes: str) -> None:
    db.add(ReviewLog(entityType=entity_type, entityId=entity_id,
                     reviewerName=reviewer, decision=decision, notes=notes))
    db.commit()


class ReviewIn(BaseModel):
    decision: str            # approve | reject | needsRevision
    reviewer: str = "adminUser"
    notes: str = ""


class SignoffIn(BaseModel):
    """gate7 sign-off: no decision field — calling the endpoint IS the approval."""
    reviewer: str = "adminUser"
    notes: str = ""


# ================================================================ keywords + research

class KeywordIn(BaseModel):
    phrase: str
    category: str | None = None


@router.post("/keywords")
def add_keyword(body: KeywordIn, db: Session = Depends(get_db)):
    phrase = body.phrase.strip().lower()
    if not phrase:
        raise HTTPException(400, "phrase is required")
    existing = db.query(Keyword).filter_by(phrase=phrase).first()
    if existing:
        raise HTTPException(409, "keyword already exists")
    kw = Keyword(phrase=phrase, category=body.category)
    db.add(kw)
    db.commit()
    db.refresh(kw)

    listings = research.run_research(db, kw)
    report = scoring.score_keyword(db, kw)
    return {"keyword": _kw(kw), "listingsCollected": len(listings),
            "sampleData": bool(listings and listings[0].isSampleData),
            "niche": _niche(report)}


@router.get("/keywords")
def list_keywords(db: Session = Depends(get_db)):
    return [_kw(k) for k in db.query(Keyword).order_by(Keyword.createdAt.desc()).all()]


@router.get("/keywords/{keyword_id}/listings")
def keyword_listings(keyword_id: str, db: Session = Depends(get_db)):
    rows = db.query(ResearchListing).filter_by(keywordId=keyword_id).all()
    return [{
        "listingTitle": r.listingTitle, "price": r.price, "reviewCount": r.reviewCount,
        "rating": r.rating, "shopName": r.shopName, "detectedStyle": r.detectedStyle,
        "isSampleData": r.isSampleData, "listingUrl": r.listingUrl,
    } for r in rows]


# ================================================================ niches

@router.get("/niches")
def list_niches(db: Session = Depends(get_db)):
    rows = db.query(NicheReport).order_by(NicheReport.nicheScore.desc()).all()
    return [_niche(n, include_phrase=True, db=db) for n in rows]


@router.post("/niches/{niche_id}/review")
def review_niche(niche_id: str, body: ReviewIn, db: Session = Depends(get_db)):
    niche = db.get(NicheReport, niche_id)
    if not niche:
        raise HTTPException(404, "niche not found")
    if niche.status == "blocked":
        raise HTTPException(400, "blocked niches cannot be approved (IP risk)")
    niche.status = "approved" if body.decision == "approve" else "rejected"
    db.commit()
    _log_review(db, "niche", niche_id, body.decision, body.reviewer, body.notes)
    return _niche(niche)


# ================================================================ briefs

@router.post("/niches/{niche_id}/briefs")
def generate_briefs(niche_id: str, count: int = 5, db: Session = Depends(get_db)):
    niche = db.get(NicheReport, niche_id)
    if not niche:
        raise HTTPException(404, "niche not found")
    try:
        rows = briefs_mod.generate_for_niche(db, niche, count)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return [_brief(b) for b in rows]


@router.get("/briefs")
def list_briefs(db: Session = Depends(get_db)):
    return [_brief(b) for b in db.query(DesignBrief).order_by(DesignBrief.createdAt.desc()).all()]


@router.post("/briefs/{brief_id}/review")
def review_brief(brief_id: str, body: ReviewIn, db: Session = Depends(get_db)):
    brief = db.get(DesignBrief, brief_id)
    if not brief:
        raise HTTPException(404, "brief not found")
    brief.status = "approved" if body.decision == "approve" else "rejected"
    db.commit()
    _log_review(db, "brief", brief_id, body.decision, body.reviewer, body.notes)
    return _brief(brief)


# ================================================================ image prompt + generation

@router.get("/briefs/{brief_id}/image-prompt")
def image_prompt(brief_id: str, db: Session = Depends(get_db)):
    brief = db.get(DesignBrief, brief_id)
    if not brief:
        raise HTTPException(404, "brief not found")
    return {"briefId": brief_id, "nicheName": brief.nicheName,
            "prompt": ai_provider.build_image_prompt(brief)}


class GenerateImageIn(BaseModel):
    prompt: str
    aspectRatio: str = "4:5"


def _gen_url(g: GeneratedImage) -> str:
    return "/storage/" + Path(g.filePath).relative_to(settings.storage_dir.resolve()).as_posix()


def _gen(g: GeneratedImage) -> dict:
    return {"id": g.id, "prompt": g.prompt, "aspectRatio": g.aspectRatio,
            "url": _gen_url(g), "model": g.model, "isPlaceholder": g.isPlaceholder,
            "attachedAssetId": g.attachedAssetId, "createdAt": g.createdAt.isoformat()}


@router.post("/generate-image")
def generate_image(body: GenerateImageIn, db: Session = Depends(get_db)):
    """One stateless image-provider call per request — a fresh context every time."""
    if not body.prompt.strip():
        raise HTTPException(400, "prompt is required")
    try:
        if settings.image_provider == "comfyui":
            image_bytes, model, placeholder = comfyui.generate_image(body.prompt, body.aspectRatio)
        elif settings.image_provider == "gemini":
            image_bytes, model, placeholder = gemini.generate_image(body.prompt, body.aspectRatio)
        else:
            raise RuntimeError(f"Unsupported IMAGE_PROVIDER: {settings.image_provider}")
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    out_dir = settings.storage_dir.resolve() / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    row = GeneratedImage(prompt=body.prompt, aspectRatio=body.aspectRatio,
                         model=model, isPlaceholder=placeholder, filePath="")
    db.add(row)
    db.flush()
    path = out_dir / f"gen-{row.id[:12]}.png"
    path.write_bytes(image_bytes)
    row.filePath = str(path)
    db.commit()
    db.refresh(row)
    return _gen(row)


@router.get("/generated-images")
def list_generated(db: Session = Depends(get_db)):
    rows = db.query(GeneratedImage).order_by(GeneratedImage.createdAt.desc()).limit(60).all()
    return [_gen(g) for g in rows]


class AttachIn(BaseModel):
    briefId: str


@router.post("/generated-images/{image_id}/attach")
def attach_generated(image_id: str, body: AttachIn, db: Session = Depends(get_db)):
    """Use a generated image as the master design for an approved brief.

    Enters the normal asset pipeline (exports -> bundle -> QC) with the
    AI-assisted flag set, so the Etsy AI disclosure is enforced downstream.
    """
    gen = db.get(GeneratedImage, image_id)
    if not gen:
        raise HTTPException(404, "generated image not found")
    brief = db.get(DesignBrief, body.briefId)
    if not brief:
        raise HTTPException(404, "brief not found")

    image_bytes = Path(gen.filePath).read_bytes()
    upscaled_from = None
    with Image.open(io.BytesIO(image_bytes)) as im:
        w, h = im.size
        if w * h < quality.MIN_MASTER_PIXELS:
            scale = (quality.MIN_MASTER_PIXELS / (w * h)) ** 0.5 * 1.05
            resized = im.convert("RGB").resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, "PNG", dpi=(300, 300))
            image_bytes = buf.getvalue()
            upscaled_from = f"{w}x{h}"

    try:
        asset = assets_mod.create_asset(db, brief, image_bytes, "generated.png", is_ai_assisted=True)
        assets_mod.export_ratios(db, asset)
        assets_mod.build_bundle(db, asset)
        quality.run_checks(db, asset)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if upscaled_from:
        report = dict(asset.qualityReport)
        report["checks"] = report.get("checks", []) + [{
            "check": "upscaledFromSource", "ok": True,
            "detail": f"model output was {upscaled_from}px and was upscaled to meet the "
                      "print minimum — verify sharpness manually before approving",
        }]
        asset.qualityReport = report

    gen.attachedAssetId = asset.assetId
    db.commit()
    return _asset(asset)


# ================================================================ assets

@router.post("/briefs/{brief_id}/assets")
async def upload_asset(brief_id: str, file: UploadFile = File(...),
                       is_ai_assisted: bool = Form(False), db: Session = Depends(get_db)):
    brief = db.get(DesignBrief, brief_id)
    if not brief:
        raise HTTPException(404, "brief not found")
    content = await file.read()
    try:
        asset = assets_mod.create_asset(db, brief, content, file.filename or "design.png",
                                        is_ai_assisted=is_ai_assisted)
        assets_mod.export_ratios(db, asset)
        assets_mod.build_bundle(db, asset)
        quality.run_checks(db, asset)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"could not process image: {e}")
    return _asset(asset)


@router.get("/assets")
def list_assets(db: Session = Depends(get_db)):
    return [_asset(a) for a in db.query(DesignAsset).order_by(DesignAsset.createdAt.desc()).all()]


def _is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _normalize_stored_path(raw: str) -> Path:
    """DB rows may hold paths written from the 'other side' of a WSL setup."""
    if sys.platform == "win32" and raw.startswith("/mnt/") and len(raw) > 6:
        return Path(f"{raw[5].upper()}:{raw[6:]}")            # /mnt/c/x -> C:/x
    if _is_wsl() and len(raw) > 2 and raw[1] == ":":
        return Path(f"/mnt/{raw[0].lower()}{raw[2:]}".replace("\\", "/"))  # C:\x -> /mnt/c/x
    return Path(raw)


@router.post("/assets/{asset_id}/open-bundle-folder")
def open_bundle_folder(asset_id: str, db: Session = Depends(get_db)):
    """Open the ZIP bundle's folder in the local file manager.

    Only meaningful when the browser and server run on the same machine,
    which is the MVP's single-user setup.
    """
    asset = db.get(DesignAsset, asset_id)
    if not asset:
        raise HTTPException(404, "asset not found")
    bundle = _normalize_stored_path(asset.bundlePath).resolve() if asset.bundlePath else None
    if not bundle or not bundle.exists():
        raise HTTPException(404, "no bundle built for this asset yet")

    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(bundle)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(bundle)])
        elif _is_wsl():
            win_path = subprocess.check_output(["wslpath", "-w", str(bundle)], text=True).strip()
            subprocess.Popen(["explorer.exe", "/select,", win_path])
        else:
            subprocess.Popen(["xdg-open", str(bundle.parent)])
    except OSError as e:
        raise HTTPException(500, f"could not open file manager: {e}")
    return {"opened": str(bundle.parent), "selected": bundle.name}


class AssetReviewIn(ReviewIn):
    gate: str = "quality"    # quality | compliance


@router.post("/assets/{asset_id}/review")
def review_asset(asset_id: str, body: AssetReviewIn, db: Session = Depends(get_db)):
    asset = db.get(DesignAsset, asset_id)
    if not asset:
        raise HTTPException(404, "asset not found")
    if body.gate == "quality":
        if body.decision == "approve" and asset.qualityStatus != "passed":
            raise HTTPException(400, "automated quality checks must pass before human approval")
        asset.qualityStatus = "approved" if body.decision == "approve" else "rejected"
    elif body.gate == "compliance":
        mapping = {"approve": "approved", "reject": "rejected", "needsRevision": "needsRevision"}
        asset.complianceStatus = mapping.get(body.decision, "rejected")
    else:
        raise HTTPException(400, "gate must be 'quality' or 'compliance'")
    db.commit()
    _log_review(db, "asset", asset_id, f"{body.gate}:{body.decision}", body.reviewer, body.notes)
    return _asset(asset)


# ================================================================ listings

@router.post("/assets/{asset_id}/listings")
def generate_listing(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(DesignAsset, asset_id)
    if not asset:
        raise HTTPException(404, "asset not found")
    return _listing(listings_mod.generate_for_asset(db, asset))


@router.get("/listings")
def list_listings(db: Session = Depends(get_db)):
    return [_listing(l) for l in db.query(Listing).order_by(Listing.createdAt.desc()).all()]


@router.post("/listings/{listing_id}/review")
def review_listing(listing_id: str, body: ReviewIn, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    if listing.status == "blocked":
        raise HTTPException(400, "blocked listings cannot be approved (IP risk)")
    listing.status = "approved" if body.decision == "approve" else "draft"
    db.commit()
    _log_review(db, "listing", listing_id, body.decision, body.reviewer, body.notes)
    return _listing(listing)


@router.post("/listings/{listing_id}/publish-draft")
def publish_draft(listing_id: str, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    try:
        listing = publisher.create_etsy_draft(db, listing)
    except publisher.GateError as e:
        raise HTTPException(409, {"gateFailures": e.failures})
    return {"listing": _listing(listing), "etsyDryRun": not settings.etsy_configured}


@router.post("/listings/{listing_id}/approve-publish")
def approve_publish(listing_id: str, body: SignoffIn, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    try:
        listing = publisher.approve_final_publish(db, listing)
    except publisher.GateError as e:
        raise HTTPException(409, {"gateFailures": e.failures})
    _log_review(db, "listing", listing_id, "publishApproved", body.reviewer, body.notes)
    return _listing(listing)


@router.post("/listings/{listing_id}/amazon-merch-package")
def merch_package(listing_id: str, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    try:
        path = publisher.build_amazon_merch_package(db, listing)
    except publisher.GateError as e:
        raise HTTPException(409, {"gateFailures": e.failures})
    return {"packagePath": path,
            "note": "Upload manually — Amazon Merch prohibits scripted uploads."}


@router.get("/listings/{listing_id}/amazon-seller-payload")
def seller_payload(listing_id: str, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    try:
        return publisher.build_amazon_seller_payload(db, listing)
    except publisher.GateError as e:
        raise HTTPException(409, {"gateFailures": e.failures})


# ================================================================ analytics + dashboard

class PerformanceIn(BaseModel):
    views: int = 0
    favorites: int = 0
    sales: int = 0
    revenue: float = 0


@router.post("/listings/{listing_id}/performance")
def add_performance(listing_id: str, body: PerformanceIn, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    rec = analytics.record(db, listing, body.views, body.favorites, body.sales, body.revenue)
    return {"id": rec.id}


@router.get("/analytics/niches")
def analytics_niches(db: Session = Depends(get_db)):
    return analytics.niche_performance(db)


@router.get("/reviews")
def list_reviews(db: Session = Depends(get_db)):
    rows = db.query(ReviewLog).order_by(ReviewLog.createdAt.desc()).limit(100).all()
    return [{
        "entityType": r.entityType, "entityId": r.entityId, "reviewerName": r.reviewerName,
        "decision": r.decision, "notes": r.notes, "createdAt": r.createdAt.isoformat(),
    } for r in rows]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    def count(model, **filters):
        return db.query(model).filter_by(**filters).count()

    total_sales = db.query(PerformanceRecord).count()
    top = (db.query(NicheReport).filter(NicheReport.status.in_(["pending", "approved"]))
           .order_by(NicheReport.nicheScore.desc()).limit(5).all())
    return {
        "mode": {
            "etsy": "live" if settings.etsy_configured else "dry-run",
            "ai": "claude-opus-4-8" if settings.anthropic_api_key else "template",
        },
        "counts": {
            "keywords": db.query(Keyword).count(),
            "niches": db.query(NicheReport).count(),
            "nichesPendingReview": count(NicheReport, status="pending") + count(NicheReport, status="needsReview"),
            "nichesBlocked": count(NicheReport, status="blocked"),
            "briefsAwaitingReview": count(DesignBrief, status="draft"),
            "assetsApproved": count(DesignAsset, qualityStatus="approved"),
            "listingsBlocked": count(Listing, status="blocked"),
            "etsyDraftsCreated": db.query(Listing).filter(
                Listing.status.in_(["draftCreated", "publishApproved"])).count(),
            "performanceRecords": total_sales,
        },
        "topNiches": [_niche(n, include_phrase=True, db=db) for n in top],
        "nextActions": _next_actions(db),
    }


def _next_actions(db: Session) -> list[str]:
    actions = []
    if db.query(Keyword).count() == 0:
        actions.append("Add seed keywords to start niche research.")
    if db.query(NicheReport).filter(NicheReport.status.in_(["pending", "needsReview"])).count():
        actions.append("Review pending niches (approve profitable, reject weak).")
    if db.query(DesignBrief).filter_by(status="draft").count():
        actions.append("Review generated design briefs.")
    if db.query(DesignAsset).filter_by(qualityStatus="passed").count():
        actions.append("Human-approve assets that passed automated quality checks.")
    if db.query(DesignAsset).filter_by(complianceStatus="pendingReview").count():
        actions.append("Run compliance review on pending assets.")
    if db.query(Listing).filter_by(status="approved").count():
        actions.append("Create Etsy draft listings for approved listings.")
    return actions or ["Pipeline is clear — add more keywords or record sales data."]


@router.get("/export/niches.csv")
def export_niches(db: Session = Depends(get_db)):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["phrase", "nicheScore", "demand", "competition", "price",
                     "trend", "visualGap", "ipRisk", "status", "riskFlags"])
    for n in db.query(NicheReport).order_by(NicheReport.nicheScore.desc()).all():
        kw = db.get(Keyword, n.keywordId)
        writer.writerow([kw.phrase if kw else "", n.nicheScore, n.demandScore,
                         n.competitionScore, n.priceScore, n.trendScore,
                         n.visualGapScore, n.ipRiskScore, n.status,
                         "; ".join(f["term"] for f in n.riskFlags)])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=niches.csv"})


# ================================================================ serializers

def _kw(k: Keyword) -> dict:
    return {"keywordId": k.keywordId, "phrase": k.phrase, "category": k.category,
            "status": k.status, "createdAt": k.createdAt.isoformat()}


def _niche(n: NicheReport, include_phrase: bool = False, db: Session | None = None) -> dict:
    out = {
        "nicheId": n.nicheId, "keywordId": n.keywordId, "nicheScore": n.nicheScore,
        "demandScore": n.demandScore, "competitionScore": n.competitionScore,
        "priceScore": n.priceScore, "trendScore": n.trendScore,
        "visualGapScore": n.visualGapScore, "ipRiskScore": n.ipRiskScore,
        "status": n.status, "riskFlags": n.riskFlags, "explanation": n.explanation,
    }
    if include_phrase and db is not None:
        kw = db.get(Keyword, n.keywordId)
        out["phrase"] = kw.phrase if kw else "?"
    return out


def _brief(b: DesignBrief) -> dict:
    return {
        "briefId": b.briefId, "nicheId": b.nicheId, "nicheName": b.nicheName,
        "targetBuyer": b.targetBuyer, "roomContext": b.roomContext,
        "styleDirection": b.styleDirection, "colorPalette": b.colorPalette,
        "subjectMatter": b.subjectMatter, "composition": b.composition,
        "ratios": b.ratios, "productFormat": b.productFormat,
        "negativePrompt": b.negativePrompt, "ipSafetyNotes": b.ipSafetyNotes,
        "generatedBy": b.generatedBy, "status": b.status,
    }


def _asset(a: DesignAsset) -> dict:
    return {
        "assetId": a.assetId, "briefId": a.briefId, "filePath": a.filePath,
        "isAiAssisted": a.isAiAssisted, "exports": a.exports, "bundlePath": a.bundlePath,
        "qualityStatus": a.qualityStatus, "complianceStatus": a.complianceStatus,
        "qualityReport": a.qualityReport,
    }


def _listing(l: Listing) -> dict:
    return {
        "listingId": l.listingId, "assetId": l.assetId, "marketplace": l.marketplace,
        "title": l.title, "description": l.description, "tags": l.tags,
        "seoKeywords": l.seoKeywords, "price": l.price, "aiDisclosure": l.aiDisclosure,
        "complianceFlags": l.complianceFlags, "generatedBy": l.generatedBy,
        "status": l.status, "externalListingId": l.externalListingId,
    }
