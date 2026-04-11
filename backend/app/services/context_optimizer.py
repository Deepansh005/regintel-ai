import math
from typing import List
import logging

from app.rag.embeddings import get_embedding_model
from app.services.llm_router import llm_chat_completion

logger = logging.getLogger(__name__)


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def deduplicate_chunks(chunks: List[dict], similarity_threshold: float = 0.92, max_chunks: int = 5) -> List[dict]:
    if not chunks:
        return []

    ranked_chunks = sorted(chunks, key=lambda item: item.get("rank", 999))
    texts = [str(chunk.get("text") or "").strip() for chunk in ranked_chunks]
    if not any(texts):
        return []

    embedding_model = get_embedding_model()
    vectors = embedding_model.embed_documents(texts)

    selected_indices = []
    for current_index, current_vector in enumerate(vectors):
        text = texts[current_index]
        if not text:
            continue

        is_duplicate = False
        for selected_index in selected_indices:
            similarity = _cosine_similarity(current_vector, vectors[selected_index])
            if similarity >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            selected_indices.append(current_index)

        if len(selected_indices) >= max_chunks:
            break

    return [ranked_chunks[index] for index in selected_indices]


def format_context(chunks: List[dict], limit: int = 2800) -> str:
    lines = []
    for chunk in chunks or []:
        chunk_id = chunk.get("chunk_id") or "unknown"
        page_number = chunk.get("page_number")
        source_file_name = chunk.get("source_file_name") or "unknown.pdf"
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"[{chunk_id} | page {page_number} | {source_file_name}] {text}")

    return "\n\n".join(lines)[:limit]


def compress_context(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    # Avoid extra round-trip for short contexts.
    if len(value) < 1500:
        return value

    prompt = (
        "Compress this regulatory text preserving all obligations, numeric thresholds, timelines, penalties, "
        "exceptions, and legal scope. Keep references and citations intact. Return plain text only.\n\n"
        f"{value}"
    )

    try:
        compressed = llm_chat_completion(
            task_type="compression",
            system_prompt="You are a precise legal text compressor. Keep all material compliance facts.",
            user_prompt=prompt,
            max_tokens=450,
            temperature=0.0,
            retries=1,
            timeout_seconds=20,
        )
    except Exception as exc:
        logger.warning("Context compression failed, using original text: %s", exc)
        return value

    if not compressed:
        logger.warning("Context compression returned empty response, using original text")
        return value

    compressed_text = compressed.strip()
    if not compressed_text:
        logger.warning("Context compression produced empty text, using original text")
        return value

    return compressed_text


def optimize_context_chunks(chunks: List[dict], max_chunks: int = 5, compress: bool = True) -> tuple[list[dict], str]:
    unique_chunks = deduplicate_chunks(chunks or [], similarity_threshold=0.92, max_chunks=max_chunks)
    context = format_context(unique_chunks, limit=3200)
    if compress:
        context = compress_context(context)
    return unique_chunks, context
