"""Does rewording one source change the model-written brief more than re-running the same text does?

    python scripts/brief_stability.py --workspace data/negotiation-workspace.json --k 3         # plan and call cap
    python scripts/brief_stability.py --workspace data/negotiation-workspace.json --k 3 --yes   # run it
    python scripts/brief_stability.py --compare runs/brief-<time> [--judge]                      # metrics only

Readings, all varying one source (the role card unless --vary names another source id or category):
  original     replicate 0, the app's own brief (normally a cache hit)
  same-r       the source re-extracted and the case re-synthesised as independent samples (B2), r = 1..K
  reworded-i   K accepted document-level paraphrases of the source, spread over the distance levels
Same-text and reworded readings cost the same: K extractions and K syntheses each.
The brief is the structured output of AnalysisService.parse, as in the app's intake call.
"""

import argparse
import itertools
import json
import os
import random
import sqlite3
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.inference import AnalysisService, InferenceError, load_env  # noqa: E402
from negotiator import llm  # noqa: E402
from negotiator.reword.embed import embed, sentences  # noqa: E402

DATABASE = ROOT / ".data" / "analysis.sqlite"   # the app's cache: the original reading is reused
MATCH = 0.80   # cosine at which two list items count as the same item
LEVELS = ["light", "moderate", "heavy"]
GROUPS = ["same|same", "reworded|same", "reworded|reworded"]


# ---------- readings ----------

def load_package(workspace: str, vary: str):
    package = json.loads(Path(workspace).read_text())["package"]
    keep = ("id", "title", "category", "visibility", "text", "format", "pages", "sections")
    sources = [{k: s[k] for k in keep if k in s} for s in package["sources"]
               if isinstance(s.get("text"), str) and s["text"].strip()]
    target = next((s for s in sources if vary in (s["id"], s.get("category"))), None)
    if target is None:
        sys.exit(f"No source with id or category {vary!r}.")
    return {"id": package["id"], "sources": sources, "requireDetailedBrief": True}, target


def reading(package: dict, source_id: str, text: str = None, replicate: int = 0) -> dict:
    def vary(s):
        if s["id"] != source_id:
            return s
        # Reworded text has no page or section map; quotes are located in the new text only.
        s = {**s, "text": text, "pages": [], "sections": []} if text is not None else dict(s)
        return {**s, "replicate": replicate} if replicate else s
    return {**package, "sources": [vary(s) for s in package["sources"]],
            **({"replicate": replicate} if replicate else {})}


def rewordings(text: str, k: int, cfg: dict):
    """All candidate records, and k accepted ones taken in turn from each level."""
    from negotiator.reword import engine
    cfg["reword"].update(k=-(-k // len(LEVELS)) + 1, levels=LEVELS, operators=["paraphrase_doc"], reorder_k=0)
    cfg["noise"]["enabled"] = False
    records, _ = engine.run([{"id": "source", "text": text, "kind": "doc"}], cfg)
    pools = {level: [r for r in records if r["accepted"] and r["level"] == level] for level in LEVELS}
    chosen = []
    while len(chosen) < k and any(pools.values()):
        for level in LEVELS:
            if pools[level] and len(chosen) < k:
                chosen.append(pools[level].pop(0))
    return records, chosen


def fields(result: dict) -> dict:
    """The parts of the brief that are compared."""
    case = result["caseAnalysis"]
    brief = case.get("brief") or {}
    text = lambda x: ((x or {}).get("text") or "").strip()
    return {"opening": text(brief.get("opening")), "fallback": text(brief.get("fallback")),
            "objective": case.get("objective") or "", "our_side": case.get("our_side"),
            "alternatives": [text(x) for x in brief.get("alternatives", [])],
            # Red lines are compared clause by clause: the same constraints are often grouped differently.
            "red_lines": [c for x in case.get("red_lines", []) for c in sentences(x.get("text") or "")],
            "our_constraints": [text(x) for x in brief.get("our_constraints", [])],
            "issues": [i.get("title", "") for i in case.get("negotiation_issues", [])],
            "tradeoffs": [x.get("proposal", "") for x in brief.get("tradeoffs", [])],
            "facts": len(result["facts"])}


# ---------- metrics ----------

def cos(a: str, b: str, encoder: str) -> float:
    if not a or not b:
        return float(a == b)
    v = embed([a, b], encoder)
    return float(v[0] @ v[1])


def soft_jaccard(a: list, b: list, encoder: str) -> float:
    """Share of items in either list with a match (cosine >= MATCH) in the other."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    s = embed(a, encoder) @ embed(b, encoder).T
    return float(((s.max(axis=1) >= MATCH).sum() + (s.max(axis=0) >= MATCH).sum()) / (len(a) + len(b)))


def similarity(f: dict, g: dict, encoder: str) -> dict:
    out = {k: cos(f[k] or "", g[k] or "", encoder) for k in ("opening", "fallback", "objective", "our_side")}
    out.update({k: soft_jaccard(f[k], g[k], encoder)
                for k in ("alternatives", "red_lines", "our_constraints", "issues", "tradeoffs")})
    return out


def condition(tag: str) -> str:
    return "reworded" if tag.startswith("reworded") else "same"   # the original is one same-text sample


def group(a: str, b: str) -> str:
    return "|".join(sorted((condition(a), condition(b))))


def judge(briefs: dict, cfg: dict) -> dict:
    """One separate call clustering openings and fallbacks into archetypes, anonymised and shuffled."""
    items = list(briefs.items())
    random.Random(cfg["seed"]).shuffle(items)
    anon = [{"id": f"P{i + 1}", "opening": f["opening"], "fallback": f["fallback"]} for i, (_, f) in enumerate(items)]
    prompt = (ROOT / "negotiator" / "prompts" / "judge_archetypes.md").read_text().replace(
        "{briefs}", json.dumps(anon, ensure_ascii=False, indent=1))
    item = {"type": "object", "additionalProperties": False,
            "required": ["id", "opening_archetype", "opening_cluster", "fallback_archetype", "fallback_cluster"],
            "properties": {"id": {"type": "string"}, "opening_archetype": {"type": "string"},
                           "opening_cluster": {"type": "integer"}, "fallback_archetype": {"type": "string"},
                           "fallback_cluster": {"type": "integer"}}}
    schema = {"type": "object", "additionalProperties": False, "required": ["items"],
              "properties": {"items": {"type": "array", "items": item}}}
    data, meta = llm.complete_json(prompt, schema, model=cfg["llm"]["model"], base_url=cfg["llm"]["base_url"],
                                   effort=cfg["llm"]["effort"], max_tokens=cfg["llm"]["max_tokens"], seed=cfg["seed"])
    back = {f"P{i + 1}": tag for i, (tag, _) in enumerate(items)}
    labels = {back[x["id"]]: x for x in data["items"] if x["id"] in back}
    flips = {}
    for name in GROUPS:
        pairs = [(a, b) for a, b in itertools.combinations(sorted(labels), 2)
                 if group(a, b) == name]
        if pairs:
            flips[name] = {k: round(statistics.mean(labels[a][k] != labels[b][k] for a, b in pairs), 3)
                            for k in ("opening_cluster", "fallback_cluster")} | {"pairs": len(pairs)}
    return {"model": meta["model"], "prompt_hash": meta["prompt_hash"], "labels": labels, "flip_rate": flips}


def compare(out: Path, cfg: dict, with_judge: bool) -> dict:
    briefs = {p.stem: json.loads(p.read_text())["brief"] for p in sorted((out / "readings").glob("*.json"))}
    briefs = {k: v for k, v in briefs.items() if v}
    encoder = cfg["filter"]["encoder"]
    pairs, groups = {}, {g: [] for g in GROUPS}
    for a, b in itertools.combinations(sorted(briefs), 2):
        m = similarity(briefs[a], briefs[b], encoder)
        pairs[f"{a}|{b}"] = m
        groups[group(a, b)].append(m)
    summary = {g: {k: {"mean": round(statistics.mean(m[k] for m in ms), 3), "min": round(min(m[k] for m in ms), 3),
                       "n": len(ms)} for k in ms[0]} for g, ms in groups.items() if ms}
    if "same|same" in summary and "reworded|same" in summary:
        # Above 0: a reworded brief is further from the same-text briefs than they are from each other.
        summary["excess_change"] = {k: round(summary["same|same"][k]["mean"] - summary["reworded|same"][k]["mean"], 3)
                                    for k in summary["same|same"]}
    result = {"readings": sorted(briefs), "summary": summary, "pairs": pairs}
    if with_judge and len(briefs) > 1:
        result["judge"] = judge(briefs, cfg)
    (out / "comparison.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return result


# ---------- run ----------

def quota():
    """Remaining HUIT budget in dollars, or None. The key is sent, never printed."""
    key = os.environ.get("HUIT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    request = urllib.request.Request("https://apis.huit.harvard.edu/ais-bedrock-llm/apigee/quota",
                                     headers={"x-api-key": key or "", "User-Agent": "NegotiationAdvisor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return float(json.load(response)["remaining_limit"])
    except Exception:
        return None


def paid_calls(database: Path) -> int:
    gateway = sqlite3.connect(database).execute("SELECT count(*) FROM calls").fetchone()[0] if database.exists() else 0
    return gateway + len(list(llm.CACHE_DIR.glob("*.json")))   # rewording/judge calls: one cache file each


def run(args, cfg: dict) -> None:
    load_env(ROOT / ".env")
    if args.model:
        os.environ["HUIT_MODEL"] = args.model
    if os.environ.get("HUIT_PROVIDER") != "bedrock":
        sys.exit("Set HUIT_PROVIDER=bedrock in .env (the brief and rewording models then share the gateway).")
    package, source = load_package(args.workspace, args.vary)
    k, n = args.k, len(package["sources"])
    reword_calls = len(LEVELS) * ((-(-k // len(LEVELS)) + 1) if cfg["reword"].get("independent") else 1)
    cap = 4 * k + reword_calls + (1 if args.judge else 0)
    print(f"Package: {n} sources; varying {source.get('title') or source['id']} ({source.get('category')}).")
    print(f"Brief model: {os.environ.get('HUIT_MODEL')}; rewording model: {cfg['llm']['model']}.")
    print(f"Readings: original + {k} same-text + {k} reworded. New calls: at most {cap}, plus up to {n + 1} "
          f"for the original if the app has not already analysed these sources with this model.")
    if not args.yes:
        print("Nothing was sent. Add --yes to run.")
        return
    out = Path(args.out or ROOT / "runs" / f"brief-{time.strftime('%Y%m%d-%H%M%S')}")
    (out / "readings").mkdir(parents=True, exist_ok=True)
    service = AnalysisService(DATABASE)
    before, calls_before = quota(), paid_calls(DATABASE)

    def one(tag, pkg, meta=None):
        started = time.monotonic()
        try:
            result = service.parse(pkg)
            row = {"tag": tag, "condition": condition(tag), "brief": fields(result), "caseCacheHit": result["caseCacheHit"],
                   "seconds": round(time.monotonic() - started), "caseAnalysis": result["caseAnalysis"], **(meta or {})}
        except InferenceError as error:
            row = {"tag": tag, "condition": condition(tag), "brief": None, "error": str(error), **(meta or {})}
        (out / "readings" / f"{tag}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False))
        print(f"{tag}: {'failed: ' + row['error'][:200] if row.get('error') else 'ok'}", flush=True)
        return row

    one("original", reading(package, source["id"]))   # extracts any uncached shared sources once
    records, chosen = rewordings(source["text"], k, cfg)
    (out / "rewordings.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    jobs = [(f"same-{r}", reading(package, source["id"], replicate=r), None) for r in range(1, k + 1)]
    jobs += [(f"reworded-{i + 1}-{r['level']}", reading(package, source["id"], text=r["text"]),
              {"rewording": {x: r[x] for x in ("id", "level", "d_emb", "nli_fwd", "nli_bwd", "seed")}})
             for i, r in enumerate(chosen)]
    with ThreadPoolExecutor(max_workers=3) as pool:   # matches the gateway's long-prompt limit
        list(pool.map(lambda job: one(*job), jobs))
    comparison = compare(out, cfg, args.judge)
    after = quota()
    manifest = {"workspace": str(args.workspace), "source": {"id": source["id"], "category": source.get("category")},
                "k": k, "brief_model": os.environ.get("HUIT_MODEL"), "reword_model": cfg["llm"]["model"],
                "rewordings": {"candidates": len(records), "accepted": sum(r["accepted"] for r in records), "used": len(chosen)},
                "paid_calls": paid_calls(DATABASE) - calls_before,
                "quota_before": before, "quota_after": after,
                "spent_usd": round(before - after, 2) if before is not None and after is not None else None}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({"manifest": manifest, "excess_change": comparison["summary"].get("excess_change"),
                      "judge_flip_rate": comparison.get("judge", {}).get("flip_rate")}, indent=1))
    print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--workspace", help="exported workspace JSON")
    mode.add_argument("--compare", help="existing run folder: recompute the comparison only")
    ap.add_argument("--vary", default="role_card", help="source id or category to vary (default role_card)")
    ap.add_argument("--k", type=int, default=3, help="same-text and reworded readings each")
    ap.add_argument("--model", help="brief model (overrides HUIT_MODEL)")
    ap.add_argument("--judge", action="store_true", help="one extra call clustering strategy archetypes")
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--out")
    ap.add_argument("--yes", action="store_true", help="make the paid calls")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    if args.compare:
        result = compare(Path(args.compare), cfg, args.judge)
        print(json.dumps({k: result["summary"].get(k) for k in ("excess_change",)} | {"judge": result.get("judge", {}).get("flip_rate")}, indent=1))
    else:
        run(args, cfg)


if __name__ == "__main__":
    main()
