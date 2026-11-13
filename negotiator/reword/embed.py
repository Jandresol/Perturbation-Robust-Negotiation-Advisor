"""One sentence encoder, loaded once per process."""

import re
from functools import lru_cache

from sentence_transformers import SentenceTransformer

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\s*\n\s*")


def sentences(text: str, min_words: int = 3) -> list[str]:
    """Split on sentence ends and line breaks (posts, headings and list items often
    end without a full stop); fragments under min_words (list markers like "4.")
    join the next one."""
    out, carry = [], ""
    for part in _SENTENCE_END.split(text.strip()):
        part = f"{carry} {part}".strip()
        if len(part.split()) < min_words:
            carry = part
        else:
            out.append(part)
            carry = ""
    if carry:
        out.append(carry)
    return out


@lru_cache(maxsize=None)
def encoder(name: str) -> SentenceTransformer:
    return SentenceTransformer(name)


def embed(texts: list[str], name: str):
    return encoder(name).encode(texts, normalize_embeddings=True)


def text_vector(text: str, name: str):
    """Mean of sentence embeddings, so long documents are not truncated by the encoder."""
    v = embed(sentences(text) or [text], name).mean(axis=0)
    return v / (v @ v) ** 0.5


def cosine(a: str, b: str, name: str) -> float:
    return float(text_vector(a, name) @ text_vector(b, name))
