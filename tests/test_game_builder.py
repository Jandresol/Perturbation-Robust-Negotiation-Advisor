import json
import subprocess
import unittest
from pathlib import Path

from game_service import build_response
from solver import respond, solve

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / "example-package.json").read_text())


def merge(package, result):
    next_package = json.loads(json.dumps(package))
    for key in ("facts", "actions", "strategies"):
        if result.get(key) is not None:
            next_package[key] = result[key]
    if result.get("game") is not None:
        next_package["game"] = result["game"]
    return next_package


class GameBuilderTests(unittest.TestCase):
    def test_example_package_keeps_quotes_and_plans_a_trade(self):
        result = respond(EXAMPLE)
        self.assertEqual([fact["id"] for fact in result["facts"]], ["fact-1", "fact-2", "fact-3"])
        self.assertLessEqual(len(result["actions"]), 12)
        self.assertTrue(all(fact["quote"] in EXAMPLE["sources"][0]["text"] for fact in result["facts"]))
        owners = {action["owner"] for action in result["actions"]}
        self.assertEqual(owners, {"us", "opponent"})
        self.assertEqual(result["game"]["maxActionsPerSide"], 1)
        self.assertIn(result["game"]["maxOffers"], (2, 3, 4))
        self.assertTrue(result["strategies"])
        opening = result["strategies"][0]
        self.assertIn("workshop", opening["opening"].lower())
        self.assertIn("review", opening["opening"].lower())
        self.assertLessEqual(opening["worstScore"], opening["meanScore"])
        self.assertTrue(opening["steps"])

    def test_confirmed_red_line_is_forbidden(self):
        package = json.loads(json.dumps(EXAMPLE))
        package["caseEdits"] = {"redLines": [{
            "id": "red-1",
            "text": "Do not offer the workshop.",
            "status": "confirmed",
            "factIds": ["fact-1"],
        }]}
        result = respond(package)
        workshop = next(action["id"] for action in result["actions"] if action["factId"] == "fact-1")
        self.assertIn(workshop, result["game"]["forbiddenActions"])
        offered = {action_id for strategy in result["strategies"] for step in strategy["steps"] for action_id in step}
        self.assertNotIn(workshop, offered)
        self.assertEqual(result["strategies"][0]["redLines"], ["Do not offer the workshop."])

    def test_empty_facts_are_quoted_from_the_source(self):
        package = {
            "id": "upload-1",
            "title": "Upload",
            "parties": {"us": "Camp Commander", "opponent": "FWB"},
            "sources": [{
                "id": "s1",
                "title": "Brief",
                "text": "The Camp Commander can provide guard supervision. FWB can provide food deliveries. Scope still needs a written agreement.",
            }],
            "facts": [],
            "walkAway": "Continue current operations.",
        }
        result = respond(package)
        self.assertGreaterEqual(len(result["facts"]), 2)
        for fact in result["facts"]:
            self.assertIn(fact["quote"], package["sources"][0]["text"])
        self.assertEqual(result["strategies"][0]["fallback"], "Continue current operations.")

    def test_solver_matches_frontend_planner_value(self):
        built = respond(EXAMPLE)
        package = merge(EXAMPLE, built)
        ours = solve(package)["strategies"][0]
        script = r"""
const {planPackage}=require('./planner');
const pkg=JSON.parse(require('fs').readFileSync(0,'utf8'));
const best=planPackage(pkg).strategies[0];
process.stdout.write(JSON.stringify(best?best.rawMean:null));
"""
        completed = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(package),
            text=True,
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        self.assertAlmostEqual(ours["rawMean"], json.loads(completed.stdout), places=6)

    def test_service_echoes_package_id_and_validates(self):
        result = build_response({"schemaVersion": 1, "packageId": EXAMPLE["id"], "task": "prepare", "package": EXAMPLE})
        self.assertEqual(result["packageId"], "example-collaboration")
        self.assertNotIn("variants", result)
        merged = merge(EXAMPLE, result)
        script = "const M=require('./model'); const p=JSON.parse(require('fs').readFileSync(0,'utf8')); M.validate(p);"
        subprocess.run(["node", "-e", script], input=json.dumps(merged), text=True, cwd=ROOT, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
