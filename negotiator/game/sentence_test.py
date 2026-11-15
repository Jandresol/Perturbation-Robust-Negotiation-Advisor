"""Sentence-level wording test: which kinds of rewording change the extraction, the game or the advice.

Setup (configs/sentence_test.json): 12 short verbatim passages, 4 per case, covering actions, goals
and constraints. For each passage and each applicable strategy a model writes
sentence_test.variants rewordings (prompts/sentence_strategies.md); doc_order instead moves the unchanged
passage to the start or end of its document. Every variant is checked by a person before it runs.

Run: a variant replaces its passage in every document that holds it; all other documents keep
their baseline extraction. The changed document(s) are re-extracted with the app's extractor,
the game is built with the model builder and solved within our lines (compare._build). The
unchanged original is repeated the same number of times per passage, with fresh samples
(extractor replicate r, builder seed + 100 r), so a strategy's change rate can be read against
what re-running alone does.

Measures, each against the case's reference run (original text, replicate 0, base seed):
  extraction  ownership: actors (claim "subject", mapped through the case's alias list) of the
              claims whose quote lies in the passage; conditions: those claims' conditions, matched
              by embedding cosine >= tau ("lost" = a reference condition with no match)
  game        the set of aligned actions, goals with their type, and red-line actions; Jaccard
              distances; owners of the builder's actions that cite a passage claim
  advice      opening = first offer of the top plan within our lines; fallback = first offer of
              the next plan within our lines, or walking away if there is none
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

from negotiator import llm
from negotiator.game import builder, compare
from negotiator.reword.embed import embed

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
STRATEGIES = ["lexical", "passive", "clause_order", "split", "register", "conditional", "nominalise", "pronoun",
              "doc_order"]
POSITIONS = ["start", "end"]          # doc_order variants 1 and 2
WALK_AWAY = "walk away"
SPEAKER = re.compile(r"[A-Z][\w.’' -]{0,40}: ")   # "CC: " at the start of a transcript line
FIELDS = ["id", "case", "passage", "kind", "strategy", "index", "position", "original", "variant",
          "cos", "nli_fwd", "nli_bwd", "hard_facts_ok", "note", "verified", "reviewer_note"]
VARIANT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["applicable", "reason", "variants"],
                  "properties": {"applicable": {"type": "boolean"}, "reason": {"type": "string"},
                                 "variants": {"type": "array", "items": {"type": "string"}}}}


# ---------- setup ----------

def strategy_prompts():
    """{name: instruction} from the '## name' sections of sentence_strategies.md."""
    parts = re.split(r"^## (\w+)\s*$", (PROMPTS / "sentence_strategies.md").read_text(), flags=re.M)
    return {name: body.strip() for name, body in zip(parts[1::2], parts[2::2])}


def holders(case, passage):
    """Ids of the sources holding the passage; it must occur exactly once in each."""
    ids = [s["id"] for s in case["sources"] if passage["text"] in s["text"]]
    bad = [s["title"] for s in case["sources"] if s["text"].count(passage["text"]) > 1]
    if not ids or bad:
        raise ValueError(f"passage {passage['id']} must occur once per document: found in {len(ids)}, repeated in {bad}")
    return ids


def _source(case, sid):
    return next(s for s in case["sources"] if s["id"] == sid)


def write_variants(case, passage, strategy, instruction, cfg):
    """{"applicable", "reason", "variants"} for one passage and model-written strategy."""
    t = cfg["sentence_test"]
    text = _source(case, holders(case, passage)[0])["text"]
    i, n = text.index(passage["text"]), len(passage["text"])
    prompt = (PROMPTS / "sentence_variant.md").read_text()
    for key, value in {"strategy": instruction, "k": t["variants"], "passage": passage["text"],
                       "before": text[max(0, i - t["context_chars"]):i], "after": text[i + n:i + n + t["context_chars"]]}.items():
        prompt = prompt.replace("{" + key + "}", str(value))
    data, _ = llm.complete_json(prompt, VARIANT_SCHEMA, model=t["model"], base_url=cfg["llm"]["base_url"],
                                effort=t["effort"], max_tokens=cfg["llm"]["max_tokens"], seed=cfg["seed"])
    variants = []
    for v in data["variants"] if data["applicable"] else []:
        if v.strip() and v.strip() != passage["text"] and v.strip() not in variants:
            variants.append(v.strip())
    return {"applicable": bool(variants), "reason": data["reason"], "variants": variants[:t["variants"]]}


def movable(text, passage, position):
    """Whether moving the passage to this end of the document moves it at all."""
    i = text.index(passage)
    return bool(text[:i].strip()) if position == "start" else bool(text[i + len(passage):].strip())


# ---------- applying a variant ----------

def substitute(text, passage, new):
    """(text with the passage replaced, span of the new wording)."""
    if text.count(passage) != 1:
        raise ValueError("passage must occur exactly once")
    i = text.index(passage)
    return text[:i] + new + text[i + len(passage):], (i, i + len(new))


def move(text, passage, position):
    """(text with the unchanged passage moved to its own line at the start or end, span of the passage).
    A transcript speaker label ("CC: ") on the passage's line goes with it, so attribution is kept."""
    i = text.index(passage)
    start = text.rfind("\n", 0, i) + 1
    head = text[start:i]
    label = m.group(0) if (m := SPEAKER.match(head)) else ""
    before, after = text[:i], text[i + len(passage):]
    if head == label and (not after or after.startswith("\n")):     # the passage was the whole line
        before, after = text[:start], after[1:]
    elif before.endswith(" ") and (not after or after[0] in " \n"):
        before = before[:-1]
    rest = before + after
    unit = label + passage
    if position == "start":
        return unit + "\n" + rest, (len(label), len(label) + len(passage))
    rest = rest.rstrip("\n")
    return rest + "\n" + unit, (len(rest) + 1 + len(label), len(rest) + 1 + len(unit))


def texts_for(case, passage, row):
    """{source id: (text, passage span)} for every source holding the passage, after the variant."""
    out = {}
    for sid in holders(case, passage):
        text = _source(case, sid)["text"]
        if row is None:
            i = text.index(passage["text"])
            out[sid] = (text, (i, i + len(passage["text"])))
        elif row["strategy"] == "doc_order":
            out[sid] = move(text, passage["text"], row["position"])
        else:
            out[sid] = substitute(text, passage["text"], row["variant"])
    return out


# ---------- runs ----------

def verified(row):
    return str(row.get("verified", "")).strip().lower() in ("yes", "y", "true", "1")


def read_rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in FIELDS} for r in rows])


def plan(passages, rows, cfg):
    """One reference run per case, `variants` original repeats per passage, and one run per
    verified variant. Variant i uses builder seed + 100 i, like original repeat i."""
    seed, step, k = cfg["seed"], compare.REPLICATE_SEED_STEP, cfg["sentence_test"]["variants"]
    runs = [{"id": f"{c}:reference", "case": c, "passage": None, "kind": None, "strategy": "reference", "index": 0,
             "replicate": 0, "seed": seed, "row": None} for c in dict.fromkeys(p["case"] for p in passages)]
    for p in passages:
        base = {"case": p["case"], "passage": p["id"], "kind": p["kind"]}
        runs += [{"id": f"{p['id']}:original:{r}", **base, "strategy": "original", "index": r, "replicate": r,
                  "seed": seed + step * r, "row": None} for r in range(1, k + 1)]
        for row in rows:
            if row["passage"] == p["id"] and row["variant"] and verified(row):
                i = int(row["index"])
                runs.append({"id": row["id"], **base, "strategy": row["strategy"], "index": i, "replicate": 0,
                             "seed": seed + step * i, "row": row})
    return runs


def run_key(run, case, passage):
    """Runs with the same inputs give the same output (original repeats of passages in one document)."""
    texts = texts_for(case, passage, run["row"]) if passage else {}
    changed = tuple(sorted((sid, text) for sid, (text, _) in texts.items()))
    return run["case"], changed, run["replicate"], run["seed"]


def extract(run, case, passage, atomise):
    """(facts of the whole case, {source id: passage span}, {source id: changed text}).
    atomise(source) returns the app extractor's claims for one source (with quoteStart/quoteEnd)."""
    if passage is None:
        return case["facts"], {}, {}
    changed = texts_for(case, passage, run["row"])
    new = []
    for sid, (text, _) in changed.items():
        new += [{**c, "sourceId": sid} for c in atomise({"id": sid, "text": text, "replicate": run["replicate"]})]
    facts = [f for f in case["facts"] if f["sourceId"] not in changed] + new
    return facts, {sid: span for sid, (_, span) in changed.items()}, {sid: text for sid, (text, _) in changed.items()}


def passage_claims(facts, spans):
    return [f for f in facts if f["sourceId"] in spans
            and f["quoteStart"] < spans[f["sourceId"]][1] and f["quoteEnd"] > spans[f["sourceId"]][0]]


def builder_facts(facts, case):
    """App claims in the model builder's fact format. The builder reads only the text, so a
    condition the extractor kept in its own field (and not in the text) is appended."""
    title = {s["id"]: s["title"] for s in case["sources"]}
    out = []
    for f in facts:
        text = f["text"]
        extra = [c for c in f.get("conditions") or [] if builder.normalise(c) not in builder.normalise(text)]
        if extra:
            text += " Conditions: " + "; ".join(extra) + "."
        out.append({"id": f["id"], "source": title[f["sourceId"]], "text": text, "verified": True})
    return out


def rolecard(case, changed):
    card = next((s for s in case["sources"] if s["category"] == "role_card"), None)
    if card is None:
        return {"id": "no role card", "text": ""}
    return {"id": card["title"], "text": changed.get(card["id"], card["text"])}


def build(facts, case, changed, cfg, seed):
    players = {"us": case["parties"]["us"], "opp": case["parties"]["opponent"]}
    return compare._build(builder_facts(facts, case), players, rolecard(case, changed), cfg, seed)


# ---------- measures ----------

def actors(subject, aliases):
    s = (subject or "").lower()
    found = {name for name, words in aliases.items() if any(re.search(rf"\b{re.escape(w)}\b", s) for w in words)}
    return found or {builder.normalise(subject or "")}


def unmatched(a, b, encoder, tau):
    """Items of a with no item of b at cosine >= tau."""
    if not a or not b:
        return list(a)
    sims = embed(a, encoder) @ embed(b, encoder).T
    return [x for x, row in zip(a, sims) if row.max() < tau]


def extraction_measures(ref, claims, aliases, cfg):
    enc, tau = cfg["filter"]["encoder"], cfg["sentence_test"]["tau"]
    owners = set().union(*(actors(f.get("subject"), aliases) for f in claims)) if claims else set()
    ref_owners = set().union(*(actors(f.get("subject"), aliases) for f in ref)) if ref else set()
    conds = [c for f in claims for c in f.get("conditions") or []]
    ref_conds = [c for f in ref for c in f.get("conditions") or []]
    lost, added = unmatched(ref_conds, conds, enc, tau), unmatched(conds, ref_conds, enc, tau)
    return {"claims": len(claims), "owners": sorted(owners), "conditions": conds, "lost": lost, "added": added,
            "ownership_changed": owners != ref_owners, "conditions_lost": bool(lost),
            "conditions_changed": bool(lost or added), "extraction_changed": owners != ref_owners or bool(lost or added)}


def signature(b):
    return (frozenset(b["actionCluster"].values()),
            frozenset((b["goalCluster"][g["id"]], g["type"]) for g in b["game"]["goals"]),
            frozenset(b["lines"]["forbidden"]))


def advice(b):
    """(opening, fallback) as sets of aligned action clusters, or WALK_AWAY."""
    kept = [s for s in b["strategies"] if s.get("steps")]
    first = [frozenset(b["actionCluster"][a] for a in s["steps"][0]) for s in kept[:2]]
    return (first[0] if first else WALK_AWAY), (first[1] if len(first) > 1 else WALK_AWAY)


def game_measures(ref, b, ref_ids, ids):
    """ref and b are aligned builds (compare.align); *_ids are their passage claim ids."""
    sig, rsig = signature(b), signature(ref)
    owners = {a["owner"] for a in b["actions"] if set(a["factIds"]) & ids}
    ref_owners = {a["owner"] for a in ref["actions"] if set(a["factIds"]) & ref_ids}
    (op, fb), (rop, rfb) = advice(b), advice(ref)
    return {"game_changed": sig != rsig,
            "action_distance": compare._jaccard_distance(sig[0], rsig[0]),
            "goal_distance": compare._jaccard_distance({g for g, _ in sig[1]}, {g for g, _ in rsig[1]}),
            "builder_owners": sorted(owners), "builder_ownership_changed": owners != ref_owners,
            "opening": sorted(op) if op != WALK_AWAY else WALK_AWAY,
            "opening_changed": op != rop, "fallback_changed": fb != rfb, "advice_changed": op != rop or fb != rfb}


# ---------- report ----------

HEADLINE = [("extraction_changed", "ownership or conditions"), ("game_changed", "inferred game"),
            ("advice_changed", "opening or fallback")]
DETAIL = ["ownership_changed", "conditions_changed", "conditions_lost", "builder_ownership_changed",
          "opening_changed", "fallback_changed"]
DISTANCES = ["action_distance", "goal_distance"]


def _rate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return {"k": sum(bool(v) for v in vals), "n": len(vals), "rate": sum(bool(v) for v in vals) / len(vals) if vals else None}


def _mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def report(rows):
    """Per strategy: share of runs that change each measure, beside the original repeats of the
    same passages (so a strategy that applies to few passages is compared like with like)."""
    by = defaultdict(list)
    for r in rows:
        by[r["strategy"]].append(r)
    out = {}
    for s in ["original"] + [x for x in STRATEGIES if x in by]:
        runs = by.get(s, [])
        passages = {r["passage"] for r in runs}
        base = [r for r in by.get("original", []) if r["passage"] in passages]
        out[s] = {"runs": len(runs), "passages": len(passages), "original_runs": len(base),
                  **{key: _rate(runs, key) for key, _ in HEADLINE + [(d, d) for d in DETAIL]},
                  **{f"original_{key}": _rate(base, key) for key, _ in HEADLINE + [(d, d) for d in DETAIL]},
                  **{key: _mean(runs, key) for key in DISTANCES},
                  **{f"original_{key}": _mean(base, key) for key in DISTANCES}}
    return out


def _cell(rate):
    return "–" if rate["rate"] is None else f"{rate['k']}/{rate['n']} ({rate['rate']:.0%})"


def markdown(rep):
    """Headline table: share of runs changed, variant vs original repeats of the same passages."""
    head = "| strategy | passages | " + " | ".join(f"{label}: variant | original" for _, label in HEADLINE) + " |"
    lines = [head, "|" + "---|" * (2 + 2 * len(HEADLINE))]
    for s, r in rep.items():
        cells = [_cell(r[k]) + " | " + ("" if s == "original" else _cell(r[f"original_{k}"])) for k, _ in HEADLINE]
        lines.append(f"| {s} | {r['passages']} | " + " | ".join(cells) + " |")
    lines += ["", "| strategy | " + " | ".join(DETAIL + DISTANCES) + " |", "|" + "---|" * (1 + len(DETAIL) + len(DISTANCES))]
    for s, r in rep.items():
        dist = ["–" if r[d] is None else f"{r[d]:.2f}" for d in DISTANCES]
        lines.append(f"| {s} | " + " | ".join([_cell(r[d]) for d in DETAIL] + dist) + " |")
    return "\n".join(lines) + "\n"
