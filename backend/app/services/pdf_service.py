import fitz  # PyMuPDF
import logging
import hashlib
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Optional imports for fallback extraction methods
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


# =============================
# 🔧 FALLBACK EXTRACTION METHODS
# =============================
def extract_with_pymupdf_simple(file_path: str) -> str:
    """
    Extract text from PDF using PyMuPDF (fitz) - basic method.
    Fallback when structured extraction fails.
    """
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        
        if text.strip():
            logger.info(f"✅ PyMuPDF simple extraction succeeded: {len(text)} chars")
            return text
        return ""
    except Exception as e:
        logger.warning(f"⚠️ PyMuPDF simple extraction failed: {e}")
        return ""


def extract_with_pdfplumber(file_path: str) -> str:
    """
    Extract text from PDF using pdfplumber - alternative text extraction.
    """
    if not HAS_PDFPLUMBER:
        logger.debug("pdfplumber not installed, skipping")
        return ""
    
    try:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if text.strip():
            logger.info(f"✅ pdfplumber extraction succeeded: {len(text)} chars")
            return text
        return ""
    except Exception as e:
        logger.warning(f"⚠️ pdfplumber extraction failed: {e}")
        return ""


def extract_with_ocr(file_path: str) -> str:
    """
    Extract text from scanned PDF using OCR (Tesseract).
    Requires Tesseract OCR engine: https://github.com/UB-Mannheim/tesseract/wiki
    """
    if not HAS_OCR:
        logger.debug("pdf2image or pytesseract not installed, skipping OCR")
        return ""
    
    try:
        logger.info("🔍 Attempting OCR extraction for scanned PDF...")
        images = convert_from_path(file_path)
        text = ""
        
        for page_num, image in enumerate(images, 1):
            try:
                page_text = pytesseract.image_to_string(image)
                if page_text.strip():
                    text += page_text + "\n"
                    logger.debug(f"OCR page {page_num}: {len(page_text)} chars")
            except Exception as e:
                logger.warning(f"OCR failed on page {page_num}: {e}")
                continue
        
        if text.strip():
            logger.info(f"✅ OCR extraction succeeded: {len(text)} chars from {len(images)} pages")
            return text
        return ""
    except RuntimeError as e:
        # Tesseract not installed
        if "tesseract" in str(e).lower():
            logger.warning("⚠️ Tesseract OCR engine not installed. Install from: https://github.com/UB-Mannheim/tesseract/wiki")
        else:
            logger.warning(f"⚠️ OCR extraction failed: {e}")
        return ""
    except Exception as e:
        logger.warning(f"⚠️ OCR extraction failed: {e}")
        return ""


def extract_pdf_text_with_fallbacks(file_path: str) -> str:
    """
    Try multiple methods to extract text from PDF.
    Priority:
    1. PyMuPDF structured extraction (best for digital PDFs)
    2. PyMuPDF simple extraction
    3. pdfplumber extraction
    4. OCR extraction (for scanned PDFs)
    
    Returns extracted text or raises RuntimeError if all methods fail.
    """
    # Method 1: PyMuPDF structured (primary)
    try:
        doc = fitz.open(file_path)
        try:
            if len(doc) == 0:
                raise RuntimeError("PDF has no pages")
            
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            
            if text and len(text.strip()) > 50:
                logger.info(f"✅ Method 1 (PyMuPDF structured): {len(text)} chars extracted")
                return text
        finally:
            doc.close()
    except Exception as e:
        logger.warning(f"Method 1 failed: {e}")
    
    # Method 2: PyMuPDF simple extraction
    text = extract_with_pymupdf_simple(file_path)
    if text and len(text.strip()) > 50:
        return text
    
    # Method 3: pdfplumber extraction
    text = extract_with_pdfplumber(file_path)
    if text and len(text.strip()) > 50:
        return text
    
    # Method 4: OCR extraction (for scanned PDFs)
    text = extract_with_ocr(file_path)
    if text and len(text.strip()) > 50:
        return text
    
    # All methods failed
    raise RuntimeError(
        "Failed to extract text from PDF after trying multiple methods. "
        "PDF may be corrupted, encrypted, or blank. "
        "For scanned PDFs, ensure Tesseract OCR is installed: "
        "https://github.com/UB-Mannheim/tesseract/wiki"
    )


def _extract_page_text(page) -> str:
    blocks = page.get_text("dict").get("blocks", [])
    lines = []

    for block in blocks:
        if "lines" not in block:
            continue

        for line in block["lines"]:
            line_text = " ".join(span["text"] for span in line["spans"]).strip()
            if not line_text:
                continue

            if line_text.isupper() and len(line_text) < 100:
                lines.append(f"## {line_text}")
            else:
                lines.append(line_text)

    return clean_markdown("\n".join(lines))


def extract_pdf_pages(file_path: str) -> List[Dict]:
    """Extract per-page text from a PDF with page metadata.
    
    Uses multiple extraction methods as fallbacks:
    1. PyMuPDF structured extraction
    2. PyMuPDF simple extraction
    3. pdfplumber
    4. OCR (for scanned PDFs)
    """
    if not os.path.exists(file_path):
        raise RuntimeError(f"PDF file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise RuntimeError("PDF file is empty (0 bytes)")

    # Try fallback extraction pipeline first to get raw text
    logger.info(f"📄 Starting extraction from: {os.path.basename(file_path)}")
    try:
        combined_text = extract_pdf_text_with_fallbacks(file_path)
        logger.info(f"📊 Extracted text length: {len(combined_text)} characters")
    except RuntimeError as e:
        logger.error(f"❌ Text extraction completely failed: {e}")
        raise

    # If we got text, now process it page by page with PyMuPDF for page tracking
    doc = fitz.open(file_path)
    try:
        if len(doc) == 0:
            raise RuntimeError("PDF has no pages")

        page_texts = []
        source_file_name = os.path.basename(file_path)

        for page_index, page in enumerate(doc, start=1):
            page_text = _extract_page_text(page)
            if not page_text or not page_text.strip():
                # If PyMuPDF can't extract, use fallback for this page
                logger.debug(f"Page {page_index}: PyMuPDF extraction empty, trying fallback")
                page_text = page.get_text()  # Simple fallback
                if not page_text.strip():
                    logger.warning(f"⚠️ Page {page_index}: No text extracted even with fallback")
                    continue

            page_texts.append(
                {
                    "page_number": page_index,
                    "text": page_text,
                    "source_file_name": source_file_name,
                }
            )
    finally:
        doc.close()

    if not page_texts:
        raise RuntimeError(
            "No text content extracted from PDF after structured processing. "
            "PDF may be image-only (requires OCR) or corrupted."
        )

    logger.info(f"✅ Successfully extracted {len(page_texts)} pages from PDF")
    return page_texts


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract structured Markdown text from PDF.
    Supports both digital and scanned PDFs through fallback methods.
    
    Extraction priority:
    1. PyMuPDF structured extraction (best for digital PDFs)
    2. PyMuPDF simple extraction
    3. pdfplumber (alternative text extraction)
    4. OCR (for scanned PDFs - requires Tesseract)
    
    Returns clean markdown-formatted text or raises RuntimeError if all methods fail.
    """
    try:
        logger.info(f"🚀 Starting PDF text extraction: {os.path.basename(file_path)}")
        page_texts = extract_pdf_pages(file_path)
        combined_text = "\n\n".join(page.get("text", "") for page in page_texts)
        
        # DEBUG LOGGING
        logger.info(f"📊 DEBUG: Extracted text length: {len(combined_text)} characters")
        logger.info(f"📊 DEBUG: Number of pages with text: {len(page_texts)}")
        
        if not combined_text or not combined_text.strip():
            raise RuntimeError("Cleaned text is empty after processing")

        logger.info(f"✅ Successfully extracted and combined {len(combined_text)} characters from PDF")
        return combined_text
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