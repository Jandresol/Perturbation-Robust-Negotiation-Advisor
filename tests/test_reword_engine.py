"""Operators, engine and cache, with the model call stubbed out (no network)."""

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
    cfg["reword"]["levels"] = ["light"]
    records, control = engine.run(UNITS, cfg)
    llm_records = [r for r in records if r["operator"] == "paraphrase_fact"]
    assert [r["accepted"] for r in llm_records] == [True, False, True, False]
    assert all(r["reject_reason"] for r in llm_records if not r["accepted"])
    assert len(control) == 2 and all(c["control"] for c in control)
    assert not {c["id"] for c in control} & {r["id"] for r in records}
    assert sum(r["operator"] == "reorder" for r in records) == 1   # 2 units: one other order


def test_cache_hit_makes_no_model_call(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
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
