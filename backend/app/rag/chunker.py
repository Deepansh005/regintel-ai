import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.clause_extractor import extract_clauses_from_text

logger = logging.getLogger(__name__)


def chunk_document(text: str):
    """
    Improved semantic chunking for regulatory documents
    """

    try:
        clauses = extract_clauses_from_text(text)
        if clauses:
            logger.info("Clause extraction started")
            logger.info("Extracted %s clauses", len(clauses))
            if clauses:
                logger.info("First clause content: %s", (clauses[0].get("content") or "")[:500])
                logger.info("First 2 clauses: %s", clauses[:2])
                print(f"Clause extraction debug: total_clauses={len(clauses)} first_clause={clauses[0].get('content', '')[:500]}")
            return clauses
    except Exception as exc:
        logger.error("Clause extraction failed in chunk_document, using legacy splitter: %s", exc)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n\n", "\n\n", "\n", "."],
    )

    return splitter.split_text(text)