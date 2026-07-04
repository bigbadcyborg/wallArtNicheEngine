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


def test_comfyui_connector_submits_polls_and_downloads(monkeypatch, tmp_path):
    from app.config import settings
    from app.connectors import comfyui

    workflow = {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old", "clip": ["4", 1]}},
        "9": {"class_type": "SaveImage", "inputs": {}},
    }
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(__import__("json").dumps(workflow), encoding="utf-8")

    monkeypatch.setattr(settings, "comfyui_workflow_path", str(workflow_path))
    monkeypatch.setattr(settings, "comfyui_base_url", "http://comfy.test")
    monkeypatch.setattr(settings, "comfyui_timeout_seconds", 2)
    monkeypatch.setattr(settings, "comfyui_prompt_node_id", "6")
    monkeypatch.setattr(settings, "comfyui_output_node_id", "9")

    class FakeResponse:
        is_error = False
        text = ""

        def __init__(self, payload=None, content=b""):
            self._payload = payload or {}
            self.content = content
            self.status_code = 200

        def json(self):
            return self._payload

    class FakeClient:
        submitted = None
        viewed = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, path, json):
            assert path == "/prompt"
            FakeClient.submitted = json
            return FakeResponse({"prompt_id": "abc"})

        def get(self, path, params=None):
            if path == "/history/abc":
                return FakeResponse({"abc": {"status": {"completed": True}, "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}}})
            assert path == "/view"
            FakeClient.viewed = params
            return FakeResponse(content=b"png-bytes")

    monkeypatch.setattr(comfyui.httpx, "Client", FakeClient)

    image_bytes, model, placeholder = comfyui.generate_image("new prompt", "4:5")

    assert image_bytes == b"png-bytes"
    assert model == "comfyui:workflow"
    assert placeholder is False
    assert FakeClient.submitted["prompt"]["6"]["inputs"]["text"] == "new prompt"
    assert FakeClient.viewed == {"filename": "out.png", "subfolder": "", "type": "output"}
