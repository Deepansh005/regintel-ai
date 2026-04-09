from langchain_community.vectorstores import Chroma
from app.rag.embeddings import get_embedding_model
import uuid
import shutil
import chromadb
from langchain_core.documents import Document


CHROMA_DB_PATH = "./chroma_db"


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def list_collections():
    client = get_chroma_client()
    collections = client.list_collections()
    print("Existing collections:", collections)
    return collections


def delete_collection(name: str):
    client = get_chroma_client()
    client.delete_collection(name=name)


def delete_all_collections():
    client = get_chroma_client()
    collections = client.list_collections()
    print("Existing collections:", collections)

    for collection in collections:
        client.delete_collection(name=collection.name)

    print("All collections deleted successfully")


def reset_chroma_db():
    shutil.rmtree(CHROMA_DB_PATH, ignore_errors=True)
    print("ChromaDB folder deleted")
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def clear_collection_if_exists(collection_name: str):
    client = get_chroma_client()
    existing = {collection.name for collection in client.list_collections()}
    if collection_name in existing:
        client.delete_collection(name=collection_name)


def get_vector_db(collection_name):
    """Get or create Chroma vector store for a collection"""
    embedding_model = get_embedding_model()

    return Chroma(
        persist_directory=CHROMA_DB_PATH,
        embedding_function=embedding_model,
        collection_name=collection_name
    )


def store_chunks(chunks: list, collection_name: str, source: str) -> None:
    """
    Store chunks into Chroma vector store with metadata.
    
    Args:
        chunks: List of text chunks to store
        collection_name: Name of collection to store in
        source: Source file path for metadata tracking
    """
    
    # Validate inputs
    if not chunks or len(chunks) == 0:
        return
    
    # Filter empty/whitespace chunks
    valid_chunks = [chunk for chunk in chunks if chunk and chunk.strip()]
    
    if not valid_chunks:
        return
    
    embedding_model = get_embedding_model()
    
    # Create Document objects with metadata
    documents = []
    for i, chunk in enumerate(valid_chunks):
        doc = Document(
            page_content=chunk,
            metadata={"source": source, "chunk_index": i}
        )
        documents.append(doc)
    
    # Clear collection if exists to avoid duplicates
    clear_collection_if_exists(collection_name)
    
    # Store in Chroma
    vectordb = Chroma.from_documents(
        documents=documents,
        embedding=embedding_model,
        collection_name=collection_name,
        persist_directory=CHROMA_DB_PATH
    )
    
    vectordb.persist()