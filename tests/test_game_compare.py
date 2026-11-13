"""Rewording comparison metrics on hand-made builds (no model calls, fake encoder)."""

import numpy as np

from negotiator.game import builder, compare


def fake_embed(texts, name):
    """Same label -> same unit vector; different labels -> orthogonal."""
    vocab = {}
    rows = []
    for t in texts:
        vocab.setdefault(t.lower(), len(vocab))
    for t in texts:
        v = np.zeros(64)
        v[vocab[t.lower()]] = 1.0
        rows.append(v)
    return np.array(rows)


def make_build(condition, labels, plan, us=(10, 5), opp=(1, 1)):
    """Two actions per build (a1 ours, b1 theirs); goals g1 needs a1, g2 needs b1."""
    actions = [{"id": "a1", "owner": "us", "label": labels[0], "factIds": ["f1"]},
               {"id": "b1", "owner": "opponent", "label": labels[1], "factIds": ["f2"]}]
    goals = [{"id": "g1", "label": "goal one", "type": "all", "actionIds": ["a1"], "usValue": us[0], "opponentValue": opp[0], "factIds": ["f1"]},
             {"id": "g2", "label": "goal two", "type": "all", "actionIds": ["b1"], "usValue": us[1], "opponentValue": opp[1], "factIds": ["f2"]}]
    return {"condition": condition, "actions": actions, "game": {"goals": goals},
            "strategies": [{"steps": plan, "actionIds": plan[0] if plan else []}] if plan else []}


def cfg():
    return {"filter": {"encoder": "fake"}, "compare": {"align_tau": 0.8, "alpha": 0.9},
            "game": {"stance_values": [10, 5, 0, -5, -10]}}


def test_metrics_count_distinct_and_novel_plans(monkeypatch):
    monkeypatch.setattr(compare, "embed", fake_embed)
    monkeypatch.setattr(builder, "best_match", lambda a, b: 1.0)
    builds = [
        make_build("baseline", ["give access", "deliver rice"], [["a1"]]),
        make_build("same-text", ["give access", "deliver rice"], [["a1"]]),
        make_build("same-text", ["give access", "deliver rice"], [["a1"]]),
        make_build("reworded", ["give access", "deliver rice"], [["a1"]]),
        make_build("reworded", ["give access", "deliver rice"], [["a1", "b1"]]),
    ]
    m = compare.metrics(builds, cfg())
    st, rw = m["conditions"]["same-text"], m["conditions"]["reworded"]
    assert st["distinct_plans"] == 1 and rw["distinct_plans"] == 2
    assert st["top_plan_agreement"] == 1.0 and rw["top_plan_agreement"] == 0.5
    assert rw["accumulation"] == [1, 2]
    # {a1, b1} is worth 15/15 on every build; {a1} is 10/15: only the reworded plan is "good".
    assert rw["best_u_bar"] == 1.0 and rw["good_plans"] == 1 and rw["novel_good_plans"] == 1
    assert st["good_plans"] == 0


def test_score_stops_at_rejected_offer(monkeypatch):
    monkeypatch.setattr(compare, "embed", fake_embed)
    b = make_build("baseline", ["give access", "deliver rice"], [["a1"]], opp=(1, -5))
    compare.align([b], cfg())
    a1, b1 = b["actionCluster"]["a1"], b["actionCluster"]["b1"]
    assert compare.score((frozenset({a1}),), b) == 10 / 15
    # adding b1 lowers the opponent's value, so that offer is rejected and the state stays {a1}
    assert compare.score((frozenset({a1}), frozenset({b1})), b) == 10 / 15
    # a cluster the build does not have adds nothing
    assert compare.score((frozenset({"Aus99"}),), b) == 0.0


def test_reworded_readings_rotate_levels_and_count_shortfall():
    facts = [{"id": "f1", "text": "x"}, {"id": "f2", "text": "y"}]
    accepted = {"f1": {"light": [{"text": "x1", "d_emb": 0.1}], "heavy": [{"text": "x3", "d_emb": 0.3}]}}
    out = compare.reworded_readings(facts, accepted, ["light", "moderate", "heavy"], 3)
    assert [r["level"] for r in out] == ["light", "moderate", "heavy"]
    assert [r["changed"] for r in out] == [1, 0, 1]
    assert out[2]["facts"][0]["text"] == "x3" and out[2]["facts"][1]["text"] == "y"


def test_plan_crossing_another_readings_red_line_scores_as_walking_away(monkeypatch):
    monkeypatch.setattr(compare, "embed", fake_embed)
    a = make_build("baseline", ["give access", "deliver rice"], [["a1", "b1"]])
    b = make_build("reworded", ["hire locals", "deliver rice"], [["b1"]])
    # in reading b, "give access" is a red line, so it is not one of b's actions
    b["game"]["redLines"] = [{"kind": "forbidden", "actionId": "a7", "label": "give access", "quote": "q", "owner": "us"}]
    b["game"]["bottomLine"] = -3
    compare.align([a, b], cfg())
    plan = compare.plans_of(a, 1)[0]
    assert compare.play(plan, a)[1] is False
    assert compare.play(plan, b)[1] is True
    assert compare.score(plan, b) == 0.0      # walking away there: bottom line -3 on a 0..15 scale, clamped to 0


def test_stability_report_identical_and_different_builds(monkeypatch):
    monkeypatch.setattr(compare, "embed", fake_embed)
    monkeypatch.setattr(builder, "best_match", lambda a, b: 1.0)
    same = [make_build("same-text", ["give access", "deliver rice"], [["a1", "b1"]]) for _ in range(3)]
    r = compare.stability_report(same, cfg())
    assert r["action_jaccard"] == r["goal_jaccard"] == r["top_plan_jaccard"] == 1.0 and r["top_plan_regret"] == 0.0
    mixed = same[:1] + [make_build("same-text", ["give access", "deliver rice"], [["a1"]])]
    r = compare.stability_report(mixed, cfg())
    assert r["top_plan_jaccard"] == 0.5
    # build 0 loses 5/15 with build 1's plan; build 1 gains with build 0's, which counts as 0, not -5/15
    assert r["top_plan_regret"] == (1.0 - 10 / 15 + 0.0) / 2
