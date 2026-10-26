"""Single seam for all model calls, with a prompt-hash cache.

Same caching idea as ../pipeline/llm.py, but calls Claude on AWS Bedrock
through Harvard's API gateway (HUIT "AI Services - AWS Bedrock", v2). The
gateway proxies Bedrock's /model/{id}/invoke path and authenticates with the
Harvard portal key in an x-api-key header, which is read from .env as
ANTHROPIC_API_KEY.
"""

import hashlib
import json
import os
from pathlib import Path

from anthropic import AnthropicBedrock
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "build" / "cache"

load_dotenv(ROOT / ".env")

_clients: dict[str, AnthropicBedrock] = {}


def _get_client(base_url: str) -> AnthropicBedrock:
    if base_url not in _clients:
        key = os.environ["ANTHROPIC_API_KEY"]
        # api_key stops the SDK from SigV4-signing; the gateway reads x-api-key.
        _clients[base_url] = AnthropicBedrock(
            base_url=base_url, aws_region="us-east-1",
            api_key=key, default_headers={"x-api-key": key},
        )
    return _clients[base_url]


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _cache_path(prompt: str, schema: dict, model: str, effort: str, seed: int) -> Path:
    """One slot per (prompt, schema, model, effort, seed); a new seed is a fresh sample."""
    material = json.dumps([prompt, schema, model, effort, seed], sort_keys=True)
    return CACHE_DIR / f"{hashlib.sha256(material.encode()).hexdigest()[:16]}.json"


def _complete(prompt: str, schema: dict, model: str, effort: str, max_tokens: int, base_url: str):
    response = _get_client(base_url).messages.create(
        model=model,
        max_tokens=max_tokens,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("hit max_tokens; raise llm.max_tokens in the config")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.model


def complete_json(prompt: str, schema: dict, *, model: str, base_url: str, effort: str = "low",
                  max_tokens: int = 16000, seed: int = 0) -> tuple[dict, dict]:
    """Return (data, meta). meta holds the served model and the prompt hash."""
    path = _cache_path(prompt, schema, model, effort, seed)
    if path.exists():
        cached = json.loads(path.read_text())
    else:
        data, served = _complete(prompt, schema, model, effort, max_tokens, base_url)
        cached = {"data": data, "model": served}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached, indent=2))
    return cached["data"], {"model": cached["model"], "prompt_hash": prompt_hash(prompt)}
