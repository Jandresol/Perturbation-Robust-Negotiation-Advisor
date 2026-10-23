"""Acceptance filter (README §3.2): cosine >= tau, two-way NLI, hard facts unchanged."""

import re
from collections import Counter
from functools import lru_cache

from sentence_transformers import CrossEncoder

from negotiator.reword.embed import cosine, embed, sentences

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CAPITALISED = re.compile(r"[A-Z][\w'’-]*")
_PERCENT = re.compile(r"\s*(?:per ?cent|percent)\b", re.I)
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.M)   # "1. " at a line start is formatting
_I_CONTRACTION = re.compile(r"I['’](m|ll|ve|d)$")   # "I'm", "I'll": not names
_CLAUSE_START = set(":;-–—…|.!?")
# "one" is left out: it is usually a pronoun ("one of the highest", "no one").
_WORD_NUMBERS = {w: str(i) for i, w in enumerate(
    "zero _ two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()) if w != "_"}


# ---------- hard facts: deterministic, no model ----------

def _numbers(text: str) -> Counter:
    text = _LIST_MARKER.sub("", _PERCENT.sub("%", text))
    found = [n.replace(",", "") for n in _NUMBER.findall(text)]
    found += [_WORD_NUMBERS[w] for w in re.findall(r"[a-z]+", text.lower()) if w in _WORD_NUMBERS]
    return Counter(found)


def _is_acronym(tok: str) -> bool:
    return any(c.isupper() for c in tok[1:])          # HfA, WHO, MASHA


def _is_title_case(sent: str) -> bool:
    """Headlines like "Staff of Health for All Detained by Tribespeople"."""
    words = [w for w in re.findall(r"[A-Za-z][\w'’-]*", sent) if len(w) >= 4]
    return len(words) >= 2 and sum(w[0].isupper() for w in words) / len(words) >= 0.6


def _names(text: str, common: set) -> tuple[set, set]:
    """(names not at a sentence start, every capitalised token).

    A capitalised word whose lowercase form occurs in either text ("After",
    "Detained") is an ordinary word, not a name. In Title Case lines only
    acronyms count, since every word there is capitalised.
    """
    inner, every = set(), set()
    for sent in sentences(text, min_words=0):
        title = _is_title_case(sent)
        for m in _CAPITALISED.finditer(sent):
            tok = re.sub(r"['’]s$", "", m.group()).rstrip("-")
            if (len(tok) < 2 or tok.lower() in common or tok.lower() in _WORD_NUMBERS
                    or _I_CONTRACTION.match(tok)):
                continue
            if title and not _is_acronym(tok):
                continue
            every.add(tok)
            # A word right after a speaker label, dash, ellipsis or "|" starts a clause.
            before = sent[: m.start()].rstrip(" \"'“‘(")
            if before and before[-1] not in _CLAUSE_START:
                inner.add(tok)
    return inner, every


def hard_fact_diff(original: str, new: str) -> dict:
    """Numbers and names that were lost or added; all empty means the hard facts match."""
    num_o, num_n = _numbers(original), _numbers(new)
    common = set(re.findall(r"\b[a-z][\w'’-]*", original + "\n" + new))
    inner_o, every_o = _names(original, common)
    inner_n, every_n = _names(new, common)
    return {
        "numbers_lost": sorted((num_o - num_n).elements()),
        "numbers_added": sorted((num_n - num_o).elements()),
        "names_lost": sorted(inner_o - every_n),
        "names_added": sorted(inner_n - every_o),
    }


def hard_facts_ok(original: str, new: str) -> bool:
    return not any(hard_fact_diff(original, new).values())


# ---------- NLI ----------

@lru_cache(maxsize=None)
def _nli(name: str):
    model = CrossEncoder(name)
    labels = {v.lower(): int(k) for k, v in model.model.config.id2label.items()}
    return model, labels["entailment"]


def entailment(premise: str, hypothesis: str, cfg: dict) -> float:
    """Min over hypothesis sentences of the best entailment prob from a premise window.

    One-sentence units reduce to a single pair. Longer units are split so the
    cross-encoder never truncates; each hypothesis sentence is checked against
    the premise windows closest to it in embedding space. Windows are every run
    of 1..window_sentences sentences: the NLI model reads a sentence buried in
    the middle of a longer premise as "neutral", so single sentences are needed,
    and longer runs cover a rewording that merged or split sentences.
    """
    model, entail_idx = _nli(cfg["nli_model"])
    prem = sentences(premise)
    windows = [" ".join(prem[i:i + w]) for w in range(1, cfg["window_sentences"] + 1)
               for i in range(len(prem) - w + 1)] or [premise]
    hyps = sentences(hypothesis)
    win_vecs, hyp_vecs = embed(windows, cfg["encoder"]), embed(hyps, cfg["encoder"])
    pairs, owner = [], []
    for h, (hyp, vec) in enumerate(zip(hyps, hyp_vecs)):
        nearest = (win_vecs @ vec).argsort()[::-1][: cfg["top_windows"]]
        pairs += [(windows[j], hyp) for j in nearest]
        owner += [h] * len(nearest)
    probs = model.predict(pairs, apply_softmax=True)[:, entail_idx]
    best = [0.0] * len(hyps)
    for h, p in zip(owner, probs):
        best[h] = max(best[h], float(p))
    return min(best)


# ---------- combined check ----------

def check(original: str, new: str, cfg: dict) -> dict:
    """All checks are run and logged; reject_reason names the first that failed."""
    cos = cosine(original, new, cfg["encoder"])
    fwd = entailment(original, new, cfg)
    bwd = entailment(new, original, cfg)
    facts = hard_facts_ok(original, new)
    failed = [name for name, ok in [
        ("cosine", cos >= cfg["tau"]),
        ("nli_fwd", fwd >= cfg["nli_threshold"]),
        ("nli_bwd", bwd >= cfg["nli_threshold"]),
        ("hard_facts", facts),
    ] if not ok]
    return {
        "cos": cos, "d_emb": 1 - cos, "nli_fwd": fwd, "nli_bwd": bwd,
        "hard_facts_ok": facts, "accepted": not failed,
        "reject_reason": failed[0] if failed else None,
    }
