"""
RAG: embeddings via Hugging Face's Inference API (hf-inference backend,
free-tier, rate-limited rather than PRO-gated -- verified before relying
on it), retrieval via pgvector cosine distance in Supabase.

Uses AsyncInferenceClient, not the sync InferenceClient -- the sync one
would block the event loop on every embedding call, stalling audio
processing mid-call. Confirmed feature_extraction is awaitable on the
async client before using it here.

Embeddings are formatted as a Postgres vector literal string ("[v1,v2,...]")
for asyncpg, which has no native pgvector type support -- confirmed this
works against the real database (including hitting and fixing a stale
vector(1536) column left over from before the HF Inference API decision;
the actual column is vector(384) now, matching
sentence-transformers/all-MiniLM-L6-v2's output size).
"""

import logging
import os

from huggingface_hub import AsyncInferenceClient

import db

logger = logging.getLogger("voice-agent")

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_client: AsyncInferenceClient | None = None


def _get_client() -> AsyncInferenceClient:
    global _client
    if _client is None:
        _client = AsyncInferenceClient(provider="hf-inference", token=os.environ["HF_TOKEN"])
    return _client


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


async def embed_text(text: str) -> list[float]:
    result = await _get_client().feature_extraction(text, model=EMBEDDING_MODEL)
    return result.tolist()


async def seed_kb(documents: list[dict]) -> None:
    """Embeds and inserts each {"title", "content"} document. Each
    document becomes one kb_documents row plus one kb_chunks row -- no
    splitting, since these are already short, single-topic entries (see
    kb_content.py's docstring)."""
    pool = await db.get_pool()
    for doc in documents:
        embedding = await embed_text(doc["content"])
        async with pool.acquire() as conn:
            doc_id = await conn.fetchval(
                "insert into kb_documents (title) values ($1) returning id",
                doc["title"],
            )
            await conn.execute(
                "insert into kb_chunks (document_id, content, embedding) "
                "values ($1, $2, $3::vector)",
                doc_id,
                doc["content"],
                _vector_literal(embedding),
            )
        logger.info("rag: seeded %r", doc["title"])


async def retrieve_chunks(query: str, k: int = 3) -> list[str]:
    embedding = await embed_text(query)
    pool = await db.get_pool()
    rows = await pool.fetch(
        "select content from kb_chunks order by embedding <=> $1::vector limit $2",
        _vector_literal(embedding),
        k,
    )
    return [row["content"] for row in rows]
