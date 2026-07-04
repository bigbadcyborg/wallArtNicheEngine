## Iterative SRS Outline: Automated Wall Art Niche Research and Publishing System

## 1. Project Name

**wallArtNicheEngine**

## 2. Purpose

The purpose of **wallArtNicheEngine** is to research profitable wall art niches from Etsy and Amazon, generate original wall art concepts for those niches, create product-ready design files, generate marketplace listing metadata, and publish or prepare listings through compliant marketplace workflows.

The system must prioritize **originality, marketplace compliance, intellectual property safety, and human approval** before anything is published. Etsy is the best first marketplace because Etsy’s Open API supports shop/listing automation, including listing creation and image upload workflows. Amazon requires more caution because Amazon Merch on Demand says scripting for bulk uploads is not allowed, while Amazon Seller Central listings can be managed through SP-API if selling through Seller Central. 

## 3. Scope

### 3.1 In Scope

The system will:

- Research wall art niches from Etsy and Amazon.
- Score niches based on demand, competition, pricing, trend signals, and IP risk.
- Generate original design briefs based on market gaps.
- Generate or assist with wall art designs.
- Create mockups and export print-ready files.
- Generate Etsy titles, descriptions, tags, and pricing suggestions.
- Create Etsy draft listings through the Etsy API.
- Prepare Amazon Seller Central listing payloads where applicable.
- Prepare Amazon Merch upload packages manually, without bulk-upload scripting.
- Track listing performance and recommend future design iterations.

### 3.2 Out of Scope for MVP

The MVP will not:

- Automatically publish Amazon Merch designs.
- Scrape platforms in violation of marketplace terms.
- Copy competitor art, titles, descriptions, tags, mockups, or product photos.
- Generate designs using copyrighted characters, brands, celebrity likenesses, sports teams, or trademarked phrases.
- Fully automate publishing without human review.

## 4. Business Objectives

1. Identify profitable wall art niches faster than manual research.
2. Create original designs that target buyer demand without copying competitors.
3. Reduce listing creation time.
4. Build a repeatable digital product pipeline.
5. Use sales data to improve future niche and design decisions.
6. Protect marketplace accounts from avoidable compliance violations.

## 5. Marketplace Compliance Requirements

### 5.1 Etsy Requirements

The system should support Etsy first. Etsy’s Open API supports REST-based shop and listing management, and Etsy’s listing tutorial includes endpoints for creating draft listings and uploading listing images. 

For AI-generated wall art, the system must include an Etsy AI disclosure field in the listing workflow. Etsy has stated that seller-prompted AI creations are allowed, but sellers should disclose AI use when applicable. 

### 5.2 Amazon Requirements

For Amazon Merch on Demand, the system must not perform scripted bulk uploads. Amazon’s Merch FAQ says scripting for bulk upload of designs is not allowed. 

For Amazon Seller Central, the system may support SP-API listing workflows. Amazon’s Listings Items API is used to manage product listings, and the Product Type Definitions API provides required catalog attributes by product type. 

## 6. Users and Roles

### 6.1 adminUser

The owner of the system. Can approve niches, approve designs, approve listings, connect APIs, and publish approved products.

### 6.2 researchUser

Can review niche reports, keyword opportunities, competition data, and pricing insights.

### 6.3 designUser

Can review generated briefs, edit designs, approve art files, and reject low-quality outputs.

### 6.4 complianceReviewer

Can approve or reject listings based on intellectual property risk, marketplace rules, AI disclosure requirements, and visual originality.

## 7. Core System Modules

## 7.1 researchAgent

### Purpose

Collect marketplace signals from Etsy and Amazon.

### Functional Requirements

- The system shall accept seed keywords.
- The system shall search Etsy for relevant wall art listings.
- The system shall collect title, price, category, tags if available, review count, shop signal, and listing freshness where available.
- The system shall collect Amazon product signals using approved API routes where access is available.
- The system shall store all research data in a structured database.
- The system shall avoid restricted scraping or prohibited automation.

### Example Data Fields

```
keywordmarketplacelistingTitlepricereviewCountratingcategorylistingUrlshopNamedetectedStyledetectedAudiencecreatedAtupdatedAt
```

## 7.2 nicheScorer

### Purpose

Rank niche opportunities.

### Functional Requirements

- The system shall calculate demandScore.
- The system shall calculate competitionScore.
- The system shall calculate priceScore.
- The system shall calculate trendScore.
- The system shall calculate ipRiskScore.
- The system shall calculate profitPotentialScore.
- The system shall reject or flag risky niches.

### Scoring Formula Draft

```
nicheScore =  demandScore * 0.25 +  priceScore * 0.20 +  trendScore * 0.20 +  visualGapScore * 0.20 -  competitionScore * 0.10 -  ipRiskScore * 0.25
```

### Auto-Reject Examples

The system should reject niches involving:

- Disney
- Marvel
- Pokémon
- NFL
- NBA
- NCAA teams
- celebrity names
- movie quotes
- song lyrics
- anime characters
- brand logos
- trademarked slogans
- living artist imitation prompts

## 7.3 designBriefGenerator

### Purpose

Convert profitable niches into original art directions.

### Functional Requirements

- The system shall create multiple design briefs per niche.
- The system shall specify target buyer persona.
- The system shall specify room context, such as nursery, bedroom, office, dorm, bathroom, or gallery wall.
- The system shall specify style, palette, composition, file ratios, and format.
- The system shall include negative prompts and IP safety notes.
- The system shall avoid competitor-specific copying.

### Example Brief Output

```
niche: neutral western nursery wall artbuyerPersona: parent decorating a soft western-themed nurserystyleDirection: minimalist desert animals, soft beige and terracotta palettefileRatios: 2:3, 3:4, 4:5, 11x14avoid: cowboy brand logos, Disney-style animals, copied quotes, celebrity namesdesignSet: 3-piece printable wall art bundle
```

## 7.4 designGenerator

### Purpose

Generate or assist in creating wall art files.

### Functional Requirements

- The system shall generate multiple design variants from approved briefs.
- The system shall support image generation through approved providers or local models.
- The system shall support manual upload of human-created artwork.
- The system shall export final files in print-ready formats.
- The system shall support common wall art aspect ratios.
- The system shall generate preview images and mockups.
- The system shall mark all AI-assisted designs for disclosure review.

### Output Formats

```
PNGJPGPDFSVG, optionalZIP bundle for digital downloads
```

### Required Ratios

```
2:33:44:511x14A1 to A5
```

## 7.5 qualityControlAgent

### Purpose

Reject low-quality files before listing.

### Functional Requirements

- The system shall check image resolution.
- The system shall check aspect ratio.
- The system shall flag unreadable AI text.
- The system shall flag distorted faces, hands, or anatomy when relevant.
- The system shall check for watermarks.
- The system shall check for brand names or logos.
- The system shall require manual approval before publishing.

### Acceptance Criteria

A design passes quality control only when:

- All required ratios are exported.
- File names are clean and organized.
- Image quality is suitable for printing.
- No obvious visual artifacts exist.
- No prohibited IP elements are detected.
- Human reviewer has approved the design.

## 7.6 complianceAgent

### Purpose

Reduce marketplace and legal risk.

### Functional Requirements

- The system shall scan titles, tags, descriptions, and prompts for trademark risk.
- The system shall flag copyrighted character references.
- The system shall flag celebrity likeness risk.
- The system shall flag living artist imitation prompts.
- The system shall require AI disclosure on Etsy listings where applicable.
- The system shall block Amazon Merch bulk-upload automation.
- The system shall store compliance review logs.

### Compliance Statuses

```
pendingReviewapprovedneedsRevisionrejectedblocked
```

## 7.7 listingGenerator

### Purpose

Generate marketplace-ready listing content.

### Functional Requirements

- The system shall generate Etsy listing titles.
- The system shall generate Etsy tags.
- The system shall generate product descriptions.
- The system shall generate SEO keyword groups.
- The system shall generate pricing suggestions.
- The system shall generate mockup captions.
- The system shall generate AI disclosure language where needed.
- The system shall generate Amazon Seller Central listing attributes where supported.

### Etsy Listing Fields

```
titledescriptiontagspricequantitytaxonomyIdwhoMadewhenMadeisSupplyisDigitalmaterialsimageFilesdigitalFilesaiDisclosure
```

## 7.8 publisherAgent

### Purpose

Create drafts or prepare listings.

### Functional Requirements

- The system shall create Etsy draft listings.
- The system shall upload Etsy listing images.
- The system shall upload Etsy digital files where supported.
- The system shall keep new listings in draft mode until approved.
- The system shall prepare Amazon Seller Central listing payloads.
- The system shall prepare Amazon Merch manual upload packages only.
- The system shall never bulk-upload to Amazon Merch.

### Publishing Modes

```
etsyDraftetsyPublishAfterApprovalamazonSellerPayloadamazonMerchManualPackage
```

## 7.9 analyticsAgent

### Purpose

Use performance data to improve future designs.

### Functional Requirements

- The system shall track views, favorites, sales, conversion rate, and revenue.
- The system shall compare nicheScore against actual performance.
- The system shall recommend new design variants for winning niches.
- The system shall pause weak niches from further generation.
- The system shall produce weekly reports.

## 8. Nonfunctional Requirements

## 8.1 Security

- API keys must be encrypted at rest.
- OAuth tokens must be stored securely.
- Admin actions must require authentication.
- Publishing actions must be logged.
- User roles must be enforced.

## 8.2 Reliability

- Failed API calls must retry safely.
- Duplicate listings must be detected.
- Upload jobs must be idempotent.
- Each generated asset must have a unique assetId.
- The system must maintain a full audit trail.

## 8.3 Performance

- The MVP should process at least 100 keyword opportunities per research batch.
- The system should generate a niche report in under 10 minutes for a small batch.
- Design generation may run asynchronously through a job queue.

## 8.4 Maintainability

- Modules should be independently replaceable.
- Marketplace connectors should be isolated.
- Prompt templates should be versioned.
- Scoring formulas should be configurable.
- Compliance rules should be editable without code changes.

## 8.5 Auditability

The system shall store:

```
sourceKeywordmarketplaceDatageneratedBriefgenerationPromptdesignVersionreviewDecisionreviewerNamelistingTextuploadStatuspublishedAt
```

## 9. Suggested Technical Stack

### Backend

```
PythonFastAPIPostgreSQLRedisCelerySQLAlchemyAlembic
```

### Frontend

```
ReactNext.jsTailwind
```

### Storage

```
S3-compatible object storagelocal dev storage for MVP
```

### Image Processing

```
PillowImageMagickOpenCV
```

### Integrations

```
Etsy Open APIAmazon SP-APIAmazon Product Type Definitions APIAI image generation provider or local modelTrademark screening API or manual search workflow
```

## 10. Database Model Draft

```
users- userId- email- role- createdAtmarketplaceSources- sourceId- marketplace- apiStatus- createdAtkeywords- keywordId- phrase- category- status- createdAtnicheReports- nicheId- keywordId- demandScore- competitionScore- priceScore- trendScore- visualGapScore- ipRiskScore- nicheScore- status- createdAtdesignBriefs- briefId- nicheId- briefText- styleDirection- targetBuyer- colorPalette- ratios- status- createdAtdesignAssets- assetId- briefId- filePath- ratio- fileType- qualityStatus- complianceStatus- createdAtlistings- listingId- assetId- marketplace- title- description- tags- price- status- externalListingId- createdAtreviewLogs- reviewId- entityType- entityId- reviewerId- decision- notes- createdAt
```

## 11. Iterative Development Plan

## Iteration 0: Research and Policy Foundation

### Goal

Define the legal, technical, and marketplace boundaries before writing automation.

### Deliverables

- Marketplace policy notes.
- API access requirements.
- Risk checklist.
- Initial keyword seed list.
- Database schema draft.
- Manual workflow map.

### Acceptance Criteria

- Etsy workflow is confirmed as first target.
- Amazon Merch automation is marked as manual-only.
- Amazon Seller Central is marked as optional phase-two integration.
- IP risk categories are defined.

## Iteration 1: Manual Research MVP

### Goal

Create a tool that helps research niches without automated publishing.

### Features

- Add seed keywords manually.
- Store niche research results.
- Score niches.
- Display niche dashboard.
- Export CSV report.

### User Stories

- As an adminUser, I want to enter a keyword so I can research a niche.
- As an adminUser, I want to see niche scores so I can choose profitable directions.
- As a complianceReviewer, I want risky keywords flagged so I avoid account problems.

### Acceptance Criteria

- User can add keywords.
- System stores research data.
- System creates a ranked niche report.
- System flags obvious IP-risk terms.

## Iteration 2: Etsy Research Integration

### Goal

Use Etsy API data to improve niche scoring.

### Features

- Connect Etsy API.
- Search Etsy listings by keyword.
- Store listing signals.
- Calculate demand and competition indicators.
- Display top competing styles without copying them.

### Acceptance Criteria

- Etsy API connection works.
- Results are stored in the database.
- Niche dashboard shows price range, listing count, and competition notes.
- System does not download or reuse competitor artwork as design input.

## Iteration 3: Niche Scoring Engine

### Goal

Turn raw research into ranked product opportunities.

### Features

- demandScore
- competitionScore
- priceScore
- visualGapScore
- ipRiskScore
- final nicheScore
- auto-reject rules

### Acceptance Criteria

- Every niche receives a score.
- Risky niches are blocked.
- Admin can adjust scoring weights.
- Score explanations are visible.

## Iteration 4: Design Brief Generator

### Goal

Create original art concepts from approved niches.

### Features

- Generate buyer persona.
- Generate style direction.
- Generate color palette.
- Generate design set idea.
- Generate negative prompt and IP safety notes.
- Save brief versions.

### Acceptance Criteria

- Each approved niche can generate at least 5 briefs.
- Briefs avoid competitor copying.
- Briefs include required ratios.
- Briefs require approval before design generation.

## Iteration 5: Design Generation and File Export

### Goal

Generate printable wall art assets.

### Features

- Generate design variants.
- Export to required ratios.
- Generate file names.
- Create ZIP bundles.
- Store assets.
- Track design versions.

### Acceptance Criteria

- User can generate designs from approved briefs.
- User can reject or approve designs.
- Approved designs are exported in required file sizes.
- ZIP bundle is created for Etsy digital download products.

## Iteration 6: Quality Control and Compliance Review

### Goal

Prevent bad or risky listings from going live.

### Features

- Image quality checks.
- Resolution checks.
- IP keyword scan.
- AI disclosure flag.
- Manual approval screen.
- Review history.

### Acceptance Criteria

- No listing can publish without approval.
- Listings with risky terms are blocked.
- Etsy AI disclosure appears when needed.
- All review actions are logged.

## Iteration 7: Etsy Draft Listing Automation

### Goal

Create Etsy draft listings automatically after approval.

### Features

- Create Etsy draft listing.
- Upload images.
- Upload digital product files.
- Insert title, description, tags, and price.
- Keep listing in draft mode.
- Allow final publish approval.

### Acceptance Criteria

- Approved design creates Etsy draft listing.
- Listing images upload successfully.
- Digital files attach successfully.
- Listing remains unpublished until admin approval.
- External Etsy listing ID is stored.

## Iteration 8: Mockup Generator

### Goal

Create better product visuals.

### Features

- Upload mockup templates.
- Place wall art into frames.
- Generate room mockups.
- Export Etsy-ready preview images.
- Track which mockups convert best.

### Acceptance Criteria

- User can select a mockup template.
- System generates listing preview images.
- Mockups are attached to Etsy draft listing.
- Mockups do not misrepresent product contents.

## Iteration 9: Amazon Research and Seller Central Preparation

### Goal

Add Amazon as a research and optional Seller Central channel.

### Features

- Pull Amazon product-type requirements.
- Prepare Seller Central listing payloads.
- Validate required fields.
- Prepare wall art product data.
- Keep Amazon Merch as manual-package only.

### Acceptance Criteria

- System can prepare Amazon Seller Central payloads.
- Product type requirements are validated.
- Amazon Merch packages are generated for manual upload only.
- No bulk upload scripting is implemented for Amazon Merch.

## Iteration 10: Sales Analytics and Feedback Loop

### Goal

Use sales data to improve future products.

### Features

- Track Etsy listing performance.
- Track views, favorites, sales, and conversion.
- Compare predicted nicheScore to actual performance.
- Recommend new variants.
- Recommend price adjustments.
- Identify dead niches.

### Acceptance Criteria

- Dashboard shows performance by niche.
- System recommends new designs based on actual sales.
- Poor niches are deprioritized.
- Winning niches are expanded into collections.

## Iteration 11: Semi-Autonomous Batch Pipeline

### Goal

Create a controlled batch workflow with human approval checkpoints.

### Features

- Batch niche research.
- Batch brief generation.
- Batch design generation.
- Batch listing generation.
- Batch compliance review.
- Batch Etsy draft creation.

### Acceptance Criteria

- User can process a batch from keyword to Etsy draft.
- Every publish action still requires approval.
- Risky listings are blocked.
- System logs all decisions.

## 12. User Flow

```
adminUser enters seed keywordsresearchAgent gathers marketplace datanicheScorer ranks opportunitiesadminUser approves nichedesignBriefGenerator creates original conceptsadminUser approves briefdesignGenerator creates wall art variantsqualityControlAgent checks filescomplianceAgent checks IP and policy risklistingGenerator creates marketplace metadataadminUser approves listingpublisherAgent creates Etsy draftadminUser publishes manually or approves final publishanalyticsAgent tracks performancesystem recommends next niche batch
```

## 13. Key Screens

### 13.1 dashboardView

Shows:

- top niches
- pending reviews
- approved designs
- blocked listings
- sales summary
- next recommended actions

### 13.2 nicheResearchView

Shows:

- keyword
- marketplace signals
- price range
- competition level
- top styles
- nicheScore
- risk flags

### 13.3 briefReviewView

Shows:

- generated briefs
- target buyer
- design direction
- color palette
- IP warnings
- approve/reject buttons

### 13.4 designReviewView

Shows:

- generated art
- ratios
- file quality
- mockups
- approve/reject buttons

### 13.5 listingReviewView

Shows:

- title
- description
- tags
- price
- AI disclosure
- compliance status
- create draft button

## 14. API Requirements

### 14.1 Etsy API

The system should support:

```
oauth authenticationcreate draft listingupload listing imageupload digital fileupdate listing metadataread listing performance where available
```

### 14.2 Amazon SP-API

The system may support:

```
retrieve product type definitionsvalidate listing payloadsprepare listing item datasubmit Seller Central listings, optional later phase
```

### 14.3 AI Provider

The system should support:

```
generate design briefgenerate listing metadatagenerate image promptgenerate image assetupscale image
```

## 15. Compliance Gates

No product can move forward unless it passes these gates:

```
gate1: nicheApprovedgate2: briefApprovedgate3: designApprovedgate4: qualityApprovedgate5: complianceApprovedgate6: listingApprovedgate7: publishApproved
```

## 16. Risk Register

RiskSeverityMitigationEtsy shop suspensionHighDraft-only publishing, AI disclosure, human reviewAmazon Merch violationHighNo bulk upload scriptingCopyright infringementHighIP filter, manual review, no competitor copyingTrademark violationHighTrademark keyword blocklist and manual reviewLow-quality AI artMediumQuality control and human approvalOversaturated nichesMediumCompetition scoringBad mockupsMediumTemplate review and visual QAAPI rate limitsMediumQueue jobs, retries, backoffDuplicate listingsMediumSimilarity check and listing hashWeak salesLowAnalytics feedback loop

## 17. MVP Definition

The MVP should be:

```
Etsy-firstdigital-download-firstdraft-listing-onlyhuman-approvedIP-risk-aware
```

### MVP Features

- Keyword entry
- Etsy research
- Niche scoring
- Design brief generation
- Manual design upload or AI design import
- File export checklist
- Listing metadata generation
- Compliance checklist
- Etsy draft listing creation

### MVP Success Criteria

- Researches at least 50 niches.
- Produces at least 10 approved design briefs.
- Generates at least 5 complete wall art product bundles.
- Creates Etsy draft listings successfully.
- Blocks high-risk IP niches.
- Requires manual approval before publishing.

## 18. Recommended Build Order

1. Database schema
2. Keyword input
3. Etsy research connector
4. Niche scoring
5. Compliance blocklist
6. Brief generator
7. Design asset manager
8. Listing generator
9. Etsy draft publisher
10. Analytics dashboard

## 19. Final Product Vision

The final version should act like a **creative commerce engine**:

```
research demandfind market gapsgenerate original ideascreate art assetsreview qualityreview compliancepublish draftstrack salesimprove next batch
```

The system should not be a marketplace spam bot. It should be a controlled production system that helps you create original wall art products faster while keeping your Etsy and Amazon accounts safe.