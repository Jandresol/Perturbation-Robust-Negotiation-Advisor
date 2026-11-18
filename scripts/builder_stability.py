"""How stable is the model-built game on the same text? Several full builds, compared pairwise.

    python scripts/builder_stability.py --facts runs/game-sim2/facts.jsonl \
        --rolecard runs/game-sim2-benac/Rolecard.txt --us "Camp Commander" --opp "FWB" \
        --builds 4 --out runs/stability-sim2/<label>

Build r uses seed + 100 r, the same seeds as the comparison's baseline and same-text
builds, so the two share the model cache. Writes stability.json and prints the report.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from negotiator.game import compare  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--rolecard", required=True)
    ap.add_argument("--us", required=True)
    ap.add_argument("--opp", required=True)
    ap.add_argument("--builds", type=int, default=4)
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    facts = [json.loads(line) for line in Path(args.facts).read_text().splitlines() if line.strip()]
    card = Path(args.rolecard)
    players, rolecard = {"us": args.us, "opp": args.opp}, {"id": card.stem, "text": card.read_text()}
    builds = [{"condition": "same-text", **compare._build(facts, players, rolecard, cfg,
                                                           cfg["seed"] + compare.REPLICATE_SEED_STEP * r)}
              for r in range(args.builds)]
    report = compare.stability_report(builds, cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stability.json").write_text(json.dumps({"report": report, "game": cfg["game"]}, indent=2))
    for key, value in report.items():
        print(f"{key:20} {round(value, 3) if isinstance(value, float) else value}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
