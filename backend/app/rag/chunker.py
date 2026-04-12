import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.semantic_block_extractor import extract_semantic_blocks

logger = logging.getLogger(__name__)


def chunk_document(text: str):
    """
    Improved semantic chunking for regulatory documents
    """

    try:
        blocks = extract_semantic_blocks(text)
        if blocks:
            logger.info("Semantic block extraction started")
            logger.info("Extracted %s blocks", len(blocks))
            print("Using semantic blocks:", len(blocks))
            return blocks
    except Exception as exc:
        logger.error("Semantic block extraction failed in chunk_document, using legacy splitter: %s", exc)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n\n", "\n\n", "\n", "."],
    )

    return splitter.split_text(text)