"""Experiment 2 repairs one field and checks whether the original advice comes back. No model calls."""

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

# Model clients are not needed: every embed call in these tests is replaced, and no builder runs.
_transformers = types.ModuleType("sentence_transformers")
_transformers.SentenceTransformer = object
_transformers.CrossEncoder = object
sys.modules["sentence_transformers"] = _transformers
_anthropic = types.ModuleType("anthropic")
_anthropic.AnthropicBedrock = object
sys.modules["anthropic"] = _anthropic
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *args, **kwargs: None
sys.modules["dotenv"] = _dotenv

from negotiator.game import attribution as att
from negotiator.game import compare
from negotiator.game import lines

ROOT = Path(__file__).resolve().parent.parent
PASSAGE = "FWB will deliver 20 supply kits only if the commander permits access by Friday."
SHORT = "FWB will deliver 20 supply kits."


_VOCAB = {}


def fake_embed(texts, name):
    """Shared coordinates across calls, so cosine compares strings rather than list positions."""
    for text in texts:
        _VOCAB.setdefault(text.lower(), len(_VOCAB))
    rows = np.zeros((len(texts), 64))
    for i, text in enumerate(texts):
        rows[i, _VOCAB[text.lower()]] = 1.0
    return rows


@pytest.fixture(autouse=True)
def embeddings(monkeypatch):
    monkeypatch.setattr(att, "embed", fake_embed)
    monkeypatch.setattr(compare, "embed", fake_embed)


def cfg():
    return {"seed": 0, "filter": {"encoder": "fake"}, "compare": {"align_tau": 0.8},
            "sentence_test": {"variants": 2, "tau": 0.8, "context_chars": 50}}


def aliases():
    return {"Food Without Borders": ["fwb", "food without borders"], "Camp Commander": ["commander", "cc"]}


def claim(cid, text, subject, conditions, category="commitment", source="src-1"):
    return {"id": cid, "sourceId": source, "text": text, "quote": text, "subject": subject,
            "attribution": subject, "conditions": list(conditions), "category": category}


def case():
    return {"sources": [{"id": "src-1", "title": "Minutes", "category": "shared", "text": PASSAGE}],
            "parties": {"us": "Camp Commander", "opponent": "Food Without Borders"}}


def row(rid, strategy, game=True, advice=True, **flags):
    base = {"id": rid, "case": "sim2", "passage": "sim2-1", "kind": "action", "strategy": strategy, "index": 1,
            "game_changed": game, "advice_changed": advice, "conditions_lost": False, "ownership_changed": False,
            "builder_ownership_changed": False}
    base.update(flags)
    return base


def test_missing_condition_is_restored_and_nothing_else_changes():
    ref = [claim("f1", PASSAGE, "FWB", ["the commander permits access by Friday"])]
    pert = [claim("f9", SHORT, "FWB", [])]
    other = claim("f2", "The meeting ended at noon.", "chair", ["the room was closed"], category="context")
    pert = pert + [other]
    edit = att.extraction_edit(ref, pert, aliases(), cfg())
    assert edit["field"] == "missing_condition" and edit["claim_id"] == "f9"
    corrected = att.correct_claims(pert, edit)
    assert pert[0]["conditions"] == []
    assert corrected[0]["conditions"] == ["the commander permits access by Friday"]
    assert corrected[1] == other
    assert corrected[0]["text"] == SHORT and corrected[0]["subject"] == "FWB"


def test_owner_correction_changes_only_that_claim():
    text = "The field office will deliver 20 supply kits."
    ref = [claim("f1", text, "FWB", [])]
    pert = [claim("f9", text, "the camp commander", []),
            claim("f8", "Guards keep the gate.", "guards", [])]
    edit = att.extraction_edit(ref, pert, aliases(), cfg())
    assert edit == {"field": "incorrect_owner", "claim_id": "f9", "subject": "FWB"}
    corrected = att.correct_claims(pert, edit)
    assert corrected[0]["subject"] == "FWB" and corrected[0]["attribution"] == "FWB"
    assert "Attribution: FWB." in corrected[0]["text"]
    assert corrected[1] == pert[1]


def test_omitted_action_inserts_one_claim():
    ref = [claim("f1", "FWB will deliver 20 supply kits.", "FWB", []),
           claim("f2", "The commander will escort the convoy.", "Camp Commander", [])]
    pert = [claim("f9", "FWB will deliver 20 supply kits.", "FWB", [])]
    edit = att.extraction_edit(ref, pert, aliases(), cfg())
    assert edit["field"] == "omitted_action" and edit["claim"]["id"] == "f2"
    corrected = att.correct_claims(pert, edit)
    assert [c["id"] for c in corrected] == ["f9", "f2"]
    assert len(pert) == 1


def test_extraction_divergence_wins_over_a_later_game_difference():
    ref = [claim("f1", PASSAGE, "FWB", ["the commander permits access by Friday"])]
    pert = [claim("f9", SHORT, "FWB", [])]
    found = att.first_divergence(ref, pert, aliases(), cfg(), ref_build={"actions": []}, pert_build={"actions": []})
    assert found["locus"] == "extraction" and found["field"] == "missing_condition"


def test_game_stance_restores_one_goal_and_its_readings():
    ref = game_of(["deliver kits"], goals=[("kits arrive", 5, 1), ("guards paid", 1, 4)], readings=[5, 1])
    pert = game_of(["deliver kits"], goals=[("kits arrive", 5, -2), ("guards paid", 1, 4)], readings=[-2, 1])
    edit = att.game_edit(ref, pert, cfg())
    assert edit["field"] == "altered_stance" and edit["goal_label"] == "kits arrive"
    repaired, status = att.apply_game_edit(pert, edit, cfg())
    assert status == "applied"
    assert repaired["game"]["goals"][0]["opponentValue"] == 1
    assert repaired["game"]["goals"][1]["usValue"] == 1 and repaired["game"]["goals"][1]["opponentValue"] == 4
    assert repaired["game"]["opponentReadings"][0]["values"]["g1"] == 5
    assert pert["game"]["goals"][0]["opponentValue"] == -2


def test_missing_constraint_drops_the_forbidden_action_and_changes_the_plan():
    permit = action("a1", "us", "permit access")
    deliver = action("b1", "opponent", "deliver kits")
    original = {
        "actions": [permit],
        "game": {"maxOffers": 2, "maxActionsPerSide": 1, "bottomLine": 0, "opponentReadings": [],
                 "goals": [goal("g1", "access permitted", ["a1"], 3, 1)],
                 "redLines": [{"kind": "forbidden", "actionId": "b1", "label": "deliver kits",
                               "quote": "Do not deliver kits before access is permitted.", "owner": "opponent"}]},
        "strategies": [],
    }
    perturbed = {
        "actions": [permit, deliver],
        "game": {"maxOffers": 2, "maxActionsPerSide": 1, "bottomLine": 0, "opponentReadings": [],
                 "goals": [goal("g1", "access permitted", ["a1"], 3, 1),
                           goal("g2", "kits delivered", ["b1"], 4, 4)],
                 "redLines": []},
        "strategies": [],
    }
    edit = att.game_edit(original, perturbed, cfg())
    assert edit["field"] == "missing_constraint" and edit["label"] == "deliver kits"
    repaired, status = att.apply_game_edit(perturbed, edit, cfg())
    assert status == "applied"
    assert [a["id"] for a in repaired["actions"]] == ["a1"]
    solved = lines.solve_within_lines(repaired, {"us": "Camp Commander", "opp": "Food Without Borders"})
    offered = {action_id for plan in solved["strategies"] for step in plan["steps"] for action_id in step}
    assert "b1" not in offered
    open_pert = lines.solve_within_lines(perturbed, {"us": "Camp Commander", "opp": "Food Without Borders"})
    offered_pert = {action_id for plan in open_pert["strategies"] for step in plan["steps"] for action_id in step}
    assert "b1" in offered_pert


def test_select_pairs_keeps_stopped_cases_and_spreads_fields():
    rows = [row(f"m{i}", "lexical", conditions_lost=True) for i in range(6)]
    rows += [row(f"o{i}", "passive", ownership_changed=True) for i in range(6)]
    rows += [row(f"u{i}", "split") for i in range(6)]
    rows.append(row("stop", "nominalise", advice=False))
    rows.append(row("same", "original", conditions_lost=True))
    picked = att.select_pairs(rows, limit=10)
    assert len(picked) == 10
    assert "stop" in {p["id"] for p in picked}
    assert "same" not in {p["id"] for p in picked}
    assert {p["field"] for p in picked} >= {"missing_condition", "incorrect_owner", "unclassified"}
    assert picked[0]["propagation"] == "stopped"


def test_sentence_test_run_yields_about_ten_pairs():
    path = ROOT / "runs" / "sentence-test" / "runs.jsonl"
    if not path.exists():
        pytest.skip("sentence-test run is local output")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    picked = att.select_pairs(rows, limit=10)
    assert len(picked) == 10
    assert {p["field"] for p in picked} >= {"missing_condition", "incorrect_owner"}
    assert all(p["strategy"] != "original" for p in picked)


def test_repeats_share_seeds_and_the_restored_condition_brings_the_advice_back():
    ref = [claim("f1", PASSAGE, "FWB", ["the commander permits access by Friday"])]
    pert = [claim("f9", SHORT, "FWB", [])]
    calls = []

    def build_fn(facts, seed):
        text = " ".join(f["text"] for f in facts)
        conditional = "only if" in text or "Conditions:" in text
        label = "deliver kits only after access is permitted" if conditional else "deliver kits"
        calls.append((seed, conditional))
        return offered(label)

    result = att.run_pair({"id": "sim2-1:conditional:1", "propagation": "reached"}, ref, pert, aliases(), cfg(),
                          build_fn, case=case(), repeats=3, seed=0)
    assert result["field"] == "missing_condition" and result["locus"] == "extraction"
    assert result["explains"] == "both"
    assert result["decision"]["verdict"] == "restored"
    assert result["decision"]["changed"] == "3/3" and result["decision"]["restored"] == "3/3"
    assert result["agreement"]["game"] == {"original": "3/3", "perturbed": "0/3", "corrected": "3/3"}
    assert calls[0] == (0, True) and calls[1] == (0, False) and calls[2] == (0, True)
    assert {seed for seed, _ in calls} == {0, 100, 200}
    assert result["openings"]["corrected"] == ["deliver kits only after access is permitted"]
    assert result["openings"]["perturbed"] == ["deliver kits"]


def test_sampling_variation_is_not_counted_as_a_restoration():
    ref = [claim("f1", "FWB will deliver 20 supply kits.", "FWB", [])]
    pert = [claim("f9", "FWB will deliver 20 supply kits.", "FWB", []),
            claim("note", "A background remark follows.", "FWB", [], category="context")]

    def build_fn(facts, seed):
        extra = any(f["id"] == "note" for f in facts)
        actions = [action("b1", "opponent", "deliver kits")]
        if not extra or seed == 100:
            actions.append(action("a1", "us", "permit access"))
        return {"actions": actions,
                "game": {"goals": [goal("g1", "kits arrive", [a["id"] for a in actions], 2, 2)],
                         "redLines": [], "bottomLine": 0},
                "strategies": [{"steps": [[a["id"] for a in actions]]}]}

    def solve_fn(built):
        return {**built, "strategies": [{"steps": [[a["id"] for a in built["actions"]]]}]}

    result = att.run_pair({"id": "p", "propagation": "stopped"}, ref, pert, aliases(), cfg(),
                          build_fn, solve_fn, repeats=2, seed=0)
    assert result["field"] == "omitted_action" and result["locus"] == "game"
    assert result["propagation"] == "stopped"
    assert [s["corrected"] for s in result["samples"]] == ["applied", "no_difference"]
    assert result["decision"]["verdict"] == "restored"
    assert result["decision"]["changed"] == "1/1" and result["decision"]["restored"] == "1/1"
    assert result["decision"]["skipped"] == 1
    assert result["game"] == "restored" and result["explains"] == "both"


def test_owner_decision_is_compared_inside_each_seed():
    text = "deliver kits"
    ref = [claim("f1", text, "FWB", [])]
    pert = [claim("f9", text, "the camp commander", [])]
    calls = {"n": 0}

    def build_fn(facts, seed):
        role = calls["n"] % 3
        calls["n"] += 1
        owner = "opponent" if role != 1 else "us"
        return {"actions": [action("b1", owner, text), action("x", "us", f"noise {seed}")],
                "game": {"goals": [goal("g1", "kits arrive", ["b1", "x"], 2, 2)], "redLines": [], "bottomLine": 0},
                "strategies": [{"steps": [["b1", "x"]]}]}

    result = att.run_pair({"id": "owner", "propagation": "reached"}, ref, pert, aliases(), cfg(),
                          build_fn, repeats=3, seed=0)
    assert result["field"] == "incorrect_owner" and result["locus"] == "extraction"
    assert result["game"] == "inconclusive"
    assert result["decision"]["verdict"] == "restored"
    assert result["decision"]["changed"] == "3/3" and result["decision"]["restored"] == "3/3"
    assert [row["perturbed"] for row in result["decision"]["seeds"]] == ["us", "us", "us"]
    assert [row["corrected"] for row in result["decision"]["seeds"]] == ["opponent", "opponent", "opponent"]


def test_owner_decision_stays_wrong_when_the_repair_does_not_reach_the_offer():
    text = "deliver kits"
    ref = [claim("f1", text, "FWB", [])]
    pert = [claim("f9", text, "the camp commander", [])]
    calls = {"n": 0}

    def build_fn(facts, seed):
        role = calls["n"] % 3
        calls["n"] += 1
        owner = "opponent" if role == 0 else "us"
        return {"actions": [action("b1", owner, text)],
                "game": {"goals": [goal("g1", "kits arrive", ["b1"], 2, 2)], "redLines": [], "bottomLine": 0},
                "strategies": [{"steps": [["b1"]]}]}

    result = att.run_pair({"id": "owner-miss", "propagation": "reached"}, ref, pert, aliases(), cfg(),
                          build_fn, repeats=3, seed=0)
    assert result["decision"]["verdict"] == "not_restored"
    assert result["decision"]["changed"] == "3/3" and result["decision"]["restored"] == "0/3"


def test_owner_decision_is_unmatched_when_the_offer_has_no_such_action():
    text = "deliver kits"
    ref = [claim("f1", text, "FWB", [])]
    pert = [claim("f9", text, "the camp commander", [])]

    def build_fn(facts, seed):
        return {"actions": [action("b1", "us", "escort the convoy")],
                "game": {"goals": [goal("g1", "kits arrive", ["b1"], 2, 2)], "redLines": [], "bottomLine": 0},
                "strategies": [{"steps": [["b1"]]}]}

    result = att.run_pair({"id": "owner-missed", "propagation": "reached"}, ref, pert, aliases(), cfg(),
                          build_fn, repeats=2, seed=0)
    assert result["decision"]["verdict"] == "unmatched"
    assert result["decision"]["changed"] == "0/2"
    missed = result["decision"]["seeds"][0]["match"]["original"]
    assert missed["target"] == "deliver kits" and missed["accepted"] is False
    assert missed["matched_label"] == "escort the convoy" and missed["cosine"] == 0.0
    assert missed["in_opening"] is True


def test_report_names_stopped_pairs():
    text = att.markdown([
        {"id": "a", "field": "missing_condition", "locus": "extraction", "propagation": "reached",
         "game": "restored", "advice": "restored", "explains": "both",
         "decision": {"verdict": "restored", "changed": "3/3", "restored": "3/3", "skipped": 0},
         "agreement": {"game": {"original": "3/3", "perturbed": "0/3", "corrected": "3/3"},
                       "advice": {"original": "3/3", "perturbed": "0/3", "corrected": "3/3"}},
         "openings": {"original": ["deliver kits only after access is permitted"], "perturbed": ["deliver kits"],
                      "corrected": ["deliver kits only after access is permitted"]}},
        {"id": "b", "field": "altered_stance", "locus": "game", "propagation": "stopped",
         "game": "restored", "advice": "no_stable_change", "explains": "game",
         "decision": {"verdict": "restored", "changed": "2/2", "restored": "2/2", "skipped": 0},
         "agreement": {}, "openings": {}},
    ])
    assert "| missing_condition | 1 | 3/3 (100%) | 3/3 (100%) | 1/1 (100%) | 1/1 (100%) |" in text
    assert "| a | missing_condition | extraction | reached | restored | 3/3 | 3/3 | 0 | restored | restored | both |" in text
    assert "Game changed while the recommendation did not: 1." in text
    assert "deliver kits only after access is permitted" in text


def action(aid, owner, label):
    return {"id": aid, "owner": owner, "label": label, "factIds": ["f1"], "runs": 1}


def goal(gid, label, action_ids, us, opp):
    return {"id": gid, "label": label, "type": "all", "actionIds": list(action_ids),
            "usValue": us, "opponentValue": opp, "factIds": ["f1"]}


def game_of(labels, goals, readings):
    actions = [action(f"a{i}", "us", label) for i, label in enumerate(labels, 1)]
    built_goals = [goal(f"g{i}", label, ["a1"], us, opp) for i, (label, us, opp) in enumerate(goals, 1)]
    return {"actions": actions,
            "game": {"goals": built_goals, "redLines": [], "bottomLine": 0,
                     "opponentReadings": [{"id": "opp-sample-1", "values": {g["id"]: readings[i] for i, g in enumerate(built_goals)}}]}}


def offered(label):
    return {"actions": [action("b1", "opponent", label)],
            "game": {"goals": [goal("g1", "kits arrive", ["b1"], 2, 2)], "redLines": [], "bottomLine": 0},
            "strategies": [{"steps": [["b1"]]}, {"steps": []}]}
