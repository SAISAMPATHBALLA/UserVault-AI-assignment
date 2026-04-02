import os
import anthropic

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def embed_question(text: str) -> list[float]:
    """
    Returns a 1536-dim embedding vector for the given text.
    Uses Claude's voyage-3 model via the Anthropic embeddings endpoint.
    """
    client = _get_client()
    response = client.embeddings.create(
        model="voyage-3",
        input=[text],
    )
    return response.embeddings[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(x ** 2 for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
