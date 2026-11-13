"""Rewording comparison on model-built games (Plan A §6.6; S1; Benac stability).

Three conditions, built with the same builder settings:
    baseline   1 build on the original facts
    same-text  K builds on the original facts with fresh seeds (B2: what re-reading alone does)
    reworded   K builds, each on the facts with every cited fact paraphrased (accepted rewordings only)

Every build is solved by solver.py. Readings name the same thing in different words, so
actions and goals are aligned across all builds by embedding the labels (best match ≥
compare.align_tau within a side). A plan is then a sequence of sets of aligned action
clusters, and its outcome is the final set. Any plan can be scored on any build's game.

Metrics (see metrics()) answer two questions per condition:
    stability  does the reading change the game or the recommended plan?
    space      how many distinct plans do K readings put on the table, and are they good?
Reworded is compared with same-text at equal K, so wording effects are separated from
the sampling noise a model builder has anyway.
"""

import copy
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations

from negotiator.game import builder, lines
from negotiator.reword import engine, operators
from negotiator.reword.embed import embed

REPLICATE_SEED_STEP = 100     # same-text replicate r uses seed + 100 r, beyond any stage's n_runs seeds


# ---------- readings ----------

def cited_facts(built):
    """Facts the baseline game rests on: cited by a kept action or goal."""
    ids = {f for a in built["actions"] for f in a["factIds"]} | {f for g in built["game"]["goals"] for f in g["factIds"]}
    return [f for f in built["facts"] if f["id"] in ids]


def reword_facts(facts, cfg, levels, per_level):
    """Accepted paraphrases {fact_id: {level: [text, ...]}} and every filter record.

    Generation runs concurrently to fill the model cache; filtering then reads it in order."""
    rcfg = copy.deepcopy(cfg)
    rcfg["reword"].update(k=per_level, levels=levels, operators=["paraphrase_fact"], independent=True)
    rcfg["noise"]["enabled"] = False
    with ThreadPoolExecutor(max_workers=cfg["game"]["parallel"]) as pool:
        list(pool.map(lambda job: operators.reword("paraphrase_fact", job[0], job[1], 1, rcfg["llm"], job[2]),
                      [(f["text"], level, rcfg["seed"] + i) for f in facts for level in levels for i in range(per_level)]))
    accepted, records = {}, []
    for f in facts:
        recs, _ = engine.run([{"id": f["id"], "text": f["text"], "kind": "fact"}], rcfg)
        records += recs
        for r in recs:
            if r["accepted"] and r["text"].strip() != f["text"].strip():
                accepted.setdefault(f["id"], {}).setdefault(r["level"], []).append({"text": r["text"], "d_emb": r["d_emb"]})
    return accepted, records


def reworded_readings(facts, accepted, levels, k):
    """K fact sets. Reading j uses level levels[j % L] and that level's (j // L)-th accepted paraphrase;
    a fact without one keeps its original text (counted as a shortfall)."""
    out = []
    for j in range(k):
        level, index = levels[j % len(levels)], j // len(levels)
        reading, changed, d = [], 0, []
        for f in facts:
            options = accepted.get(f["id"], {}).get(level, [])
            if index < len(options):
                reading.append({**f, "text": options[index]["text"]})
                changed += 1
                d.append(options[index]["d_emb"])
            else:
                reading.append(f)
        out.append({"facts": reading, "level": level, "changed": changed, "d_emb": sum(d) / len(d) if d else 0.0})
    return out


def _build(facts, players, rolecard, cfg, seed):
    built = builder.build(facts, players, rolecard, {**cfg, "seed": seed})
    plans = lines.solve_within_lines(built, players)
    return {**built, "strategies": plans["strategies"], "rejected": plans["rejected"]}


def run(facts, players, rolecard, cfg):
    """Baseline, then K same-text and K reworded builds. Returns (builds, rewording records)."""
    c = cfg["compare"]
    k, seed = c["k"], cfg["seed"]
    base = _build(facts, players, rolecard, cfg, seed)
    builds = [{"condition": "baseline", "replicate": 0, **base}]
    builds += [{"condition": "same-text", "replicate": r,
                **_build(facts, players, rolecard, cfg, seed + REPLICATE_SEED_STEP * r)} for r in range(1, k + 1)]
    cited = cited_facts(base)
    per_level = math.ceil(k / len(c["levels"]))
    accepted, records = reword_facts(cited, cfg, c["levels"], per_level)
    for j, reading in enumerate(reworded_readings(cited, accepted, c["levels"], k), 1):
        swapped = {f["id"]: f for f in reading["facts"]}
        full = [swapped.get(f["id"], f) for f in base["facts"]]
        builds.append({"condition": "reworded", "replicate": j, "level": reading["level"],
                       "factsReworded": reading["changed"], "factsCited": len(cited), "d_emb": reading["d_emb"],
                       **_build(full, players, rolecard, cfg, seed)})
    return builds, records


# ---------- alignment ----------

def _cluster(items, tau, encoder, prefix):
    """items: (key, side, text) in a fixed order. Greedy: join the best cluster on the same side
    whose first member has cosine ≥ tau, else start a new one. Returns {key: cluster id}."""
    if not items:
        return {}
    vecs = embed([text for _, _, text in items], encoder)
    reps, assign = [], {}
    for (key, side, _), v in zip(items, vecs):
        best = max(((float(v @ rv), cid) for s, rv, cid in reps if s == side), default=(-1.0, None))
        if best[0] >= tau:
            assign[key] = best[1]
        else:
            cid = f"{prefix}{side}{len(reps) + 1}"
            reps.append((side, v, cid))
            assign[key] = cid
    return assign


def align(builds, cfg):
    """Map every build's action and goal ids to shared clusters, in place: build["actionCluster"],
    ["goalCluster"], and build["lines"] (its red-line and must-have clusters and bottom line).
    Red-line actions are not in the game, so their labels are clustered with the actions."""
    enc, tau = cfg["filter"]["encoder"], cfg["compare"]["align_tau"]
    acts = [((b_i, a["id"]), a["owner"], a["label"]) for b_i, b in enumerate(builds) for a in b["actions"]]
    acts += [((b_i, "red-line:" + r["actionId"]), r["owner"], r["label"]) for b_i, b in enumerate(builds)
             for r in b["game"].get("redLines") or [] if r["kind"] == "forbidden"]
    goals = [((b_i, g["id"]), "", g["label"]) for b_i, b in enumerate(builds) for g in b["game"]["goals"]]
    a_map, g_map = _cluster(acts, tau, enc, "A"), _cluster(goals, tau, enc, "G")
    for b_i, b in enumerate(builds):
        b["actionCluster"] = {a["id"]: a_map[(b_i, a["id"])] for a in b["actions"]}
        b["goalCluster"] = {g["id"]: g_map[(b_i, g["id"])] for g in b["game"]["goals"]}
        red = b["game"].get("redLines") or []
        b["lines"] = {"forbidden": {a_map[(b_i, "red-line:" + r["actionId"])] for r in red if r["kind"] == "forbidden"},
                      "required": {b["actionCluster"][r["actionId"]] for r in red if r["kind"] == "required"},
                      "bottom": b["game"].get("bottomLine", 0)}


def plans_of(build, top=None):
    """Plans as tuples of frozensets of action clusters (one set per offer)."""
    out = []
    for s in build["strategies"][:top]:
        steps = s.get("steps") or ([s["actionIds"]] if s.get("actionIds") else [])
        out.append(tuple(frozenset(build["actionCluster"][a] for a in step) for step in steps))
    return out


def outcome(plan):
    return frozenset().union(*plan) if plan else frozenset()


# ---------- scoring a plan on any build's game ----------

def play(plan, build):
    """Play a plan on this build's game. Each offer adds the build's actions in those clusters
    (clusters it lacks add nothing) and is accepted only if the build's opponent value does not
    fall; play stops at the first rejection. Returns (final state, crossed): crossed if we would
    have to offer a red-line action, pass below the bottom line, or end a deal without a must-have."""
    goals, lim = build["game"]["goals"], build["lines"]
    members = {}
    for a, c in build["actionCluster"].items():
        members.setdefault(c, set()).add(a)
    state, done = set(), set()
    for step in plan:
        if step & lim["forbidden"]:
            return state, True
        nxt = state | {a for c in step for a in members.get(c, ())}
        if lines.reward(nxt, goals, "opponentValue") + 1e-9 < lines.reward(state, goals, "opponentValue"):
            break
        state, done = nxt, done | step
        if lines.reward(state, goals) + 1e-9 < lim["bottom"]:
            return state, True
    return state, bool(state) and bool(lim["required"] - done)


def score(plan, build):
    """Our normalised value [0, 1] for the plan on this build's game, on solver.py's scale. A plan
    that crosses this build's lines scores as walking away there (the bottom line)."""
    goals = build["game"]["goals"]
    low = sum(min(0, g["usValue"]) for g in goals)
    high = sum(max(0, g["usValue"]) for g in goals)
    if high == low:
        return 0.0
    state, crossed = play(plan, build)
    value = build["lines"]["bottom"] if crossed else lines.reward(state, goals)
    return min(1.0, max(0.0, (value - low) / (high - low)))


# ---------- metrics ----------

def _best_match_labels(a, b, enc):
    if not a or not b:
        return 0.0
    return builder.best_match(embed(a, enc), embed(b, enc))


def _jaccard_distance(x, y):
    return 1 - len(x & y) / len(x | y) if x | y else 0.0


def metrics(builds, cfg):
    """Per-condition stability and strategy-space metrics. See README of this module."""
    align(builds, cfg)
    enc, alpha = cfg["filter"]["encoder"], cfg["compare"]["alpha"]
    base = builds[0]
    base_top = outcome(plans_of(base, 1)[0]) if base["strategies"] else frozenset()

    # Every distinct plan from any build, scored on every build's game (cross-reading score Ū and worst case).
    pool = {}
    for b in builds:
        for p in plans_of(b):
            pool.setdefault(p, None)
    scores = {p: [score(p, b) for b in builds] for p in pool}
    u_bar = {p: sum(s) / len(s) for p, s in scores.items()}
    worst = {p: min(s) for p, s in scores.items()}
    best_overall = max(u_bar.values(), default=0.0)
    good = {outcome(p) for p in pool if u_bar[p] >= alpha * best_overall}

    def by_condition(name):
        group = [b for b in builds if b["condition"] == name]
        if not group:
            return None
        tops = [outcome(plans_of(b, 1)[0]) if b["strategies"] else frozenset() for b in group]
        top_plans = [plans_of(b, 1)[0] if b["strategies"] else () for b in group]
        outcomes = [{outcome(p) for p in plans_of(b)} for b in group]
        seen, curve = set(), []
        for o in outcomes:
            seen |= o
            curve.append(len(seen))
        counts = Counter(tops)
        entropy = -sum(v / len(tops) * math.log(v / len(tops)) for v in counts.values())
        own_pool = {p for b in group for p in plans_of(b)}
        own_outcomes = {outcome(p) for p in own_pool}
        others = {outcome(p) for b in builds if b["condition"] != name for p in plans_of(b)}

        def side_sim(b, side):
            return _best_match_labels([a["label"] for a in b["actions"] if a["owner"] == side],
                                      [a["label"] for a in base["actions"] if a["owner"] == side], enc)

        base_goal_value = {base["goalCluster"][g["id"]]: g["usValue"] for g in base["game"]["goals"]}
        diffs = [abs(g["usValue"] - base_goal_value[b["goalCluster"][g["id"]]]) / (2 * max(cfg["game"]["stance_values"]))
                 for b in group for g in b["game"]["goals"] if b["goalCluster"][g["id"]] in base_goal_value]
        return {
            "builds": len(group),
            # structure vs baseline (Benac-style best-match cosine)
            "action_similarity": sum((side_sim(b, "us") + side_sim(b, "opponent")) / 2 for b in group) / len(group),
            "goal_similarity": sum(_best_match_labels([g["label"] for g in b["game"]["goals"]],
                                                      [g["label"] for g in base["game"]["goals"]], enc)
                                   for b in group) / len(group),
            "action_clusters": len({c for b in group for c in b["actionCluster"].values()}),
            "g_us_l1": sum(diffs) / len(diffs) if diffs else None,
            # the recommendation
            "top_plan_agreement": sum(t == base_top for t in tops) / len(tops),
            "distinct_top_plans": len(counts),
            "effective_top_plans": math.exp(entropy),
            "top_plan_jaccard": (sum(_jaccard_distance(x, y) for x, y in combinations(tops, 2))
                                 / math.comb(len(tops), 2)) if len(tops) > 1 else 0.0,
            "top_plan_u_bar": sum(u_bar[p] for p in top_plans) / len(top_plans),
            "top_plan_worst": sum(worst[p] for p in top_plans) / len(top_plans),
            # lines: does a reading's top plan cross the red lines or bottom line of any reading?
            "top_plans_crossing_lines": sum(any(play(p, b)[1] for b in builds) for p in top_plans) / len(top_plans),
            "solver_plans_rejected": sum(len(b.get("rejected") or []) for b in group) / len(group),
            # the strategy space
            "distinct_plans": len(own_outcomes),
            "accumulation": curve,
            "best_u_bar": max((u_bar[p] for p in own_pool), default=0.0),
            "good_plans": len(own_outcomes & good),
            "novel_good_plans": len((own_outcomes & good) - others),
        }

    return {
        "alpha": alpha,
        "best_u_bar_overall": best_overall,
        "good_plans_overall": len(good),
        "conditions": {name: by_condition(name) for name in ("same-text", "reworded")},
        "baseline": {"actions": len(base["actions"]), "goals": len(base["game"]["goals"]),
                     "top_plan": sorted(base_top), "top_plan_u_bar": u_bar.get(plans_of(base, 1)[0]) if base["strategies"] else None},
        "readings": [{k: b.get(k) for k in ("condition", "replicate", "level", "factsReworded", "factsCited", "d_emb")}
                     | {"actions": len(b["actions"]), "goals": len(b["game"]["goals"]),
                        "top_plan": sorted(outcome(plans_of(b, 1)[0])) if b["strategies"] else []}
                     for b in builds],
    }


# ---------- builder stability (same text, several full builds; Benac App. B compares 5) ----------

def stability_report(builds, cfg):
    """Pairwise agreement between full builds of the same text, stage by stage.

    Structure: Benac's best-match cosine of labels, and Jaccard of aligned goal, action and
    red-line sets. Values: mean |change| of our value on goals both builds have (0-1).
    Advice: Jaccard of top-plan outcomes, and regret, the loss in our score on build j from
    playing build i's top plan instead of j's own, floored at 0 so a gain elsewhere cannot hide
    a loss (0 = the plans are interchangeable)."""
    align(builds, cfg)
    enc, top = cfg["filter"]["encoder"], max(cfg["game"]["stance_values"])
    n = len(builds)
    pairs = list(combinations(range(n), 2))

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    def jac(a, b):
        return len(a & b) / len(a | b) if a | b else 1.0

    def labels(b, side):
        return [a["label"] for a in b["actions"] if a["owner"] == side]

    goals = [set(b["goalCluster"].values()) for b in builds]
    acts = [set(b["actionCluster"].values()) for b in builds]
    reds = [b["lines"]["forbidden"] | b["lines"]["required"] for b in builds]
    tops = [plans_of(b, 1)[0] if b["strategies"] else () for b in builds]
    vals = [{b["goalCluster"][g["id"]]: g["usValue"] for g in b["game"]["goals"]} for b in builds]
    return {
        "builds": n,
        "action_similarity": mean([(_best_match_labels(labels(builds[i], "us"), labels(builds[j], "us"), enc)
                                    + _best_match_labels(labels(builds[i], "opponent"), labels(builds[j], "opponent"), enc)) / 2
                                   for i, j in pairs]),
        "goal_similarity": mean([_best_match_labels([g["label"] for g in builds[i]["game"]["goals"]],
                                                    [g["label"] for g in builds[j]["game"]["goals"]], enc) for i, j in pairs]),
        "goal_jaccard": mean([jac(goals[i], goals[j]) for i, j in pairs]),
        "action_jaccard": mean([jac(acts[i], acts[j]) for i, j in pairs]),
        "red_line_jaccard": mean([jac(reds[i], reds[j]) for i, j in pairs]),
        "g_us_l1": mean([mean([abs(vals[i][c] - vals[j][c]) / (2 * top) for c in vals[i].keys() & vals[j].keys()])
                         for i, j in pairs]),
        "top_plan_jaccard": mean([jac(outcome(tops[i]), outcome(tops[j])) for i, j in pairs]),
        "top_plan_regret": mean([max(0.0, score(tops[j], builds[j]) - score(tops[i], builds[j]))
                                 for i in range(n) for j in range(n) if i != j]),
        "goals_per_build": [len(b["game"]["goals"]) for b in builds],
    }
