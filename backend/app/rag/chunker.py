import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.clause_extractor import extract_clauses_from_text, filter_relevant_clauses

logger = logging.getLogger(__name__)


def chunk_document(text: str):
    """
    Improved semantic chunking for regulatory documents
    """

    try:
        clauses = extract_clauses_from_text(text)
        if clauses:
            clauses = filter_relevant_clauses(clauses)
            logger.info("Clause extraction started")
            logger.info("Extracted %s clauses", len(clauses))
            return clauses
    except Exception as exc:
        logger.error("Clause extraction failed in chunk_document, using legacy splitter: %s", exc)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n\n", "\n\n", "\n", "."],
    )

    return splitter.split_text(text)