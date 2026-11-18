"""Experiment 2: which intermediate change actually causes different advice?

From the sentence-level wording test (experiment 1), take about ten pairs whose inferred game or
recommendation changed. One field differs between the original extraction and the reworded one —
a missing condition, the wrong owner, a dropped action, a different stance, or a missing constraint.
Three inputs then go through the same downstream settings:

    original    extraction of the original document
    perturbed   extraction of the reworded document
    corrected   perturbed extraction, with only that one field put back

If the extractions still agree and the game is where they first diverge, the same repair is made
on the built game and only the solver is re-run. Downstream model calls are repeated with a shared
seed schedule so a restoration can be told apart from sampling variation.

Pairs whose game changes while the recommendation does not are kept. They show where the
variation stops propagating.
"""

import copy
from collections import Counter, defaultdict

from negotiator.game import builder, compare, sentence_test as st
from negotiator.reword.embed import embed

FIELDS = ("missing_condition", "incorrect_owner", "omitted_action", "altered_stance", "missing_constraint")
ACTION_CATEGORIES = {"commitment", "resource", "timeline", "action"}
CONSTRAINT_CATEGORIES = {"constraint", "condition"}
SKIP_CATEGORIES = {"goal", "context"}


def actor_name(claim):
    """Extractor actor: `subject` when the sentence test stored one, otherwise `attribution`."""
    for key in ("subject", "attribution"):
        value = claim.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def propagation_of(row):
    """How far experiment 1's change travelled: stopped at the game, or reached the advice."""
    game, advice = bool(row.get("game_changed")), bool(row.get("advice_changed"))
    if game and not advice:
        return "stopped"
    if game and advice:
        return "reached"
    if advice:
        return "advice_only"
    return "none"


def guess_field(row):
    """Field suggested by experiment 1's flags, before the claims themselves are compared."""
    if row.get("conditions_lost"):
        return "missing_condition", "extraction"
    if row.get("ownership_changed"):
        return "incorrect_owner", "extraction"
    if row.get("builder_ownership_changed"):
        return "incorrect_owner", "game"
    if row.get("game_changed") or row.get("advice_changed"):
        return "unclassified", "game" if row.get("game_changed") else "downstream"
    return None, None


def select_pairs(rows, limit=10):
    """About `limit` pairs, spread across fields, always keeping game-changed / advice-unchanged rows.

    Same-text repeats are not pairs: a pair is one verified rewording against its original.
    """
    eligible = []
    for row in rows:
        if row.get("strategy") in (None, "reference", "original"):
            continue
        propagation = propagation_of(row)
        if propagation == "none":
            continue
        field, locus = guess_field(row)
        eligible.append({
            "id": row["id"], "case": row.get("case"), "passage": row.get("passage"),
            "kind": row.get("kind"), "strategy": row["strategy"], "index": row.get("index"),
            "field": field, "locus": locus, "propagation": propagation,
            "game_changed": bool(row.get("game_changed")), "advice_changed": bool(row.get("advice_changed")),
        })
    eligible.sort(key=lambda r: (str(r["case"]), str(r["passage"]), str(r["strategy"]), str(r["index"]), str(r["id"])))
    stopped = [r for r in eligible if r["propagation"] == "stopped"]
    moving = [r for r in eligible if r["propagation"] != "stopped"]
    reserve = min(len(stopped), 2 if limit >= 8 else (1 if limit >= 4 else 0))
    chosen = list(stopped[:reserve])
    buckets = defaultdict(list)
    for row in moving:
        buckets[row["field"]].append(row)
    order = [field for field in (*FIELDS, "unclassified") if buckets[field]]
    while len(chosen) < limit and any(buckets.values()):
        for field in order:
            if buckets[field] and len(chosen) < limit:
                chosen.append(buckets[field].pop(0))
    for row in stopped[reserve:]:
        if len(chosen) >= limit:
            break
        chosen.append(row)
    return chosen[:limit]


# ---------- diffs ----------

def _sim_matrix(left, right, encoder):
    sims = embed(left, encoder) @ embed(right, encoder).T
    return [[float(sims[i, j]) for j in range(len(right))] for i in range(len(left))]


def _match(ref, pert, text_of, encoder, tau):
    """Greedy one-to-one pairs at cosine >= tau, then leftovers whose texts contain each other."""
    if not ref or not pert:
        return [], list(ref), list(pert)
    sims = _sim_matrix([text_of(x) or " " for x in ref], [text_of(x) or " " for x in pert], encoder)
    order = sorted(((sims[i][j], i, j) for i in range(len(ref)) for j in range(len(pert))), reverse=True)
    used_r, used_p, pairs = set(), set(), []
    for score, i, j in order:
        if score < tau or i in used_r or j in used_p:
            continue
        used_r.add(i)
        used_p.add(j)
        pairs.append((ref[i], pert[j]))
    for i, left in enumerate(ref):
        if i in used_r:
            continue
        best = None
        for j, right in enumerate(pert):
            if j in used_p or not _contains(text_of(left), text_of(right)):
                continue
            score = sims[i][j]
            if best is None or score > best[0]:
                best = (score, j, right)
        if best:
            used_r.add(i)
            used_p.add(best[1])
            pairs.append((left, best[2]))
    missing = [x for i, x in enumerate(ref) if i not in used_r]
    extra = [x for j, x in enumerate(pert) if j not in used_p]
    return pairs, missing, extra


def _contains(a, b):
    """True when one claim is the other with a clause or a final stop removed."""
    na, nb = (builder.normalise(a or "").strip(" ."), builder.normalise(b or "").strip(" ."))
    if len(na) < 12 or len(nb) < 12:
        return False
    return na in nb or nb in na


def _lost(ref_items, pert_items, encoder, tau):
    if not ref_items:
        return []
    if not pert_items:
        return list(ref_items)
    sims = _sim_matrix(ref_items, pert_items, encoder)
    return [item for item, row in zip(ref_items, sims) if max(row) < tau]


def _best_scored(items, text, text_of, encoder):
    """(nearest item, cosine), even when the cosine is below the acceptance threshold."""
    if not items or not text:
        return None, None
    sims = _sim_matrix([text], [text_of(x) or " " for x in items], encoder)[0]
    j = max(range(len(items)), key=lambda i: sims[i])
    return items[j], float(sims[j])


def _best(items, text, text_of, encoder, tau):
    item, score = _best_scored(items, text, text_of, encoder)
    if item is None or score < tau:
        return None
    return item


def _linked(ids, focus_ids):
    return bool(focus_ids) and bool(set(ids or []) & set(focus_ids))


def extraction_edit(ref_claims, pert_claims, aliases, cfg):
    """The first extraction field that differs, or None when the passage claims still agree."""
    enc, tau = cfg["filter"]["encoder"], cfg["sentence_test"]["tau"]
    pairs, missing, _extra = _match(ref_claims, pert_claims, lambda c: c.get("text") or "", enc, tau)
    lost_pairs = []
    for ref, pert in pairs:
        lost = _lost([c for c in ref.get("conditions") or [] if c.strip()],
                     [c for c in pert.get("conditions") or [] if c.strip()], enc, tau)
        if lost:
            lost_pairs.append((len(lost), ref, pert, lost))
    if lost_pairs:
        _, ref, pert, lost = max(lost_pairs, key=lambda item: (item[0], item[2].get("id", "")))
        return {"field": "missing_condition", "claim_id": pert["id"], "restore_conditions": lost}

    owners = [(ref, pert) for ref, pert in pairs
              if st.actors(actor_name(ref), aliases) != st.actors(actor_name(pert), aliases)]
    if owners:
        ref, pert = sorted(owners, key=lambda item: item[1].get("id", ""))[0]
        return {"field": "incorrect_owner", "claim_id": pert["id"], "subject": actor_name(ref)}

    dropped = [c for c in missing if (c.get("category") or "") not in SKIP_CATEGORIES]
    actions = [c for c in dropped if (c.get("category") or "commitment") not in CONSTRAINT_CATEGORIES]
    constraints = [c for c in dropped if c.get("category") in CONSTRAINT_CATEGORIES]
    if actions:
        return {"field": "omitted_action", "claim": copy.deepcopy(sorted(actions, key=lambda c: c.get("id", ""))[0])}
    if constraints:
        return {"field": "missing_constraint", "claim": copy.deepcopy(sorted(constraints, key=lambda c: c.get("id", ""))[0])}
    return None


def game_edit(ref, pert, cfg, focus_ids=None):
    """The first game-construction field that differs. Passage-linked differences win over others."""
    enc, tau = cfg["filter"]["encoder"], cfg["compare"]["align_tau"]
    focus_ids = set(focus_ids or [])
    pairs, missing, _extra = _match(ref.get("actions") or [], pert.get("actions") or [], lambda a: a.get("label") or "", enc, tau)
    found = []

    def add(priority, linked, edit):
        found.append((0 if linked else 1, priority, edit))

    for ref_a, pert_a in pairs:
        if ref_a.get("owner") != pert_a.get("owner"):
            linked = _linked(ref_a.get("factIds"), focus_ids) or _linked(pert_a.get("factIds"), focus_ids)
            add(0, linked, {"field": "incorrect_owner", "action_label": pert_a.get("label") or "", "owner": ref_a.get("owner")})
    for action in missing:
        linked = _linked(action.get("factIds"), focus_ids)
        goals = [g.get("label") or "" for g in ref.get("game", {}).get("goals") or [] if action["id"] in (g.get("actionIds") or [])]
        add(1, linked, {"field": "omitted_action", "action": copy.deepcopy(action), "goal_labels": goals})

    g_pairs, _, _ = _match(ref.get("game", {}).get("goals") or [], pert.get("game", {}).get("goals") or [],
                           lambda g: g.get("label") or "", enc, tau)
    for ref_g, pert_g in g_pairs:
        du = abs(float(ref_g.get("usValue", 0)) - float(pert_g.get("usValue", 0)))
        do = abs(float(ref_g.get("opponentValue", 0)) - float(pert_g.get("opponentValue", 0)))
        if du <= 1e-9 and do <= 1e-9:
            continue
        readings = [r.get("values", {}).get(ref_g["id"], ref_g.get("opponentValue"))
                    for r in ref.get("game", {}).get("opponentReadings") or []]
        linked = _linked(ref_g.get("factIds"), focus_ids) or _linked(pert_g.get("factIds"), focus_ids)
        add(2, linked, {"field": "altered_stance", "goal_label": ref_g.get("label") or "",
                        "usValue": ref_g["usValue"], "opponentValue": ref_g["opponentValue"], "readings": readings,
                        "gap": du + do})

    ref_lines = [r for r in ref.get("game", {}).get("redLines") or []]
    pert_lines = [r for r in pert.get("game", {}).get("redLines") or []]
    _, missing_lines, _ = _match(ref_lines, pert_lines, lambda r: f"{r.get('kind', '')} {r.get('label', '')}", enc, tau)
    for line in missing_lines:
        action = next((a for a in ref.get("actions") or [] if a["id"] == line.get("actionId")), None)
        linked = _linked((action or {}).get("factIds"), focus_ids)
        add(3, linked, {"field": "missing_constraint", "kind": line.get("kind"), "label": line.get("label") or "",
                        "quote": line.get("quote") or "", "owner": line.get("owner")})
    if not found:
        return None
    found.sort(key=lambda item: (item[0], item[1], -item[2].get("gap", 0), item[2].get("action_label", ""), item[2].get("goal_label", ""), item[2].get("label", "")))
    edit = dict(found[0][2])
    edit.pop("gap", None)
    return edit


def first_divergence(ref_claims, pert_claims, aliases, cfg, ref_build=None, pert_build=None, focus_ids=None):
    """Extraction first. The game is repaired only when the extractions still agree."""
    edit = extraction_edit(ref_claims, pert_claims, aliases, cfg)
    if edit:
        return {"locus": "extraction", "field": edit["field"], "edit": edit}
    if ref_build is None or pert_build is None:
        return {"locus": None, "field": None, "edit": None}
    edit = game_edit(ref_build, pert_build, cfg, focus_ids)
    if edit:
        return {"locus": "game", "field": edit["field"], "edit": edit}
    return {"locus": None, "field": None, "edit": None}


# ---------- repairs ----------

def correct_claims(claims, edit):
    """Perturbed claims with one field put back. Other claims are copied through unchanged."""
    out = copy.deepcopy(claims)
    field = edit["field"]
    if field == "missing_condition":
        for claim in out:
            if claim.get("id") == edit["claim_id"]:
                have = list(claim.get("conditions") or [])
                for condition in edit["restore_conditions"]:
                    if condition not in have:
                        have.append(condition)
                claim["conditions"] = have
                return out
        raise KeyError(edit["claim_id"])
    if field == "incorrect_owner":
        for claim in out:
            if claim.get("id") == edit["claim_id"]:
                claim["subject"] = edit["subject"]
                claim["attribution"] = edit["subject"]
                if builder.normalise(edit["subject"]) not in builder.normalise(claim.get("text") or ""):
                    claim["text"] = (claim.get("text") or "").rstrip(". ") + f". Attribution: {edit['subject']}."
                return out
        raise KeyError(edit["claim_id"])
    if field in ("omitted_action", "missing_constraint"):
        claim = copy.deepcopy(edit["claim"])
        if any(c.get("id") == claim.get("id") for c in out):
            claim["id"] = f"{claim.get('id')}:restored"
        out.append(claim)
        return out
    raise ValueError(field)


def apply_game_edit(build, edit, cfg):
    """(repaired game, status). status is applied, no_difference, or at_cap. The input is not mutated."""
    enc, tau = cfg["filter"]["encoder"], cfg["compare"]["align_tau"]
    out = copy.deepcopy(build)
    field = edit["field"]
    if field == "incorrect_owner":
        action = _best(out.get("actions") or [], edit.get("action_label"), lambda a: a.get("label") or "", enc, tau)
        if action is None or action.get("owner") == edit.get("owner"):
            return out, "no_difference"
        action["owner"] = edit["owner"]
        return out, "applied"
    if field == "omitted_action":
        action = copy.deepcopy(edit["action"])
        if _best(out.get("actions") or [], action.get("label") or "", lambda a: a.get("label") or "", enc, tau):
            return out, "no_difference"
        if len(out.get("actions") or []) >= 12:
            return out, "at_cap"
        ids = {a["id"] for a in out.get("actions") or []}
        if action["id"] in ids:
            action["id"] = f"{action['id']}:restored"
        out.setdefault("actions", []).append(action)
        for label in edit.get("goal_labels") or []:
            goal = _best(out.get("game", {}).get("goals") or [], label, lambda g: g.get("label") or "", enc, tau)
            if goal is not None and action["id"] not in (goal.get("actionIds") or []):
                goal.setdefault("actionIds", []).append(action["id"])
        return out, "applied"
    if field == "altered_stance":
        goal = _best(out.get("game", {}).get("goals") or [], edit.get("goal_label"), lambda g: g.get("label") or "", enc, tau)
        if goal is None:
            return out, "no_difference"
        readings = out.get("game", {}).get("opponentReadings") or []
        wanted = [edit["readings"][i] if i < len(edit.get("readings") or []) else edit["opponentValue"] for i in range(len(readings))]
        same_values = float(goal.get("usValue", 0)) == float(edit["usValue"]) and float(goal.get("opponentValue", 0)) == float(edit["opponentValue"])
        same_readings = all((reading.get("values") or {}).get(goal["id"]) == value for reading, value in zip(readings, wanted))
        if same_values and same_readings:
            return out, "no_difference"
        goal["usValue"] = edit["usValue"]
        goal["opponentValue"] = edit["opponentValue"]
        for reading, value in zip(readings, wanted):
            reading.setdefault("values", {})[goal["id"]] = value
        return out, "applied"
    if field == "missing_constraint":
        key = lambda line: f"{line.get('kind', '')} {line.get('label', '')}"
        if _best(out.get("game", {}).get("redLines") or [], f"{edit.get('kind', '')} {edit.get('label', '')}", key, enc, tau):
            return out, "no_difference"
        action = _best(out.get("actions") or [], edit.get("label") or "", lambda a: a.get("label") or "", enc, tau)
        if action is None:
            return out, "no_difference"
        if edit.get("kind") == "forbidden":
            out["actions"] = [a for a in out.get("actions") or [] if a["id"] != action["id"]]
            kept = []
            for goal in out.get("game", {}).get("goals") or []:
                goal["actionIds"] = [i for i in goal.get("actionIds") or [] if i != action["id"]]
                if goal["actionIds"]:
                    kept.append(goal)
            out["game"]["goals"] = kept
        out["game"].setdefault("redLines", []).append({
            "kind": edit.get("kind"), "actionId": action["id"], "label": edit.get("label") or action.get("label"),
            "quote": edit.get("quote") or "", "owner": edit.get("owner") or action.get("owner"),
        })
        return out, "applied"
    raise ValueError(field)


# ---------- repeats ----------

def _face(claims, case):
    return st.builder_facts(claims, case) if case is not None else claims


def outcomes(builds, cfg):
    """Game signature and (opening, fallback) after one joint alignment, so repeats share cluster ids."""
    compare.align(builds, cfg)
    out = []
    for build in builds:
        opening, fallback = st.advice(build)
        out.append({"game": st.signature(build), "advice": (opening, fallback)})
    return out


def _opening_actions(build):
    """Actions named in the first offer. An empty plan offers nothing."""
    strategies = [s for s in build.get("strategies") or [] if s.get("steps")]
    if not strategies or not strategies[0]["steps"] or not strategies[0]["steps"][0]:
        return []
    named = set(strategies[0]["steps"][0])
    return [a for a in build.get("actions") or [] if a["id"] in named]


def _by_label(build, label, cfg, kind="actions"):
    if not label:
        return None
    enc, tau = cfg["filter"]["encoder"], cfg["compare"]["align_tau"]
    if kind == "goals":
        return _best(build.get("game", {}).get("goals") or [], label, lambda g: g.get("label") or "", enc, tau)
    return _best(build.get("actions") or [], label, lambda a: a.get("label") or "", enc, tau)


def _target_label(edit):
    if edit.get("action_label"):
        return edit["action_label"]
    if edit.get("label"):
        return edit["label"]
    action = edit.get("action") or {}
    if action.get("label"):
        return action["label"]
    claim = edit.get("claim") or {}
    if claim.get("text"):
        return claim["text"]
    return edit.get("claim_text") or ""


def locate(build, edit, cfg):
    """The action the scorer searched for, and the nearest action it actually found.

    `accepted` is the match the score uses. `matched_label` and `cosine` are recorded even
    when the cosine is below the threshold, so a miss can be told from an absent offer.
    """
    label = _target_label(edit)
    enc, tau = cfg["filter"]["encoder"], cfg["compare"]["align_tau"]
    opening = _opening_actions(build)
    opening_ids = {a["id"] for a in opening}
    action, score = _best_scored(build.get("actions") or [], label, lambda a: a.get("label") or "", enc)
    accepted = action is not None and score is not None and score >= tau
    in_opening = action is not None and action["id"] in opening_ids
    return {"target": label, "tau": tau,
            "matched_label": (action.get("label") or "") if action is not None else "",
            "cosine": None if score is None else round(score, 3),
            "accepted": accepted,
            "in_opening": in_opening,
            "owner": action.get("owner") if action is not None else None,
            "opening": [a.get("label") or "" for a in opening]}


def decision_value(build, edit, cfg):
    """The one outcome this repair is supposed to change, read from this build.

    An owner repair is who offers the targeted action. An omitted action is whether that
    action is offered. A missing constraint is whether the forbidden action stays out of the
    offer. A stance repair is that goal's two values. A missing condition is the offer's
    labels, which is where the condition shows up.
    """
    field = edit.get("field")
    if field == "altered_stance":
        goal = _by_label(build, edit.get("goal_label") or "", cfg, "goals")
        if goal is None:
            return None
        return (goal.get("usValue"), goal.get("opponentValue"))
    found = locate(build, edit, cfg)
    if field == "missing_condition" or not found["target"]:
        return tuple(sorted(a.get("label") or "" for a in _opening_actions(build)))
    if field == "incorrect_owner":
        return found["owner"] if found["accepted"] and found["in_opening"] else None
    if field == "omitted_action":
        return found["accepted"] and found["in_opening"]
    if field == "missing_constraint":
        return not (found["accepted"] and found["in_opening"])
    return tuple(sorted(a.get("label") or "" for a in _opening_actions(build)))


def _show(value):
    if value is None:
        return "absent"
    if isinstance(value, tuple):
        return " | ".join(str(part) for part in value) or "absent"
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def _scoring_edit(edit, pert_claims):
    """Copy of the edit with the claim text attached, so an owner can be found by its sentence."""
    edit = dict(edit)
    claim = next((c for c in pert_claims or [] if c.get("id") == edit.get("claim_id")), None)
    if claim and not edit.get("claim_text"):
        edit["claim_text"] = claim.get("text") or ""
    return edit


def score_decisions(builds, samples, edit, cfg):
    """Per seed: did the perturbation change this decision, and did the repair put it back?

    A seed whose edit was not applied is counted as skipped and left out of both tallies.
    """
    rows = []
    for i, sample in enumerate(samples):
        status = sample.get("corrected")
        if status != "applied":
            rows.append({"seed": sample.get("seed"), "status": status, "changed": False, "restored": False})
            continue
        triple = builds[3 * i:3 * i + 3]
        original, perturbed, corrected = (decision_value(b, edit, cfg) for b in triple)
        changed = perturbed != original
        rows.append({"seed": sample.get("seed"), "status": status, "original": _show(original),
                     "perturbed": _show(perturbed), "corrected": _show(corrected),
                     "changed": changed, "restored": bool(changed and corrected == original),
                     "match": {role: locate(build, edit, cfg) for role, build in zip(("original", "perturbed", "corrected"), triple)}})
    applied = [row for row in rows if row["status"] == "applied"]
    changed = [row for row in applied if row["changed"]]
    restored = [row for row in changed if row["restored"]]
    skipped = len(rows) - len(applied)
    unseen = bool(applied) and all(row.get("original") == "absent" and row.get("perturbed") == "absent" and row.get("corrected") == "absent" for row in applied)
    if not applied:
        verdict = "not_applied"
    elif unseen:
        verdict = "unmatched"
    elif not changed:
        verdict = "no_change"
    elif len(restored) * 2 > len(changed):
        verdict = "restored"
    elif (len(changed) - len(restored)) * 2 > len(changed):
        verdict = "not_restored"
    else:
        verdict = "inconclusive"
    target = ""
    for row in rows:
        found = ((row.get("match") or {}).get("original") or {}).get("target")
        if found:
            target = found
            break
    return {"verdict": verdict, "target": target, "changed": f"{len(changed)}/{len(applied)}",
            "restored": f"{len(restored)}/{len(changed)}" if changed else "0/0",
            "skipped": skipped, "seeds": rows}


def _mode(values):
    counts = Counter(values)
    best = max(counts.values())
    modes = [value for value, count in counts.items() if count == best]
    modes.sort(key=repr)
    return modes[0], best


def _status(original, perturbed, corrected):
    """restored / not_restored / no_stable_change / inconclusive, plus agreement counts."""
    n = len(original)
    mode, agree = _mode(original)
    p_mode, p_agree = _mode(perturbed)
    c_mode, c_agree = _mode(corrected)
    p_match = sum(value == mode for value in perturbed)
    c_match = sum(value == mode for value in corrected)
    counts = {"original": f"{agree}/{n}", "perturbed": f"{p_match}/{n}", "corrected": f"{c_match}/{n}"}
    if agree * 2 <= n or p_agree * 2 <= n:
        return "inconclusive", counts
    if p_mode == mode:
        return "no_stable_change", counts
    if c_mode == mode and c_agree * 2 > n:
        return "restored", counts
    return "not_restored", counts


def _explains(game, advice):
    if game == "restored" and advice == "restored":
        return "both"
    if game == "restored":
        return "game"
    if advice == "restored":
        return "advice"
    if "inconclusive" in (game, advice):
        return "inconclusive"
    if game == "no_stable_change" and advice == "no_stable_change":
        return "no_stable_change"
    return "neither"


def run_pair(pair, ref_claims, pert_claims, aliases, cfg, build_fn, solve_fn=None, case=None,
             ref_focus=None, pert_focus=None, ref_build=None, pert_build=None, repeats=3, seed=0):
    """Repeat the downstream call `repeats` times on original, perturbed, and corrected inputs.

    `build_fn(facts, seed)` is the game builder (and its solver). `solve_fn(build)` re-solves a
    game after a game-level repair, without another builder call. Seeds are shared across the
    three conditions.
    """
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    ref_diff = ref_claims if ref_focus is None else ref_focus
    pert_diff = pert_claims if pert_focus is None else pert_focus
    focus_ids = {c.get("id") for c in ref_diff + pert_diff}
    found = first_divergence(ref_diff, pert_diff, aliases, cfg, ref_build, pert_build, focus_ids)
    cached = None
    if found["edit"] is None and ref_build is None:
        cached = (build_fn(_face(ref_claims, case), seed), build_fn(_face(pert_claims, case), seed))
        found = first_divergence(ref_diff, pert_diff, aliases, cfg, cached[0], cached[1], focus_ids)
    result = {
        "id": pair.get("id"), "case": pair.get("case"), "passage": pair.get("passage"),
        "strategy": pair.get("strategy"), "propagation": pair.get("propagation"),
        "field": found["field"], "locus": found["locus"], "edit": public_edit(found["edit"]),
    }
    if found["edit"] is None:
        result.update(game="not_applicable", advice="not_applicable", explains="no_listed_field", samples=[])
        return result

    step = compare.REPLICATE_SEED_STEP
    builds, samples = [], []
    if found["locus"] == "extraction":
        corrected = correct_claims(pert_claims, found["edit"])
        faced = {"original": _face(ref_claims, case), "perturbed": _face(pert_claims, case), "corrected": _face(corrected, case)}
        for r in range(repeats):
            s = seed + step * r
            for role in ("original", "perturbed", "corrected"):
                builds.append(build_fn(faced[role], s))
            samples.append({"repeat": r, "seed": s, "corrected": "applied"})
    else:
        for r in range(repeats):
            s = seed + step * r
            if r == 0 and cached is not None:
                original, perturbed = cached
            else:
                original = build_fn(_face(ref_claims, case), s)
                perturbed = build_fn(_face(pert_claims, case), s)
            repaired, status = apply_game_edit(perturbed, found["edit"], cfg)
            if status == "applied":
                if solve_fn is None:
                    raise ValueError("a game-level correction needs solve_fn so the repaired game is re-solved")
                try:
                    repaired = solve_fn(repaired)
                except ValueError as exc:
                    status = "solver_rejected"
                    repaired = perturbed
                    samples.append({"repeat": r, "seed": s, "corrected": status, "error": str(exc)})
                    builds.extend([original, perturbed, repaired])
                    continue
            samples.append({"repeat": r, "seed": s, "corrected": status})
            builds.extend([original, perturbed, repaired])
    measured = outcomes(builds, cfg)
    original = [measured[i] for i in range(0, len(measured), 3)]
    perturbed = [measured[i] for i in range(1, len(measured), 3)]
    corrected = [measured[i] for i in range(2, len(measured), 3)]
    # Whole-game agreement is secondary, and only seeds whose edit applied are part of it.
    applied = [i for i, sample in enumerate(samples) if sample["corrected"] == "applied"]
    decision = score_decisions(builds, samples, _scoring_edit(found["edit"], pert_claims), cfg)
    if not applied:
        game = advice = explains = "not_applied"
        counts = {"game": {}, "advice": {}}
    else:
        game, g_counts = _status([original[i]["game"] for i in applied], [perturbed[i]["game"] for i in applied], [corrected[i]["game"] for i in applied])
        advice, a_counts = _status([original[i]["advice"] for i in applied], [perturbed[i]["advice"] for i in applied], [corrected[i]["advice"] for i in applied])
        explains = _explains(game, advice)
        counts = {"game": g_counts, "advice": a_counts}
    result.update(decision=decision, game=game, advice=advice, explains=explains, agreement=counts, samples=samples,
                  applied=sum(s["corrected"] == "applied" for s in samples), repeats=repeats,
                  openings={"original": opening_labels(builds[0]), "perturbed": opening_labels(builds[1]),
                            "corrected": opening_labels(builds[2])} if builds else {})
    return result


def opening_labels(build):
    """Labels in the first offer, or walk away when the plan has no offer."""
    strategies = [s for s in build.get("strategies") or [] if s.get("steps")]
    if not strategies or not strategies[0]["steps"][0]:
        return ["walk away"]
    labels = {a["id"]: a.get("label") or a["id"] for a in build.get("actions") or []}
    return [labels.get(action_id, action_id) for action_id in strategies[0]["steps"][0]]


def public_edit(edit):
    """JSON-sized description of the single restored field."""
    if not edit:
        return None
    field = edit["field"]
    if field in ("omitted_action", "missing_constraint") and "claim" in edit:
        claim = edit["claim"]
        return {"field": field, "claim_id": claim.get("id"), "category": claim.get("category"),
                "text": (claim.get("text") or "")[:240]}
    if field == "omitted_action" and "action" in edit:
        return {"field": field, "label": edit["action"].get("label"), "owner": edit["action"].get("owner"),
                "goal_labels": list(edit.get("goal_labels") or [])}
    if field == "missing_condition":
        return {"field": field, "claim_id": edit["claim_id"], "conditions": list(edit["restore_conditions"])}
    if field == "incorrect_owner" and "subject" in edit:
        return {"field": field, "claim_id": edit["claim_id"], "subject": edit["subject"]}
    keep = ("field", "action_label", "owner", "goal_label", "usValue", "opponentValue", "kind", "label", "quote")
    return {key: edit[key] for key in keep if key in edit}


def _count(text):
    """(numerator, denominator) from a 'k/n' cell. Missing cells are (0, 0)."""
    if not isinstance(text, str) or "/" not in text:
        return 0, 0
    left, right = text.split("/", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return 0, 0


def _seed_tally(row):
    """(applied seeds, seeds whose decision changed, seeds the repair put back)."""
    seeds = [s for s in (row.get("decision") or {}).get("seeds") or [] if s.get("status") == "applied"]
    if seeds:
        changed = sum(1 for s in seeds if s.get("changed"))
        return len(seeds), changed, sum(1 for s in seeds if s.get("restored"))
    decision = row.get("decision") or {}
    changed, applied = _count(decision.get("changed"))
    restored, _of_changed = _count(decision.get("restored"))
    return applied, changed, restored


def _match_tally(row):
    """(accepted, in the offer, recorded matches, cosines) across the three conditions."""
    accepted = offered = total = 0
    cosines = []
    for seed in (row.get("decision") or {}).get("seeds") or []:
        for side in (seed.get("match") or {}).values():
            if not isinstance(side, dict) or "accepted" not in side:
                continue
            total += 1
            accepted += bool(side.get("accepted"))
            offered += bool(side.get("in_opening"))
            if isinstance(side.get("cosine"), (int, float)):
                cosines.append(side["cosine"])
    return accepted, offered, total, cosines


def _stable(text):
    """True when a strict majority of the original repeats share one outcome."""
    agree, n = _count(text)
    return None if n == 0 else agree * 2 > n


def _blank():
    return {"pairs": 0, "applied": 0, "changed": 0, "restored": 0,
            "accepted": 0, "offered": 0, "matches": 0, "cosines": [],
            "game_stable": 0, "game_known": 0, "advice_stable": 0, "advice_known": 0}


def _add(bucket, row):
    applied, changed, restored = _seed_tally(row)
    accepted, offered, matches, cosines = _match_tally(row)
    agreement = row.get("agreement") or {}
    game = _stable((agreement.get("game") or {}).get("original"))
    advice = _stable((agreement.get("advice") or {}).get("original"))
    bucket["pairs"] += 1
    bucket["applied"] += applied
    bucket["changed"] += changed
    bucket["restored"] += restored
    bucket["accepted"] += accepted
    bucket["offered"] += offered
    bucket["matches"] += matches
    bucket["cosines"] += cosines
    if game is not None:
        bucket["game_known"] += 1
        bucket["game_stable"] += bool(game)
    if advice is not None:
        bucket["advice_known"] += 1
        bucket["advice_stable"] += bool(advice)


def _cell(k, n):
    return "–" if not n else f"{k}/{n} ({k / n:.0%})"


def _mean(values):
    return "–" if not values else f"{sum(values) / len(values):.2f}"


def _rate_table(title, groups):
    """One rate row per group, in the same k/n (%) form as the sentence-level report."""
    head = ("group", "pairs", "decision changed", "brought back", "original game stable",
            "original advice stable", "target accepted", "nearest in the offer", "mean cosine")
    lines = [title, "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, bucket in groups:
        lines.append("| " + " | ".join([
            name, str(bucket["pairs"]),
            _cell(bucket["changed"], bucket["applied"]),
            _cell(bucket["restored"], bucket["changed"]),
            _cell(bucket["game_stable"], bucket["game_known"]),
            _cell(bucket["advice_stable"], bucket["advice_known"]),
            _cell(bucket["accepted"], bucket["matches"]),
            _cell(bucket["offered"], bucket["matches"]),
            _mean(bucket["cosines"]),
        ]) + " |")
    return lines


def _groups(results, key, order):
    buckets = defaultdict(_blank)
    for row in results:
        _add(buckets[row.get(key) or "–"], row)
    names = [name for name in order if name in buckets]
    names += [name for name in buckets if name not in names]
    return [(name, buckets[name]) for name in names]


def markdown(results):
    """Rates by repaired field and by wording strategy, then one row per pair.

    `original game stable` and `original advice stable` are the same-text baseline: a strict
    majority of the original repeats already agreed, before any repair is credited.
    `brought back` is counted only on seeds whose decision changed.
    """
    by_field = _groups(results, "field", FIELDS)
    by_strategy = _groups(results, "strategy", ["lexical", "passive", "clause_order", "split", "register",
                                                "conditional", "nominalise", "pronoun", "doc_order"])
    total = _blank()
    for row in results:
        _add(total, row)
    lines = _rate_table("By repaired field. Each rate is seeds, except the two original-stability columns, which are pairs.",
                        by_field + [("all", total)])
    lines += ["", ""]
    lines += _rate_table("By wording strategy, over the pairs selected for this experiment.", by_strategy)
    lines += ["", "Original game stable is the same-text baseline: the share of pairs whose original repeats "
              "already agreed. A repair rate above that line is the quantity the sentence-level report puts "
              "beside its original column.", ""]
    head = ("pair", "field", "locus", "propagation", "decision", "changed", "restored", "skipped",
            "game", "advice", "explains",
            "original game", "perturbed game", "corrected game", "original advice", "perturbed advice", "corrected advice")
    lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for row in results:
        agreement = row.get("agreement") or {}
        game, advice = agreement.get("game") or {}, agreement.get("advice") or {}
        decision = row.get("decision") or {}
        cells = [row.get("id") or "", row.get("field") or "–", row.get("locus") or "–", row.get("propagation") or "–",
                 decision.get("verdict") or "–", decision.get("changed") or "–", decision.get("restored") or "–",
                 decision.get("skipped", "–"),
                 row.get("game") or "–", row.get("advice") or "–", row.get("explains") or "–",
                 game.get("original", "–"), game.get("perturbed", "–"), game.get("corrected", "–"),
                 advice.get("original", "–"), advice.get("perturbed", "–"), advice.get("corrected", "–")]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    stopped = [row for row in results if row.get("propagation") == "stopped"]
    lines += ["",
              f"Pairs: {len(results)}. Decision changed {_cell(total['changed'], total['applied'])}, "
              f"brought back {_cell(total['restored'], total['changed'])}. "
              f"Original game stable {_cell(total['game_stable'], total['game_known'])}, "
              f"original advice stable {_cell(total['advice_stable'], total['advice_known'])}.",
              f"Game changed while the recommendation did not: {len(stopped)}.",
              ""]
    for row in results:
        openings = row.get("openings") or {}
        decision = row.get("decision") or {}
        if not openings and not decision:
            continue
        lines.append(f"- `{row.get('id')}`: {row.get('field')} at {row.get('locus')} → "
                     f"decision {decision.get('verdict', '–')} ({decision.get('restored', '–')} brought back). "
                     f"Whole outcome {row.get('explains')}. "
                     f"Opening original: {_join(openings.get('original'))}. "
                     f"Perturbed: {_join(openings.get('perturbed'))}. "
                     f"Corrected: {_join(openings.get('corrected'))}.")
    return "\n".join(lines) + "\n"


def _join(labels):
    return "; ".join(labels or []) or "–"
