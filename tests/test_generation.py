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


def _png_bytes(size=(1024, 1280), color=(120, 100, 80)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG", dpi=(300, 300))
    return buf.getvalue()


class _MockResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = content
        self.text = text

    @property
    def is_error(self):
        return self.status_code >= 400

    def json(self):
        return self._json_data


def test_provider_selection_calls_comfyui_when_configured(db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    calls = []

    def fake_generate(prompt, aspect_ratio):
        calls.append((prompt, aspect_ratio))
        return _png_bytes(), "comfyui", False

    monkeypatch.setattr(settings, "image_provider", "comfyui")
    monkeypatch.setattr("app.connectors.comfyui.generate_image", fake_generate)
    _override_db(app, db)
    client = TestClient(app)
    try:
        r = client.post("/api/generate-image", json={"prompt": "soft botanical print", "aspectRatio": "4:5"})
        assert r.status_code == 200, r.text
        assert calls == [("soft botanical print", "4:5")]
        assert r.json()["model"] == "comfyui"
        assert r.json()["isPlaceholder"] is False
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(settings, "image_provider", "")


def test_comfyui_connector_submits_workflow_containing_prompt(monkeypatch):
    from app.config import settings
    from app.connectors import comfyui

    posted = {}
    prompt = "misty sage botanical wall art"
    prompt_id = "abc123"

    def fake_post(url, json, timeout):
        posted["url"] = url
        posted["json"] = json
        posted["timeout"] = timeout
        return _MockResponse(json_data={"prompt_id": prompt_id})

    def fake_get(url, params=None, timeout=None):
        if url.endswith(f"/history/{prompt_id}"):
            return _MockResponse(json_data={prompt_id: {"outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}}})
        if url.endswith("/view"):
            return _MockResponse(content=_png_bytes())
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(settings, "comfyui_base_url", "http://comfy.test")
    monkeypatch.setattr("app.connectors.comfyui.httpx.post", fake_post)
    monkeypatch.setattr("app.connectors.comfyui.httpx.get", fake_get)

    image_bytes, model, placeholder = comfyui.generate_image(prompt, "4:5")

    assert Image.open(io.BytesIO(image_bytes)).size == (1024, 1280)
    assert model == "comfyui"
    assert placeholder is False
    assert posted["url"] == "http://comfy.test/prompt"
    assert posted["json"]["prompt"]["6"]["inputs"]["text"] == prompt


def test_comfyui_connector_maps_4x5_to_portrait_dimensions():
    from app.connectors import comfyui

    workflow = comfyui.build_workflow("portrait botanical", "4:5")

    assert workflow["5"]["inputs"]["width"] == 1024
    assert workflow["5"]["inputs"]["height"] == 1280


def test_comfyui_failure_returns_clear_api_error(db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    def fake_generate(prompt, aspect_ratio):
        raise RuntimeError("ComfyUI error 500: model missing")

    monkeypatch.setattr(settings, "image_provider", "comfyui")
    monkeypatch.setattr("app.connectors.comfyui.generate_image", fake_generate)
    _override_db(app, db)
    client = TestClient(app)
    try:
        r = client.post("/api/generate-image", json={"prompt": "soft botanical print", "aspectRatio": "4:5"})
        assert r.status_code == 502
        assert "ComfyUI error 500: model missing" in r.text
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(settings, "image_provider", "")


def test_comfyui_generated_image_can_attach_and_export_all_ratios(db, approved_brief, monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    def fake_generate(prompt, aspect_ratio):
        return _png_bytes((4000, 5000)), "comfyui", False

    monkeypatch.setattr(settings, "image_provider", "comfyui")
    monkeypatch.setattr("app.connectors.comfyui.generate_image", fake_generate)
    _override_db(app, db)
    client = TestClient(app)
    try:
        r = client.post("/api/generate-image", json={"prompt": "soft botanical print", "aspectRatio": "4:5"})
        assert r.status_code == 200, r.text
        gen = r.json()
        assert gen["model"] == "comfyui"
        assert gen["isPlaceholder"] is False

        r = client.post(f"/api/generated-images/{gen['id']}/attach", json={"briefId": approved_brief.briefId})
        assert r.status_code == 200, r.text
        assert set(r.json()["exports"]) == {"2x3", "3x4", "4x5", "11x14", "A-series"}
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(settings, "image_provider", "")
