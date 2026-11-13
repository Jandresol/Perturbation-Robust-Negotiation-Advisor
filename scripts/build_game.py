"""Build a commitment game from atomised facts with the model-based builder, then solve it.

    python scripts/build_game.py --facts runs/game-sim2/facts.jsonl \
        --rolecard runs/game-sim2-benac/Rolecard.txt --us "Camp Commander" --opp "FWB" \
        --out runs/game-sim2-benac

Writes game.json (actions + game in the solver.py schema), notes.json (raw runs,
merge reports, stability) and plan.json (solver.py strategies), and prints a summary.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from negotiator.game import builder  # noqa: E402
from negotiator.game import lines  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True, help="facts.jsonl (id, source, text, verified, relevance)")
    ap.add_argument("--rolecard", required=True, help="our role card as .txt; its stem is the source id in the facts")
    ap.add_argument("--us", required=True)
    ap.add_argument("--opp", required=True)
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    facts = [json.loads(line) for line in Path(args.facts).read_text().splitlines() if line.strip()]
    card = Path(args.rolecard)
    built = builder.build(facts, {"us": args.us, "opp": args.opp}, {"id": card.stem, "text": card.read_text()}, cfg)
    built["notes"]["stability"] = builder.stability(built["notes"], cfg)
    plans = lines.solve_within_lines(built, {"us": args.us, "opp": args.opp})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "game.json").write_text(json.dumps({"actions": built["actions"], "game": built["game"]}, indent=2))
    (out / "notes.json").write_text(json.dumps(built["notes"], indent=2))
    (out / "plan.json").write_text(json.dumps(plans, indent=2))

    print(f"facts used: {len(built['facts'])}; model: {cfg['game']['model']}; runs per stage: {cfg['game']['n_runs']}")
    for a in built["actions"]:
        print(f"  {a['id']} [{a['owner']}] ({a['runs']}/{cfg['game']['n_runs']} runs) {a['label']}")
    print(f"{'goal':4} {'us':>5} {'opp':>5} {'opp runs':>12}  type  requires  label")
    for goal in built["game"]["goals"]:
        readings = [r["values"][goal["id"]] for r in built["game"]["opponentReadings"]]
        print(f"{goal['id']:4} {goal['usValue']:5} {goal['opponentValue']:5} {str(readings):>12}  "
              f"{goal['type']:4}  {'+'.join(goal['actionIds'])}  {goal['label']}")
    print(f"BATNA: {built['game']['batna']}; bottom line (ours): {built['game']['bottomLine']}")
    for r in built["game"]["redLines"]:
        print(f"  {r['kind']:9} {r['actionId']} [{r['owner']}] {r['label']}\n            \"{r['quote'][:150]}\"")
    for name, report in built["notes"]["reports"].items():
        dropped = {k: v for k, v in report.items() if v}
        if dropped:
            print(f"dropped ({name}): {dropped}")
    print("stability:", {k: (round(v, 3) if v is not None else None) for k, v in built["notes"]["stability"].items()})
    for r in plans["rejected"]:
        print(f"rejected (crosses a line): {r['steps']}: {'; '.join(r['linesCrossed'])}")
    best = plans["strategies"][0]
    print(f"plan: {best['opening']} | steps {best['steps']} | mean {best.get('meanScore')} worst {best.get('worstScore')}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
