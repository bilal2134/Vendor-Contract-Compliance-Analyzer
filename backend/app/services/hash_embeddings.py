from __future__ import annotations

import hashlib
import math
import re

VECTOR_SIZE = 192
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{1,}")


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    tokens = TOKEN_RE.findall(text.lower())
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
