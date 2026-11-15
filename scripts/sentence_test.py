"""Sentence-level wording test (negotiator/game/sentence_test.py; passages in configs/sentence_test.json).

    # 1. write the variants: one model call per passage and strategy, pre-screened by the meaning filter
    python scripts/sentence_test.py variants --out runs/sentence-test          # plan only
    python scripts/sentence_test.py variants --out runs/sentence-test --yes
    # 2. a person fills the "verified" column of runs/sentence-test/variants.csv with yes or no
    # 3. run: extraction only (one extractor call per changed document), then the full build
    python scripts/sentence_test.py run --out runs/sentence-test --stage extract --yes
    python scripts/sentence_test.py run --out runs/sentence-test --stage build --yes --cap 50

`run` writes runs.jsonl (one row per run with its measures), report.json, report.md and, for the
build stage, builds/<run>.json. Only verified variants run. All model calls are cached, so a
re-run is free; --cap stops before the next build once gateway spend passes it (USD).
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from negotiator.game import compare  # noqa: E402
from negotiator.game import sentence_test as st  # noqa: E402

QUOTA = "https://apis.huit.harvard.edu/ais-bedrock-llm/apigee/quota"
DATABASE = ROOT / ".data" / "analysis.sqlite"
BUILD_COST = 3.5      # USD per build, rough: the Sim 2 rewording comparison
EXTRACT_COST = 0.15   # USD per document extraction, rough


def remaining():
    request = urllib.request.Request(QUOTA, headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"]})
    return float(json.loads(urllib.request.urlopen(request, timeout=30).read())["remaining_limit"])


def load(path, case_filter, passage_filter):
    spec = json.loads(Path(path).read_text())
    cases = {}
    for name, c in spec["cases"].items():
        pkg = json.loads((ROOT / c["package"]).read_text())
        cases[name] = {"sources": pkg["sources"], "facts": pkg["facts"], "parties": pkg["parties"], "actors": c["actors"]}
    passages = [p for p in spec["passages"] if (not case_filter or p["case"] in case_filter)
                and (not passage_filter or p["id"] in passage_filter)]
    for p in passages:
        st.holders(cases[p["case"]], p)     # each passage occurs once in each document holding it
    return cases, passages


def variants(args, cfg, cases, passages):
    from negotiator.reword import filter as meaning
    prompts = st.strategy_prompts()
    jobs = [(p, s) for p in passages for s in st.STRATEGIES if s != "doc_order"]
    print(f"{len(jobs)} variant calls ({len(passages)} passages x {len(jobs) // max(1, len(passages))} strategies, "
          f"{cfg['sentence_test']['variants']} variants each); doc_order needs none")
    path = Path(args.out) / "variants.csv"
    if not args.yes:
        print("Plan only. Add --yes to write the variants.")
        return
    if path.exists() and not args.force:
        sys.exit(f"{path} exists and holds the review; pass --force to overwrite it.")
    with ThreadPoolExecutor(max_workers=cfg["game"]["parallel"]) as pool:
        results = list(pool.map(lambda j: st.write_variants(cases[j[0]["case"]], j[0], j[1], prompts[j[1]], cfg), jobs))
    by_job = {(p["id"], s): r for (p, s), r in zip(jobs, results)}
    rows = []
    for p in passages:
        base = {"case": p["case"], "passage": p["id"], "kind": p["kind"], "original": p["text"]}
        for s in st.STRATEGIES:
            if s == "doc_order":
                text = st._source(cases[p["case"]], st.holders(cases[p["case"]], p)[0])["text"]
                for i, pos in enumerate(st.POSITIONS, 1):
                    if st.movable(text, p["text"], pos):
                        rows.append({**base, "id": f"{p['id']}:{s}:{i}", "strategy": s, "index": i, "position": pos,
                                     "variant": p["text"], "note": f"unchanged passage moved to the {pos} of its document"})
                continue
            res = by_job[(p["id"], s)]
            if not res["variants"]:
                rows.append({**base, "id": f"{p['id']}:{s}:0", "strategy": s, "index": 0,
                             "note": f"not applicable: {res['reason']}"})
            for i, v in enumerate(res["variants"], 1):
                chk = meaning.check(p["text"], v, cfg["filter"])
                rows.append({**base, "id": f"{p['id']}:{s}:{i}", "strategy": s, "index": i, "variant": v,
                             "cos": round(chk["cos"], 3), "nli_fwd": round(chk["nli_fwd"], 3),
                             "nli_bwd": round(chk["nli_bwd"], 3), "hard_facts_ok": chk["hard_facts_ok"],
                             "note": f"filter flags {chk['reject_reason']}" if chk["reject_reason"] else ""})
    path.parent.mkdir(parents=True, exist_ok=True)
    st.write_rows(path, rows)
    usable = [r for r in rows if r.get("variant")]
    print(f"wrote {path}: {len(usable)} variants to review "
          f"({Counter(r['strategy'] for r in usable)}); {len(rows) - len(usable)} not applicable")


def build_order(distinct):
    """References, then original repeats, then variants round-robin over strategies (one passage of
    each strategy in turn), so a spending cap leaves every strategy with some builds."""
    items = list(distinct.items())
    first = [x for x in items if x[1]["strategy"] in ("reference", "original")]
    first.sort(key=lambda x: x[1]["strategy"] != "reference")
    queues = [[x for x in items if x[1]["strategy"] == s] for s in st.STRATEGIES]
    rest = [q[i] for i in range(max(map(len, queues), default=0)) for q in queues if i < len(q)]
    return first + rest


def run(args, cfg, cases, passages):
    rows = st.read_rows(Path(args.out) / "variants.csv")
    if args.strategies:
        rows = [r for r in rows if r["strategy"] in args.strategies]
    if args.index:
        # Run only variant `index` of each strategy, without waiting for the review; the original
        # is then repeated once per passage, so both sides keep an equal number of runs.
        rows = [{**r, "verified": "yes"} for r in rows if r["index"] == str(args.index)]
        cfg["sentence_test"]["variants"] = 1
        print(f"running variant {args.index} of each strategy, reviewed or not")
    runs = st.plan(passages, rows, cfg)
    if args.strategies:
        runs = [r for r in runs if r["strategy"] in ("reference", "original", *args.strategies)]
    by_id = {p["id"]: p for p in passages}
    key = {r["id"]: st.run_key(r, cases[r["case"]], by_id.get(r["passage"])) for r in runs}
    distinct = {}
    for r in runs:
        distinct.setdefault(key[r["id"]], r)
    n_extract = sum(len(st.holders(cases[r["case"]], by_id[r["passage"]])) for r in distinct.values() if r["passage"])
    n_build = len(distinct) if args.stage == "build" else 0
    unreviewed = [r for r in rows if r.get("variant") and not r.get("verified", "").strip()]
    print(f"runs: {dict(Counter(r['strategy'] for r in runs))}")
    print(f"distinct inputs {len(distinct)}: {n_extract} extractor calls, {n_build} builds "
          f"(rough cost ${n_extract * EXTRACT_COST + n_build * BUILD_COST:.0f} before cache hits)")
    if unreviewed:
        print(f"{len(unreviewed)} variants are not reviewed yet and will not run")
    if not args.yes:
        print("Plan only. Add --yes to run.")
        return

    from backend.inference import AnalysisService, load_env
    load_env(ROOT / ".env")
    service = AnalysisService(DATABASE)
    start = remaining()

    def spent():
        return start - remaining()

    def atomise(source):
        return service.document(source)["analysis"]["claims"]

    with ThreadPoolExecutor(max_workers=cfg["game"]["parallel"]) as pool:
        extracted = dict(zip(distinct, pool.map(
            lambda r: st.extract(r, cases[r["case"]], by_id.get(r["passage"]), atomise), distinct.values())))
    print(f"extraction done; spend ${spent():.2f}", flush=True)

    builds = {}
    if args.stage == "build":
        folder = Path(args.out) / "builds"
        folder.mkdir(parents=True, exist_ok=True)
        for k, r in build_order(distinct):
            if spent() >= args.cap:
                print(f"stopping: spend ${spent():.2f} reached the cap ${args.cap:.2f}; {len(builds)} builds done")
                break
            facts, _, changed = extracted[k]
            builds[k] = st.build(facts, cases[r["case"]], changed, cfg, r["seed"])
            (folder / (r["id"].replace(":", "_") + ".json")).write_text(json.dumps(
                {x: builds[k][x] for x in ("actions", "game", "strategies", "rejected")}, indent=1))
            print(f"  built {r['id']}; spend ${spent():.2f}", flush=True)
        for c in cases:
            compare.align([b for k, b in builds.items() if k[0] == c], cfg)

    def spans(case, p, row):
        return {sid: span for sid, (_, span) in st.texts_for(case, p, row).items()}

    out = []
    for r in runs:
        if r["passage"] is None:
            continue
        case, p = cases[r["case"]], by_id[r["passage"]]
        facts = extracted[key[r["id"]]][0]
        claims = st.passage_claims(facts, spans(case, p, r["row"]))
        ref_claims = st.passage_claims(case["facts"], spans(case, p, None))
        row = {k: r[k] for k in ("id", "case", "passage", "kind", "strategy", "index")}
        row.update(st.extraction_measures(ref_claims, claims, case["actors"], cfg))
        ref_key = key[f"{r['case']}:reference"]
        if key[r["id"]] in builds and ref_key in builds:
            row.update(st.game_measures(builds[ref_key], builds[key[r["id"]]],
                                        {f["id"] for f in ref_claims}, {f["id"] for f in claims}))
        out.append(row)

    folder = Path(args.out)
    (folder / "runs.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=list) + "\n" for x in out))
    rep = st.report(out)
    (folder / "report.json").write_text(json.dumps(rep, indent=1))
    md = st.markdown(rep)
    (folder / "report.md").write_text(md)
    print(md)
    print(f"spend ${spent():.2f}; wrote {folder}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["variants", "run"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--spec", default=ROOT / "configs" / "sentence_test.json")
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--passages", nargs="*")
    ap.add_argument("--strategies", nargs="*", choices=st.STRATEGIES)
    ap.add_argument("--stage", choices=["extract", "build"], default="extract")
    ap.add_argument("--cap", type=float, default=30.0)
    ap.add_argument("--index", type=int, help="run only this variant number of each strategy, skipping the review")
    ap.add_argument("--force", action="store_true", help="overwrite variants.csv (and its review)")
    ap.add_argument("--yes", action="store_true", help="make the paid calls")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    cases, passages = load(args.spec, args.cases, args.passages)
    (variants if args.command == "variants" else run)(args, cfg, cases, passages)


if __name__ == "__main__":
    main()
