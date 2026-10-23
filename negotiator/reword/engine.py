"""Run the operators over a set of units and filter the results.

A unit is {"id", "text", "kind"} with kind "fact" (one atomic fact) or "doc"
(one source document). Accepted rewordings and the noise control come back
as separate lists and are written to separate files.
"""

import random

from negotiator.reword import filter as accept
from negotiator.reword import noise, operators
from negotiator.reword.embed import cosine


def run(units: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    rc, fc, seed = cfg["reword"], cfg["filter"], cfg["seed"]
    records, control = [], []
    for unit in units:
        for op in operators.LLM_OPERATORS[unit["kind"]]:
            if op not in rc["operators"]:
                continue
            for level in rc["levels"]:
                texts, meta = operators.reword(op, unit["text"], level, rc["k"], cfg["llm"], seed)
                for i, text in enumerate(texts):
                    rec = {
                        "id": f"{unit['id']}:{op}:{level}:{seed}:{i}",
                        "source_id": unit["id"], "kind": unit["kind"],
                        "operator": op, "level": level, "text": text,
                        **accept.check(unit["text"], text, fc),
                        **meta, "seed": seed,
                    }
                    records.append(rec)
                    if rec["accepted"]:
                        nz = noise.matched(unit["text"], rec["d_emb"], cfg["noise"]["rates"],
                                           fc["encoder"], seed + i)
                        control.append({"id": f"noise:{rec['id']}", "matched_to": rec["id"],
                                        "source_id": unit["id"], "control": True, **nz})
    if "reorder" in rc["operators"] and len(units) > 1:
        records += _reorders(units, rc["reorder_k"], fc["encoder"], seed)
    return records, control


def _reorders(units: list[dict], n: int, encoder: str, seed: int) -> list[dict]:
    """Permutations are meaning-preserving by construction; d_emb is on the joined text."""
    by_id = {u["id"]: u["text"] for u in units}
    original = "\n\n".join(by_id[u["id"]] for u in units)
    out = []
    for i, order in enumerate(operators.reorder(list(by_id), n, seed)):
        cos = cosine(original, "\n\n".join(by_id[x] for x in order), encoder)
        out.append({
            "id": f"package:reorder:-:{seed}:{i}", "source_id": "package", "kind": "package",
            "operator": "reorder", "level": None, "order": order,
            "cos": cos, "d_emb": 1 - cos, "nli_fwd": None, "nli_bwd": None,
            "hard_facts_ok": True, "accepted": True, "reject_reason": None,
            "model": None, "prompt_hash": None, "seed": seed,
        })
    return out


def human_sample(records: list[dict], rate: float, seed: int) -> list[dict]:
    """Random sample of accepted LLM rewordings for the human meaning check."""
    pool = [r for r in records if r["accepted"] and r["operator"] != "reorder"]
    if not pool:
        return []
    return random.Random(seed).sample(pool, max(1, round(rate * len(pool))))
