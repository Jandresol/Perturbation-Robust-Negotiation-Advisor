"""The four rewording operators (README §3.2)."""

import random
from pathlib import Path

from negotiator import llm

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
_PROMPT_FILE = {
    "paraphrase_fact": "reword_paraphrase.md",
    "paraphrase_doc": "reword_paraphrase.md",
    "register": "reword_register.md",
}
_SCHEMA = {
    "type": "object",
    "properties": {"rewordings": {"type": "array", "items": {"type": "string"}}},
    "required": ["rewordings"],
    "additionalProperties": False,
}
# Which LLM operators apply to which kind of unit.
LLM_OPERATORS = {"fact": ["paraphrase_fact"], "doc": ["paraphrase_doc", "register"]}


def render(operator: str, text: str, level: str, n: int) -> str:
    template = (PROMPTS / _PROMPT_FILE[operator]).read_text()
    # str.replace, not str.format: case text can contain braces.
    return template.replace("{level}", level).replace("{n}", str(n)).replace("{text}", text)


def reword(operator: str, text: str, level: str, n: int, llm_cfg: dict, seed: int):
    """Return (candidate texts, meta) for one unit at one level."""
    prompt = render(operator, text, level, n)
    data, meta = llm.complete_json(
        prompt, _SCHEMA, model=llm_cfg["model"], base_url=llm_cfg["base_url"],
        effort=llm_cfg["effort"],
        max_tokens=llm_cfg["max_tokens"], seed=seed,
    )
    return [t.strip() for t in data["rewordings"] if t.strip()], meta


def reorder(ids: list[str], n: int, seed: int) -> list[list[str]]:
    """Up to n distinct permutations of the unit order, none equal to the original."""
    rng = random.Random(seed)
    seen, out = {tuple(ids)}, []
    for _ in range(n * 20):
        if len(out) == n:
            break
        perm = ids[:]
        rng.shuffle(perm)
        if tuple(perm) not in seen:
            seen.add(tuple(perm))
            out.append(perm)
    return out
