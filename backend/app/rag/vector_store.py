import os
import shutil
import uuid
import logging

import chromadb
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

from app.rag.embeddings import get_embedding_model

logger = logging.getLogger(__name__)


CHROMA_DB_PATH = "./chroma_db"


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def list_collections():
    client = get_chroma_client()
    collections = client.list_collections()
    logger.info(f"Existing collections: {[c.name for c in collections]}")
    return collections


def delete_collection(name: str):
    client = get_chroma_client()
    client.delete_collection(name=name)


def delete_all_collections():
    client = get_chroma_client()
    collections = client.list_collections()
    logger.info(f"Existing collections: {[c.name for c in collections]}")

    for collection in collections:
        client.delete_collection(name=collection.name)

    logger.info("All collections deleted successfully")


def reset_chroma_db():
    shutil.rmtree(CHROMA_DB_PATH, ignore_errors=True)
    logger.info("ChromaDB folder deleted")
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def clear_collection_if_exists(collection_name: str):
    client = get_chroma_client()
    existing = {collection.name for collection in client.list_collections()}
    if collection_name in existing:
        client.delete_collection(name=collection_name)


def get_vector_db(collection_name):
    """Get or create Chroma vector store for a collection."""
    embedding_model = get_embedding_model()

    return Chroma(
        persist_directory=CHROMA_DB_PATH,
        embedding_function=embedding_model,
        collection_name=collection_name,
    )


def _normalize_chunk_record(chunk, collection_name: str, source_file_name: str | None = None) -> dict | None:
    if isinstance(chunk, dict):
        text = str(chunk.get("text") or chunk.get("page_content") or "").strip()
        if not text:
            return None

        normalized_source = chunk.get("source_file_name") or source_file_name or collection_name
        normalized_source = os.path.basename(str(normalized_source))
        return {
            "chunk_id": str(chunk.get("chunk_id") or uuid.uuid4().hex),
            "text": text,
            "page_number": chunk.get("page_number"),
            "source_file_name": normalized_source,
            "collection_name": collection_name,
            "clause_id": chunk.get("clause_id"),
            "title": chunk.get("title"),
        }

    text = str(chunk or "").strip()
    if not text:
        return None

    return {
        "chunk_id": uuid.uuid4().hex,
        "text": text,
        "page_number": None,
        "source_file_name": os.path.basename(str(source_file_name or collection_name)),
        "collection_name": collection_name,
        "clause_id": None,
        "title": None,
    }


def store_chunks(chunks: list, collection_name: str, source: str) -> list[str]:
    """
    Store chunks into Chroma vector store with metadata.

    Args:
        chunks: List of text chunks or chunk records to store
        collection_name: Name of collection to store in
        source: Source file path for metadata tracking
    """

    normalized_chunks = []
    for chunk in chunks or []:
        normalized = _normalize_chunk_record(chunk, collection_name, source)
        if normalized:
            normalized_chunks.append(normalized)

    if not normalized_chunks:
        return []

    clear_collection_if_exists(collection_name)

    vectordb = get_vector_db(collection_name)
    documents = []
    chunk_ids = []

    for index, chunk in enumerate(normalized_chunks):
        chunk_id = chunk["chunk_id"]
        metadata = {
            "chunk_id": chunk_id,
            "text": chunk["text"],
            "page_number": chunk["page_number"],
            "source_file_name": chunk["source_file_name"],
            "collection_name": collection_name,
            "source": source,
            "chunk_index": index,
            "clause_id": chunk.get("clause_id"),
            "title": chunk.get("title"),
        }

        documents.append(Document(page_content=chunk["text"], metadata=metadata))
        chunk_ids.append(chunk_id)

    vectordb.add_documents(documents=documents, ids=chunk_ids)

    if hasattr(vectordb, "persist"):
        vectordb.persist()

    return chunk_ids


def retrieve_with_metadata(query: str, collection_name: str, k: int = 5):
    """Retrieve k most similar chunks with source metadata."""
    try:
        vectordb = get_vector_db(collection_name)
        results = vectordb.similarity_search(query, k=k)

        if not results:
            return []

        formatted_chunks = []

        for rank, result in enumerate(results):
            chunk_text = result.page_content
            if not chunk_text or not chunk_text.strip():
                continue

            metadata = result.metadata or {}
            formatted_chunks.append(
                {
                    "chunk_id": metadata.get("chunk_id"),
                    "text": chunk_text,
                    "page_number": metadata.get("page_number"),
                    "source_file_name": metadata.get("source_file_name") or metadata.get("source") or collection_name,
                    "collection_name": collection_name,
                    "rank": rank + 1,
                }
            )

        return formatted_chunks
    except Exception as e:
        logger.error(f"Retrieval error from {collection_name}: {e}")
        return []


def get_chunk_details(chunk_ids: list[str]):
    """Fetch chunk details across all collections by chunk_id."""
    requested_ids = [str(chunk_id) for chunk_id in (chunk_ids or []) if chunk_id]
    if not requested_ids:
        return []

    client = get_chroma_client()
    details = []
    seen_ids = set()

    for collection_info in client.list_collections():
        try:
            collection = client.get_collection(name=collection_info.name)
            result = collection.get(ids=requested_ids, include=["documents", "metadatas"])

            for chunk_id, document, metadata in zip(result.get("ids", []), result.get("documents", []), result.get("metadatas", [])):
                if not chunk_id or chunk_id in seen_ids:
                    continue

                seen_ids.add(chunk_id)
                details.append(
                    {
                        "chunk_id": chunk_id,
                        "text": document or "",
                        "page_number": metadata.get("page_number") if isinstance(metadata, dict) else None,
                        "source_file_name": metadata.get("source_file_name") if isinstance(metadata, dict) else None,
                        "collection_name": metadata.get("collection_name") if isinstance(metadata, dict) else collection_info.name,
                        "clause_id": metadata.get("clause_id") if isinstance(metadata, dict) else None,
                        "title": metadata.get("title") if isinstance(metadata, dict) else None,
                    }
                )
        except Exception as exc:
            print(f"Chunk lookup error in {collection_info.name}: {exc}")

    order = {chunk_id: index for index, chunk_id in enumerate(requested_ids)}
    details.sort(key=lambda item: order.get(item["chunk_id"], len(order)))
    return details