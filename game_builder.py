"""Turn a frontend package into a commitment game planner.js can search.

Facts already on the package are kept, including their ids and verbatim quotes.
Confirmed red lines become forbidden actions. Utility numbers are role estimates:
our concession costs us and benefits them, theirs does the reverse, and a paired
package adds joint value. They are not measurements taken from a role card.
"""
import re

MAX_ACTIONS = 12
MAX_GOALS = 64
ACTION_CATEGORIES = ("commitment", "resource", "timeline")
PROHIBITION = re.compile(
    r"\b(must not|shall not|cannot|prohibited|red line|non-negotiable|not authorized|do not)\b",
    re.I,
)
# "Scope and dates need agreement from both teams" is a condition on the deal, not a move.
AGREEMENT = re.compile(r"\b(agree(?:d|ment)?|approv\w*|consent|sign[- ]off)\b", re.I)
JOINT = re.compile(r"\b(both|each|all|joint(?:ly)?|mutual(?:ly)?)\b", re.I)
# Our role card and private briefs are about our own options; read them first.
SOURCE_PRIORITY = {"role_card": 0, "specific": 1}

ASSUMPTIONS = [
    "Commitments are binding and additive.",
    "Utilities are estimates from who gives each commitment: ours costs us and benefits them, theirs does the reverse, and taking both adds joint value.",
    "The extra opponent column lowers that joint value. It is a sensitivity check, not a measured opponent type.",
    "Confirmed red lines are forbidden actions. Other constraints stay as text for the team.",
    "Facts about third parties, stated worries and joint-agreement requirements stay as evidence, not actions.",
]


def build_game(package):
    if not isinstance(package, dict):
        raise ValueError("Package must be an object.")
    parties = package.get("parties") or {}
    if not all(isinstance(parties.get(side), str) and parties[side].strip() for side in ("us", "opponent")):
        raise ValueError("Package needs parties.us and parties.opponent.")
    sources = package.get("sources") or []
    if not isinstance(sources, list) or not sources:
        raise ValueError("Package needs at least one source.")
    source_text = {source.get("id"): source.get("text") or "" for source in sources if isinstance(source, dict)}

    facts, extracted = _facts(package, sources, source_text)
    if not facts:
        raise ValueError("No source-linked facts with verbatim quotes.")
    actions, unused = _actions(facts, sources, parties)
    if not actions:
        raise ValueError("No facts could be turned into commitments. Add a claim about what a side can provide or must deliver.")
    forbidden = _forbidden(package, actions)
    goals, readings = _goals(actions, forbidden)
    game = {
        "maxOffers": 3 if len(actions) > 2 else 2,
        "maxActionsPerSide": 1,
        "goals": goals,
        "forbiddenActions": forbidden,
        "assumptions": list(ASSUMPTIONS),
        "opponentReadings": readings,
    }
    if extracted:
        game["assumptions"].append("Facts were split from source sentences because the package had no extracted facts.")
    if unused:
        game["assumptions"].append("Some facts stay as evidence and are not commitments.")
    return {"facts": facts, "actions": actions, "game": game}


def _facts(package, sources, source_text):
    incoming = package.get("facts") if isinstance(package.get("facts"), list) else []
    kept = []
    seen = set()
    for fact in incoming:
        if not isinstance(fact, dict):
            continue
        quote = fact.get("quote")
        source_id = fact.get("sourceId")
        text = fact.get("text")
        fact_id = fact.get("id")
        if not all(isinstance(value, str) and value.strip() for value in (quote, text, fact_id, source_id)):
            continue
        if quote not in source_text.get(source_id, ""):
            continue
        if fact_id in seen:
            continue
        seen.add(fact_id)
        kept.append(dict(fact))
    if kept:
        return kept, False
    extracted = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("text"), str):
            continue
        per_source = 0
        for quote in _sentences(source["text"]):
            fact_id = f"fact-{source['id']}-{per_source + 1}"
            if fact_id in seen:
                continue
            seen.add(fact_id)
            per_source += 1
            extracted.append({
                "id": fact_id,
                "sourceId": source["id"],
                "text": quote,
                "quote": quote,
                "category": _category(quote),
            })
            if len(extracted) >= 40:
                return extracted, True
    return extracted, True


def _sentences(text):
    seen = set()
    for part in re.split(r"(?<=[.!?])\s+|\n+", text.strip()):
        quote = part.strip()
        if len(quote) < 20 or quote in seen or quote not in text:
            continue
        if not re.search(r"[A-Za-z]", quote):
            continue
        seen.add(quote)
        yield quote


def _category(text):
    if PROHIBITION.search(text):
        return "constraint"
    if re.search(r"\b(if|unless|provided that|subject to|conditional|only when)\b", text, re.I):
        return "condition"
    if re.search(r"\b(deadline|before|after|schedule|deliver(?:y)?|days?|weeks?|months?)\b", text, re.I):
        return "timeline"
    if re.search(r"\b(must|shall|required|requirement|limit|maximum|minimum|at least|at most)\b", text, re.I):
        return "constraint"
    if re.search(r"\b(can provide|will provide|offer|commit|agree|responsib|undertake|deliver|supply)\b", text, re.I):
        return "commitment"
    if re.search(r"\b(goal|objective|prioriti|aim|seek|want|need|prefer)\w*", text, re.I):
        return "goal"
    if re.search(r"[\d$€£¥]|\b(budget|cost|capacity|staff|resources|funding)\b", text, re.I):
        return "resource"
    return "context"


def _actions(facts, sources, parties):
    by_id = {source.get("id"): source for source in sources if isinstance(source, dict)}
    ranked = []
    for index, fact in enumerate(facts):
        category = fact.get("category") if isinstance(fact.get("category"), str) else _category(fact["text"])
        if category == "constraint" or PROHIBITION.search(fact["text"]):
            continue
        if category not in ACTION_CATEGORIES and category != "goal":
            continue
        if fact.get("force") in ("concern", "approval_requirement") or (AGREEMENT.search(fact["text"]) and JOINT.search(fact["text"])):
            continue
        if _subject_owner(fact, parties) == "third":
            continue
        priority = SOURCE_PRIORITY.get((by_id.get(fact["sourceId"]) or {}).get("category"), len(SOURCE_PRIORITY))
        rank = ACTION_CATEGORIES.index(category) if category in ACTION_CATEGORIES else len(ACTION_CATEGORIES)
        ranked.append((priority, rank, index, fact, category))
    ranked.sort(key=lambda item: item[:3])
    chosen = [item for item in ranked if item[4] in ACTION_CATEGORIES][:MAX_ACTIONS]
    if len(chosen) < 2:
        for item in ranked:
            if item in chosen:
                continue
            chosen.append(item)
            if len(chosen) >= 2:
                break
    chosen = chosen[:MAX_ACTIONS]
    counts = {"us": 0, "opponent": 0}
    actions = []
    for _, _, _, fact, _category_name in chosen:
        owner = _owner(fact, by_id.get(fact["sourceId"]), parties, counts)
        counts[owner] += 1
        actions.append({
            "id": f"{'a' if owner == 'us' else 'b'}{counts[owner]}",
            "owner": owner,
            "label": _label(fact["text"]),
            "factId": fact["id"],
        })
    return actions, len(facts) - len(actions)


def _owner(fact, source, parties, counts):
    subject = _subject_owner(fact, parties)
    if subject in ("us", "opponent"):
        return subject
    text = fact["text"]
    us = _mentions(parties["us"], text)
    opponent = _mentions(parties["opponent"], text)
    if us and not opponent:
        return "us"
    if opponent and not us:
        return "opponent"
    private = isinstance(source, dict) and (source.get("visibility") == "private" or source.get("category") == "role_card")
    if private:
        return "us"
    return "us" if counts["us"] <= counts["opponent"] else "opponent"


def _subject_owner(fact, parties):
    """Who the extractor says the fact is about: "us", "opponent", "third", or None without a subject field.

    Party names also match their initials ("CC" for Camp Commander, "Food without
    borders" for FWB). An extracted fact with an empty subject has an unknown actor,
    so it is not a move for either side unless its text names exactly one party."""
    if "subject" not in fact:
        return None
    subject = fact["subject"]
    if not isinstance(subject, str) or not subject.strip():
        us, opponent = _mentions(parties["us"], fact["text"]), _mentions(parties["opponent"], fact["text"])
        return ("us" if us else "opponent") if us != opponent else "third"
    us, opponent = _names_party(parties["us"], subject), _names_party(parties["opponent"], subject)
    if us != opponent:
        return "us" if us else "opponent"
    return None if us else "third"


def _aliases(name):
    words = re.findall(r"[A-Za-z]+", name)
    found = {name.strip().lower()}
    if len(words) > 1:
        found.add("".join(word[0] for word in words).lower())
    return found


def _names_party(name, subject):
    party, other = _aliases(name), _aliases(subject)
    return bool(party & other) or any(
        len(alias) >= 2 and re.search(rf"\b{re.escape(alias)}\b", subject.lower()) for alias in party
    )


def _mentions(name, text):
    name = name.strip()
    if len(name) < 3:
        return False
    return name.lower() in text.lower()


def _label(text):
    label = re.sub(r"\s+", " ", text).strip()
    if len(label) > 90:
        label = label[:87].rstrip() + "..."
    return label


def _forbidden(package, actions):
    edits = package.get("caseEdits") if isinstance(package.get("caseEdits"), dict) else {}
    lines = edits.get("redLines") if isinstance(edits.get("redLines"), list) else []
    blocked = set()
    for line in lines:
        if not isinstance(line, dict) or line.get("status") != "confirmed":
            continue
        for fact_id in line.get("factIds") or []:
            blocked.add(fact_id)
    return [action["id"] for action in actions if action["factId"] in blocked]


def _goals(actions, forbidden):
    goals = []
    for action in actions:
        if action["owner"] == "us":
            us_value, opponent_value = -1, 2
        else:
            us_value, opponent_value = 2, -1
        goals.append({
            "id": f"g-{action['id']}",
            "type": "all",
            "actionIds": [action["id"]],
            "usValue": us_value,
            "opponentValue": opponent_value,
        })
    ours = [action["id"] for action in actions if action["owner"] == "us" and action["id"] not in forbidden]
    theirs = [action["id"] for action in actions if action["owner"] == "opponent" and action["id"] not in forbidden]
    for index, (us_action, opponent_action) in enumerate(zip(ours, theirs), start=1):
        if len(goals) >= MAX_GOALS:
            break
        goals.append({
            "id": f"g-joint-{index}",
            "type": "all",
            "actionIds": [us_action, opponent_action],
            "usValue": 3,
            "opponentValue": 3,
        })
    reading = {}
    for goal in goals:
        value = 1 if goal["id"].startswith("g-joint-") else goal["opponentValue"]
        reading[goal["id"]] = value
    readings = [{"id": "lower-joint-benefit", "values": reading}] if reading else []
    return goals, readings
