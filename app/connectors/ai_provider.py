"""AI provider (SRS §14.3): design briefs + listing metadata via the Anthropic API.

Uses claude-opus-4-8 with structured outputs (output_config.format json_schema)
so responses are guaranteed-valid JSON. Falls back to deterministic templates
when ANTHROPIC_API_KEY is not configured or the API call fails, so the whole
pipeline works offline.
"""
import json
import logging

from ..config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"

REQUIRED_RATIOS = ["2:3", "3:4", "4:5", "11x14", "A-series"]

_BRIEF_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "nicheName": {"type": "string"},
        "targetBuyer": {"type": "string"},
        "roomContext": {"type": "string"},
        "styleDirection": {"type": "string"},
        "colorPalette": {"type": "string"},
        "subjectMatter": {"type": "string"},
        "composition": {"type": "string"},
        "productFormat": {"type": "string"},
        "negativePrompt": {"type": "string"},
        "ipSafetyNotes": {"type": "string"},
    },
    "required": [
        "nicheName", "targetBuyer", "roomContext", "styleDirection", "colorPalette",
        "subjectMatter", "composition", "productFormat", "negativePrompt", "ipSafetyNotes",
    ],
    "additionalProperties": False,
}

BRIEFS_SCHEMA = {
    "type": "object",
    "properties": {"briefs": {"type": "array", "items": _BRIEF_ITEM_SCHEMA}},
    "required": ["briefs"],
    "additionalProperties": False,
}

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "seoKeywords": {"type": "array", "items": {"type": "string"}},
        "priceSuggestion": {"type": "number"},
    },
    "required": ["title", "description", "tags", "seoKeywords", "priceSuggestion"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are wallArtNicheEngine, a commerce-focused creative assistant for original "
    "printable wall art. Hard rules: never reference copyrighted characters, brands, "
    "sports teams, celebrities, song lyrics, movie quotes, or living artists by name. "
    "Describe original directions from market gaps; never say 'like this Etsy listing'. "
    "Be practical and profit-aware; do not keyword-stuff."
)


def _client():
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    except Exception:  # SDK missing or misconfigured -> template mode
        logger.exception("Anthropic client unavailable; using template fallback")
        return None


def _generate_json(prompt: str, schema: dict) -> dict | None:
    client = _client()
    if client is None:
        return None
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            logger.warning("Model refused generation request")
            return None
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception:
        logger.exception("AI generation failed; using template fallback")
        return None


# ---------------------------------------------------------------- briefs

def generate_briefs(niche_context: dict, count: int = 5) -> tuple[list[dict], str]:
    """Return (briefs, generatedBy). niche_context: phrase, scores, styles, riskFlags."""
    prompt = (
        f"Create {count} distinct, original wall art design briefs for this niche.\n\n"
        f"Niche keyword: {niche_context['phrase']}\n"
        f"Niche score: {niche_context.get('nicheScore')}\n"
        f"Visual gap notes: {niche_context.get('visualGap', 'n/a')}\n"
        f"Common styles already saturating the market (avoid copying them): "
        f"{niche_context.get('styles', 'unknown')}\n"
        f"Known IP risks to avoid: {niche_context.get('riskFlags', 'none')}\n\n"
        "Each brief targets a digital-download wall art product (single print or "
        "3-piece set). negativePrompt must list what the image generator should avoid; "
        "ipSafetyNotes must state concrete IP boundaries for this niche."
    )
    data = _generate_json(prompt, BRIEFS_SCHEMA)
    if data and data.get("briefs"):
        briefs = data["briefs"][:count]
        for b in briefs:
            b["ratios"] = REQUIRED_RATIOS
        return briefs, MODEL

    return _template_briefs(niche_context, count), "template"


def _template_briefs(ctx: dict, count: int) -> list[dict]:
    phrase = ctx["phrase"]
    variants = [
        ("minimalist line art", "soft beige, cream, and charcoal", "bedroom or living room gallery wall"),
        ("muted watercolor", "sage green, terracotta, and sand", "nursery or reading nook"),
        ("modern abstract shapes", "rust, ochre, and off-white", "office or entryway"),
        ("botanical illustration", "deep green, ivory, and warm taupe", "bathroom or kitchen"),
        ("vintage-inspired print", "navy, mustard, and antique white", "study or hallway"),
    ]
    briefs = []
    for i in range(min(count, len(variants))):
        style, palette, room = variants[i]
        briefs.append({
            "nicheName": phrase,
            "targetBuyer": f"shopper decorating a {room.split(' or ')[0]} around '{phrase}'",
            "roomContext": room,
            "styleDirection": f"{style} interpretation of {phrase}",
            "colorPalette": palette,
            "subjectMatter": f"original {phrase} motifs, no brands or characters",
            "composition": "balanced composition with generous negative space, print-safe margins",
            "ratios": REQUIRED_RATIOS,
            "productFormat": "digital download bundle",
            "negativePrompt": "logos, brand names, watermarks, text artifacts, distorted anatomy, celebrity likeness",
            "ipSafetyNotes": "Avoid any franchise, team, brand, or living-artist reference tied to this niche.",
        })
    return briefs


# ---------------------------------------------------------------- listings

def generate_listing(brief: dict, *, is_ai_assisted: bool) -> tuple[dict, str]:
    prompt = (
        "Write Etsy listing metadata for this original digital-download wall art product.\n\n"
        f"Design brief: {json.dumps(brief, default=str)}\n\n"
        "Rules: title under 140 characters, buyer-benefit led; exactly 13 tags, each "
        "20 characters or fewer, no trademarks; description covers what's included "
        "(digital files in ratios 2:3, 3:4, 4:5, 11x14, A-series), sizing/printing "
        "guidance, usage instructions, and a no-refunds-on-digital note; "
        "priceSuggestion in USD for a digital download."
    )
    data = _generate_json(prompt, LISTING_SCHEMA)
    if data:
        data["tags"] = [t[:20] for t in data.get("tags", [])][:13]
        return _attach_disclosure(data, is_ai_assisted), MODEL
    return _attach_disclosure(_template_listing(brief), is_ai_assisted), "template"


def _template_listing(brief: dict) -> dict:
    niche = brief.get("nicheName", "wall art")
    style = brief.get("styleDirection", "minimalist")
    title = f"{niche.title()} Printable Wall Art | {style.title()[:40]} | Digital Download Set"[:140]
    tags = [
        niche[:20], "printable wall art", "digital download", "wall decor",
        "home decor prints", "gallery wall set", "instant download", "art print set",
        "modern wall art", "printable art", "digital print", "wall art set", "decor bundle",
    ]
    description = (
        f"Original {style} wall art for the {brief.get('roomContext', 'home')}.\n\n"
        "WHAT'S INCLUDED\nHigh-resolution digital files in ratios 2:3, 3:4, 4:5, 11x14 "
        "and A-series — covers all common frame sizes from 4x6 up to 24x36 and A1-A5.\n\n"
        "HOW IT WORKS\n1. Purchase and download instantly.\n2. Print at home, at a local "
        "print shop, or via an online printer.\n3. Frame and enjoy.\n\n"
        "PLEASE NOTE\nThis is a digital download — no physical item ships. Because of the "
        "digital nature of this product, refunds are not available; message us with any issue "
        "and we'll make it right.\n\nColors may vary slightly between screens and printers."
    )
    return {
        "title": title,
        "description": description,
        "tags": [t[:20] for t in tags][:13],
        "seoKeywords": [niche, f"{niche} print", f"{niche} decor", "printable wall art"],
        "priceSuggestion": 8.99,
    }


def _attach_disclosure(listing: dict, is_ai_assisted: bool) -> dict:
    listing["aiDisclosure"] = (
        "This design was created by the seller using AI-assisted tools and reviewed "
        "by a human before listing." if is_ai_assisted else ""
    )
    if is_ai_assisted:
        listing["description"] = listing["description"].rstrip() + "\n\n" + listing["aiDisclosure"]
    return listing
