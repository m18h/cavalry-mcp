"""Semantic search over the official Cavalry documentation.

Uses a bundled vector store (built by scripts/build_knowledge_base.py) and
fastembed (ONNX runtime, no torch) to embed queries. Both the store and the
embedding model load lazily on first use.
"""

from __future__ import annotations

import io
import json
from functools import lru_cache
from importlib.resources import files
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    import numpy as np

_SNIPPET_LIMIT = 700

KB_SETUP_HINT = (
    "Knowledge base not available. Build it with: "
    "uv sync --extra kb && uv run python scripts/build_knowledge_base.py"
)


class KnowledgeBaseUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def _store() -> tuple[list[dict], np.ndarray, str]:
    """Load (chunks, vectors, model_name) from the bundled data files."""
    try:
        import numpy as np  # optional dependency (extra: kb)
    except ImportError as exc:
        raise KnowledgeBaseUnavailable(KB_SETUP_HINT) from exc
    try:
        data = files("cavalry_mcp").joinpath("data")
        chunks_text = data.joinpath("knowledge_chunks.json").read_text(encoding="utf-8")
        vectors_bytes = data.joinpath("knowledge_vectors.npz").open("rb").read()
    except FileNotFoundError as exc:
        raise KnowledgeBaseUnavailable(KB_SETUP_HINT) from exc
    payload = json.loads(chunks_text)
    vectors = np.load(io.BytesIO(vectors_bytes))["vectors"].astype(np.float32)
    return payload["chunks"], vectors, payload["model"]


@lru_cache(maxsize=1)
def _embedder():
    """Load fastembed lazily — it is an optional dependency (extra: kb)."""
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise KnowledgeBaseUnavailable(KB_SETUP_HINT) from exc
    _chunks, _vectors, model_name = _store()
    return TextEmbedding(model_name)


def search(query: str, limit: int = 5) -> list[dict]:
    import numpy as np  # optional dependency (extra: kb)

    chunks, vectors, _model = _store()
    query_vector = np.array(
        list(_embedder().query_embed([query])), dtype=np.float32
    )[0]
    scores = (vectors @ query_vector) / (
        np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_vector) + 1e-12
    )
    top = np.argsort(-scores)[:limit]
    results = []
    for idx in top:
        chunk = chunks[int(idx)]
        text = chunk["text"]
        if len(text) > _SNIPPET_LIMIT:
            text = text[:_SNIPPET_LIMIT].rstrip() + "…"
        results.append(
            {
                "title": chunk["title"],
                "heading": chunk["heading"],
                "url": chunk["url"],
                "score": round(float(scores[idx]), 3),
                "text": text,
            }
        )
    return results


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_search_knowledge(query: str, limit: int = 5) -> dict:
        """Semantic search over the full official Cavalry documentation.

        Use this for concepts, how-tos, guides and "how do I…" questions
        (e.g. "how to stagger animation on a duplicator", "loop an animation",
        "export Lottie"). For exact API signatures use cavalry_search_api.

        Args:
            query: Natural language question or topic.
            limit: Max passages to return.
        """
        try:
            results = search(query, limit=limit)
        except KnowledgeBaseUnavailable as exc:
            return {"available": False, "error": str(exc), "results": []}
        return {"available": True, "count": len(results), "results": results}
