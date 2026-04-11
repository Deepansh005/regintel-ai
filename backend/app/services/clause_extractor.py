import logging
import os
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

MIN_CLAUSE_TOKENS = 50
MAX_CLAUSE_TOKENS = 800
CLAUSE_DEBUG = os.getenv("CLAUSE_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
MAX_HEADING_PREVIEW = 5
MAX_CLAUSE_PREVIEW = 5

# Regex-based heading matcher for splitting by heading boundaries.
# Supports:
# - Numbered: 1., 1.1, 2.3.1
# - Lettered: A., B., C.
# - Chapter: Chapter I, Chapter II, Chapter 1
# - Section: Section 5, Section 6
HEADING_SPLIT_PATTERN = re.compile(
    r"(?im)(?:^|\n)\s*"
    r"(?P<marker>"
    r"\(\d+(?:\.\d+)*\)|"
    r"\d+(?:\.\d+)*\.?|"
    r"[A-Z]\."
    r"|"
    r"Chapter(?:\s+(?:[IVXLCM]+|\d+))?|"
    r"Section(?:\s+(?:\d+|[A-Z]))?"
    r")"
    r"(?:\s+(?P<title>[^\n]*))?"
)


def _token_count(text: str) -> int:
    """Count tokens (words) in text."""
    return len(re.findall(r"\S+", text or ""))


def _debug_print(message: str) -> None:
    if CLAUSE_DEBUG:
        print(message)


def _legacy_paragraph_split(text: str) -> List[str]:
    """Split text by double newlines (paragraph breaks)."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text or "") if part and part.strip()]
    return paragraphs


def _extract_heading_text(line: str) -> str:
    """Extract the heading text from a line."""
    line = line.strip()
    # Remove heading markers to get the actual title
    line = re.sub(r"^\(\d+(?:\.\d+)*\)\s*", "", line)
    line = re.sub(r"^[\d.]+\s*[.)]?\s*", "", line)  # Remove numbered prefix
    line = re.sub(r"^[A-Z]\.\s*", "", line)  # Remove letter prefix
    line = re.sub(r"^(?:Chapter|Section)\s*(?:[IVXivx\d]+|[A-Z])?\s*", "", line)  # Remove chapter/section
    return line.strip()


def _detect_headings(text: str) -> List[Tuple[int, int, str, str]]:
    """
    Detect heading boundaries using regex-based matching.
    Returns list of tuples:
    (match_start, match_end, heading_marker, heading_title)
    """
    hits: List[Tuple[int, int, str, str]] = []
    for match in HEADING_SPLIT_PATTERN.finditer(text):
        marker = (match.group("marker") or "").strip()
        title = (match.group("title") or "").strip()
        if marker:
            hits.append((match.start(), match.end(), marker, title))
    return hits


def _split_by_headings(text: str) -> List[Dict[str, str]]:
    """
    Split text by detected headings (primary strategy).
    Returns list of clauses with clause_id, title, and content.
    """
    heading_hits = _detect_headings(text)

    if not heading_hits:
        return []

    clauses: List[Dict[str, str]] = []
    headings_preview: List[str] = []

    for idx, (match_start, match_end, marker, title) in enumerate(heading_hits):
        next_start = heading_hits[idx + 1][0] if idx + 1 < len(heading_hits) else len(text)
        content = text[match_start:next_start].strip()

        if content:
            clauses.append({
                "clause_id": marker.strip().strip("().") or f"c{idx + 1}",
                "title": title or _extract_heading_text(marker) or f"Clause {idx + 1}",
                "content": content,
                "has_heading": True,
            })

        headings_preview.append(f"{marker} {title}".strip())

    _debug_print(f"[DEBUG] Headings detected: {len(heading_hits)}")
    _debug_print(f"[DEBUG] Heading markers (first 10): {headings_preview[:10]}")

    return clauses


def _print_pdf_summary(
    pdf_name: str,
    total_clauses: int,
    avg_clause_size: int,
    min_clause_size: int,
    max_clause_size: int,
    total_tokens: int,
    headings_detected: List[str],
    clauses: List[Dict[str, str]],
) -> None:
    print("\n" + "=" * 70)
    print(f"📄 PDF: {pdf_name}")
    print("-" * 70)
    print(f"Total clauses: {total_clauses}")
    print(f"Tokens avg/min/max: {avg_clause_size}/{min_clause_size}/{max_clause_size}")
    print(f"Total tokens: {total_tokens}")

    if not CLAUSE_DEBUG:
        print("=" * 70)
        return

    print("-" * 70)
    print("Top headings")
    if headings_detected:
        for index, heading in enumerate(headings_detected[:MAX_HEADING_PREVIEW], start=1):
            print(f"{index}. {heading}")
    else:
        print("No headings detected")

    print("-" * 70)
    print("Clause preview")
    for clause in clauses[:MAX_CLAUSE_PREVIEW]:
        print(
            f"id={clause.get('clause_id')} | heading={clause.get('title')} | tokens={_token_count(clause.get('content') or '')}"
        )

    print("=" * 70)


def extract_clauses_from_page(page_text: str, page_number: int | None = None, source_file_name: str | None = None) -> List[Dict[str, str]]:
    """Extract clauses from a single page and preserve page metadata."""
    clauses = extract_clauses_from_text(page_text)
    annotated: List[Dict[str, str]] = []

    for clause in clauses:
        item = dict(clause)
        if page_number is not None:
            item["page_number"] = page_number
        if source_file_name:
            item["source_file_name"] = source_file_name
        annotated.append(item)

    if page_number is not None:
        _debug_print(f"[DEBUG] Page {page_number}: clauses={len(annotated)}")

    return annotated


def extract_clauses_from_pages(page_records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Extract clauses page-wise and then combine results in order."""
    combined: List[Dict[str, str]] = []
    headings_detected: List[str] = []
    pdf_name = "unknown.pdf"

    for page_record in page_records or []:
        page_number = page_record.get("page_number")
        page_text = page_record.get("text") or ""
        source_file_name = page_record.get("source_file_name")

        if source_file_name:
            pdf_name = source_file_name

        if not page_text.strip():
            continue

        for _, _, marker, title in _detect_headings(page_text):
            headings_detected.append(f"{marker} {title}".strip())

        page_clauses = extract_clauses_from_page(
            page_text,
            page_number=page_number,
            source_file_name=source_file_name,
        )
        combined.extend(page_clauses)

        _debug_print(f"[DEBUG] Page {page_number}: clause_count={len(page_clauses)}")

    total_clauses = len(combined)
    clause_sizes = [_token_count(c.get("content") or "") for c in combined]
    total_tokens = sum(clause_sizes)
    avg_clause_size = int(round(total_tokens / total_clauses)) if total_clauses else 0
    min_clause_size = min(clause_sizes, default=0)
    max_clause_size = max(clause_sizes, default=0)

    # Deduplicate headings while preserving order.
    seen_headings = set()
    unique_headings = []
    for heading in headings_detected:
        normalized_heading = heading.strip().lower()
        if normalized_heading and normalized_heading not in seen_headings:
            seen_headings.add(normalized_heading)
            unique_headings.append(heading)

    _print_pdf_summary(
        pdf_name=pdf_name,
        total_clauses=total_clauses,
        avg_clause_size=avg_clause_size,
        min_clause_size=min_clause_size,
        max_clause_size=max_clause_size,
        total_tokens=total_tokens,
        headings_detected=unique_headings,
        clauses=combined,
    )

    if total_clauses < 10:
        logger.warning("Low clause count detected: %s clauses", total_clauses)

    return combined


def _split_text_to_max_tokens(text: str, max_tokens: int) -> List[str]:
    """Split text into chunks that do not exceed max_tokens."""
    paragraphs = _legacy_paragraph_split(text)
    if not paragraphs:
        return []

    parts: List[str] = []
    current = ""

    def flush_current() -> None:
        nonlocal current
        if current.strip():
            parts.append(current.strip())
            current = ""

    def add_fragment(fragment: str) -> None:
        nonlocal current
        fragment = fragment.strip()
        if not fragment:
            return

        candidate = f"{current}\n\n{fragment}".strip() if current else fragment
        if _token_count(candidate) <= max_tokens:
            current = candidate
            return

        flush_current()

        if _token_count(fragment) <= max_tokens:
            current = fragment
            return

        # Split by sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", fragment) if s and s.strip()]
        sentence_buf = ""
        for sentence in sentences:
            sentence_candidate = f"{sentence_buf} {sentence}".strip() if sentence_buf else sentence
            if _token_count(sentence_candidate) <= max_tokens:
                sentence_buf = sentence_candidate
                continue

            if sentence_buf:
                parts.append(sentence_buf.strip())
                sentence_buf = ""

            if _token_count(sentence) <= max_tokens:
                sentence_buf = sentence
                continue

            # Split by words as last resort
            words = sentence.split()
            word_buf: List[str] = []
            for word in words:
                word_candidate = " ".join(word_buf + [word]).strip()
                if _token_count(word_candidate) <= max_tokens:
                    word_buf.append(word)
                else:
                    if word_buf:
                        parts.append(" ".join(word_buf).strip())
                    word_buf = [word]
            if word_buf:
                parts.append(" ".join(word_buf).strip())

        if sentence_buf:
            parts.append(sentence_buf.strip())

    for paragraph in paragraphs:
        add_fragment(paragraph)

    flush_current()
    return [part for part in parts if part.strip()]


def _merge_small_clauses(clauses: List[Dict[str, str]], min_tokens: int) -> List[Dict[str, str]]:
    """
    Merge clauses that are smaller than min_tokens with the next clause.
    """
    if not clauses:
        return []

    merged: List[Dict[str, str]] = []
    index = 0

    # Pairwise merge only for paragraph-only clauses; heading-based clauses stay separate.
    while index < len(clauses):
        current = clauses[index]
        current_tokens = _token_count(current["content"])

        if (
            current_tokens < min_tokens
            and not current.get("has_heading")
            and index + 1 < len(clauses)
            and not clauses[index + 1].get("has_heading")
        ):
            next_clause = clauses[index + 1]
            merged.append(
                {
                    "clause_id": current["clause_id"],
                    "title": f"{current['title']} + {next_clause['title']}",
                    "content": f"{current['content']}\n\n{next_clause['content']}".strip(),
                    "has_heading": False,
                }
            )
            index += 2
            continue

        merged.append(current)
        index += 1

    return merged


def _split_large_clauses(clauses: List[Dict[str, str]], max_tokens: int) -> List[Dict[str, str]]:
    """
    Split clauses larger than max_tokens into multiple parts.
    """
    result: List[Dict[str, str]] = []
    
    for clause in clauses:
        if _token_count(clause["content"]) <= max_tokens:
            result.append(clause)
            continue
        
        # Split this clause into smaller parts
        parts = _split_text_to_max_tokens(clause["content"], max_tokens)
        
        for part_idx, part in enumerate(parts, start=1):
            result.append({
                "clause_id": f"{clause['clause_id']}.{part_idx}" if part_idx > 1 else clause['clause_id'],
                "title": f"{clause['title']} (Part {part_idx}/{len(parts)})" if len(parts) > 1 else clause['title'],
                "content": part,
                "has_heading": clause.get("has_heading", False),
            })
    
    return result


def _build_clause(title: str, clause_id: str, content: str) -> Dict[str, str]:
    """Build a normalized clause dict."""
    clean_title = (title or "").strip() or "Untitled Clause"
    clean_content = (content or "").strip()
    return {
        "clause_id": str(clause_id),
        "title": clean_title,
        "content": clean_content,
        "has_heading": False,
    }


def extract_clauses_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extract ordered clauses from text using enhanced heading detection.

    Strategy order:
    1. Detect structured headings (numbered, lettered, chapter/section patterns)
    2. Fall back to paragraph splitting (double newline)
    3. Enforce size bounds: merge small (<200 tokens), split large (>800 tokens)
    4. Return deduplicated clauses in order

    Returns:
        List of dicts with 'clause_id', 'title', 'content' keys
    """
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        _debug_print("[DEBUG] Empty input text, returning empty clauses")
        return []

    _debug_print("[DEBUG] Starting clause extraction")
    _debug_print(f"[DEBUG] Input text length: {len(normalized)} chars")

    # Strategy 1: Try to detect structured headings
    base_clauses = _split_by_headings(normalized)

    # Strategy 2: Fallback to paragraph splitting if no headings found
    if not base_clauses:
        _debug_print("[DEBUG] No structured headings detected, falling back to paragraph splitting")
        paragraphs = _legacy_paragraph_split(normalized)
        _debug_print(f"[DEBUG] Extracted {len(paragraphs)} paragraphs")
        
        for para_index, paragraph in enumerate(paragraphs, start=1):
            if paragraph.strip():
                base_clauses.append(_build_clause(
                    title=f"Paragraph {para_index}",
                    clause_id=f"p{para_index}",
                    content=paragraph
                ))

    if not base_clauses:
        _debug_print("[DEBUG] No clauses created, returning empty")
        return []

    _debug_print(f"[DEBUG] Base clauses created: {len(base_clauses)}")
    
    # Strategy 3: Split large clauses (>800 tokens)
    sized_clauses = _split_large_clauses(base_clauses, MAX_CLAUSE_TOKENS)
    _debug_print(f"[DEBUG] After splitting large clauses: {len(sized_clauses)}")

    # Strategy 4: Merge only very small paragraph-only clauses (<50 tokens)
    merged_clauses = _merge_small_clauses(sized_clauses, MIN_CLAUSE_TOKENS)
    _debug_print(f"[DEBUG] After merging small clauses: {len(merged_clauses)}")

    # Strategy 5: Deduplicate IDs (in case merges/splits create collisions)
    seen_ids = set()
    ordered_clauses: List[Dict[str, str]] = []
    
    for clause in merged_clauses:
        clause_id = clause["clause_id"]
        suffix = 1
        
        while clause_id in seen_ids:
            suffix += 1
            clause_id = f"{clause['clause_id']}_{suffix}"
        
        seen_ids.add(clause_id)
        ordered_clauses.append({
            "clause_id": clause_id,
            "title": clause["title"],
            "content": clause["content"],
        })

    # Calculate statistics
    clause_count = len(ordered_clauses)
    total_tokens = sum(_token_count(item["content"]) for item in ordered_clauses)
    avg_tokens = int(round(total_tokens / clause_count)) if clause_count > 0 else 0
    clause_sizes = [_token_count(item["content"]) for item in ordered_clauses]
    min_tokens_in_clause = min(
        clause_sizes,
        default=0
    )
    max_tokens_in_clause = max(
        clause_sizes,
        default=0
    )

    # Keep this function lightweight; full structured report is printed in extract_clauses_from_pages.
    _debug_print(f"[DEBUG] Clause extraction summary: count={clause_count}, avg={avg_tokens}, min={min_tokens_in_clause}, max={max_tokens_in_clause}, total_tokens={total_tokens}")
    if clause_sizes:
        _debug_print(f"[DEBUG] Clause size distribution (first 25): {clause_sizes[:25]}")

    # Log to logger as well
    logger.info(
        "Extracted %s clauses (avg=%s tokens, min=%s, max=%s)",
        clause_count, avg_tokens, min_tokens_in_clause, max_tokens_in_clause
    )

    if clause_count < 10:
        logger.warning("Low clause count detected after extraction: %s clauses", clause_count)

    return ordered_clauses
