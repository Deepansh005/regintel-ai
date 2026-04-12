"""
Semantic Block Extractor for Regulatory Documents

Replaces fragment-based clause extraction with large semantic blocks (200-800 tokens).
Each block preserves regulatory context and meaning.

Key principle: NO FRAGMENTATION. Extract meaningful regulatory units.
"""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# Block size targets (in tokens/words, approximate)
MIN_BLOCK_TOKENS = 200
TARGET_BLOCK_TOKENS = 400
MAX_BLOCK_TOKENS = 800
MIN_BLOCK_COUNT = 5

# Threshold for detecting section headers - SIMPLIFIED and more reliable
SECTION_PATTERN = re.compile(
    r"(?im)^(?:Chapter|Part|Section|Article|Rule|Regulation|Clause|Schedule|Appendix|Annex|Title)\s+[\w.:\d-]+",
    re.MULTILINE
)


def _token_count(text: str) -> int:
    """Approximate token count (words)."""
    return len(re.findall(r"\S+", text or ""))


def _extract_section_header(text: str, max_length: int = 100) -> str:
    """Extract section header from text."""
    first_line = text.split('\n')[0].strip()
    return first_line[:max_length] if first_line else ""


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text by empty lines (paragraph breaks)."""
    paragraphs = [
        p.strip() 
        for p in re.split(r"\n\s*\n+", text or "") 
        if p and p.strip()
    ]
    return paragraphs


def _paragraph_fallback_blocks(text: str, section_id: str = "fallback") -> List[Dict[str, any]]:
    """Fallback splitter: one paragraph per semantic block."""
    paragraphs = _split_into_paragraphs(text)
    blocks: List[Dict[str, any]] = []

    for index, paragraph in enumerate(paragraphs, start=1):
        blocks.append(
            {
                "block_id": f"{section_id}_p{index}",
                "heading": _extract_section_header(paragraph) or "Paragraph Block",
                "content": paragraph,
                "token_count": _token_count(paragraph),
            }
        )

    return blocks


def _detect_section_boundaries(text: str) -> List[int]:
    """Find positions of major section headers in text."""
    boundaries = [0]  # Always start at beginning
    
    for match in SECTION_PATTERN.finditer(text):
        boundaries.append(match.start())
    
    # If no sections detected, split by major paragraph breaks (triple newlines)
    if len(boundaries) <= 1:
        for match in re.finditer(r"\n\s*\n\s*\n", text):
            boundaries.append(match.start())
    
    boundaries.append(len(text))
    return sorted(set(boundaries))


def _extract_blocks_from_section(section_text: str, section_id: str) -> List[Dict[str, any]]:
    """
    Extract semantic blocks from a single section.
    
    Strategy:
    1. If section is small (< MAX_BLOCK_TOKENS), treat as single block
    2. If section is large, group paragraphs into blocks of 200-800 tokens
    3. Never break mid-paragraph
    """
    
    if not section_text or not section_text.strip():
        return []
    
    section_tokens = _token_count(section_text)
    
    # Small section → single block
    if section_tokens < MAX_BLOCK_TOKENS:
        return [{
            "block_id": f"{section_id}_full",
            "heading": _extract_section_header(section_text),
            "content": section_text.strip(),
            "token_count": section_tokens,
        }]
    
    # Large section → group paragraphs into blocks
    paragraphs = _split_into_paragraphs(section_text)
    if not paragraphs:
        return [{
            "block_id": f"{section_id}_full",
            "heading": _extract_section_header(section_text),
            "content": section_text.strip(),
            "token_count": section_tokens,
        }]
    
    blocks = []
    current_block = []
    current_tokens = 0
    block_counter = 0
    
    for para in paragraphs:
        para_tokens = _token_count(para)
        
        # If single paragraph exceeds max, force it into its own block anyway
        if para_tokens > MAX_BLOCK_TOKENS:
            # Flush current block if any
            if current_block:
                block_text = "\n\n".join(current_block)
                blocks.append({
                    "block_id": f"{section_id}_b{block_counter}",
                    "heading": _extract_section_header(section_text),
                    "content": block_text.strip(),
                    "token_count": _token_count(block_text),
                })
                current_block = []
                current_tokens = 0
                block_counter += 1
            
            # Add oversized paragraph as single block
            blocks.append({
                "block_id": f"{section_id}_b{block_counter}",
                "heading": _extract_section_header(section_text),
                "content": para.strip(),
                "token_count": para_tokens,
            })
            block_counter += 1
            continue
        
        # If adding this paragraph keeps us under target or target+50%, add it
        if current_tokens + para_tokens <= TARGET_BLOCK_TOKENS + 200:
            current_block.append(para)
            current_tokens += para_tokens
        else:
            # Block is full, flush it
            if current_block:
                block_text = "\n\n".join(current_block)
                blocks.append({
                    "block_id": f"{section_id}_b{block_counter}",
                    "heading": _extract_section_header(section_text),
                    "content": block_text.strip(),
                    "token_count": _token_count(block_text),
                })
                block_counter += 1
            
            # Start new block with current paragraph
            current_block = [para]
            current_tokens = para_tokens
    
    # Flush remaining block
    if current_block:
        block_text = "\n\n".join(current_block)
        blocks.append({
            "block_id": f"{section_id}_b{block_counter}",
            "heading": _extract_section_header(section_text),
            "content": block_text.strip(),
            "token_count": _token_count(block_text),
        })
    
    return blocks


def _with_block_metadata(blocks: List[Dict[str, any]], file_name: str | None = None, page_number: int | None = None) -> List[Dict[str, any]]:
    normalized = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        content = str(block.get("content") or "").strip()
        enriched = {
            **block,
            "text": content,
            "source": file_name,
            "page": page_number,
        }
        normalized.append(enriched)
    return normalized


def extract_semantic_blocks(
    text: str,
    file_name: str | None = None,
    page_number: int | None = None,
    log_output: bool = True,
) -> List[Dict[str, any]]:
    """
    Extract semantic blocks from regulatory document.
    
    Returns list of blocks:
    {
        "block_id": "uniqueID",
        "heading": "section title",
        "content": "full regulatory text",
        "token_count": 300
    }
    """
    
    if not text or not text.strip():
        if file_name and log_output:
            print(f"📄 {file_name} -> Blocks: 0")
        return []
    
    # Find section boundaries
    boundaries = _detect_section_boundaries(text)
    
    blocks = []
    
    # If no or very few boundaries found, treat entire document as single section
    # and group by paragraphs
    if len(boundaries) <= 2:
        direct_blocks = _extract_blocks_from_section(text.strip(), "doc")
        direct_blocks = _with_block_metadata(direct_blocks, file_name=file_name, page_number=page_number)
        if file_name and log_output:
            print(f"📄 {file_name} -> Blocks: {len(direct_blocks)}")
        return direct_blocks
    
    # Extract each section separately
    for idx in range(len(boundaries) - 1):
        start = boundaries[idx]
        end = boundaries[idx + 1]
        section_text = text[start:end].strip()
        
        if section_text and len(section_text.split()) >= 20:  # Minimum content threshold
            section_blocks = _extract_blocks_from_section(
                section_text, 
                f"sec{idx}"
            )
            blocks.extend(section_blocks)
    
    # If sectioning failed or produced nothing, fall back to whole-document grouping
    if not blocks:
        blocks = _extract_blocks_from_section(text.strip(), "doc")
    
    # Quality check: filter out very small blocks
    valid_blocks = [
        b for b in blocks
        if b.get("token_count", 0) >= 30  # Allow smaller blocks as minimum
    ]
    
    # If quality check filtered everything, return original blocks
    if not valid_blocks:
        valid_blocks = blocks
    
    # Enforce fallback split when semantic pass under-segments.
    if len(valid_blocks) < MIN_BLOCK_COUNT:
        fallback_blocks = _paragraph_fallback_blocks(text.strip(), section_id="doc")
        if len(fallback_blocks) > len(valid_blocks):
            valid_blocks = fallback_blocks

    # Logging metrics (logger only; terminal output is concise per PDF).
    total_tokens = sum(b.get("token_count", 0) for b in valid_blocks)
    avg_tokens = total_tokens // len(valid_blocks) if valid_blocks else 0
    
    logger.info(
        "Semantic blocks extracted: total_blocks=%s avg_tokens=%s total_tokens=%s",
        len(valid_blocks),
        avg_tokens,
        total_tokens
    )
    
    valid_blocks = _with_block_metadata(valid_blocks, file_name=file_name, page_number=page_number)

    if file_name and log_output:
        print(f"📄 {file_name} -> Blocks: {len(valid_blocks)}")

    return valid_blocks


def extract_semantic_blocks_from_pages(page_records: List[Dict[str, any]], file_name: str | None = None) -> List[Dict[str, any]]:
    """Extract semantic blocks per-page while retaining source/page metadata."""
    combined_blocks: List[Dict[str, any]] = []
    source_label = file_name or "unknown.pdf"

    for page in page_records or []:
        if not isinstance(page, dict):
            continue
        page_text = str(page.get("text") or "").strip()
        if not page_text:
            continue
        page_number = page.get("page_number")
        page_blocks = extract_semantic_blocks(
            page_text,
            file_name=source_label,
            page_number=page_number if isinstance(page_number, int) else None,
            log_output=False,
        )
        combined_blocks.extend(page_blocks)

    print(f"📄 {source_label} -> Blocks: {len(combined_blocks)}")
    return combined_blocks
