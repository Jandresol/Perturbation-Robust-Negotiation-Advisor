"""Random-noise control (H2, baseline B4).

Character- and word-level noise at a target embedding distance. Deliberately
NOT checked for meaning, so it must never be mixed into accepted rewordings.
"""

import random
import string

from negotiator.reword.embed import cosine


def perturb(text: str, rate: float, rng: random.Random) -> str:
    words = text.split()
    out = []
    for word in words:
        r = rng.random()
        if r < rate / 3:
            continue                                   # drop word
        if r < 2 * rate / 3:
            out += [word, word]                        # duplicate word
            continue
        chars = list(word)
        for i in range(len(chars)):
            if rng.random() < rate:
                op = rng.randrange(3)
                if op == 0 and i + 1 < len(chars):
                    chars[i], chars[i + 1] = chars[i + 1], chars[i]
                elif op == 1:
                    chars[i] = rng.choice(string.ascii_lowercase)
                else:
                    chars[i] = ""
        out.append("".join(chars))
    for i in range(len(out) - 1):                      # swap adjacent words
        if rng.random() < rate / 3:
            out[i], out[i + 1] = out[i + 1], out[i]
    return " ".join(out)


def matched(text: str, target_d: float, rates: list[float], encoder: str, seed: int,
            draws: int = 5) -> dict:
    """The noised version whose d_emb is closest to target_d.

    Several draws per rate: on a short fact one rate step can jump from no
    change to a large one, and extra draws fill in the distances between.
    """
    best = None
    for rate in rates:
        for k in range(draws):
            noised = perturb(text, rate, random.Random(f"{seed}:{rate}:{k}"))
            d = 1 - cosine(text, noised, encoder)
            if best is None or abs(d - target_d) < abs(best["d_emb"] - target_d):
                best = {"text": noised, "d_emb": d, "rate": rate}
    return best
