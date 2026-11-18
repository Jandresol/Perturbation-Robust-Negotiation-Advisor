"""Sentence-level wording test on a hand-made case (no model calls, fake encoder)."""

import json
from pathlib import Path

import numpy as np
import pytest

from negotiator.game import compare
from negotiator.game import sentence_test as st

ROOT = Path(__file__).resolve().parent.parent
PASSAGE = "FWB will deliver 20 supply kits only if the commander permits access by Friday."


def fake_embed(texts, name):
    vocab = {}
    for t in texts:
        vocab.setdefault(t.lower(), len(vocab))
    rows = np.zeros((len(texts), 64))
    for i, t in enumerate(texts):
        rows[i, vocab[t.lower()]] = 1.0
    return rows


def cfg():
    return {"seed": 0, "filter": {"encoder": "fake"}, "compare": {"align_tau": 0.8},
            "sentence_test": {"variants": 2, "tau": 0.8, "context_chars": 50}}


def case():
    text = f"Minutes of the meeting.\nThe officer spoke first. {PASSAGE} The meeting ended."
    facts = [claim("src-1", text, PASSAGE, "FWB", ["commander permits access by Friday"], "f-ref-0"),
             claim("src-1", text, "The meeting ended.", "chair", [], "f-ref-1")]
    return {"sources": [{"id": "src-1", "title": "Minutes", "category": "shared", "text": text},
                        {"id": "src-2", "title": "Rolecard", "category": "role_card", "text": "You are the commander."}],
            "facts": facts, "parties": {"us": "Camp Commander", "opponent": "Food Without Borders"},
            "actors": {"Food Without Borders": ["fwb", "food without borders"], "Camp Commander": ["commander", "cc"]}}


def claim(sid, text, quote, subject, conditions, cid):
    i = text.index(quote)
    return {"id": cid, "sourceId": sid, "text": quote, "quote": quote, "subject": subject, "conditions": conditions,
            "quoteStart": i, "quoteEnd": i + len(quote)}


PASSAGES = [{"id": "p1", "case": "c", "kind": "action", "text": PASSAGE}]


def test_substitute_replaces_once_and_returns_the_new_span():
    text = f"A. {PASSAGE} B."
    new, (s, e) = st.substitute(text, PASSAGE, "FWB will provide 20 supply kits.")
    assert new == "A. FWB will provide 20 supply kits. B." and new[s:e] == "FWB will provide 20 supply kits."
    with pytest.raises(ValueError):
        st.substitute(text + " " + PASSAGE, PASSAGE, "x")


def test_move_keeps_the_text_and_carries_the_speaker_label():
    text = "SML: Feed the guards.\nCC: We have our methods. One block at a time.\nSML: Right."
    out, (s, e) = st.move(text, "One block at a time.", "start")
    assert out[s:e] == "One block at a time." and out.startswith("CC: One block at a time.\n")
    assert "CC: We have our methods.\n" in out
    out, (s, e) = st.move(text, "One block at a time.", "end")
    assert out.endswith("\nCC: One block at a time.") and out[s:e] == "One block at a time."
    # a passage that was a whole line leaves no empty line behind
    out, _ = st.move("Title\nOnly line.\nLast.", "Only line.", "end")
    assert out == "Title\nLast.\nOnly line."
    assert not st.movable("First. Second.", "First.", "start") and st.movable("First. Second.", "First.", "end")


def test_plan_runs_only_verified_variants_and_repeats_the_original_equally():
    rows = [{"id": "p1:lexical:1", "passage": "p1", "strategy": "lexical", "index": "1", "variant": "v1", "verified": "yes"},
            {"id": "p1:lexical:2", "passage": "p1", "strategy": "lexical", "index": "2", "variant": "v2", "verified": "no"},
            {"id": "p1:split:1", "passage": "p1", "strategy": "split", "index": "1", "variant": "v3", "verified": ""},
            {"id": "p1:pronoun:0", "passage": "p1", "strategy": "pronoun", "index": "0", "variant": "", "verified": "yes"}]
    runs = st.plan(PASSAGES, rows, cfg())
    assert [(r["strategy"], r["index"], r["replicate"], r["seed"]) for r in runs] == [
        ("reference", 0, 0, 0), ("original", 1, 1, 100), ("original", 2, 2, 200), ("lexical", 1, 0, 100)]


def test_extract_replaces_only_the_changed_document_and_finds_passage_claims():
    c = case()
    row = {"strategy": "split", "variant": "FWB will deliver 20 supply kits. This applies only if the commander permits access by Friday."}
    calls = []

    def atomise(source):
        calls.append((source["id"], source["replicate"]))
        return [claim(source["id"], source["text"], "FWB will deliver 20 supply kits.", "FWB", [], "f-new-0")]

    run = {"row": row, "replicate": 0}
    facts, spans, changed = st.extract(run, c, {**PASSAGES[0]}, atomise)
    assert calls == [("src-1", 0)] and set(changed) == {"src-1"}
    assert [f["id"] for f in facts] == ["f-new-0"]          # src-1's baseline claims are replaced
    assert [f["id"] for f in st.passage_claims(facts, spans)] == ["f-new-0"]


def test_extraction_measures_flag_a_lost_condition_but_not_an_alias(monkeypatch):
    monkeypatch.setattr(st, "embed", fake_embed)
    ref = [{"subject": "FWB", "conditions": ["commander permits access by Friday"]}]
    same = [{"subject": "Food Without Borders field office", "conditions": ["commander permits access by Friday"]}]
    lost = [{"subject": "FWB", "conditions": []}]
    flipped = [{"subject": "the camp commander", "conditions": ["commander permits access by Friday"]}]
    actors = case()["actors"]
    m = st.extraction_measures(ref, same, actors, cfg())
    assert not m["ownership_changed"] and not m["conditions_changed"] and not m["extraction_changed"]
    m = st.extraction_measures(ref, lost, actors, cfg())
    assert m["conditions_lost"] and m["extraction_changed"] and not m["ownership_changed"]
    m = st.extraction_measures(ref, flipped, actors, cfg())
    assert m["ownership_changed"] and m["owners"] == ["Camp Commander"]
    # whole words only: "access" does not name CC
    assert st.actors("access team", actors) == {"access team"}


def test_builder_facts_append_a_condition_missing_from_the_text():
    c = case()
    c["facts"][0]["text"] = "FWB will deliver 20 supply kits."
    c["facts"][1]["conditions"] = ["the meeting ended"]          # already in the text
    out = st.builder_facts(c["facts"], c)
    assert out[0]["text"] == "FWB will deliver 20 supply kits. Conditions: commander permits access by Friday."
    assert out[0]["source"] == "Minutes" and out[1]["text"] == "The meeting ended."
    assert st.rolecard(c, {"src-2": "changed card"}) == {"id": "Rolecard", "text": "changed card"}


def make_build(labels, strategies, fact_ids=("f1",)):
    actions = [{"id": f"a{i}", "owner": "us", "label": label, "factIds": list(fact_ids)} for i, label in enumerate(labels, 1)]
    goals = [{"id": "g1", "label": "goal one", "type": "all", "actionIds": ["a1"], "usValue": 5, "opponentValue": 1}]
    return {"actions": actions, "game": {"goals": goals}, "strategies": strategies}


def test_game_measures_compare_opening_and_fallback(monkeypatch):
    monkeypatch.setattr(compare, "embed", fake_embed)
    ref = make_build(["give access", "deliver rice"], [{"steps": [["a1"]]}, {"steps": [["a2"]]}])
    same = make_build(["give access", "deliver rice"], [{"steps": [["a1"]]}, {"steps": [["a2"]]}])
    walk = make_build(["give access", "deliver rice"], [{"steps": [["a1"]]}, {"steps": []}], fact_ids=("f9",))
    compare.align([ref, same, walk], cfg())
    m = st.game_measures(ref, same, {"f1"}, {"f1"})
    assert not m["game_changed"] and not m["advice_changed"] and m["action_distance"] == 0.0
    m = st.game_measures(ref, walk, {"f1"}, {"f1"})
    assert not m["opening_changed"] and m["fallback_changed"] and m["advice_changed"]
    assert m["builder_ownership_changed"]          # no kept action cites the passage claim any more


def test_report_compares_each_strategy_with_originals_of_the_same_passages():
    rows = [{"strategy": "original", "passage": "p1", "extraction_changed": False},
            {"strategy": "original", "passage": "p1", "extraction_changed": True},
            {"strategy": "original", "passage": "p2", "extraction_changed": True},
            {"strategy": "split", "passage": "p1", "extraction_changed": True},
            {"strategy": "split", "passage": "p1", "extraction_changed": True}]
    rep = st.report(rows)
    assert rep["split"]["extraction_changed"] == {"k": 2, "n": 2, "rate": 1.0}
    assert rep["split"]["original_extraction_changed"] == {"k": 1, "n": 2, "rate": 0.5}
    assert rep["original"]["extraction_changed"]["n"] == 3
    assert rep["split"]["game_changed"]["rate"] is None      # extraction stage only
    assert "| split | 1 | 2/2 (100%) | 1/2 (50%) |" in st.markdown(rep)


def test_every_strategy_has_a_prompt_and_every_passage_is_verbatim_once():
    prompts = st.strategy_prompts()
    assert set(prompts) == set(st.STRATEGIES) - {"doc_order"}
    spec = json.loads((ROOT / "configs" / "sentence_test.json").read_text())
    assert len(spec["passages"]) == 12 and {p["case"] for p in spec["passages"]} == set(spec["cases"])
    for name, c in spec["cases"].items():
        path = ROOT / c["package"]
        if not path.exists():
            pytest.skip("case packages are local run output")
        sources = json.loads(path.read_text())["sources"]
        for p in (p for p in spec["passages"] if p["case"] == name):
            assert st.holders({"sources": sources}, p)
