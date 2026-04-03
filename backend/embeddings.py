"""
Embedding utility — all-MiniLM-L6-v2 via sentence-transformers, dim=384.
Computed once in Node 02, stored in LangGraph state, reused in Node 03+04.
"""
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_question(text: str) -> list[float]:
    """
    Returns a 384-dim embedding vector for the given text.
    Uses all-MiniLM-L6-v2 via sentence-transformers (local, no API key).
    """
    return _get_model().encode(text).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(x ** 2 for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
