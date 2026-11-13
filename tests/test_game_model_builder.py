"""Model-built game (negotiator/game/builder.py) with a scripted fake model."""

import random
import re

import numpy as np

from negotiator import llm
from negotiator.game import builder
from solver import solve

PLAYERS = {"us": "Camp Commander", "opp": "FWB"}
ROLECARD = {"id": "Rolecard", "text": "You run the camp."}
FACTS = [
    {"id": "f1", "source": "Rolecard", "text": "The camp needs food.", "verified": True, "relevance": 3},
    {"id": "f2", "source": "MoM", "text": "The town is tense.", "verified": True, "relevance": 3},
    {"id": "f3", "source": "MoM", "text": "FWB can provide rice.", "verified": True, "relevance": 3},
    {"id": "f4", "source": "MoM", "text": "It rained.", "verified": True, "relevance": 0},
]


def fake(prompt, schema, seed):
    props = schema["properties"]
    us = "Camp Commander cares" in prompt or "Camp Commander could make" in prompt or "what Camp Commander values" in prompt
    if "issues" in props:
        if us:
            items = [{"text": "Refugees get food", "direction": "secure", "fact_ids": ["f1"]}]
            if seed == 0:   # found in one run of three: dropped
                items.append({"text": "Town tension eases", "direction": "secure", "fact_ids": ["f2"]})
            return {"issues": items}
        return {"issues": [{"text": "Food reaches refugees", "direction": "secure", "fact_ids": ["f3", "nope"]}]}
    if "groups" in props:
        lines = re.findall(r"^\[([^\]]+)\] \(run \d+, [^)]+\) (.*)$", prompt, re.M)
        if "merging goals" in prompt:
            food = [i for i, text in lines if "food" in text.lower()]
            rest = [{"label": text, "members": [i]} for i, text in lines if i not in food]
            return {"groups": [{"label": "Refugees receive food", "members": food}, *rest]}
        texts = list(dict.fromkeys(text for _, text in lines))
        return {"groups": [{"label": t, "members": [i for i, x in lines if x == t]} for t in texts]}
    if "forbidden" in props:
        ids = dict((label, i) for i, label in re.findall(r"^(\w+) \([^)]+\): (.*)$", prompt, re.M))
        return {"forbidden": [{"action_id": ids["Hire locals"], "quote": "you  run the CAMP."}],   # verbatim up to case/space
                "required": [{"action_id": ids["Grant access"], "quote": "not in the role card"}]}   # unverified: ignored
    if "actions" in props:
        if not us:
            return {"actions": [{"text": "Deliver rice", "fact_ids": ["f3"]}]}
        items = [{"text": "Grant access", "fact_ids": ["f1"]}, {"text": "Hire locals", "fact_ids": ["f1"]}]
        if seed == 0:   # one run of three is enough for a candidate action
            items.append({"text": "Pay guards", "fact_ids": ["f1"]})
        return {"actions": items}
    if "batna" in props:
        if us:
            goals = props["stances"]["items"]["properties"]["goal_id"]["enum"]
            return {"stances": [{"goal_id": k, "stance": "strongly_support"} for k in goals], "batna": "neutral"}
        # opponent: a distribution per goal; runs disagree, and seed 2 sums to 50 (normalised)
        dist = [{"moderately_support": 100}, {"neutral": 100}, {"moderately_support": 25, "neutral": 25}][seed % 3]
        goals = props["stances"]["items"]["properties"]["goal_id"]["enum"]
        return {"stances": [{"goal_id": k, "percent": [dist.get(s, 0) for s in builder.STANCES]} for k in goals],
                "batna": "neutral"}
    if "links" in props:
        item = props["links"]["items"]["properties"]
        return {"links": [{"goal_id": k, "action_ids": item["action_ids"]["items"]["enum"]} for k in item["goal_id"]["enum"]]}
    goals = props["kinds"]["items"]["properties"]["goal_id"]["enum"]
    return {"kinds": [{"goal_id": k, "kind": "binary"} for k in goals]}


def _cfg(cfg):
    return {**cfg, "game": {**cfg["game"], "n_runs": 3}}


def _patch_call(monkeypatch, prompts=None):
    def call(prompt, schema, cfg, seed):
        if prompts is not None:
            prompts.append(prompt)
        return fake(prompt, schema, seed)
    monkeypatch.setattr(builder, "_call", call)


def test_majority_goals_actions_and_values(monkeypatch, cfg):
    _patch_call(monkeypatch)
    out = builder.build(FACTS, PLAYERS, ROLECARD, _cfg(cfg))
    [goal] = out["game"]["goals"]
    assert goal["label"] == "Refugees receive food"
    assert goal["runs"] == 3 and goal["factIds"] == ["f1", "f3"]      # unknown fact id dropped
    assert out["notes"]["reports"]["goals"]["too_few_runs"] == ["Town tension eases"]
    # a2 "Hire locals" is a red line, so it never enters the game; a3 came up in one run only and is kept
    assert [(a["id"], a["owner"]) for a in out["actions"]] == [("a1", "us"), ("b1", "opponent"), ("a3", "us")]
    assert goal["actionIds"] == ["a1", "b1", "a3"] and goal["type"] == "all"
    assert goal["usValue"] == 10
    # averaged distribution: moderately_support (1 + 0 + .5)/3 = .5, neutral .5 -> expected value 2.5
    assert goal["opponentValue"] == 2.5
    readings = [r["values"]["g1"] for r in out["game"]["opponentReadings"]]
    assert len(readings) == cfg["game"]["opp_samples"] and set(readings) == {0, 5}     # spread, from the distribution
    assert "f4" not in {f["id"] for f in out["facts"]}                # below min_relevance


def test_output_is_solvable(monkeypatch, cfg):
    _patch_call(monkeypatch)
    out = builder.build(FACTS, PLAYERS, ROLECARD, _cfg(cfg))
    plans = solve({"actions": out["actions"], "game": out["game"],
                   "parties": {"us": "Camp Commander", "opponent": "FWB"}})["strategies"]
    assert sorted(plans[0]["actionIds"]) == ["a1", "a3", "b1"]


def test_red_lines_need_a_verbatim_role_card_quote(monkeypatch, cfg):
    _patch_call(monkeypatch)
    out = builder.build(FACTS, PLAYERS, ROLECARD, _cfg(cfg))
    assert out["game"]["redLines"] == [{"kind": "forbidden", "actionId": "a2", "label": "Hire locals",
                                        "quote": "you  run the CAMP.", "owner": "us"}]
    assert [x["action_id"] for x in out["notes"]["reports"]["red_lines"]["unverified_quotes"]] == ["a1"] * 3
    assert out["game"]["bottomLine"] == 0      # our BATNA, "neutral"


def test_selection_covers_goals_before_adding_more_of_the_same():
    cands = [{"id": "a1", "owner": "us", "label": "x", "runs": 3}, {"id": "a2", "owner": "us", "label": "y", "runs": 3},
             {"id": "a3", "owner": "us", "label": "z", "runs": 1}, {"id": "a4", "owner": "us", "label": "w", "runs": 3}]
    links = {("g1", "a1"), ("g1", "a2"), ("g2", "a3"), ("g1", "a4")}
    notes = {"reports": {}}
    # g1 is worth more, but once a1 covers it the one-run a3 is the only way to g2; a4 is a red line
    chosen = builder._select(cands, links, {"g1": 10, "g2": 3}, {"a4"}, set(), 2, notes)
    assert [a["id"] for a in chosen] == ["a1", "a3"]
    assert notes["reports"]["selection"]["over_cap"] == ["y"] and notes["reports"]["selection"]["red_line_actions"] == ["a4"]


def test_fact_order_does_not_change_prompts(monkeypatch, cfg):
    first, second = [], []
    _patch_call(monkeypatch, first)
    builder.build(FACTS, PLAYERS, ROLECARD, _cfg(cfg))
    _patch_call(monkeypatch, second)
    shuffled = FACTS[:]
    random.Random(1).shuffle(shuffled)
    builder.build(shuffled, PLAYERS, ROLECARD, _cfg(cfg))
    assert sorted(first) == sorted(second)      # calls run concurrently, so compare as sets


def test_repeat_run_makes_no_model_calls(monkeypatch, tmp_path, cfg):
    calls = []

    def complete(prompt, schema, model, effort, max_tokens, base_url):
        calls.append(prompt)
        return fake(prompt, schema, len(calls) % 3), model     # seed is not passed here; vary anyway

    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_complete", complete)
    builder.build(FACTS, PLAYERS, ROLECARD, _cfg(cfg))
    first = len(calls)
    builder.build(FACTS, PLAYERS, ROLECARD, _cfg(cfg))
    assert first > 0 and len(calls) == first


def test_best_match_is_symmetric_and_one_for_identical_sets():
    a = np.eye(3)[:2]
    b = np.eye(3)
    assert builder.best_match(a, a) == 1.0
    assert builder.best_match(a, b) == builder.best_match(b, a)
