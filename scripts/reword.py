"""Generate and filter rewordings.

    python scripts/reword.py --facts runs/<id>/facts.json --k 16
    python scripts/reword.py --docs ../build/extracted --limit 2

--facts: JSON list of {"id", "text"} (one atomic fact each).
--docs:  folder of .txt files, one source document each.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from negotiator.reword import engine  # noqa: E402


def load_units(args) -> list[dict]:
    if args.facts:
        return [{"id": f["id"], "text": f["text"], "kind": "fact"}
                for f in json.loads(Path(args.facts).read_text())]
    return [{"id": p.stem, "text": p.read_text(), "kind": "doc"}
            for p in sorted(Path(args.docs).glob("*.txt"))]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--facts")
    src.add_argument("--docs")
    ap.add_argument("--config", default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--k", type=int, help="override reword.k")
    ap.add_argument("--seed", type=int, help="override seed")
    ap.add_argument("--limit", type=int, help="only the first N units (pilots)")
    ap.add_argument("--out", help="output folder (default runs/reword-<time>)")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    if args.k is not None:
        cfg["reword"]["k"] = args.k
    if args.seed is not None:
        cfg["seed"] = args.seed
    units = load_units(args)[: args.limit]

    records, control = engine.run(units, cfg)

    out = Path(args.out or ROOT / "runs" / f"reword-{time.strftime('%Y%m%d-%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "units.jsonl", units)
    write_jsonl(out / "rewordings.jsonl", records)
    write_jsonl(out / "noise_control.jsonl", control)
    write_jsonl(out / "human_review_sample.jsonl",
                engine.human_sample(records, cfg["human_sample_rate"], cfg["seed"]))

    by_op = Counter(r["operator"] for r in records)
    accepted = Counter(r["operator"] for r in records if r["accepted"])
    reasons = Counter((r["operator"], r["reject_reason"]) for r in records if not r["accepted"])
    summary = {
        "config": cfg, "units": len(units),
        "per_operator": {op: {"candidates": n, "accepted": accepted[op],
                              "rejection_rate": round(1 - accepted[op] / n, 3)}
                         for op, n in by_op.items()},
        "reject_reasons": {f"{op}/{why}": n for (op, why), n in reasons.items()},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("units", "per_operator", "reject_reasons")}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
