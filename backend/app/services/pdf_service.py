import fitz  # PyMuPDF
import logging
import hashlib
import os

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract structured Markdown text from PDF.
    Priority:
    1. pymupdf4llm (best structure)
    2. PyMuPDF fallback (basic structure)
    
    Raises RuntimeError if extraction fails or PDF is empty.
    """
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise RuntimeError(f"PDF file not found: {file_path}")
    
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise RuntimeError("PDF file is empty (0 bytes)")

    # =============================
    # ✅ TRY pymupdf4llm (BEST)
    # =============================
    try:
        import pymupdf4llm

        logger.info("✅ Using pymupdf4llm for Markdown extraction")

        md_text = pymupdf4llm.to_markdown(file_path)
        
        # Validate extracted text
        if not md_text or not md_text.strip():
            logger.warning("⚠️ pymupdf4llm returned empty text, falling back to PyMuPDF")
        else:
            cleaned = clean_markdown(md_text)
            
            if not cleaned or not cleaned.strip():
                logger.warning("⚠️ Cleaned markdown is empty, falling back to PyMuPDF")
            else:
                logger.info(f"✅ Successfully extracted {len(cleaned)} characters from PDF")
                return cleaned

    except Exception as e:
        logger.warning(f"⚠️ pymupdf4llm failed, falling back. Error: {e}")

    # =============================
    # 🔁 FALLBACK: PyMuPDF
    # =============================
    try:
        logger.info("🔁 Using PyMuPDF fallback extraction")

        doc = fitz.open(file_path)
        
        if len(doc) == 0:
            raise RuntimeError("PDF has no pages")
        
        md_parts = []

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    line_text = " ".join(
                        span["text"] for span in line["spans"]
                    ).strip()

                    if not line_text:
                        continue

                    # Detect headings (simple heuristic)
                    if line_text.isupper() and len(line_text) < 100:
                        md_parts.append(f"\n## {line_text}\n")
                    else:
                        md_parts.append(line_text)

        raw_text = "\n".join(md_parts)
        
        if not raw_text or not raw_text.strip():
            raise RuntimeError("No text content extracted from PDF (PDF may be image-only or corrupted)")

        cleaned = clean_markdown(raw_text)
        
        if not cleaned or not cleaned.strip():
            raise RuntimeError("Cleaned text is empty after processing")
        
        logger.info(f"✅ Successfully extracted {len(cleaned)} characters from PDF using fallback")
        return cleaned

    except Exception as e:
        logger.error(f"❌ PDF extraction completely failed: {e}")
        raise RuntimeError(f"PDF extraction failed: {str(e)}")


# =============================
# 🧹 CLEAN MARKDOWN
# =============================
def clean_markdown(text: str) -> str:
    """
    Clean Markdown while preserving structure
    """

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        if not line:
            cleaned_lines.append("")
            continue

        # Normalize spacing
        line = " ".join(line.split())

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash for a file.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()