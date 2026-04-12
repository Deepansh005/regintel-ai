"""
Smart Semantic Block Matcher

Matches OLD and NEW regulatory blocks by semantic similarity.
NO random pairing. Each NEW block matched to BEST OLD block only.

Uses cosine similarity on text to find semantically similar blocks.
"""

import logging
import re
from typing import Dict, List, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def _normalize_for_similarity(text: str) -> str:
    """Normalize text for comparison."""
    # Convert to lowercase
    text = text.lower()
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove special characters but keep structure
    text = re.sub(r"[^\w\s\-./()%]", "", text)
    return text.strip()


def _extract_key_terms(text: str, limit: int = 10) -> set:
    """Extract key regulatory terms for matching."""
    normalized = _normalize_for_similarity(text)
    
    # Split into words
    words = normalized.split()
    
    # Filter for meaningful words (> 4 chars, not common words)
    common_words = {
        "the", "and", "or", "is", "are", "have", "has", "be", "been", "being",
        "this", "that", "these", "those", "with", "from", "to", "in", "on", "at"
    }
    
    key_terms = [
        w for w in words
        if len(w) > 4 and w not in common_words
    ]
    
    return set(key_terms[:limit])


def _heading_similarity(old_heading: str, new_heading: str) -> float:
    """Calculate similarity between two headings (0.0 to 1.0)."""
    if not old_heading or not new_heading:
        return 0.0
    
    old_norm = _normalize_for_similarity(old_heading)
    new_norm = _normalize_for_similarity(new_heading)
    
    # Exact or near-exact match
    if old_norm == new_norm:
        return 1.0
    
    # Use SequenceMatcher for fuzzy matching
    ratio = SequenceMatcher(None, old_norm, new_norm).ratio()
    return ratio


def _content_similarity(old_content: str, new_content: str) -> float:
    """
    Calculate content similarity using:
    1. Key term overlap
    2. Sequence matching on normalized text
    """
    if not old_content or not new_content:
        return 0.0
    
    # Extract key terms
    old_terms = _extract_key_terms(old_content)
    new_terms = _extract_key_terms(new_content)
    
    if not old_terms and not new_terms:
        return 0.0
    
    # Term overlap score
    if old_terms and new_terms:
        overlap = len(old_terms & new_terms)
        union = len(old_terms | new_terms)
        term_similarity = overlap / union if union > 0 else 0.0
    else:
        term_similarity = 0.0
    
    # Sequence matching on first 500 chars (preview)
    old_preview = _normalize_for_similarity(old_content[:500])
    new_preview = _normalize_for_similarity(new_content[:500])
    
    sequence_similarity = SequenceMatcher(None, old_preview, new_preview).ratio()
    
    # Weighted average (term similarity more important for regulatory text)
    combined = (term_similarity * 0.6) + (sequence_similarity * 0.4)
    
    return combined


def match_blocks(
    old_blocks: List[Dict],
    new_blocks: List[Dict],
    heading_match_threshold: float = 0.6,
    content_match_threshold: float = 0.5,
) -> List[Dict]:
    """
    Match NEW blocks to OLD blocks.
    
    Strategy:
    1. For each NEW block, find BEST OLD block by combined similarity
    2. Combined score = (heading_sim * 0.4) + (content_sim * 0.6)
    3. Track unmatched OLD blocks (removed content)
    4. Track unmatched NEW blocks (added content)
    
    Returns list of match records:
    {
        "match_type": "matched|added|removed",
        "old_block": {...},
        "new_block": {...},
        "match_score": 0.75,
        "heading_similarity": 0.8,
        "content_similarity": 0.7
    }
    """
    
    old_items = [b for b in (old_blocks or []) if isinstance(b, dict)]
    new_items = [b for b in (new_blocks or []) if isinstance(b, dict)]
    
    if not old_items:
        # All new blocks are "added"
        return [
            {
                "match_type": "added",
                "old_block": None,
                "new_block": b,
                "match_score": 1.0,
                "heading_similarity": 0.0,
                "content_similarity": 0.0,
            }
            for b in new_items
        ]
    
    if not new_items:
        # All old blocks are "removed"
        return [
            {
                "match_type": "removed",
                "old_block": b,
                "new_block": None,
                "match_score": 1.0,
                "heading_similarity": 0.0,
                "content_similarity": 0.0,
            }
            for b in old_items
        ]
    
    matches = []
    used_old_indices = set()
    used_new_indices = set()
    
    # First pass: match by heading similarity (primary)
    for new_idx, new_block in enumerate(new_items):
        new_heading = new_block.get("heading", "")
        old_idx_best = -1
        score_best = 0.0
        
        for old_idx, old_block in enumerate(old_items):
            if old_idx in used_old_indices:
                continue
            
            old_heading = old_block.get("heading", "")
            h_sim = _heading_similarity(old_heading, new_heading)
            
            if h_sim > score_best and h_sim >= heading_match_threshold:
                score_best = h_sim
                old_idx_best = old_idx
        
        if old_idx_best >= 0:
            old_block = old_items[old_idx_best]
            new_block_content = new_block.get("content", "")
            old_block_content = old_block.get("content", "")
            
            c_sim = _content_similarity(old_block_content, new_block_content)
            combined_score = (score_best * 0.4) + (c_sim * 0.6)
            
            matches.append({
                "match_type": "matched",
                "old_block": old_block,
                "new_block": new_block,
                "match_score": round(combined_score, 3),
                "heading_similarity": round(score_best, 3),
                "content_similarity": round(c_sim, 3),
            })
            
            used_old_indices.add(old_idx_best)
            used_new_indices.add(new_idx)
    
    # Second pass: match remaining NEW blocks by content similarity
    for new_idx, new_block in enumerate(new_items):
        if new_idx in used_new_indices:
            continue
        
        new_content = new_block.get("content", "")
        old_idx_best = -1
        score_best = 0.0
        
        for old_idx, old_block in enumerate(old_items):
            if old_idx in used_old_indices:
                continue
            
            old_content = old_block.get("content", "")
            c_sim = _content_similarity(old_content, new_content)
            
            if c_sim > score_best and c_sim >= content_match_threshold:
                score_best = c_sim
                old_idx_best = old_idx
        
        if old_idx_best >= 0:
            old_block = old_items[old_idx_best]
            combined_score = score_best
            
            matches.append({
                "match_type": "matched",
                "old_block": old_block,
                "new_block": new_block,
                "match_score": round(combined_score, 3),
                "heading_similarity": 0.0,
                "content_similarity": round(score_best, 3),
            })
            
            used_old_indices.add(old_idx_best)
            used_new_indices.add(new_idx)
    
    # Third pass: mark remaining blocks as removed/added
    for old_idx, old_block in enumerate(old_items):
        if old_idx not in used_old_indices:
            matches.append({
                "match_type": "removed",
                "old_block": old_block,
                "new_block": None,
                "match_score": 1.0,
                "heading_similarity": 0.0,
                "content_similarity": 0.0,
            })
    
    for new_idx, new_block in enumerate(new_items):
        if new_idx not in used_new_indices:
            matches.append({
                "match_type": "added",
                "old_block": None,
                "new_block": new_block,
                "match_score": 1.0,
                "heading_similarity": 0.0,
                "content_similarity": 0.0,
            })
    
    # Logging
    matched_count = len([m for m in matches if m["match_type"] == "matched"])
    added_count = len([m for m in matches if m["match_type"] == "added"])
    removed_count = len([m for m in matches if m["match_type"] == "removed"])
    
    logger.info(
        "Block matching complete: matched=%s added=%s removed=%s",
        matched_count,
        added_count,
        removed_count
    )
    
    print(f"\n🔗 Block Matching Results:")
    print(f"   Matched: {matched_count}")
    print(f"   Added: {added_count}")
    print(f"   Removed: {removed_count}")
    print()
    
    return matches
