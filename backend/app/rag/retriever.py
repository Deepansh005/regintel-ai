from langchain_community.vectorstores import Chroma
from app.rag.embeddings import get_embedding_model


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
        print(f"Retrieval error from {collection_name}: {e}")
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

            formatted_chunks.append(
                f"[SOURCE {i+1} | {collection_name}]\n{chunk_text}"
            )

        return formatted_chunks
    
    except Exception as e:
        print(f"Retrieval error from {collection_name}: {e}")
        return []