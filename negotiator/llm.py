"""Single seam for all model calls, with a prompt-hash cache.

Harvard's gateway is selected by HUIT_PROVIDER in .env:

- openai: chat completions at ais-openai-direct, key HUIT_API_KEY, model HUIT_MODEL.
  A Claude model id in the yaml is served as HUIT_MODEL, because that key is an OpenAI key.
- bedrock: Claude on AWS Bedrock at ais-bedrock-llm, key ANTHROPIC_API_KEY (or HUIT_API_KEY).
"""

import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "build" / "cache"
OPENAI_URL = "https://apis.huit.harvard.edu/ais-openai-direct/v2/chat/completions"
BEDROCK_QUOTA = "https://apis.huit.harvard.edu/ais-bedrock-llm/apigee/quota"
OPENAI_QUOTA = "https://apis.huit.harvard.edu/ais-openai-direct/apigee/quota"
# Rough dollars per new cache file or extractor call, used only when the quota endpoint is unreachable.
CALL_COST = 0.15

load_dotenv(ROOT / ".env")

_clients: dict[str, object] = {}


def _provider() -> str:
    return os.environ.get("HUIT_PROVIDER", "openai").strip().lower()


def _key() -> str:
    key = os.environ.get("HUIT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set HUIT_API_KEY in .env. No model request was made.")
    return key


def _served_model(requested: str) -> str:
    """The yaml still names Claude. An OpenAI key cannot call that model."""
    if _provider() == "openai" and ("anthropic" in requested or "claude" in requested):
        return os.environ.get("HUIT_MODEL") or "gpt-4.1-mini"
    return requested


def _get_client(base_url: str):
    if base_url not in _clients:
        from anthropic import AnthropicBedrock
        key = os.environ.get("ANTHROPIC_API_KEY") or _key()
        # api_key stops the SDK from SigV4-signing; the gateway reads x-api-key.
        _clients[base_url] = AnthropicBedrock(
            base_url=base_url, aws_region="us-east-1",
            api_key=key, default_headers={"x-api-key": key},
            max_retries=6,   # the gateway returns transient 503s under concurrent calls
        )
    return _clients[base_url]


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _cache_path(prompt: str, schema: dict, model: str, effort: str, seed: int) -> Path:
    """One slot per (prompt, schema, model, effort, seed); a new seed is a fresh sample."""
    material = json.dumps([prompt, schema, model, effort, seed], sort_keys=True)
    return CACHE_DIR / f"{hashlib.sha256(material.encode()).hexdigest()[:16]}.json"


def _loads(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


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


def _complete_openai(prompt: str, schema: dict, model: str, max_tokens: int, seed: int):
    """Chat completions. The gateway accepts json_object, so the schema rides in the prompt."""
    user = prompt + "\n\nReturn one JSON object matching this schema:\n" + json.dumps(schema)
    body = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "seed": seed,
        "messages": [
            {"role": "system", "content": "Return only a JSON object. No markdown."},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        OPENAI_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "api-key": _key(), "User-Agent": "NegotiationAdvisor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HUIT returned HTTP {exc.code} for the model call.") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("HUIT could not be reached or timed out.") from None
    try:
        choice = result["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("incomplete")
        return _loads(choice["message"]["content"]), result.get("model", model)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise RuntimeError("The model returned incomplete or invalid JSON.") from None


def complete_json(prompt: str, schema: dict, *, model: str, base_url: str, effort: str = "low",
                  max_tokens: int = 16000, seed: int = 0) -> tuple[dict, dict]:
    """Return (data, meta). meta holds the served model and the prompt hash."""
    model = _served_model(model)
    path = _cache_path(prompt, schema, model, effort, seed)
    if path.exists():
        cached = json.loads(path.read_text())
    else:
        if _provider() == "openai":
            data, served = _complete_openai(prompt, schema, model, max_tokens, seed)
        elif _provider() == "bedrock":
            data, served = _complete(prompt, schema, model, effort, max_tokens, base_url)
        else:
            raise RuntimeError("HUIT_PROVIDER must be openai or bedrock.")
        cached = {"data": data, "model": served}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached, indent=2))
    return cached["data"], {"model": cached["model"], "prompt_hash": prompt_hash(prompt)}


def gateway_remaining() -> float | None:
    """Remaining HUIT budget in dollars, or None when the quota endpoint cannot be read."""
    key = os.environ.get("HUIT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    if _provider() == "openai":
        url, header = OPENAI_QUOTA, "api-key"
    else:
        url, header = BEDROCK_QUOTA, "x-api-key"
    request = urllib.request.Request(url, headers={header: key, "User-Agent": "NegotiationAdvisor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return float(json.loads(response.read())["remaining_limit"])
    except (urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _paid_marks() -> int:
    cached = len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0
    database = ROOT / ".data" / "analysis.sqlite"
    calls = 0
    if database.exists():
        try:
            calls = sqlite3.connect(database).execute("SELECT count(*) FROM calls").fetchone()[0]
        except sqlite3.Error:
            calls = 0
    return cached + calls


def spend_meter():
    """Dollars spent since this meter was created. Uses the quota endpoint, then a per-call estimate."""
    start = gateway_remaining()
    marks = _paid_marks()

    def spent() -> float:
        if start is not None:
            now = gateway_remaining()
            if now is not None:
                return round(start - now, 2)
        return round((_paid_marks() - marks) * CALL_COST, 2)

    return spent
