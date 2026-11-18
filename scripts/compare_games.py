"""Rewording comparison on model-built games: baseline, K same-text builds, K reworded builds.

    python scripts/compare_games.py --facts runs/game-sim2/facts.jsonl \
        --rolecard runs/game-sim2-benac/Rolecard.txt --us "Camp Commander" --opp "FWB" \
        --out runs/compare-sim2

Writes builds.json (every game and plan), rewordings.jsonl (every filter record),
metrics.json, and prints the comparison. All model calls are cached, so a re-run is free.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from negotiator.game import compare  # noqa: E402

ROWS = [
    ("action_similarity", "action similarity to baseline (best-match cosine)"),
    ("goal_similarity", "goal similarity to baseline"),
    ("action_clusters", "distinct actions across builds"),
    ("g_us_l1", "our values: mean |change| on matched goals (0-1)"),
    ("top_plan_agreement", "top plan = baseline's (share)"),
    ("distinct_top_plans", "distinct top plans"),
    ("effective_top_plans", "effective number of top plans (exp entropy)"),
    ("top_plan_jaccard", "mean pairwise Jaccard distance of top plans"),
    ("top_plan_u_bar", "top plan: cross-reading score U-bar (mean)"),
    ("top_plan_worst", "top plan: worst-case score (mean)"),
    ("top_plans_crossing_lines", "top plan crosses a line on some reading (share)"),
    ("solver_plans_rejected", "solver plans rejected for crossing lines (per build)"),
    ("distinct_plans", "strategy space: distinct plans in pool"),
    ("accumulation", "  ...after 1..K builds"),
    ("best_u_bar", "best U-bar in pool"),
    ("good_plans", "good plans (U-bar >= alpha * best)"),
    ("novel_good_plans", "good plans no other condition found"),
]


def _fmt(v):
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--rolecard", required=True, help="our role card as .txt; its stem is the source id in the facts")
    ap.add_argument("--us", required=True)
    ap.add_argument("--opp", required=True)
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    facts = [json.loads(line) for line in Path(args.facts).read_text().splitlines() if line.strip()]
    card = Path(args.rolecard)
    k, n = cfg["compare"]["k"], cfg["game"]["n_runs"]
    print(f"builds: 1 baseline + {k} same-text + {k} reworded; about {10 * n + 3} builder calls each "
          f"(~{(2 * k + 1) * (10 * n + 3)} total, fewer with cache hits) + one rewording call per cited fact and level")

    builds, records = compare.run(facts, {"us": args.us, "opp": args.opp}, {"id": card.stem, "text": card.read_text()}, cfg)
    result = compare.metrics(builds, cfg)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    keep = ("condition", "replicate", "level", "factsReworded", "factsCited", "d_emb", "actions", "game",
            "strategies", "rejected", "actionCluster", "goalCluster")
    (out / "builds.json").write_text(json.dumps([{k_: b.get(k_) for k_ in keep} for b in builds], indent=2))
    (out / "rewordings.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    (out / "metrics.json").write_text(json.dumps(result, indent=2, default=list))

    accepted = sum(r["accepted"] for r in records)
    print(f"rewordings: {accepted}/{len(records)} accepted")
    for r in result["readings"]:
        extra = f" level {r['level']}, {r['factsReworded']}/{r['factsCited']} facts, d_emb {r['d_emb']:.3f}" if r["level"] else ""
        print(f"  {r['condition']:9} #{r['replicate']}: {r['actions']} actions, {r['goals']} goals, top plan {r['top_plan']}{extra}")
    st, rw = result["conditions"]["same-text"], result["conditions"]["reworded"]
    print(f"\n{'metric':55} {'same-text':>10} {'reworded':>10}")
    for key, label in ROWS:
        print(f"{label:55} {_fmt(st[key]):>10} {_fmt(rw[key]):>10}")
    print(f"\nbest U-bar over all plans {result['best_u_bar_overall']:.3f}; good plans overall {result['good_plans_overall']} "
          f"(alpha {result['alpha']}); baseline top plan U-bar {_fmt(result['baseline']['top_plan_u_bar'])}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
