"""Red lines, must-haves and the bottom line on plans (negotiator/game/lines.py)."""

from negotiator.game import lines

GAME = {
    "goals": [{"id": "g1", "type": "all", "actionIds": ["a1"], "usValue": -6, "opponentValue": 5},
              {"id": "g2", "type": "all", "actionIds": ["b1"], "usValue": 8, "opponentValue": -2},
              {"id": "g3", "type": "all", "actionIds": ["a2"], "usValue": 1, "opponentValue": 1}],
    "redLines": [{"kind": "required", "actionId": "a2", "label": "z", "quote": "q", "owner": "us"},
                 {"kind": "forbidden", "actionId": "a9", "label": "never", "quote": "q", "owner": "us"}],
    "bottomLine": -5,
}


def test_within_lines():
    assert lines.crossed([["a2", "b1"], ["a1"]], GAME) == []
    assert lines.crossed([], GAME) == []          # walking away crosses nothing


def test_each_kind_of_crossing():
    assert "red-line" in lines.crossed([["a9", "a2"]], GAME)[0]
    assert "must-have" in lines.crossed([["a1", "b1"]], GAME)[0]
    # conceding a1 first leaves us at -6 < -5 before their b1 arrives
    assert "bottom line" in lines.crossed([["a1"], ["b1", "a2"]], GAME)[0]


def test_walk_away_when_every_solver_plan_crosses(monkeypatch):
    monkeypatch.setattr(lines, "solve", lambda package: {"strategies": [{"steps": [["a1"]], "opening": "x"}]})
    out = lines.solve_within_lines({"actions": [], "game": GAME}, {"us": "U", "opp": "O"})
    assert out["strategies"][0]["id"] == "plan-walk-away" and out["rejected"][0]["linesCrossed"]
