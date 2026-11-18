"""Run the whole tool on each simulation pack and benchmark it.

    python scripts/benchmark_sims.py --out runs/benchmark-<date>                 # plan only
    python scripts/benchmark_sims.py --out runs/benchmark-<date> --yes --cap 30  # paid run

Per pack: source intake (extraction + case synthesis), baseline game and plan,
fact-order shuffles (free), the app's fact-level rewording job, the random-noise
control (B4) put through the same builder (free), and the app's document-level
job with its same-text controls. Gateway spend is read from the quota endpoint
between stages; the run stops before a stage once spend passes --cap.
"""

import argparse
import copy
import json
import random
import re
import sys
import time
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os  # noqa: E402

import yaml  # noqa: E402


def use_builder(ref: str, folder: Path) -> None:
    """Import game_builder.py and solver.py as they are at git ref, ahead of the working tree's."""
    import subprocess
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("game_builder.py", "solver.py"):
        (folder / name).write_text(subprocess.run(["git", "show", f"{ref}:{name}"], cwd=ROOT, check=True,
                                                  capture_output=True, text=True).stdout)
    sys.path.insert(0, str(folder))


if "--builder-ref" in sys.argv:
    _ref = sys.argv[sys.argv.index("--builder-ref") + 1]
    _out = Path(sys.argv[sys.argv.index("--out") + 1])
    use_builder(_ref, _out / "builder")

from backend.engines import PeerEngines, build_peer_game, game_signature, plan_signature  # noqa: E402
from backend.inference import AnalysisService, load_env  # noqa: E402

DATABASE = ROOT / ".data" / "analysis.sqlite"
PACKS = ROOT / "data" / "packs"
SHUFFLES = 20


# ---------- packs ----------

def docx_text(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode()
    paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    lines = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in paragraphs]
    text = "\n".join(line for line in lines if line.strip())
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")


def source(i, title, text, category):
    return {"id": f"source-{i:02d}", "title": title, "category": category,
            "visibility": "private" if category != "shared" else "shared", "text": text}


def sim1():
    # The PDFs' text as extracted for the Sim 1 rewording benchmark. No role card exists.
    folder = ROOT.parent / "build" / "extracted"
    sources = [source(i, p.stem, p.read_text(), "shared") for i, p in enumerate(sorted(folder.glob("*.txt")))]
    return {"id": "sim1", "title": "Simulation 1", "sources": sources,
            "parties": {"us": "Health for All", "opponent": "Tribal leaders"}}


def sim2():
    paths = [p for p in sorted((PACKS / "sim2").glob("*.docx"))]
    category = lambda p: "role_card" if p.stem.lower().startswith("rolecard") else "specific" if "Brother" in p.stem else "shared"
    sources = [source(i, p.stem, docx_text(p), category(p)) for i, p in enumerate(paths)]
    return {"id": "sim2", "title": "Simulation 2", "sources": [s for s in sources if s["text"].strip()],
            "parties": {"us": "Camp Commander", "opponent": "Food Without Borders"}}


def qiso():
    # The live-test workspace: its extraction is cached in the app database.
    package = json.loads((ROOT / "data" / "negotiation-workspace.json").read_text())["package"]
    keep = ("id", "title", "category", "visibility", "text", "format", "pages", "sections")
    sources = [{k: s[k] for k in keep if k in s} for s in package["sources"] if (s.get("text") or "").strip()]
    return {"id": package["id"], "title": "Simulation 3 (Qiso)", "sources": sources, "parties": package["parties"],
            "facts": package["facts"]}


# Party names use the extractor's own wording ("Camp Commander", initials CC); the builder
# treats a subject that matches neither party as a third party.
PACK_LOADERS = {"sim1": sim1, "sim2": sim2, "qiso": qiso}


# ---------- spend ----------

def remaining() -> float:
    key = os.environ["ANTHROPIC_API_KEY"]
    request = urllib.request.Request("https://apis.huit.harvard.edu/ais-bedrock-llm/apigee/quota", headers={"x-api-key": key})
    return float(json.loads(urllib.request.urlopen(request, timeout=30).read())["remaining_limit"])


class Budget:
    def __init__(self, cap):
        self.cap, self.start = cap, remaining()

    def spent(self):
        return round(self.start - remaining(), 2)

    def check(self, stage):
        spent = self.spent()
        print(f"  spend so far ${spent:.2f} (cap ${self.cap:.2f}) before {stage}", flush=True)
        if spent >= self.cap:
            raise SystemExit(f"Stopping before {stage}: spend ${spent:.2f} reached the cap.")


# ---------- stages ----------

def intake(service, pack):
    if pack.get("facts"):
        return pack, {"cached": True}
    result = service.parse({"id": pack["id"], "sources": pack["sources"], "requireDetailedBrief": True})
    case = result["caseAnalysis"]
    parties = pack.get("parties") or {"us": case.get("our_side"), "opponent": case.get("opponent")}
    package = {**pack, "facts": result["facts"], "parties": parties}
    return package, {"cached": False, "documents": len(result["documents"]), "facts": len(result["facts"]),
                     "cache": result["cache"], "our_side": case.get("our_side"), "opponent": case.get("opponent"),
                     "opening": ((case.get("brief") or {}).get("opening") or {}).get("text") if isinstance((case.get("brief") or {}).get("opening"), dict) else None}


def baseline_summary(built):
    owners = Counter(a["owner"] for a in built["actions"])
    best = built["strategies"][0] if built["strategies"] else None
    return {"facts": len(built["facts"]), "actions": len(built["actions"]), "actions_us": owners["us"],
            "actions_opponent": owners["opponent"], "goals": len(built["game"]["goals"]),
            "forbidden": len(built["game"].get("forbiddenActions", [])), "strategies": len(built["strategies"]),
            "best": best and {k: best.get(k) for k in ("title", "opening", "fallback", "worstScore", "meanScore")}}


def order_shuffles(package, base):
    out = Counter()
    for seed in range(SHUFFLES):
        shuffled = copy.deepcopy(package)
        random.Random(seed).shuffle(shuffled["facts"])
        built = build_peer_game(shuffled)
        out["game_changed"] += game_signature(built) != game_signature(base)
        out["plan_changed"] += plan_signature(built) != plan_signature(base)
    return {"shuffles": SHUFFLES, **out}


def run_job(engines, package, engine):
    job = engines.start({"package": package, "engine": engine, "factSetFrozen": True})
    while True:
        state = engines.get(job["jobId"])
        if state["status"] in ("complete", "failed", "cancelled"):
            return state
        time.sleep(5)


def outcomes(variants, condition=None):
    rows = [v for v in variants if condition is None or v.get("condition") == condition]
    return dict(Counter(v["outcome"] for v in rows))


def noise_through_builder(package, base, variants, cfg):
    """B4: for each accepted fact rewording, a meaning-unfiltered noise copy of the original
    fact at the same d_emb goes through the same builder and solver."""
    from negotiator.reword import noise
    facts = {f["id"]: f for f in package["facts"]}
    rows = []
    for i, v in enumerate(v for v in variants if v["outcome"] in ("stable", "sensitive", "changed")):
        d = json.loads(v["validation"])["d_emb"]
        nz = noise.matched(facts[v["factId"]]["text"], d, cfg["noise"]["rates"], cfg["filter"]["encoder"], cfg["seed"] + i)
        reading = copy.deepcopy(package)
        reading["facts"] = [{**f, "text": nz["text"]} if f["id"] == v["factId"] else f for f in reading["facts"]]
        built = build_peer_game(reading)
        same_game, same_plan = game_signature(built) == game_signature(base), plan_signature(built) == plan_signature(base)
        rows.append({"factId": v["factId"], "d_emb_target": d, "d_emb": nz["d_emb"], "reworded_outcome": v["outcome"],
                     "outcome": "stable" if same_game and same_plan else "sensitive" if same_plan else "changed"})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--packs", nargs="+", default=list(PACK_LOADERS))
    ap.add_argument("--cap", type=float, default=30.0, help="stop before a stage once gateway spend reaches this (USD)")
    ap.add_argument("--skip", nargs="*", default=[], choices=["fact", "doc"])
    ap.add_argument("--builder-ref", help="git ref whose game_builder.py and solver.py to use (default: working tree)")
    ap.add_argument("--yes", action="store_true", help="make the paid calls")
    args = ap.parse_args()
    load_env(ROOT / ".env")
    if os.environ.get("HUIT_PROVIDER") != "bedrock":
        sys.exit("Set HUIT_PROVIDER=bedrock in .env.")
    packs = {name: PACK_LOADERS[name]() for name in args.packs}
    for name, pack in packs.items():
        print(f"{name}: {len(pack['sources'])} sources, {'cached facts' if pack.get('facts') else 'needs intake'}")
    if not args.yes:
        print("Plan only. Add --yes to run.")
        return
    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())
    service = AnalysisService(DATABASE)
    engines = PeerEngines(service)
    budget = Budget(args.cap)
    out = Path(args.out)
    import game_builder
    summary = {"started": time.strftime("%Y-%m-%d %H:%M"), "model": service.model, "remaining_before": budget.start,
               "builder": {"ref": args.builder_ref or "working tree", "file": game_builder.__file__}, "packs": {}}
    for name, pack in packs.items():
        folder = out / name
        folder.mkdir(parents=True, exist_ok=True)
        print(f"== {name}", flush=True)
        rec = summary["packs"][name] = {}
        budget.check("intake")
        package, rec["intake"] = intake(service, pack)
        (folder / "package.json").write_text(json.dumps(package, ensure_ascii=False))
        base = build_peer_game(package)
        rec["baseline"] = baseline_summary(base)
        (folder / "baseline.json").write_text(json.dumps(base, ensure_ascii=False, indent=1))
        rec["order"] = order_shuffles(package, base)
        print(f"  baseline {rec['baseline']['actions']} actions; order {rec['order']}", flush=True)
        if "fact" not in args.skip:
            budget.check("fact-level job")
            state = run_job(engines, package, "perturbation")
            (folder / "fact_job.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
            if state["status"] == "complete":
                result = state["result"]
                accepted = [v for v in result["variants"] if v["outcome"] != "rejected"]
                levels = Counter(json.loads(v["validation"])["level"] for v in accepted)
                rec["fact_job"] = {"perturbed_facts": len(result["perturbedFacts"]),
                                   "baseline_action_facts": sum(f["baselineAction"] for f in result["perturbedFacts"]),
                                   "candidates": len(result["variants"]), "accepted": len(accepted), "levels": dict(levels),
                                   "outcomes": outcomes(result["variants"])}
                b4 = noise_through_builder(package, base, result["variants"], cfg)
                (folder / "noise_b4.json").write_text(json.dumps(b4, indent=1))
                rec["noise_b4"] = {"readings": len(b4), "outcomes": dict(Counter(r["outcome"] for r in b4))}
            else:
                rec["fact_job"] = {"status": state["status"], "error": state.get("error")}
            print(f"  fact job {rec.get('fact_job')}; B4 {rec.get('noise_b4')}", flush=True)
        if "doc" not in args.skip:
            budget.check("document-level job")
            state = run_job(engines, package, "perturbation-doc")
            (folder / "doc_job.json").write_text(json.dumps(state, ensure_ascii=False, indent=1))
            if state["status"] == "complete":
                result = state["result"]
                rec["doc_job"] = {"comparison": result.get("comparison"), "extractions": result.get("generation", {}).get("extractions"),
                                  "candidates": len(result["variants"])}
            else:
                rec["doc_job"] = {"status": state["status"], "error": state.get("error")}
            print(f"  doc job {rec['doc_job']}", flush=True)
        rec["spend_after"] = budget.spent()
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    summary["spent"] = budget.spent()
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
