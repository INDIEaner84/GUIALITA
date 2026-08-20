"""GUIALITA Memory Retrieval V1 - Deterministisches Embedding.

Leichtgewichtige Feature-Hashing Methode:
  - Tokenisierung (lowercase, Alpha-Numerisch split)
  - Feature-Hashing (jeder Token → feste Dimension)
  - TF-Gewichtung (Häufigkeit)
  - Feste Dimension (default 512)
  - L2-Normalisierung
  - Versioniert (embedding_version)

Kein neuronales Modell, kein Netzwerk, kein Download.
Nur numpy (bereits vorhanden).
"""

import hashlib
import logging
import re
from typing import List

import numpy as np

log = logging.getLogger("guialita.memory.embedding")

EMBEDDING_VERSION = 1
DEFAULT_DIMENSIONS = 512

_TOKEN_PATTERN = re.compile(r"[a-z0-9äöüß]+", re.IGNORECASE)


def _hash_token(token: str, dim: int) -> int:
    """Deterministischer Hash eines Tokens auf Dimension [0, dim)."""
    h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
    return h % dim


def tokenize(text: str) -> List[str]:
    """Tokenisiert Text in lowercase Alpha-Numerisch Tokens."""
    return _TOKEN_PATTERN.findall(text.lower())


def embed(text: str, dimensions: int = DEFAULT_DIMENSIONS) -> np.ndarray:
    """Erzeugt ein deterministisches Feature-Hashing Embedding.

    Verfahren:
      1. Tokenisierung (lowercase, Alpha-Numerisch)
      2. Für jeden Token: sha256 Hash → Dimension indizes
      3. TF-Gewichtung: Anzahl der Tokens pro Dimension
      4. L2-Normalisierung

    Liefert deterministischen Vektor der Form (dimensions,).
    """
    tokens = tokenize(text)
    vec = np.zeros(dimensions, dtype=np.float64)
    for token in tokens:
        idx = _hash_token(token, dimensions)
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def embed_to_bytes(text: str, dimensions: int = DEFAULT_DIMENSIONS) -> bytes:
    """Embedding als Bytes (zum Speichern in SQLite BLOB)."""
    vec = embed(text, dimensions)
    return vec.tobytes()


def bytes_to_embedding(data: bytes, dimensions: int = DEFAULT_DIMENSIONS) -> np.ndarray:
    """Bytes zurück zu Embedding Vektor."""
    vec = np.frombuffer(data, dtype=np.float64)
    if vec.shape[0] != dimensions:
        raise ValueError(
            f"Embedding-Dimension-Mismatch: erwartet {dimensions}, "
            f"erhalten {vec.shape[0]}"
        )
    return vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine Similarity zwischen zwei Vektoren. Beide L2-normalisiert."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
