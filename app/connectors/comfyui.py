"""ComfyUI image generation connector.

This connector only returns image bytes to the existing generated-image storage
record. Generated images must still be attached through
POST /api/generated-images/{image_id}/attach so exports, bundles, QC, AI
assistance disclosure, and human approval gates remain centralized.
"""
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from ..config import settings


class ComfyUIConfigurationError(RuntimeError):
    """Raised when ComfyUI generation is requested without required config."""


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return (image_bytes, model_label, is_placeholder) from a ComfyUI workflow."""
    if not settings.comfyui_base_url:
        raise ComfyUIConfigurationError("COMFYUI_BASE_URL is required when using ComfyUI")
    if not settings.comfyui_workflow_path:
        raise ComfyUIConfigurationError("COMFYUI_WORKFLOW_PATH is required when using ComfyUI")

    workflow_path = Path(settings.comfyui_workflow_path)
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow = _inject_prompt(workflow, prompt, aspect_ratio)

    client_id = str(uuid4())
    base_url = settings.comfyui_base_url.rstrip("/")
    timeout = settings.comfyui_timeout_seconds

    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            queued = client.post("/prompt", json={"prompt": workflow, "client_id": client_id})
            queued.raise_for_status()
            prompt_id = queued.json().get("prompt_id")
            if not prompt_id:
                raise RuntimeError("ComfyUI did not return a prompt_id")

            history = _wait_for_history(client, prompt_id, timeout)
            image_ref = _first_image_ref(history)
            image = client.get("/view", params=image_ref)
            image.raise_for_status()
            return image.content, _model_label(), False
    except httpx.HTTPError as exc:
        raise RuntimeError(f"ComfyUI request failed: {exc}") from exc


def _inject_prompt(workflow: dict[str, Any], prompt: str, aspect_ratio: str) -> dict[str, Any]:
    """Insert prompt text into a workflow without owning any downstream asset logic."""
    inserted = False
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        if _is_positive_prompt_node(node):
            inputs["text"] = prompt
            inserted = True
        if "aspect_ratio" in inputs:
            inputs["aspect_ratio"] = aspect_ratio

    if not inserted:
        raise ComfyUIConfigurationError(
            "ComfyUI workflow must include a positive CLIPTextEncode node with a text input"
        )
    return workflow


def _is_positive_prompt_node(node: dict[str, Any]) -> bool:
    meta = node.get("_meta") if isinstance(node.get("_meta"), dict) else {}
    title = str(meta.get("title", "")).lower()
    return node.get("class_type") == "CLIPTextEncode" and "positive" in title


def _wait_for_history(client: httpx.Client, prompt_id: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/history/{prompt_id}")
        response.raise_for_status()
        payload = response.json()
        if payload.get(prompt_id):
            return payload[prompt_id]
        time.sleep(1)
    raise RuntimeError(f"ComfyUI generation timed out after {timeout_seconds:g} seconds")


def _first_image_ref(history: dict[str, Any]) -> dict[str, str]:
    outputs = history.get("outputs", {})
    for output in outputs.values():
        for image in output.get("images", []):
            filename = image.get("filename")
            if filename:
                return {
                    "filename": filename,
                    "subfolder": image.get("subfolder", ""),
                    "type": image.get("type", "output"),
                }
    raise RuntimeError("ComfyUI completed without an output image")


def _model_label() -> str:
    configured = settings.comfyui_model_label.strip()
    return configured or "comfyui"
