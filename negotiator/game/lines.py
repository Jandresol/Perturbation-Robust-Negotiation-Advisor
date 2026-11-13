"""Our red lines and bottom line, enforced on every plan the solver returns.

A plan crosses a line if it
  - offers a red-line action (game.redLines kind "forbidden"),
  - ends without a must-have action (kind "required"), or
  - passes through an agreed state worth less to us than the bottom line (game.bottomLine, our
    BATNA). Commitments are binding, so talks can stop after any accepted offer.
Walking away crosses nothing.

The builder already leaves red-line actions out of the game, so the solver cannot offer them.
Must-haves and the bottom line are checked here, after the search: solver.py does not take them
as constraints, so a plan within the lines that ranks below its top 5 is not found. In that case
the answer is to walk away, never a plan that crosses a line.
"""

from solver import solve


def reward(state, goals, key="usValue"):
    total = 0.0
    for g in goals:
        done = sum(a in state for a in g["actionIds"])
        total += g[key] * (float(done == len(g["actionIds"])) if g["type"] == "all" else done / len(g["actionIds"]))
    return total


def crossed(steps, game):
    """Reasons this plan crosses our lines; empty if it does not."""
    if not steps:
        return []
    lines = game.get("redLines") or []
    forbidden = {r["actionId"] for r in lines if r["kind"] == "forbidden"}
    required = {r["actionId"] for r in lines if r["kind"] == "required"}
    bottom = game.get("bottomLine")
    reasons, state = [], set()
    for i, step in enumerate(steps, 1):
        if bad := set(step) & forbidden:
            reasons.append(f"offer {i} includes red-line action(s) {sorted(bad)}")
        state |= set(step)
        value = reward(state, game["goals"])
        if bottom is not None and value + 1e-9 < bottom:
            reasons.append(f"after offer {i} our value {value:g} is below the bottom line {bottom:g}")
    if missing := required - state:
        reasons.append(f"the deal leaves out must-have action(s) {sorted(missing)}")
    return reasons


def solve_within_lines(built, players):
    """solver.py strategies that cross no line; walk away if none is left. Crossing plans are
    returned separately with their reasons, for the record."""
    game = built["game"]
    result = solve({"actions": built["actions"], "game": game,
                    "parties": {"us": players["us"], "opponent": players["opp"]}})
    kept, rejected = [], []
    for s in result["strategies"]:
        reasons = crossed(s.get("steps") or [], game)
        if reasons:
            rejected.append({**s, "linesCrossed": reasons})
        else:
            kept.append(s)
    if not kept:
        kept = [{
            "id": "plan-walk-away", "title": "Walk away", "actionIds": [], "steps": [],
            "opening": "No plan found within our red lines and bottom line. Take the outside option.",
            "method": "game-solver", "linesCrossed": [],
            "redLines": [f"{r['kind']}: {r['label']} (\"{r['quote']}\")" for r in game.get("redLines") or []],
        }]
    return {"strategies": kept, "rejected": rejected}
