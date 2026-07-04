# wallArtNicheEngine

MVP implementation of [SRS.md](SRS.md) — an Etsy-first, human-approved pipeline for
researching wall art niches, generating original design briefs, producing print-ready
assets, and creating **draft-only** Etsy listings. Behavior rules live in [SOUL.md](SOUL.md).

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — the dashboard covers the whole workflow.

Run tests: `pytest`

## Operating modes

The app runs fully offline by default and upgrades itself when keys are present
(copy `.env.example` to `.env`):

| Capability | Without keys | With keys |
|---|---|---|
| Etsy research | deterministic sample data, labeled `[SAMPLE DATA]` | live `findAllListingsActive` via Etsy Open API |
| Brief / listing generation | deterministic templates | `claude-opus-4-8` with structured JSON outputs |
| Etsy draft creation | dry-run (payload stored on the listing for audit) | real draft listing + image + digital file upload |

## The pipeline (SRS §12, §15)

Every product must clear seven gates; the publisher refuses to act until the whole
chain upstream is approved, and *final publish is always a manual action in Etsy*:

```
keyword → researchAgent → nicheScorer ──gate1 approve──▶ designBriefGenerator
  ──gate2 approve──▶ upload master design → ratio exports (2:3, 3:4, 4:5, 11x14, A-series)
  → ZIP bundle → qualityControlAgent (auto) ──gate3/4 human approve──▶
  complianceAgent ──gate5 approve──▶ listingGenerator ──gate6 approve──▶
  publisherAgent (Etsy DRAFT only) ──gate7 approve──▶ activate by hand in Etsy
```

Compliance guardrails:

- IP blocklist in [config/compliance.yaml](config/compliance.yaml) (editable, no code changes) —
  blocked terms auto-reject niches, briefs, and listings; every text surface is scanned.
- AI-assisted designs are flagged at upload and carry an Etsy AI disclosure in the listing.
- **Amazon Merch is manual-package-only**: the publisher builds a ZIP with art + metadata
  for hand upload; there is deliberately no Merch upload code path (Amazon prohibits it).
- Amazon Seller Central SP-API payloads are *prepared* (phase-two integration per the SRS).
- Every human decision is written to the review audit log.

Scoring weights and thresholds are in [config/scoring.yaml](config/scoring.yaml)
(the SRS §7.2 draft formula, editable without code changes).

## Layout

```
app/
  api.py            REST endpoints (user flow §12, key screens §13)
  gates.py          gate chain enforcement (§15)
  models.py         database model (§10)
  config.py         settings + YAML config loading
  connectors/
    ai_provider.py  Anthropic (claude-opus-4-8) briefs/listings + template fallback
    etsy.py         Etsy Open API v3 (draft-only, dry-run without keys)
  modules/
    research.py     researchAgent (§7.1)     scoring.py    nicheScorer (§7.2)
    briefs.py       designBriefGenerator (§7.3)  assets.py  design asset manager (§7.4)
    quality.py      qualityControlAgent (§7.5)   compliance.py complianceAgent (§7.6)
    listings.py     listingGenerator (§7.7)      publisher.py  publisherAgent (§7.8)
    analytics.py    analyticsAgent (§7.9)
config/             editable scoring weights + IP blocklist
static/index.html   dashboard UI (Dashboard / Research / Niches / Briefs / Designs / Listings / Reviews)
tests/              compliance, scoring, and end-to-end gate-chain tests
```

## Etsy OAuth note

The Etsy connector expects an OAuth2 access token in `ETSY_ACCESS_TOKEN`. Etsy uses
OAuth2 + PKCE; the simplest path for a single-shop MVP is to mint a token once via
Etsy's OAuth flow (see their "Quick Start" tutorial) and paste it into `.env`.
Token refresh automation is a follow-up (SRS iteration 2/7 hardening).

## Not in the MVP (per SRS §3.2)

Automatic Amazon Merch publishing, scraping of any kind, competitor asset reuse,
image *generation* (designs are uploaded — AI or human-made — and processed),
mockup generator (iteration 8), and Etsy sales sync (iteration 10 records
performance manually for now).
