"""Facts -> commitment game, staged after Benac et al. (2026, arXiv 2603.14066, App. B).

    1 issues     per party: outcomes it wants to secure or avoid           (n runs)
    2 canonical  merge issues from all runs into shared goals; keep goals found in a majority of runs
    3 stance     ours: label per goal from the role card (median); theirs: a distribution per goal,
                 from which opponent readings are drawn; BATNA for both     (n runs)
    4 actions    per party: commitments it could make; merged; every fact-supported one is a candidate
    5 red lines  candidates our role card forbids or requires, each with a verified verbatim quote
    6 mapping    per party: which candidates bring about each goal          (n runs, majority per link)
    7 select     must-haves, never red-line actions, then greedy goal coverage weighted by |G|
    8 kind       each goal binary or gradual                                (n runs, majority vote)

The paper gives no prompts and no stance-to-number map, so both are our choices
(negotiator/prompts/game_*.md; game.stance_values). The output uses the package
schema solver.py reads, so the rule-based game_builder.py stays the baseline.
Red lines and the bottom line are enforced on plans by negotiator/game/lines.py.
"""

import random
import re
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

from negotiator import llm

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SIDES = ("us", "opp")
STANCES = ["strongly_support", "moderately_support", "neutral", "moderately_oppose", "strongly_oppose"]

STR = {"type": "string"}


def _obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _arr(item):
    return {"type": "array", "items": item}


def _enum(values):
    return {"type": "string", "enum": list(values)}


ISSUES = _obj({"issues": _arr(_obj({"text": STR, "direction": {"type": "string", "enum": ["secure", "avoid"]},
                                    "fact_ids": _arr(STR)}))})
GROUPS = _obj({"groups": _arr(_obj({"label": STR, "members": _arr(STR)}))})
ACTIONS = _obj({"actions": _arr(_obj({"text": STR, "fact_ids": _arr(STR)}))})

LABEL_RULES = {
    "goal": "- Phrase each label as a neutral outcome that either party could value, positively or negatively "
            "(\"FWB staff move unescorted inside the camp\"), not as one side's wish.",
    "action": "- Phrase each label as a commitment by the party named in the statements, starting with a verb.",
}


def _render(name, **fields):
    text = (PROMPTS / name).read_text()
    for key, value in fields.items():     # str.replace: case text can contain braces
        text = text.replace("{" + key + "}", str(value))
    return text


def _call(prompt, schema, cfg, seed):
    g = cfg["game"]
    return llm.complete_json(prompt, schema, model=g["model"], base_url=cfg["llm"]["base_url"],
                             effort=g["effort"], max_tokens=g["max_tokens"], seed=seed)[0]


def _usable(facts, g):
    """Verified, relevant facts in a fixed order, so the input order of facts never matters."""
    keep = [f for f in facts if f.get("verified", True) and f.get("relevance", 3) >= g["min_relevance"]]
    return sorted(keep, key=lambda f: f["id"])


def _fact_lines(facts):
    return "\n".join(f"[{f['id']}] ({f.get('source') or f.get('sourceId')}) {f['text']}" for f in facts)


def _average_distribution(runs):
    """Mean over runs of each run's label percentages, normalised to sum to 1 (a run of all zeros counts as uniform)."""
    out = dict.fromkeys(STANCES, 0.0)
    for run in runs:
        total = sum(max(0, run[k]) for k in STANCES)
        for k in STANCES:
            out[k] += (max(0, run[k]) / total if total else 1 / len(STANCES)) / len(runs)
    return out


def normalise(text):
    """For quote matching: unify quotes and dashes, collapse whitespace, ignore case."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}))
    return re.sub(r"\s+", " ", text).strip().lower()


def _majority(n):
    return n // 2 + 1


def _canonical(items, kind, players, cfg, cap, known_facts, min_runs):
    """Merge statements from all runs (one model call), then keep groups that cite a known fact
    and appear in at least min_runs runs (at most cap, most runs first). Returns (kept groups, report)."""
    by_id = {x["id"]: x for x in items}
    if not items:
        return [], {"unassigned": [], "unsupported": [], "too_few_runs": [], "over_cap": []}
    lines = "\n".join(f"[{x['id']}] (run {x['run'] + 1}, {players[x['side']]}) {x['text']}" for x in items)
    out = _call(_render("game_canonicalise.md", kind=kind, kind_plural=kind + "s", us=players["us"],
                        opp=players["opp"], label_rule=LABEL_RULES[kind], items=lines),
                GROUPS, cfg, cfg["seed"])
    groups, seen = [], set()
    for group in out["groups"]:
        members = [m for m in dict.fromkeys(group["members"]) if m in by_id and m not in seen]
        seen.update(members)
        if members:
            groups.append({
                "label": group["label"],
                "members": sorted(members),
                "runs": len({by_id[m]["run"] for m in members}),
                "sides": sorted({by_id[m]["side"] for m in members}),
                "factIds": sorted({f for m in members for f in by_id[m]["fact_ids"] if f in known_facts}),
            })
    supported = [x for x in groups if x["factIds"]]
    kept = sorted((x for x in supported if x["runs"] >= min_runs),
                  key=lambda x: (-x["runs"], -len(x["members"]), x["label"]))
    report = {
        "unassigned": sorted(set(by_id) - seen),
        "unsupported": [x["label"] for x in groups if not x["factIds"]],
        "too_few_runs": [x["label"] for x in supported if x["runs"] < min_runs],
        "over_cap": [x["label"] for x in kept[cap:]] if cap is not None else [],
    }
    return kept[:cap], report


def _calls(jobs, cfg):
    """Run (prompt, schema, seed) jobs concurrently; results come back in job order."""
    with ThreadPoolExecutor(max_workers=cfg["game"]["parallel"]) as pool:
        return list(pool.map(lambda job: _call(job[0], job[1], cfg, job[2]), jobs))


def _extract(prompts, schema, key, seeds, cfg):
    """n runs of one extraction prompt per party ({side: prompt}), as statements tagged with run and side."""
    jobs = [(side, run, seed) for side in prompts for run, seed in enumerate(seeds)]
    outs = _calls([(prompts[side], schema, seed) for side, _, seed in jobs], cfg)
    return {side: [{**x, "id": f"{s}{run + 1}.{i + 1}", "run": run, "side": s}
                   for (s, run, _), out in zip(jobs, outs) if s == side for i, x in enumerate(out[key])]
            for side in prompts}


def build(facts, players, rolecard, cfg):
    """Game from atomised facts. players = {"us": name, "opp": name}; rolecard = {"id": source id, "text": ...}.

    Returns {"facts", "actions", "game", "notes"}; "actions" and "game" are what solver.solve reads,
    and game["redLines"] / game["bottomLine"] are what lines.py enforces on every plan."""
    g = cfg["game"]
    n = g["n_runs"]
    need = _majority(n)
    seeds = [cfg["seed"] + i for i in range(n)]
    facts = _usable(facts, g)
    known = {f["id"] for f in facts}
    ctx = {"us": players["us"], "opp": players["opp"], "facts": _fact_lines(facts), "rolecard_id": rolecard["id"]}
    notes = {"raw": {}, "reports": {}}

    # 1-2 issues -> canonical goals (kept if found in a majority of runs)
    raw = _extract({side: _render("game_issues.md", party=players[side], max_items=g["max_goals"], **ctx)
                    for side in SIDES}, ISSUES, "issues", seeds, cfg)
    issues = raw["us"] + raw["opp"]
    # Most goals come up in every run, so a small cap was decided by tie-breaks (member count, then
    # alphabetical order) and made builds of the same text disagree; keep them all, up to the solver's limit.
    goals, notes["reports"]["goals"] = _canonical(issues, "goal", players, cfg, g["max_goals_in_game"], known, need)
    for i, goal in enumerate(goals, 1):
        goal["id"] = f"g{i}"
    notes["raw"]["issues"] = issues
    goal_lines = "\n".join(f"{x['id']}: {x['label']}" for x in goals)

    # 3 stance: before actions, so action selection can weigh goals by what they are worth
    us_col, opp_col, readings, batna = _stances(goals, goal_lines, players, rolecard, ctx, seeds, cfg, notes)

    # 4 actions per party: every fact-supported commitment from any run is a candidate
    # (Benac deduplicates actions; a majority rule here dropped the actions whole goals depended on)
    raw = _extract({side: _render("game_actions.md", party=players[side],
                                  other=players["opp" if side == "us" else "us"], goals=goal_lines,
                                  max_items=g["max_candidates_per_side"], **ctx)
                    for side in SIDES}, ACTIONS, "actions", seeds, cfg)
    candidates = []
    for side, prefix in (("us", "a"), ("opp", "b")):
        kept, notes["reports"][f"actions_{side}"] = _canonical(raw[side], "action", players, cfg, None, known,
                                                               g["action_min_runs"])
        candidates += [{**x, "id": f"{prefix}{i}", "owner": side} for i, x in enumerate(kept, 1)]
        notes["raw"][f"actions_{side}"] = raw[side]
    action_lines = "\n".join(f"{a['id']} ({players[a['owner']]}): {a['label']}" for a in candidates)

    # 5 red lines and must-haves from our role card (each needs a verbatim role-card quote)
    red_lines = _red_lines(candidates, action_lines, players, rolecard, seeds, cfg, notes)
    forbidden = {r["actionId"] for r in red_lines if r["kind"] == "forbidden"}
    required = {r["actionId"] for r in red_lines if r["kind"] == "required"}

    # 6 mapping on all candidates: majority vote on each (goal, action) link
    jobs = []
    for side in SIDES:
        own = [a for a in candidates if a["owner"] == side]
        if not own or not goals:
            continue
        schema = _obj({"links": _arr(_obj({"goal_id": _enum(x["id"] for x in goals),
                                           "action_ids": _arr(_enum(a["id"] for a in own))}))})
        prompt = _render("game_mapping.md", party=players[side], goals=goal_lines,
                         actions="\n".join(f"{a['id']}: {a['label']}" for a in own), **ctx)
        jobs += [(prompt, schema, seed) for seed in seeds]
    votes = Counter()
    for out in _calls(jobs, cfg):     # a goal left out has no links in that run
        votes.update({(x["goal_id"], a) for x in out["links"] for a in x["action_ids"]})
    links = {(gid, a) for (gid, a), v in votes.items() if v >= need}

    # 7 select at most max_actions_per_side per side: must-haves first, red-line actions never,
    # then greedily the action that brings about the most goal weight not yet covered
    weight = {x["id"]: abs(us_col[x["id"]]) + abs(opp_col[x["id"]]) for x in goals}
    actions = _select(candidates, links, weight, forbidden, required, g["max_actions_per_side"], notes)
    order = {a["id"]: i for i, a in enumerate(actions)}
    for goal in goals:
        goal["actionIds"] = sorted((a for gid, a in links if gid == goal["id"] and a in order), key=order.get)
    notes["reports"]["goals"]["no_actions"] = [x["label"] for x in goals if not x["actionIds"]]
    goals = [x for x in goals if x["actionIds"]]
    labels = {a["id"]: a["label"] for a in candidates}
    owner = {a["id"]: a["owner"] for a in candidates}

    # 8 kind: majority vote, binary vs gradual
    if goals:
        schema = _obj({"kinds": _arr(_obj({"goal_id": _enum(x["id"] for x in goals),
                                           "kind": _enum(["binary", "gradual"])}))})
        prompt = _render("game_kind.md", us=players["us"], opp=players["opp"], goals="\n".join(
            f"{x['id']}: {x['label']}\n" + "\n".join(f"  - {a}: {labels[a]}" for a in x["actionIds"])
            for x in goals))
        kinds = [{x["goal_id"]: x["kind"] for x in out["kinds"]} for out in _calls([(prompt, schema, seed) for seed in seeds], cfg)]
        for goal in goals:   # a goal left out of a run counts as gradual in that run
            goal["type"] = "all" if sum(k.get(goal["id"]) == "binary" for k in kinds) >= need else "linear"

    kept_ids = {x["id"] for x in goals}
    game = {
        "maxOffers": g["max_offers"],
        "maxActionsPerSide": g["max_actions_per_offer"],
        "goals": [{"id": x["id"], "label": x["label"], "type": x["type"], "actionIds": x["actionIds"],
                   "usValue": us_col[x["id"]], "opponentValue": opp_col[x["id"]],
                   "factIds": x["factIds"], "runs": x["runs"]} for x in goals],
        "forbiddenActions": [],
        "opponentReadings": [{"id": f"opp-sample-{i}", "values": {k: v for k, v in r.items() if k in kept_ids}}
                             for i, r in enumerate(readings, 1)],
        "batna": batna,
        "bottomLine": batna["us"],
        "redLines": [{**r, "owner": "us" if owner[r["actionId"]] == "us" else "opponent"} for r in red_lines],
        "assumptions": [
            "Commitments are binding and additive.",
            f"Goals and goal-action links were each extracted {n} times by a model; only those found in a majority of runs are kept.",
            "Actions are chosen to bring about as much goal value as possible, within the solver's size limit.",
            "Our values are the median of stances elicited from our role card.",
            "The opponent column is the expected value of an elicited stance distribution (shared documents only); each opponent reading is one draw from it, independently per goal.",
            "Stance labels map to numbers by a fixed scale (game.stance_values), not a measured utility.",
            "Red lines and must-haves come from our role card, each with a verbatim quote. No plan may include a red-line action, leave out a must-have, or pass through a state worth less to us than our BATNA (the bottom line).",
        ],
        "model": g["model"],
    }
    out_actions = [{"id": a["id"], "owner": "us" if a["owner"] == "us" else "opponent", "label": a["label"],
                    "factId": a["factIds"][0], "factIds": a["factIds"], "runs": a["runs"]} for a in actions]
    return {"facts": facts, "actions": out_actions, "game": game, "notes": notes}


def _stances(goals, goal_lines, players, rolecard, ctx, seeds, cfg, notes):
    """Ours: one label per goal from the role card, median over runs. Theirs: a probability per label
    per goal (one label is always the model's single most likely guess, so runs agree and pi(G_opp)
    has no spread); the runs' distributions are averaged and opp_samples readings drawn from it."""
    g, n = cfg["game"], len(seeds)
    value = dict(zip(STANCES, g["stance_values"]))
    enum = {"type": "string", "enum": STANCES}
    us_prompt = _render("game_stance.md", party=players["us"], us=players["us"], opp=players["opp"],
                        perspective=(f"You are given {players['us']}'s private role card below. Judge the issues from "
                                     f"{players['us']}'s own point of view, as the role card describes it."),
                        goals=goal_lines, facts=ctx["facts"],
                        rolecard=f"\n{players['us']}'s private role card ({rolecard['id']}):\n<<<\n{rolecard['text']}\n>>>")
    opp_prompt = _render("game_stance_opp.md", party=players["opp"], us=players["us"], opp=players["opp"],
                         perspective=(f"You do not have {players['opp']}'s private brief. Infer what {players['opp']} values "
                                      f"from the shared documents and its stated positions. Facts from {rolecard['id']} "
                                      f"are {players['us']}'s private view and may be biased about {players['opp']}."),
                         goals=goal_lines, facts=ctx["facts"])
    us_schema = _obj({"stances": _arr(_obj({"goal_id": _enum(x["id"] for x in goals), "stance": enum})), "batna": enum})
    # Per-goal answers are lists, not one property per goal: 16 goals x 5 required fields compiled to
    # a grammar the gateway rejects. A goal left out of a run is filled in and reported.
    opp_schema = _obj({"stances": _arr(_obj({"goal_id": _enum(x["id"] for x in goals),
                                              "percent": _arr({"type": "integer"})})), "batna": enum})
    outs = _calls([(us_prompt, us_schema, seed) for seed in seeds] + [(opp_prompt, opp_schema, seed) for seed in seeds], cfg)
    us_runs, opp_runs = outs[:n], outs[n:]
    notes["raw"]["stances_us"], notes["raw"]["stances_opp"] = us_runs, opp_runs
    # Per run {goal: {label: percent}}; a goal left out or without five numbers counts as uniform.
    uniform = dict.fromkeys(STANCES, 1)
    filled, opp_tables = [], []
    for r in opp_runs:
        given = {x["goal_id"]: dict(zip(STANCES, x["percent"])) for x in r["stances"] if len(x["percent"]) == len(STANCES)}
        filled += [gid for gid in (x["id"] for x in goals) if gid not in given]
        opp_tables.append({x["id"]: given.get(x["id"], uniform) for x in goals})
    notes["reports"]["stance_opp"] = {"filled_uniform": filled}

    us_tables = [{x["goal_id"]: x["stance"] for x in r["stances"]} for r in us_runs]
    notes["reports"]["stance_us"] = {"filled_neutral": [x["id"] for t in us_tables for x in goals if x["id"] not in t]}
    us_col = {x["id"]: median(value[t.get(x["id"], "neutral")] for t in us_tables) for x in goals}
    dist = {x["id"]: _average_distribution([t[x["id"]] for t in opp_tables]) for x in goals}
    opp_col = {gid: round(sum(p * value[k] for k, p in d.items()), 3) for gid, d in dist.items()}
    rng = random.Random(cfg["seed"])
    readings = [{gid: value[rng.choices(STANCES, weights=[d[k] for k in STANCES])[0]] for gid, d in dist.items()}
                for _ in range(g["opp_samples"])]
    notes["opp_distribution"] = dist
    batna = {"us": median(value[r["batna"]] for r in us_runs), "opp": median(value[r["batna"]] for r in opp_runs)}
    return us_col, opp_col, readings, batna


def _red_lines(candidates, action_lines, players, rolecard, seeds, cfg, notes):
    """Candidate actions our role card rules out (forbidden) or makes a condition of any deal (required).

    A model proposes them with a quote; the quote must appear verbatim in the role card (checked here,
    not by a model) and the same (kind, action) must come up in a majority of runs. If an action is
    both, it is forbidden: a deal that needs it cannot be accepted."""
    if not candidates:
        return []
    ids = [a["id"] for a in candidates]
    item = _obj({"action_id": {"type": "string", "enum": ids}, "quote": STR})
    schema = _obj({"forbidden": _arr(item), "required": _arr(item)})
    prompt = _render("game_red_lines.md", us=players["us"], opp=players["opp"], actions=action_lines,
                     rolecard_id=rolecard["id"], rolecard=rolecard["text"])
    outs = _calls([(prompt, schema, seed) for seed in seeds], cfg)
    notes["raw"]["red_lines"] = outs
    source = normalise(rolecard["text"])
    votes, quotes, unverified = Counter(), {}, []
    for out in outs:
        for kind in ("forbidden", "required"):
            for x in out[kind]:
                if x["quote"].strip() and normalise(x["quote"]) in source:
                    votes[(kind, x["action_id"])] += 1
                    quotes.setdefault((kind, x["action_id"]), x["quote"])
                else:
                    unverified.append({"kind": kind, **x})
    kept = {key for key, v in votes.items() if v >= _majority(len(seeds))}
    conflicts = {a for kind, a in kept if kind == "required" and ("forbidden", a) in kept}
    labels = {a["id"]: a["label"] for a in candidates}
    notes["reports"]["red_lines"] = {"unverified_quotes": unverified, "conflicts": sorted(conflicts),
                                     "minority": [f"{k}:{a}" for (k, a), v in votes.items() if v < _majority(len(seeds))]}
    return [{"kind": kind, "actionId": a, "label": labels[a], "quote": quotes[(kind, a)]}
            for kind, a in sorted(kept) if not (kind == "required" and a in conflicts)]


def _select(candidates, links, weight, forbidden, required, cap, notes):
    """Must-haves first; never red-line actions; then the action covering the most goal weight not yet
    covered by a chosen action, until each side has cap actions or nothing linked is left."""
    goals_of = {a["id"]: {gid for gid, x in links if x == a["id"]} for a in candidates}
    chosen = [a for a in candidates if a["id"] in required]
    covered = set().union(*(goals_of[a["id"]] for a in chosen)) if chosen else set()
    pool = [a for a in candidates if a["id"] not in forbidden and a["id"] not in required and goals_of[a["id"]]]
    while True:
        room = [a for a in pool if sum(c["owner"] == a["owner"] for c in chosen) < cap]
        if not room:
            break
        best = min(room, key=lambda a: (-sum(weight[x] for x in goals_of[a["id"]] - covered),
                                        -sum(weight[x] for x in goals_of[a["id"]]), -a["runs"], a["id"]))
        chosen.append(best)
        covered |= goals_of[best["id"]]
        pool.remove(best)
    picked = {a["id"] for a in chosen}
    notes["reports"]["selection"] = {
        "red_line_actions": sorted(forbidden),
        "unlinked": [a["label"] for a in candidates if not goals_of[a["id"]] and a["id"] not in forbidden],
        "over_cap": [a["label"] for a in pool if a["id"] not in picked],
    }
    return chosen


# ---------- stability (Benac App. B: symmetric best-match cosine over labels) ----------

def best_match(a, b):
    """Symmetric best-match cosine between two sets of unit vectors (rows)."""
    if not len(a) or not len(b):
        return 0.0
    sim = a @ b.T
    return float((sim.max(axis=1).mean() + sim.max(axis=0).mean()) / 2)


def stability(notes, cfg):
    """Mean pairwise best-match cosine between runs: issues per party (goal similarity),
    actions within actor (action similarity); our mean pairwise stance agreement; the opponent's value spread."""
    from itertools import combinations

    from negotiator.reword.embed import embed

    def across_runs(items):
        runs = sorted({x["run"] for x in items})
        vecs = {r: embed([x["text"] for x in items if x["run"] == r], cfg["filter"]["encoder"]) for r in runs}
        pairs = [best_match(vecs[i], vecs[j]) for i, j in combinations(runs, 2)]
        return sum(pairs) / len(pairs) if pairs else None

    def agreement(runs):
        pairs = [sum(a[k] == b.get(k) for k in a) / len(a) for a, b in combinations(runs, 2) if a]
        return sum(pairs) / len(pairs) if pairs else None

    raw = notes["raw"]
    out = {}
    for side in SIDES:
        out[f"issue_similarity_{side}"] = across_runs([x for x in raw["issues"] if x["side"] == side])
        out[f"action_similarity_{side}"] = across_runs(raw[f"actions_{side}"])
    out["stance_agreement_us"] = agreement([{x["goal_id"]: x["stance"] for x in r["stances"]} | {"batna": r["batna"]}
                                            for r in raw["stances_us"]])
    # Opponent: spread of pi(G_opp), as the mean over goals of the standard deviation of the value.
    values = dict(zip(STANCES, cfg["game"]["stance_values"]))
    sds = []
    for d in notes["opp_distribution"].values():
        mean = sum(p * values[k] for k, p in d.items())
        sds.append(sum(p * (values[k] - mean) ** 2 for k, p in d.items()) ** 0.5)
    out["opp_value_sd"] = sum(sds) / len(sds) if sds else None
    return out
