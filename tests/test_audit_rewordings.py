"""Human audit tool: sampling covers every (operator, level) cell; judgements resume and gate."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_rewordings as audit  # noqa: E402


def _run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "units.jsonl").write_text(json.dumps({"id": "u1", "text": "Staff must stay."}) + "\n")
    rows = [{"id": f"u1:paraphrase_fact:{lvl}:0:{i}", "source_id": "u1", "operator": "paraphrase_fact", "level": lvl,
             "text": f"Staff are required to stay ({lvl} {i}).", "accepted": True} for lvl in ("light", "heavy") for i in range(3)]
    (run / "rewordings.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (run / "human_review_sample.jsonl").write_text(json.dumps(rows[0]) + "\n")
    return run


def test_sample_covers_cells_and_judging_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "JUDGEMENTS", tmp_path / "judgements.jsonl")
    todo = audit.items([str(_run(tmp_path))], per_cell=2, seed=0)
    assert sorted((x["level"]) for x in todo) == ["heavy", "heavy", "light", "light"]
    assert todo[0]["original"] == "Staff must stay."
    answers = iter(["y", "n", "dropped the obligation", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    audit.judge(todo, "A")
    first = audit.report(todo)
    assert first["judged"] == 2 and first["gate"]["passed"] is False
    answers = iter(["y", "y"])
    audit.judge(todo, "A")                       # resumes with the two unjudged items
    final = audit.report(todo)
    assert final["judged"] == 4 and final["preserved_rate"]["all"] == 0.75
    assert final["changed_notes"][0]["note"] == "dropped the obligation"
