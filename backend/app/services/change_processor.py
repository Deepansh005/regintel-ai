"""
Change Validation & Output Processing Pipeline

Phases 5-9:
- Hard validation layer (reject vague/duplicate/short)
- Deduplication by change signature
- Clean terminal output
- Logging & debugging
- Fallback for edge cases
"""

import hashlib
import json
import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Hard validation parameters
VAGUE_TERMS = {
    "improve", "enhance", "develop", "refine",
    "various", "etc", "and so on",
    "more", "less", "better", "worse",
    "strengthen", "weaken", "adjust",
    "modify", "update", "change"
}

MIN_CHANGE_LENGTH = 15  # Characters
MIN_STATEMENT_WORDS = 3


def _normalize_for_comparison(text: str) -> str:
    """Normalize text for deduplication."""
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)  # Collapse whitespace
    text = re.sub(r"[^\w\s\-./()%]", "", text)  # Remove special chars
    return text.strip()


def _create_change_signature(change: Dict) -> str:
    """Create unique signature for change deduplication."""
    
    change_type = str(change.get("type", "")).strip().lower()
    statement = _normalize_for_comparison(str(change.get("statement", "")))
    old_text = _normalize_for_comparison(str(change.get("old_text", "")))
    new_text = _normalize_for_comparison(str(change.get("new_text", "")))
    
    # Create sig: type|statement|old_hash|new_hash
    sig_parts = [
        change_type,
        statement[:50],  # First 50 chars of statement
        hashlib.md5(old_text.encode()).hexdigest()[:6],
        hashlib.md5(new_text.encode()).hexdigest()[:6],
    ]
    
    return "|".join(sig_parts)


def validate_change(change: Dict) -> Tuple[bool, str]:
    """
    Validate individual change entry.
    
    Returns (is_valid, reason)
    """
    
    if not isinstance(change, dict):
        return False, "not_a_dict"
    
    # Must have type
    change_type = str(change.get("type", "")).strip().lower()
    if change_type not in {"added", "removed", "modified"}:
        return False, f"invalid_type:{change_type}"
    
    # Must have statement
    statement = str(change.get("statement", "")).strip()
    if not statement:
        return False, "empty_statement"
    
    if len(statement) < MIN_CHANGE_LENGTH:
        return False, f"statement_too_short:{len(statement)}"
    
    if len(statement.split()) < MIN_STATEMENT_WORDS:
        return False, "too_few_words"
    
    # Check for vague terms
    statement_lower = statement.lower()
    found_vague = [term for term in VAGUE_TERMS if term in statement_lower]
    if found_vague:
        return False, f"vague_terms:{found_vague[0]}"
    
    # For modified changes: old and new must differ
    if change_type == "modified":
        old_text = str(change.get("old_text", "")).strip()
        new_text = str(change.get("new_text", "")).strip()
        
        if not old_text or not new_text:
            return False, "modified_missing_text"
        
        old_norm = _normalize_for_comparison(old_text)
        new_norm = _normalize_for_comparison(new_text)
        
        if old_norm == new_norm:
            return False, "old_equals_new"
    
    # For added: must have new_text
    if change_type == "added":
        new_text = str(change.get("new_text", "")).strip()
        if not new_text:
            return False, "added_no_new_text"
    
    # For removed: must have old_text
    if change_type == "removed":
        old_text = str(change.get("old_text", "")).strip()
        if not old_text:
            return False, "removed_no_old_text"
    
    return True, "valid"


def hard_validate_changes(changes: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Apply hard validation layer to all changes.
    
    Returns:
    - Filtered valid changes
    - Stats dict
    """
    
    valid = []
    stats = {
        "input_count": len(changes),
        "valid_count": 0,
        "rejected": {},
    }
    
    for change in changes or []:
        is_valid, reason = validate_change(change)
        
        if is_valid:
            valid.append(change)
            stats["valid_count"] += 1
        else:
            stats["rejected"][reason] = stats["rejected"].get(reason, 0) + 1
    
    logger.info(
        "Hard validation: input=%s valid=%s rejected=%s",
        stats["input_count"],
        stats["valid_count"],
        stats["input_count"] - stats["valid_count"]
    )
    
    return valid, stats


def deduplicate_changes(changes: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Deduplicate changes by signature.
    
    Returns:
    - Deduplicated changes
    - Stats dict
    """
    
    seen_sigs = set()
    deduped = []
    removed_count = 0
    
    for change in changes or []:
        sig = _create_change_signature(change)
        
        if sig in seen_sigs:
            removed_count += 1
            continue
        
        seen_sigs.add(sig)
        deduped.append(change)
    
    stats = {
        "input_count": len(changes),
        "output_count": len(deduped),
        "duplicates_removed": removed_count,
    }
    
    logger.info(
        "Deduplication: input=%s output=%s removed=%s",
        stats["input_count"],
        stats["output_count"],
        stats["duplicates_removed"]
    )
    
    return deduped, stats


def limit_output_changes(changes: List[Dict], max_count: int = 15) -> List[Dict]:
    """Limit output to top N most relevant changes."""
    
    if len(changes) <= max_count:
        return changes
    
    # Simple heuristic: prioritize "modified" over "added/removed"
    modified = [c for c in changes if c.get("type") == "modified"]
    rest = [c for c in changes if c.get("type") != "modified"]
    
    # Return modified first, then others
    combined = modified + rest
    return combined[:max_count]


def render_final_output(changes: List[Dict]) -> str:
    """
    Render clean terminal output.
    
    Format:
    FINAL CHANGES
    - <type>: <statement>
      old: <old_text>
      new: <new_text>
    """
    
    if not changes:
        return "FINAL CHANGES\n(No changes detected)"
    
    lines = ["FINAL CHANGES"]
    lines.append("-" * 60)
    
    for idx, change in enumerate(changes, 1):
        change_type = str(change.get("type", "")).upper()
        statement = str(change.get("statement", "")).strip()
        old_text = str(change.get("old_text", "")).strip()
        new_text = str(change.get("new_text", "")).strip()
        
        lines.append(f"{idx}. [{change_type}] {statement}")
        
        if old_text:
            # Wrap long text
            if len(old_text) > 80:
                old_text = old_text[:77] + "..."
            lines.append(f"   OLD: {old_text}")
        
        if new_text:
            if len(new_text) > 80:
                new_text = new_text[:77] + "..."
            lines.append(f"   NEW: {new_text}")
        
        lines.append("")
    
    lines.append("-" * 60)
    lines.append(f"Total changes: {len(changes)}")
    
    return "\n".join(lines)


def process_changes_pipeline(
    raw_changes: List[Dict],
    max_output: int = 15,
    debug: bool = False
) -> Tuple[List[Dict], Dict]:
    """
    Complete change processing pipeline:
    1. Hard validation
    2. Deduplication
    3. Limiting to max output
    
    Returns:
    - Final clean changes
    - Combined stats
    """
    
    print("\n🔍 Processing Changes Pipeline...")
    
    # Step 1: Hard validation
    valid_changes, val_stats = hard_validate_changes(raw_changes)
    print(f"   After validation: {val_stats['valid_count']}/{val_stats['input_count']}")
    
    # Step 2: Deduplication
    deduped_changes, dedup_stats = deduplicate_changes(valid_changes)
    print(f"   After dedup: {dedup_stats['output_count']}/{dedup_stats['input_count']}")
    
    # Step 3: Limit output
    final_changes = limit_output_changes(deduped_changes, max_count=max_output)
    print(f"   Final output: {len(final_changes)} (limited to {max_output})")
    print()
    
    # Render output
    output_text = render_final_output(final_changes)
    print(output_text)
    
    # Combined stats
    combined_stats = {
        "input_changes": val_stats["input_count"],
        "after_validation": val_stats["valid_count"],
        "after_dedup": dedup_stats["output_count"],
        "final_output": len(final_changes),
        "validation_rejections": sum(val_stats["rejected"].values()),
        "dedup_duplicates": dedup_stats["duplicates_removed"],
    }
    
    logger.info(
        "Pipeline complete: input=%s final=%s",
        combined_stats["input_changes"],
        combined_stats["final_output"]
    )
    
    return final_changes, combined_stats


def fallback_paragraph_comparison(
    old_text: str,
    new_text: str,
    limit: int = 3
) -> List[Dict]:
    """
    Fallback: If semantic block comparison fails or returns no changes,
    do high-level paragraph comparison.
    
    This is NOT fine-grained matching, just detecting if document structure changed.
    """
    
    logger.info("Fallback: Performing paragraph-level comparison")
    
    old_paras = [p.strip() for p in old_text.split('\n\n') if p.strip()]
    new_paras = [p.strip() for p in new_text.split('\n\n') if p.strip()]
    
    changes = []
    
    if len(old_paras) != len(new_paras):
        changes.append({
            "type": "modified" if len(old_paras) == len(new_paras) else "modified",
            "statement": f"Document structure changed: {len(old_paras)} → {len(new_paras)} major sections",
            "old_text": f"{len(old_paras)} sections",
            "new_text": f"{len(new_paras)} sections",
        })
    
    return changes[:limit]
