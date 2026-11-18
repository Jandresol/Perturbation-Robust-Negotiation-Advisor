"""Human audit of accepted rewordings (the Week 3 gate: >= 95% judged meaning-preserving).

    python scripts/audit_rewordings.py --judge NAME runs/sim2-facts runs/sim2-docs   # judge items one by one
    python scripts/audit_rewordings.py --report runs/sim2-facts runs/sim2-docs       # rates, gate, agreement

The items are each run's human_review_sample.jsonl, topped up from its accepted
rewordings to --per-cell items per (operator, level), so every cell is covered.
Judgements are appended to runs/audit/judgements.jsonl, one line per (item, judge);
quitting part-way keeps everything judged so far, and a rerun skips judged items.
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUDGEMENTS = ROOT / "runs" / "audit" / "judgements.jsonl"
GATE = 0.95
ANSWERS = {"y": "preserved", "n": "changed", "u": "unsure"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    # Not splitlines(): extracted texts can contain U+2028, which it treats as a line break.
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def items(runs: list[str], per_cell: int, seed: int) -> list[dict]:
    out = []
    for run in map(Path, runs):
        originals = {u["id"]: u["text"] for u in read_jsonl(run / "units.jsonl")}
        accepted = [r for r in read_jsonl(run / "rewordings.jsonl") if r["accepted"] and r["operator"] != "reorder"]
        chosen = {r["id"]: r for r in read_jsonl(run / "human_review_sample.jsonl")}
        cells = defaultdict(list)
        for r in accepted:
            cells[(r["operator"], r["level"])].append(r)
        rng = random.Random(seed)
        for cell in sorted(cells):
            pool = [r for r in cells[cell] if r["id"] not in chosen]
            have = sum((r["operator"], r["level"]) == cell for r in chosen.values())
            for r in rng.sample(pool, max(0, min(per_cell - have, len(pool)))):
                chosen[r["id"]] = r
        out += [{"key": f"{run.name}/{r['id']}", "run": run.name, "operator": r["operator"], "level": r["level"],
                 "original": originals.get(r["source_id"]), "text": r["text"]}
                for r in chosen.values() if originals.get(r["source_id"])]
    return out


def judge(todo: list[dict], name: str) -> None:
    done = {(j["key"], j["judge"]) for j in read_jsonl(JUDGEMENTS)}
    todo = [x for x in todo if (x["key"], name) not in done]
    JUDGEMENTS.parent.mkdir(parents=True, exist_ok=True)
    print(f"{len(todo)} items to judge. Same meaning? y = yes, n = no (meaning changed), u = unsure, q = quit.")
    for i, item in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] {item['run']} · {item['operator']} · {item['level']}")
        print(f"ORIGINAL:\n{item['original']}\n\nREWORDING:\n{item['text']}\n")
        answer = ""
        while answer not in (*ANSWERS, "q"):
            answer = input("Same meaning? [y/n/u/q] ").strip().lower()[:1]
        if answer == "q":
            return
        note = input("Note (what changed, optional): ").strip() if answer != "y" else ""
        with JUDGEMENTS.open("a") as f:
            f.write(json.dumps({"key": item["key"], "judge": name, "verdict": ANSWERS[answer], "note": note,
                                "run": item["run"], "operator": item["operator"], "level": item["level"]}) + "\n")


def report(todo: list[dict]) -> dict:
    keys = {x["key"] for x in todo}
    rows = [j for j in read_jsonl(JUDGEMENTS) if j["key"] in keys]
    cells = defaultdict(lambda: defaultdict(int))
    for j in rows:
        for cell in ("all", f"{j['operator']}/{j['level']}"):
            cells[cell][j["verdict"]] += 1
    rate = lambda c: round(c["preserved"] / (c["preserved"] + c["changed"] + c["unsure"]), 3)
    by_item = defaultdict(dict)
    for j in rows:
        by_item[j["key"]][j["judge"]] = j["verdict"]
    shared = [v for v in by_item.values() if len(v) > 1]
    overall = cells.get("all")
    return {"items": len(todo), "judged": len(by_item), "judgements": len(rows),
            "preserved_rate": {cell: rate(c) for cell, c in sorted(cells.items())},
            "gate": None if not overall else {"threshold": GATE, "passed": len(by_item) == len(todo) and rate(overall) >= GATE},
            "unsure_counts_as_not_preserved": True,
            "agreement": round(sum(len(set(v.values())) == 1 for v in shared) / len(shared), 3) if shared else None,
            "items_with_two_judges": len(shared),
            "changed_notes": [{"key": j["key"], "judge": j["judge"], "note": j["note"]} for j in rows if j["verdict"] != "preserved"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="run folders with units.jsonl and rewordings.jsonl")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--judge", help="your name; judgements are recorded per judge")
    mode.add_argument("--report", action="store_true")
    ap.add_argument("--per-cell", type=int, default=4, help="minimum items per (operator, level) per run")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    todo = items(args.runs, args.per_cell, args.seed)
    if not todo:
        sys.exit("No accepted rewordings with their originals found in these runs.")
    if args.judge:
        judge(todo, args.judge)
    print(json.dumps(report(todo), indent=1))


if __name__ == "__main__":
    main()
