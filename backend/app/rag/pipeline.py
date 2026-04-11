from app.rag.chunker import chunk_document
from app.rag.vector_store import store_chunks


def process_document(text: str, collection_name: str, source: str = None):
    """
    Process document: chunk → store in vector DB
    """
    
    if not text or not text.strip():
        raise ValueError("Empty document text")

    chunks = chunk_document(text)
    
    if not chunks or len(chunks) == 0:
        raise ValueError("Document produced no chunks after processing")

    chunk_ids = store_chunks(chunks, collection_name, source or collection_name)

    return {
        "status": "success",
        "collection": collection_name,
        "num_chunks": len(chunks),
        "chunk_ids": chunk_ids,
    }