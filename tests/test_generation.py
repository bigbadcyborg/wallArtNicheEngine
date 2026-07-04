"""Prompt builder + Gemini connector (placeholder mode) + attach pipeline."""
import io

import pytest
from PIL import Image

from app.connectors import ai_provider, gemini
from app.models import DesignBrief, Keyword
from app.modules import briefs as briefs_mod, research, scoring


@pytest.fixture()
def approved_brief(db):
    kw = Keyword(phrase="sage green botanical")
    db.add(kw)
    db.commit()
    research.run_research(db, kw)
    niche = scoring.score_keyword(db, kw)
    niche.status = "approved"
    db.commit()
    brief = briefs_mod.generate_for_niche(db, niche, count=1)[0]
    brief.status = "approved"
    db.commit()
    return brief


def test_build_image_prompt_contains_brief_fields(approved_brief):
    prompt = ai_provider.build_image_prompt(approved_brief)
    assert approved_brief.styleDirection in prompt
    assert approved_brief.colorPalette in prompt
    assert "DO NOT INCLUDE" in prompt
    assert "4000 x 5000" in prompt
    assert "2:3, 3:4, 4:5, 11x14 and A-series" in prompt


def test_build_image_prompt_reserves_text_space_for_verse_niches(approved_brief):
    approved_brief.nicheName = "nursery bible verse"
    prompt = ai_provider.build_image_prompt(approved_brief)
    assert "open area in the center" in prompt


def test_placeholder_generation_without_key():
    # conftest clears GEMINI_API_KEY-adjacent env; settings has no key in tests
    image_bytes, model, placeholder = gemini.generate_image("test prompt", "4:5")
    assert placeholder and model == "placeholder"
    img = Image.open(io.BytesIO(image_bytes))
    assert img.size == (4000, 5000)  # passes the QC master-resolution minimum


def _override_db(app, db):
    from app.database import get_db

    def _dep():
        yield db
    app.dependency_overrides[get_db] = _dep


def test_generate_and_attach_via_api(db, approved_brief):
    from fastapi.testclient import TestClient
    from app.main import app

    _override_db(app, db)
    client = TestClient(app)
    try:
        r = client.post("/api/generate-image", json={"prompt": "soft botanical print", "aspectRatio": "4:5"})
        assert r.status_code == 200, r.text
        gen = r.json()
        assert gen["isPlaceholder"] and gen["url"].startswith("/storage/generated/")

        r = client.post(f"/api/generated-images/{gen['id']}/attach",
                        json={"briefId": approved_brief.briefId})
        assert r.status_code == 200, r.text
        asset = r.json()
        assert asset["isAiAssisted"] is True          # forces Etsy AI disclosure later
        assert asset["qualityStatus"] == "passed"
        assert set(asset["exports"]) == {"2x3", "3x4", "4x5", "11x14", "A-series"}

        r = client.get("/api/generated-images")
        assert r.json()[0]["attachedAssetId"] == asset["assetId"]
    finally:
        app.dependency_overrides.clear()


def test_generate_image_delegates_to_selected_provider(monkeypatch, db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app import api

    calls = []

    def fake_comfyui(prompt, aspect_ratio):
        calls.append((prompt, aspect_ratio))
        return gemini.generate_image(prompt, aspect_ratio)

    _override_db(app, db)
    monkeypatch.setattr(api.settings, "image_provider", "comfyui")
    monkeypatch.setattr(api.comfyui, "generate_image", fake_comfyui)
    client = TestClient(app)
    try:
        r = client.post("/api/generate-image", json={"prompt": "soft botanical print", "aspectRatio": "1:1"})
        assert r.status_code == 200, r.text
        gen = r.json()
        assert calls == [("soft botanical print", "1:1")]
        assert set(gen) == {
            "id", "url", "prompt", "aspectRatio", "model", "isPlaceholder",
            "attachedAssetId", "createdAt",
        }
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(api.settings, "image_provider", "gemini")

def test_generate_image_rejects_empty_prompt(db):
    from fastapi.testclient import TestClient
    from app.main import app

    _override_db(app, db)
    client = TestClient(app)
    try:
        r = client.post("/api/generate-image", json={"prompt": "   "})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()
