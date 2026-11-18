"""Exact offer search for games produced by game_builder.

The bounds match planner.js: at most 12 actions, 4 offers, 2 new commitments
per side, and 16 extra opponent columns. The opponent accepts an offer when
their estimated value does not fall. Our value is what the search maximizes.
"""
from game_builder import build_game


def solve(package, commitments=None):
    actions = package.get("actions") or []
    game = package.get("game") or {}
    goals = game.get("goals") or []
    if not actions or not goals:
        raise ValueError("Solver needs actions and goals.")
    if not 1 <= len(actions) <= 12:
        raise ValueError("Solver supports 1–12 actions.")
    if len(goals) > 64:
        raise ValueError("Solver supports up to 64 goals.")
    rounds = game.get("maxOffers", 3)
    cap = game.get("maxActionsPerSide", 1)
    if not isinstance(rounds, int) or not 1 <= rounds <= 4:
        raise ValueError("maxOffers must be an integer from 1 to 4.")
    if not isinstance(cap, int) or not 1 <= cap <= 2:
        raise ValueError("maxActionsPerSide must be 1 or 2.")

    index = {action["id"]: bit for bit, action in enumerate(actions)}
    total = 1 << len(actions)
    us_mask = _mask(index, [action["id"] for action in actions if action.get("owner") == "us"])
    opponent_mask = (total - 1) ^ us_mask
    forbidden = _mask(index, game.get("forbiddenActions") or [])
    start = _mask(index, commitments or [])
    goal_rows = []
    for goal in goals:
        ids = goal.get("actionIds") or []
        if goal.get("type") not in ("linear", "all") or not ids or len(set(ids)) != len(ids):
            raise ValueError("Each goal needs type linear or all and unique action ids.")
        if not all(isinstance(goal.get(key), (int, float)) for key in ("usValue", "opponentValue")):
            raise ValueError("Each goal needs finite usValue and opponentValue.")
        goal_rows.append({**goal, "mask": _mask(index, ids)})

    us_value, satisfaction = _tables(total, goal_rows, "usValue")
    models = [{"id": "baseline", "values": [goal["opponentValue"] for goal in goal_rows]}]
    for reading in game.get("opponentReadings") or []:
        if len(models) >= 17:
            raise ValueError("Solver supports up to 16 opponent readings.")
        values = reading.get("values") or {}
        models.append({"id": reading.get("id"), "values": [values[goal["id"]] for goal in goal_rows]})

    legal = []
    for add in range(1, total):
        if add & forbidden:
            continue
        if _count(add & us_mask) <= cap and _count(add & opponent_mask) <= cap:
            legal.append(add)
    additions = {state: [add for add in legal if not state & add] for state in range(total)}

    paths = []
    seen = set()
    for model in models:
        opponent_value = _column_values(total, satisfaction, model["values"])
        memo = {}

        def search(state, left, opponent_value=opponent_value, memo=memo):
            key = state * 5 + left
            if key in memo:
                return memo[key]
            best = (us_value[state], ())
            if left:
                for add in additions[state]:
                    nxt = state | add
                    if opponent_value[nxt] + 1e-9 < opponent_value[state]:
                        continue
                    rest_value, rest_path = search(nxt, left - 1)
                    candidate = (rest_value, (add,) + rest_path)
                    if _prefer(candidate, best):
                        best = candidate
            memo[key] = best
            return best

        path = search(start, rounds)[1]
        if path and path not in seen:
            seen.add(path)
            paths.append((path, model["id"]))

    low = sum(min(0, goal["usValue"]) for goal in goal_rows)
    high = sum(max(0, goal["usValue"]) for goal in goal_rows)

    def normalize(value):
        if high == low:
            return 0.0
        return max(0.0, min(1.0, (value - low) / (high - low)))

    parties = package.get("parties") or {"us": "Our side", "opponent": "Other side"}
    fallback = package.get("walkAway") or "Pause and review the outside option if the offer is rejected."
    red_lines = _red_line_text(package)
    candidates = []
    for number, (path, origin) in enumerate(paths, start=1):
        scores = [_accepted_value(path, start, satisfaction, model["values"], us_value) for model in models]
        raw_mean = sum(scores) / len(scores)
        if raw_mean + 1e-9 < us_value[start]:
            continue
        mean_score = normalize(raw_mean)
        worst_score = min(normalize(score) for score in scores)
        if worst_score > mean_score:
            worst_score = mean_score
        opening = _describe(path[0], actions, parties)
        later = [
            f"After acceptance, offer {step + 2}: {_describe(mask, actions, parties)}"
            for step, mask in enumerate(path[1:])
        ]
        assumptions = list(package["game"].get("assumptions") or [])
        candidates.append({
            "id": f"plan-{number}",
            "title": f"Option {number}",
            "opening": opening,
            "fallback": fallback,
            "actionIds": _ids(path[0], actions),
            "steps": [_ids(mask, actions) for mask in path],
            "meanScore": round(mean_score, 6),
            "worstScore": round(worst_score, 6),
            "rawMean": raw_mean,
            "rawWorst": min(scores),
            "baselineValue": us_value[start],
            "origin": origin,
            "method": "game-solver",
            "freshRescored": False,
            "redLines": red_lines,
            "assumptions": assumptions[:4],
            "ethicsFlags": ["No automated ethics review has been run. Review this option before use."],
            "branches": later + ["If rejected: pause this sequence. No commitment is added."],
        })
    candidates.sort(key=lambda item: (-item["worstScore"], -item["meanScore"]))
    strategies = candidates[:5]
    if not strategies:
        strategies = [{
            "id": "plan-walk-away",
            "title": "Walk away",
            "opening": "No improving offer under these assumptions.",
            "fallback": fallback,
            "actionIds": [],
            "steps": [],
            "assumptions": list(package["game"].get("assumptions") or [])[:4],
            "ethicsFlags": ["No automated ethics review has been run."],
            "branches": ["If the other side offers something outside this game, record it as a new issue."],
            "redLines": red_lines,
            "method": "game-solver",
            "freshRescored": False,
        }]
    return {
        "strategies": strategies,
        "report": {
            "method": "Exact bounded search over offers, with modeled accept or reject responses",
            "actionCount": len(actions),
            "offerHorizon": rounds,
            "models": len(models),
            "generatedBy": "game-solver",
        },
    }


def respond(package, commitments=None):
    """Build a game from a frontend package and solve it."""
    built = build_game(package)
    solved = solve({**package, "actions": built["actions"], "game": built["game"]}, commitments)
    return {**built, "strategies": solved["strategies"]}


def _mask(index, ids):
    mask = 0
    for action_id in ids or []:
        if action_id not in index:
            raise ValueError(f"Unknown action: {action_id}")
        mask |= 1 << index[action_id]
    return mask


def _count(mask):
    return bin(mask).count("1")


def _prefer(candidate, best):
    """Prefer a higher score. On a tie, take fewer offers, then a broader first offer."""
    if candidate[0] > best[0] + 1e-9:
        return True
    if abs(candidate[0] - best[0]) > 1e-9:
        return False
    if len(candidate[1]) != len(best[1]):
        return len(candidate[1]) < len(best[1])
    candidate_width = _count(candidate[1][0]) if candidate[1] else 0
    best_width = _count(best[1][0]) if best[1] else 0
    return candidate_width > best_width


def _satisfaction(state, goal):
    covered = _count(state & goal["mask"])
    if goal["type"] == "all":
        return 1.0 if (state & goal["mask"]) == goal["mask"] else 0.0
    return covered / len(goal["actionIds"])


def _tables(total, goals, key):
    values = [0.0] * total
    satisfaction = [None] * total
    for state in range(total):
        row = [_satisfaction(state, goal) for goal in goals]
        satisfaction[state] = row
        values[state] = sum(level * goal[key] for level, goal in zip(row, goals))
    return values, satisfaction


def _column_values(total, satisfaction, column):
    return [
        sum(level * weight for level, weight in zip(satisfaction[state], column))
        for state in range(total)
    ]


def _accepted_value(path, start, satisfaction, column, us_value):
    state = start
    for add in path:
        nxt = state | add
        delta = sum((satisfaction[nxt][i] - satisfaction[state][i]) * column[i] for i in range(len(column)))
        if delta < -1e-9:
            break
        state = nxt
    return us_value[state]


def _ids(mask, actions):
    return [action["id"] for bit, action in enumerate(actions) if mask & (1 << bit)]


def _describe(mask, actions, parties):
    parts = []
    for owner in ("us", "opponent"):
        labels = [action["label"] for bit, action in enumerate(actions) if action.get("owner") == owner and mask & (1 << bit)]
        if labels:
            parts.append(f"{parties.get(owner, owner)}: {'; '.join(labels)}")
    return " ↔ ".join(parts)


def _red_line_text(package):
    edits = package.get("caseEdits") if isinstance(package.get("caseEdits"), dict) else {}
    lines = []
    for line in edits.get("redLines") or []:
        if isinstance(line, dict) and line.get("status") == "confirmed" and isinstance(line.get("text"), str):
            lines.append(line["text"].strip())
    return lines
