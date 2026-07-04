"""Database model per SRS §10, with compliance-gate statuses from §15."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Keyword(Base):
    __tablename__ = "keywords"
    keywordId: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    phrase: Mapped[str] = mapped_column(String, unique=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="new")  # new | researched | blocked
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    listings = relationship("ResearchListing", back_populates="keyword", cascade="all, delete-orphan")
    niches = relationship("NicheReport", back_populates="keyword", cascade="all, delete-orphan")


class ResearchListing(Base):
    """Raw marketplace signals collected by researchAgent (SRS §7.1)."""
    __tablename__ = "research_listings"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    keywordId: Mapped[str] = mapped_column(ForeignKey("keywords.keywordId"))
    marketplace: Mapped[str] = mapped_column(String, default="etsy")
    listingTitle: Mapped[str] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewCount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    listingUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    shopName: Mapped[str | None] = mapped_column(String, nullable=True)
    detectedStyle: Mapped[str | None] = mapped_column(String, nullable=True)
    detectedAudience: Mapped[str | None] = mapped_column(String, nullable=True)
    isSampleData: Mapped[bool] = mapped_column(Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    keyword = relationship("Keyword", back_populates="listings")


class NicheReport(Base):
    __tablename__ = "niche_reports"
    nicheId: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    keywordId: Mapped[str] = mapped_column(ForeignKey("keywords.keywordId"))
    demandScore: Mapped[float] = mapped_column(Float, default=0)
    competitionScore: Mapped[float] = mapped_column(Float, default=0)
    priceScore: Mapped[float] = mapped_column(Float, default=0)
    trendScore: Mapped[float] = mapped_column(Float, default=0)
    visualGapScore: Mapped[float] = mapped_column(Float, default=0)
    ipRiskScore: Mapped[float] = mapped_column(Float, default=0)
    nicheScore: Mapped[float] = mapped_column(Float, default=0)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    riskFlags: Mapped[list] = mapped_column(JSON, default=list)
    # gate1 nicheApproved: pending | approved | needsReview | rejected | blocked
    status: Mapped[str] = mapped_column(String, default="pending")
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    keyword = relationship("Keyword", back_populates="niches")
    briefs = relationship("DesignBrief", back_populates="niche", cascade="all, delete-orphan")


class DesignBrief(Base):
    __tablename__ = "design_briefs"
    briefId: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    nicheId: Mapped[str] = mapped_column(ForeignKey("niche_reports.nicheId"))
    nicheName: Mapped[str] = mapped_column(String)
    targetBuyer: Mapped[str] = mapped_column(Text, default="")
    roomContext: Mapped[str] = mapped_column(String, default="")
    styleDirection: Mapped[str] = mapped_column(Text, default="")
    colorPalette: Mapped[str] = mapped_column(Text, default="")
    subjectMatter: Mapped[str] = mapped_column(Text, default="")
    composition: Mapped[str] = mapped_column(Text, default="")
    ratios: Mapped[list] = mapped_column(JSON, default=list)
    productFormat: Mapped[str] = mapped_column(String, default="digital download bundle")
    negativePrompt: Mapped[str] = mapped_column(Text, default="")
    ipSafetyNotes: Mapped[str] = mapped_column(Text, default="")
    generatedBy: Mapped[str] = mapped_column(String, default="template")  # template | claude-opus-4-8
    version: Mapped[int] = mapped_column(Integer, default=1)
    # gate2 briefApproved: draft | approved | rejected
    status: Mapped[str] = mapped_column(String, default="draft")
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    niche = relationship("NicheReport", back_populates="briefs")
    assets = relationship("DesignAsset", back_populates="brief", cascade="all, delete-orphan")


class DesignAsset(Base):
    __tablename__ = "design_assets"
    assetId: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    briefId: Mapped[str] = mapped_column(ForeignKey("design_briefs.briefId"))
    filePath: Mapped[str] = mapped_column(String)
    fileType: Mapped[str] = mapped_column(String, default="png")
    ratio: Mapped[str] = mapped_column(String, default="master")
    isAiAssisted: Mapped[bool] = mapped_column(Boolean, default=False)  # forces AI disclosure review
    exports: Mapped[dict] = mapped_column(JSON, default=dict)           # ratio -> file path
    bundlePath: Mapped[str | None] = mapped_column(String, nullable=True)
    qualityReport: Mapped[dict] = mapped_column(JSON, default=dict)
    # gate3/4 designApproved+qualityApproved: pending | passed | failed | approved | rejected
    qualityStatus: Mapped[str] = mapped_column(String, default="pending")
    # gate5 complianceApproved: pendingReview | approved | needsRevision | rejected | blocked
    complianceStatus: Mapped[str] = mapped_column(String, default="pendingReview")
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    brief = relationship("DesignBrief", back_populates="assets")
    listings = relationship("Listing", back_populates="asset", cascade="all, delete-orphan")


class Listing(Base):
    __tablename__ = "listings"
    listingId: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    assetId: Mapped[str] = mapped_column(ForeignKey("design_assets.assetId"))
    marketplace: Mapped[str] = mapped_column(String, default="etsy")
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    seoKeywords: Mapped[list] = mapped_column(JSON, default=list)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    aiDisclosure: Mapped[str] = mapped_column(Text, default="")
    complianceFlags: Mapped[list] = mapped_column(JSON, default=list)
    generatedBy: Mapped[str] = mapped_column(String, default="template")
    # gate6/7 listingApproved+publishApproved:
    # draft | approved | blocked | draftCreated | publishApproved
    status: Mapped[str] = mapped_column(String, default="draft")
    externalListingId: Mapped[str | None] = mapped_column(String, nullable=True)
    publishPayload: Mapped[dict] = mapped_column(JSON, default=dict)  # dry-run audit copy
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    asset = relationship("DesignAsset", back_populates="listings")
    performance = relationship("PerformanceRecord", back_populates="listing", cascade="all, delete-orphan")


class ReviewLog(Base):
    """Audit trail for every human gate decision (SRS §8.5)."""
    __tablename__ = "review_logs"
    reviewId: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    entityType: Mapped[str] = mapped_column(String)  # niche | brief | asset | listing
    entityId: Mapped[str] = mapped_column(String)
    reviewerName: Mapped[str] = mapped_column(String, default="adminUser")
    decision: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text, default="")
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PerformanceRecord(Base):
    """analyticsAgent inputs (SRS §7.9) — entered manually or synced later."""
    __tablename__ = "performance_records"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    listingId: Mapped[str] = mapped_column(ForeignKey("listings.listingId"))
    views: Mapped[int] = mapped_column(Integer, default=0)
    favorites: Mapped[int] = mapped_column(Integer, default=0)
    sales: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    recordedAt: Mapped[datetime] = mapped_column(DateTime, default=_now)

    listing = relationship("Listing", back_populates="performance")
