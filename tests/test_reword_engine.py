"""Operators, engine and cache, with the model call stubbed out (no network)."""

import json
from types import SimpleNamespace

from negotiator import llm
from negotiator.reword import engine, operators

UNITS = [
    {"id": "f1", "kind": "fact",
     "text": "The Mayor said FWB may deliver 40 tonnes of food to the camp each week."},
    {"id": "f2", "kind": "fact", "text": "The guards have not been paid for three months."},
]
GOOD = {
    "f1": "According to the Mayor, FWB is allowed to bring 40 tonnes of food into the camp every week.",
    "f2": "For three months the guards have gone unpaid.",
}


def _stub_llm(monkeypatch):
    def fake(prompt, schema, **kw):
        unit = next(u for u in UNITS if u["text"] in prompt)
        bad = unit["text"].replace("40", "50").replace("three", "four")
        return {"rewordings": [GOOD[unit["id"]], bad]}, {"model": "stub", "prompt_hash": "x"}
    monkeypatch.setattr(llm, "complete_json", fake)


def test_reorder_is_a_permutation():
    ids = [f"f{i}" for i in range(6)]
    perms = operators.reorder(ids, 4, seed=0)
    assert len(perms) == 4 and len({tuple(p) for p in perms}) == 4
    assert all(sorted(p) == sorted(ids) and p != ids for p in perms)


def test_render_keeps_braces_in_text():
    prompt = operators.render("paraphrase_fact", "budget {draft} 40", "light", 3)
    assert "budget {draft} 40" in prompt and "{level}" not in prompt


def test_engine_filters_and_keeps_noise_separate(monkeypatch, cfg):
    _stub_llm(monkeypatch)
    cfg["reword"].update(levels=["light"], independent=False)
    records, control = engine.run(UNITS, cfg)
    llm_records = [r for r in records if r["operator"] == "paraphrase_fact"]
    assert [r["accepted"] for r in llm_records] == [True, False, True, False]
    assert all(r["reject_reason"] for r in llm_records if not r["accepted"])
    assert len(control) == 2 and all(c["control"] for c in control)
    assert not {c["id"] for c in control} & {r["id"] for r in records}
    assert sum(r["operator"] == "reorder" for r in records) == 1   # 2 units: one other order


def test_independent_candidates_are_separate_calls_with_their_own_seeds(monkeypatch, cfg):
    calls = []

    def fake(prompt, schema, **kw):
        calls.append(kw["seed"])
        return {"rewordings": [GOOD["f2"], "ignored extra"]}, {"model": "stub", "prompt_hash": "x"}
    monkeypatch.setattr(llm, "complete_json", fake)
    cfg["reword"].update(levels=["light"], independent=True, k=3)
    cfg["noise"]["enabled"] = False
    records, _ = engine.run(UNITS[1:], cfg)
    assert calls == [cfg["seed"], cfg["seed"] + 1, cfg["seed"] + 2]
    assert [r["seed"] for r in records] == calls and all(r["text"] == GOOD["f2"] for r in records)


def test_cache_hit_makes_no_model_call(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("HUIT_PROVIDER", "bedrock")
    calls = []

    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                               content=[SimpleNamespace(type="text", text='{"rewordings": ["a"]}')])

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(llm, "_get_client", lambda base_url: client)
    args = ("prompt", {"type": "object"})
    kw = {"model": "us.anthropic.claude-opus-5-5", "base_url": "https://gateway.example"}
    first = llm.complete_json(*args, **kw)
    second = llm.complete_json(*args, **kw)
    assert first == second and len(calls) == 1
    llm.complete_json(*args, **kw, seed=1)                        # new seed = fresh sample
    assert len(calls) == 2


def test_openai_provider_uses_huit_model(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("HUIT_PROVIDER", "openai")
    monkeypatch.setenv("HUIT_API_KEY", "test-key")
    monkeypatch.setenv("HUIT_MODEL", "gpt-4.1-mini")
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "model": "gpt-4.1-mini",
                "choices": [{"finish_reason": "stop", "message": {"content": '{"applicable": true}'}}],
            }).encode()

    def urlopen(request, timeout=30):
        calls.append(request)
        return Response()

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    data, meta = llm.complete_json(
        "prompt", {"type": "object"}, model="us.anthropic.claude-opus-5-5", base_url="https://bedrock.example")
    assert data == {"applicable": True}
    assert meta["model"] == "gpt-4.1-mini"
    body = json.loads(calls[0].data.decode())
    assert body["model"] == "gpt-4.1-mini"
    assert calls[0].full_url == llm.OPENAI_URL
    assert calls[0].get_header("Api-key") == "test-key"
    assert "schema" in json.loads(calls[0].data.decode())["messages"][1]["content"]
    llm.complete_json(
        "prompt", {"type": "object"}, model="us.anthropic.claude-opus-5-5", base_url="https://bedrock.example")
    assert len(calls) == 1
