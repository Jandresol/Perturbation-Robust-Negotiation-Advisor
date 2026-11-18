"""Experiment 2: which intermediate change causes different advice? (negotiator/game/attribution.py)

Reads a finished sentence-level run (experiment 1) and repairs one field on about ten pairs.

    # plan only: which pairs, which field, no model calls
    python scripts/experiment2.py plan --sentence-out runs/sentence-test --out runs/experiment2

    # paid: re-run the downstream builder (or only the solver, when the game is the first divergence)
    python scripts/experiment2.py run --sentence-out runs/sentence-test --out runs/experiment2 --yes --repeats 3 --cap 40

Original facts are the reference extraction already stored on the case package. Perturbed facts are
the reworded document's extraction (a cache hit when experiment 1 extracted it). Corrected facts
are that perturbed extraction with one field restored. Every repeat uses the same seed for all
three conditions.

Model calls follow HUIT_PROVIDER in .env. With openai, the yaml's Claude id is served as HUIT_MODEL.
If a case package or variants.csv is missing, the run rebuilds the case from the study passages and
writes new rewordings for the selected pairs before measuring them.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from negotiator import llm  # noqa: E402
from negotiator.game import attribution as att  # noqa: E402
from negotiator.game import compare, sentence_test as st  # noqa: E402
from negotiator.game.cases import materialize  # noqa: E402

DATABASE = ROOT / ".data" / "analysis.sqlite"


def require_key():
    provider = os.environ.get("HUIT_PROVIDER", "openai")
    key = os.environ.get("HUIT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Set HUIT_API_KEY in .env. No model request was made.")
    if provider == "bedrock" and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = key
    return key


def load_cases(spec_path, case_filter):
    materialize(spec_path, ROOT)
    spec = json.loads(Path(spec_path).read_text())
    cases, passages = {}, []
    for name, case in spec["cases"].items():
        if case_filter and name not in case_filter:
            continue
        package_path = ROOT / case["package"]
        if not package_path.exists():
            print(f"skip case {name}: {package_path} is not on disk")
            continue
        package = json.loads(package_path.read_text())
        cases[name] = {"sources": package["sources"], "facts": package["facts"], "parties": package["parties"],
                       "actors": case["actors"], "reconstructed": bool(package.get("reconstructed"))}
    for passage in spec["passages"]:
        if passage["case"] in cases:
            passages.append(passage)
    return cases, {p["id"]: p for p in passages}


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def saved_build(folder, run_id):
    path = Path(folder) / "builds" / (str(run_id).replace(":", "_") + ".json")
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    data.setdefault("actions", [])
    data.setdefault("game", {})
    data.setdefault("strategies", [])
    return data


def write_report(folder, results, pairs):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pairs.json").write_text(json.dumps(pairs, indent=1))
    (folder / "results.json").write_text(json.dumps(results, indent=1, default=str))
    text = att.markdown(results) if results else att.markdown([])
    if not results:
        text = plan_text(pairs) + "\n" + text
    (folder / "report.md").write_text(text if results else plan_text(pairs))
    return text


def plan_text(pairs):
    lines = ["| pair | field guess | locus guess | propagation | game changed | advice changed |",
             "|---|---|---|---|---|---|"]
    for row in pairs:
        lines.append(f"| {row['id']} | {row['field']} | {row['locus']} | {row['propagation']} | "
                     f"{row['game_changed']} | {row['advice_changed']} |")
    stopped = sum(row["propagation"] == "stopped" for row in pairs)
    lines.append("")
    lines.append(f"{len(pairs)} pairs selected. {stopped} changed the game while the recommendation stayed the same.")
    lines.append("Plan only. `run --yes` repeats the downstream calls.")
    return "\n".join(lines) + "\n"


def ensure_variants(path, cases, passages, pairs, cfg):
    """Write rewordings for the selected pairs when the reviewed variants file is gone."""
    path = Path(path)
    if path.exists():
        return
    from negotiator.reword import filter as meaning

    prompts = st.strategy_prompts()
    needed = []
    for pair in pairs:
        key = (pair["passage"], pair["strategy"])
        if pair["strategy"] != "doc_order" and key not in needed:
            needed.append(key)
    print(f"{path.name} is not on disk. Writing {len(needed)} new rewordings for the selected pairs.")
    written = {}
    for passage_id, strategy in needed:
        passage = passages[passage_id]
        written[(passage_id, strategy)] = st.write_variants(
            cases[passage["case"]], passage, strategy, prompts[strategy], cfg)
    rows = []
    for pair in pairs:
        passage = passages.get(pair["passage"])
        if passage is None:
            continue
        base = {"case": pair["case"], "passage": pair["passage"], "kind": passage["kind"],
                "original": passage["text"], "verified": "yes",
                "reviewer_note": "written for this run; the reviewed variants.csv was not on disk"}
        if pair["strategy"] == "doc_order":
            pos = st.POSITIONS[int(pair["index"]) - 1]
            rows.append({**base, "id": pair["id"], "strategy": "doc_order", "index": pair["index"], "position": pos,
                         "variant": passage["text"], "note": f"unchanged passage moved to the {pos} of its document"})
            continue
        res = written[(pair["passage"], pair["strategy"])]
        variants = res["variants"]
        index = int(pair["index"])
        if index < 1 or index > len(variants):
            print(f"skip {pair['id']}: model returned {len(variants)} variant(s) ({res['reason']})")
            continue
        variant = variants[index - 1]
        chk = meaning.check(passage["text"], variant, cfg["filter"])
        rows.append({**base, "id": pair["id"], "strategy": pair["strategy"], "index": pair["index"], "variant": variant,
                     "cos": round(chk["cos"], 3), "nli_fwd": round(chk["nli_fwd"], 3),
                     "nli_bwd": round(chk["nli_bwd"], 3), "hard_facts_ok": chk["hard_facts_ok"],
                     "note": f"filter flags {chk['reject_reason']}" if chk["reject_reason"] else ""})
    path.parent.mkdir(parents=True, exist_ok=True)
    st.write_rows(path, rows)
    print(f"wrote {path}: {len(rows)} variants")


def run(args, cfg, cases, passages):
    rows = read_jsonl(Path(args.sentence_out) / "runs.jsonl")
    pairs = att.select_pairs(rows, args.limit)
    if args.pairs:
        wanted = set(args.pairs)
        pairs = [row for row in pairs if row["id"] in wanted]
    from backend.inference import AnalysisService, load_env
    from negotiator.game import lines

    load_env(ROOT / ".env")
    require_key()
    model = os.environ.get("HUIT_MODEL", "gpt-4.1-mini")
    provider = os.environ.get("HUIT_PROVIDER", "openai")
    print(f"model: {model} via {provider}")
    spent = llm.spend_meter()
    ensure_variants(Path(args.sentence_out) / "variants.csv", cases, passages, pairs, cfg)
    variants = {row["id"]: row for row in st.read_rows(Path(args.sentence_out) / "variants.csv")}
    service = AnalysisService(DATABASE)

    def atomise(source):
        return service.document(source)["analysis"]["claims"]

    needed = {pair["case"] for pair in pairs}
    for name, case in cases.items():
        if name not in needed or case["facts"]:
            continue
        print(f"extracting the original documents for {name}", flush=True)
        facts = []
        for source in case["sources"]:
            facts += atomise({"id": source["id"], "text": source["text"]})
        case["facts"] = facts

    if args.repeats < 3:
        print(f"warning: {args.repeats} repeat(s) cannot separate a correction from sampling variation; 3 is the default")
    results = []
    for pair in pairs:
        if spent() >= args.cap:
            print(f"stopping: spend ${spent():.2f} reached the cap ${args.cap:.2f}")
            break
        variant = variants.get(pair["id"])
        passage = passages.get(pair["passage"])
        case = cases.get(pair["case"])
        if variant is None or passage is None or case is None:
            print(f"skip {pair['id']}: missing variant, passage, or case")
            continue
        ref_facts = case["facts"]
        ref_spans = {sid: span for sid, (_, span) in st.texts_for(case, passage, None).items()}
        pert_facts, pert_spans, changed = st.extract({"row": variant, "replicate": 0}, case, passage, atomise)
        players = {"us": case["parties"]["us"], "opp": case["parties"]["opponent"]}

        def build_fn(facts, seed, case=case, changed=changed, players=players):
            return compare._build(facts, players, st.rolecard(case, changed), cfg, seed)

        def solve_fn(built, players=players):
            solved = lines.solve_within_lines(built, players)
            return {**built, "strategies": solved["strategies"], "rejected": solved["rejected"]}

        # Saved builds belong to the original full documents. A passage-only package is a new case.
        ref_build = pert_build = None
        if not case.get("reconstructed"):
            ref_build = saved_build(args.sentence_out, f"{pair['case']}:reference")
            pert_build = saved_build(args.sentence_out, pair["id"])
        result = att.run_pair(
            pair, ref_facts, pert_facts, case["actors"], cfg, build_fn, solve_fn, case=case,
            ref_focus=st.passage_claims(ref_facts, ref_spans), pert_focus=st.passage_claims(pert_facts, pert_spans),
            ref_build=ref_build, pert_build=pert_build, repeats=args.repeats, seed=cfg["seed"])
        results.append(result)
        decision = (result.get("decision") or {}).get("verdict", result["explains"])
        print(f"  {pair['id']}: {result['field']} at {result['locus']} → decision {decision}; "
              f"whole outcome {result['explains']}; spend ${spent():.2f}", flush=True)

    text = write_report(args.out, results, pairs)
    print(text)
    print(f"spend ${spent():.2f}; wrote {args.out}")


def main():
    ap = argparse.ArgumentParser(description="Experiment 2: restore one intermediate field and re-measure advice.")
    ap.add_argument("command", choices=["plan", "run"])
    ap.add_argument("--sentence-out", default=ROOT / "runs" / "sentence-test")
    ap.add_argument("--out", default=ROOT / "runs" / "experiment2")
    ap.add_argument("--spec", default=ROOT / "configs" / "sentence_test.json")
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--pairs", nargs="*", help="restrict the run to these experiment-1 pair ids")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--repeats", type=int, default=3, help="downstream repeats; the same seeds are used for every condition")
    ap.add_argument("--cap", type=float, default=40.0, help="stop before the next pair once gateway spend passes this many USD")
    ap.add_argument("--yes", action="store_true", help="make the paid downstream calls")
    args = ap.parse_args()
    if args.command == "plan":
        args.yes = False
    cfg = yaml.safe_load(Path(args.config).read_text())
    if not args.yes:
        rows = read_jsonl(Path(args.sentence_out) / "runs.jsonl")
        pairs = att.select_pairs(rows, args.limit)
        if args.pairs:
            wanted = set(args.pairs)
            pairs = [row for row in pairs if row["id"] in wanted]
        text = plan_text(pairs)
        print(text)
        write_report(args.out, [], pairs)
        print(f"wrote {args.out}")
        return
    cases, passages = load_cases(args.spec, set(args.cases) if args.cases else None)
    run(args, cfg, cases, passages)


if __name__ == "__main__":
    main()
