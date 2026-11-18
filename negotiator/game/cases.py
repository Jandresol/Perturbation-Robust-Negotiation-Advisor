"""Case packages for the sentence-level study.

The benchmark packages lived under runs/ and were not kept. When one is missing, this writes a
package whose only document is the study passages for that case, each once, so the wording test
and experiment 2 can still load the case.
"""

import json
from pathlib import Path

PARTIES = {
    "sim1": {"us": "Health for All", "opponent": "Tribal leaders"},
    "sim2": {"us": "Camp Commander", "opponent": "Food Without Borders"},
    "qiso": {"us": "Border Authority", "opponent": "Mayor of Qiso"},
}


def package_from_passages(name: str, passages: list[dict]) -> dict:
    parties = PARTIES[name]
    texts = [p["text"] for p in passages if p["case"] == name]
    body = f"You are {parties['us']}. The other party is {parties['opponent']}.\n\n" + "\n\n".join(texts)
    return {
        "id": name,
        "title": name,
        "reconstructed": True,
        "note": "Built from the study passages. The original case package was not on disk. Each passage occurs once.",
        "parties": parties,
        "sources": [{
            "id": "source-00",
            "title": f"{name} passages",
            "category": "role_card",
            "visibility": "private",
            "text": body,
        }],
        "facts": [],
    }


def materialize(spec_path, root) -> list[Path]:
    """Write any missing package named by the sentence-test spec. Returns the paths written."""
    spec = json.loads(Path(spec_path).read_text())
    root = Path(root)
    written = []
    for name, case in spec["cases"].items():
        path = root / case["package"]
        if path.exists() or name not in PARTIES:
            continue
        passages = [p for p in spec["passages"] if p["case"] == name]
        if not passages:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(package_from_passages(name, passages), ensure_ascii=False, indent=1))
        written.append(path)
        print(f"wrote {path} from the study passages; the original case package was not on disk")
    return written
