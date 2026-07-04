"""ComfyUI image generation connector.

The API layer owns orchestration/persistence, while this module owns only the
ComfyUI HTTP workflow: submit a prompt, poll for completion, and download the
selected output image.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

import httpx

from ..config import settings


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI is unavailable or generation fails."""


def generate_image(prompt: str, aspect_ratio: str = "4:5") -> tuple[bytes, str, bool]:
    """Return (image_bytes, model_label, is_placeholder)."""
    workflow = _load_workflow()
    workflow = _workflow_with_prompt(workflow, prompt, aspect_ratio)
    label = _workflow_label()

    timeout = max(float(settings.comfyui_timeout_seconds), 1.0)
    try:
        with httpx.Client(base_url=settings.comfyui_base_url, timeout=timeout) as client:
            prompt_id = _submit_prompt(client, workflow)
            history = _poll_history(client, prompt_id, timeout)
            image_ref = _select_image(history)
            return _download_image(client, image_ref), f"comfyui:{label}", False
    except httpx.HTTPError as exc:
        raise ComfyUIError(f"ComfyUI request failed: {exc}") from exc


def _load_workflow() -> dict[str, Any]:
    if settings.comfyui_workflow_path:
        path = Path(settings.comfyui_workflow_path).expanduser()
        if not path.exists():
            raise ComfyUIError(f"ComfyUI workflow file not found: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ComfyUIError(f"ComfyUI workflow file is not valid JSON: {path}") from exc
    return copy.deepcopy(_DEFAULT_WORKFLOW)


def _workflow_with_prompt(workflow: dict[str, Any], prompt: str, aspect_ratio: str) -> dict[str, Any]:
    """Inject the final image prompt into a ComfyUI API-format workflow."""
    prompt_node_id = settings.comfyui_prompt_node_id
    if prompt_node_id:
        node = workflow.get(prompt_node_id)
        if not isinstance(node, dict):
            raise ComfyUIError(f"ComfyUI prompt node '{prompt_node_id}' was not found in workflow")
        _set_node_text(node, prompt)
        return workflow

    text_nodes = [node for node in workflow.values() if _is_text_encode_node(node)]
    if not text_nodes:
        raise ComfyUIError(
            "ComfyUI workflow has no CLIPTextEncode text node; set COMFYUI_PROMPT_NODE_ID"
        )
    _set_node_text(text_nodes[0], prompt)

    width, height = _dimensions_for_aspect_ratio(aspect_ratio)
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            inputs = node.setdefault("inputs", {})
            inputs["width"] = width
            inputs["height"] = height
    return workflow


def _submit_prompt(client: httpx.Client, workflow: dict[str, Any]) -> str:
    response = client.post("/prompt", json={"prompt": workflow})
    if response.is_error:
        raise ComfyUIError(f"ComfyUI /prompt error {response.status_code}: {response.text[:300]}")
    prompt_id = response.json().get("prompt_id")
    if not prompt_id:
        raise ComfyUIError("ComfyUI /prompt response did not include prompt_id")
    return prompt_id


def _poll_history(client: httpx.Client, prompt_id: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status = "queued"
    while time.monotonic() < deadline:
        response = client.get(f"/history/{prompt_id}")
        if response.is_error:
            raise ComfyUIError(f"ComfyUI history error {response.status_code}: {response.text[:300]}")
        data = response.json()
        history = data.get(prompt_id)
        if history:
            status = history.get("status", {})
            last_status = status.get("status_str", last_status)
            if status.get("completed") is True:
                return history
            messages = status.get("messages") or []
            if any(isinstance(msg, (list, tuple)) and msg and msg[0] == "execution_error" for msg in messages):
                raise ComfyUIError(f"ComfyUI generation failed: {messages[-1]}")
        time.sleep(0.5)
    raise ComfyUIError(f"ComfyUI generation timed out after {timeout_seconds:g}s (last status: {last_status})")


def _select_image(history: dict[str, Any]) -> dict[str, str]:
    outputs = history.get("outputs") or {}
    node_ids = [settings.comfyui_output_node_id] if settings.comfyui_output_node_id else list(outputs)
    for node_id in node_ids:
        output = outputs.get(node_id) or {}
        images = output.get("images") or []
        if images:
            image = images[0]
            return {
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            }
    selector = settings.comfyui_output_node_id or "any output node"
    raise ComfyUIError(f"ComfyUI history contained no images for {selector}")


def _download_image(client: httpx.Client, image_ref: dict[str, str]) -> bytes:
    response = client.get("/view", params=image_ref)
    if response.is_error:
        raise ComfyUIError(f"ComfyUI image download error {response.status_code}: {response.text[:300]}")
    return response.content


def _workflow_label() -> str:
    if settings.comfyui_workflow_path:
        return Path(settings.comfyui_workflow_path).expanduser().stem
    return "default-sd15-workflow"


def _is_text_encode_node(node: Any) -> bool:
    return isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode" and "text" in node.get("inputs", {})


def _set_node_text(node: dict[str, Any], prompt: str) -> None:
    inputs = node.setdefault("inputs", {})
    if "text" not in inputs:
        raise ComfyUIError("Configured ComfyUI prompt node does not have an inputs.text field")
    inputs["text"] = prompt


def _dimensions_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    sizes = {"2:3": (1024, 1536), "3:4": (1152, 1536), "4:5": (1024, 1280), "1:1": (1024, 1024), "9:16": (1024, 1792)}
    return sizes.get(aspect_ratio, sizes["4:5"])


_DEFAULT_WORKFLOW: dict[str, Any] = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 24, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1280, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "text, watermark, logo, signature", "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "wallart", "images": ["8", 0]}},
}
