from langchain_community.vectorstores import Chroma
from app.rag.embeddings import get_embedding_model
import logging

logger = logging.getLogger(__name__)

def get_vector_db(collection_name):
    embedding_model = get_embedding_model()

    return Chroma(
        persist_directory="./chroma_db",
        embedding_function=embedding_model,
        collection_name=collection_name
    )

# ✅ BASIC RETRIEVAL (optional)
def retrieve_from_collection(query: str, collection_name: str, k: int = 5):
    """Retrieve k most similar chunks from collection"""
    try:
        vectordb = get_vector_db(collection_name)
        results = vectordb.similarity_search(query, k=k)
        
        if not results:
            return []
        
        return [r.page_content for r in results if r.page_content and r.page_content.strip()]
    except Exception as e:
        logger.error(f"Retrieval error from {collection_name}: {e}")
        return []

# ✅ SOURCE-GROUNDED RETRIEVAL (MAIN FUNCTION)
def retrieve_with_metadata(query: str, collection_name: str, k: int = 5):
    """Retrieve k most similar chunks with source metadata"""
    try:
        vectordb = get_vector_db(collection_name)
        results = vectordb.similarity_search(query, k=k)

        if not results:
            return []

        formatted_chunks = []

        for i, r in enumerate(results):
            chunk_text = r.page_content
            
            if not chunk_text or not chunk_text.strip():
                continue

            metadata = r.metadata or {}
            formatted_chunks.append(
                {
                    "chunk_id": metadata.get("chunk_id"),
                    "text": chunk_text,
                    "page_number": metadata.get("page_number"),
                    "source_file_name": metadata.get("source_file_name") or metadata.get("source") or collection_name,
                    "collection_name": metadata.get("collection_name") or collection_name,
                    "rank": i + 1,
                }
            )

        return formatted_chunks
    
    except Exception as e:
        logger.error(f"Retrieval error from {collection_name}: {e}")
        return []
