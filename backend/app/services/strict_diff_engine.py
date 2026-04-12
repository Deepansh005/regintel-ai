"""
Strict Legal Diff Engine

Deterministic comparison of regulatory blocks.
ONLY extracts explicit, factual differences.
NO interpretation, NO summarization, NO vague language.

Focus: numeric changes, conditions, obligations, additions, removals
"""

import json
import logging
import re
from typing import Dict, List, Tuple

from app.services.llm_router import call_groq_with_retry

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimation."""
    return len(text.split())


def _truncate_text(text: str, max_tokens: int = 500) -> str:
    """Truncate text to approximate token length."""
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens]) + "..."


def _parse_diff_response(content: str) -> Dict | None:
    """
    Parse LLM response expecting JSON structure:
    {
      "changes": [
        {
          "type": "added|removed|modified",
          "statement": "exact factual difference",
          "old_text": "...",
          "new_text": "..."
        }
      ]
    }
    """
    
    if not content or not isinstance(content, str):
        return None
    
    content = content.strip()
    
    # Try direct JSON parsing
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "changes" in data:
            return data
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON from markdown fence
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, re.IGNORECASE)
    if fence_match:
        try:
            data = json.loads(fence_match.group(1))
            if isinstance(data, dict) and "changes" in data:
                return data
        except json.JSONDecodeError:
            pass
    
    # Try extracting bare JSON object
    brace_match = re.search(r"\{[\s\S]*\}", content)
    if brace_match:
        try:
            data = json.loads(brace_match.group(0))
            if isinstance(data, dict) and "changes" in data:
                return data
        except json.JSONDecodeError:
            pass
    
    return None


def _is_valid_change(change: Dict) -> bool:
    """Validate change entry."""
    
    if not isinstance(change, dict):
        return False
    
    # Must have type
    change_type = str(change.get("type", "")).strip().lower()
    if change_type not in {"added", "removed", "modified"}:
        return False
    
    # Must have statement
    statement = str(change.get("statement", "")).strip()
    if not statement or len(statement) < 10:
        return False
    
    # old_text and new_text should differ
    old_text = str(change.get("old_text", "")).strip()
    new_text = str(change.get("new_text", "")).strip()
    
    # For "modified", both should exist and differ
    if change_type == "modified":
        if not old_text or not new_text or old_text == new_text:
            return False
    
    # For "added", must have new_text
    if change_type == "added":
        if not new_text:
            return False
    
    # For "removed", must have old_text
    if change_type == "removed":
        if not old_text:
            return False
    
    return True


def _contains_vague_terms(text: str) -> bool:
    """Check if text contains vague regulatory language."""
    
    vague_terms = [
        "improve", "enhance", "develop", "various",
        "more", "less", "better", "worse",
        "somehow", "some of", "etc",
        "generally", "typically", "usually",
        "could", "might", "may"  # uncertain language
    ]
    
    text_lower = text.lower()
    return any(term in text_lower for term in vague_terms)


def compare_blocks(old_block: Dict, new_block: Dict, debug: bool = False) -> List[Dict]:
    """
    Compare OLD and NEW regulatory blocks.
    
    Returns list of changes:
    [
        {
            "type": "added|removed|modified",
            "statement": "exact factual difference",
            "old_text": "original text",
            "new_text": "new text"
        }
    ]
    """
    
    # Extract content
    old_content = str(old_block.get("content", "") or "").strip() if old_block else ""
    new_content = str(new_block.get("content", "") or "").strip() if new_block else ""
    old_heading = str(old_block.get("heading", "") or "").strip() if old_block else ""
    new_heading = str(new_block.get("heading", "") or "").strip() if new_block else ""
    block_id = str(old_block.get("block_id", "") or new_block.get("block_id", "") or "unknown")
    
    # Handle added/removed blocks
    if not old_content and new_content:
        # Block was added
        return [{
            "type": "added",
            "statement": f"New regulatory requirement added: {new_heading or 'Untitled section'}",
            "old_text": "",
            "new_text": _truncate_text(new_content, 200),
            "block_id": block_id,
        }]
    
    if old_content and not new_content:
        # Block was removed
        return [{
            "type": "removed",
            "statement": f"Regulatory requirement removed: {old_heading or 'Untitled section'}",
            "old_text": _truncate_text(old_content, 200),
            "new_text": "",
            "block_id": block_id,
        }]
    
    if not old_content and not new_content:
        return []
    
    # Both exist → compare for modifications
    # Truncate for LLM (stay within token budget)
    old_for_llm = _truncate_text(old_content, 400)
    new_for_llm = _truncate_text(new_content, 400)
    
    # Construct comparison prompt
    prompt = f"""You are a legal diff engine. Extract ONLY explicit differences.

STRICT RULES:
- Only factual differences
- NO summarization
- NO interpretation
- NO generalization
- NO inferred meaning
- Compare actual text only

Focus ONLY on:
- numeric changes (%, limits, values, amounts)
- dates or timeframes
- conditions or requirements
- obligations (shall, must, required, should)
- explicit added/removed text

If NO difference exists → return {{"changes": []}}
Do NOT return empty descriptions.
Do NOT infer meaning.

Return ONLY valid JSON:
{{
  "changes": [
    {{
      "type": "added|removed|modified",
      "statement": "exact factual difference statement",
      "old_text": "exact original text",
      "new_text": "exact new text"
    }}
  ]
}}

OLD TEXT:
{old_for_llm}

NEW TEXT:
{new_for_llm}"""
    
    try:
        response = call_groq_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict JSON legal comparison tool. Return ONLY valid JSON matching the required schema.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_tokens=500,
            temperature=0.0,
            retries=1,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.error("LLM comparison failed for block %s: %s", block_id, exc)
        return []
    
    # Parse response
    parsed = _parse_diff_response(response)
    if not parsed or not isinstance(parsed.get("changes"), list):
        logger.warning("Failed to parse diff response for block %s", block_id)
        return []
    
    # Validate changes
    valid_changes = []
    
    for change in parsed.get("changes", []):
        if not _is_valid_change(change):
            if debug:
                logger.debug("Skipping invalid change: %s", change)
            continue
        
        statement = str(change.get("statement", "")).strip()
        
        # Reject vague language
        if _contains_vague_terms(statement):
            if debug:
                logger.debug("Skipping vague change: %s", statement)
            continue
        
        valid_changes.append({
            "type": change.get("type"),
            "statement": statement,
            "old_text": str(change.get("old_text", "")).strip(),
            "new_text": str(change.get("new_text", "")).strip(),
            "block_id": block_id,
        })
    
    if debug:
        logger.info(
            "Block comparison %s: extracted=%s valid=%s",
            block_id,
            len(parsed.get("changes", [])),
            len(valid_changes)
        )
    
    return valid_changes


def compare_all_matched_blocks(matches: List[Dict], debug: bool = False) -> Tuple[List[Dict], Dict]:
    """
    Compare all matched block pairs.
    
    Returns:
    - List of all detected changes
    - Stats dict with summary
    """
    
    all_changes = []
    stats = {
        "total_comparisons": 0,
        "matched_pairs": 0,
        "added_blocks": 0,
        "removed_blocks": 0,
        "total_changes_detected": 0,
        "api_calls": 0,
    }
    
    for match in matches:
        match_type = match.get("match_type", "")
        stats["total_comparisons"] += 1
        
        if match_type == "added":
            stats["added_blocks"] += 1
            # Return generic "added" change
            new_block = match.get("new_block")
            if new_block:
                all_changes.append({
                    "type": "added",
                    "statement": f"Section added: {new_block.get('heading', 'Untitled')}",
                    "old_text": "",
                    "new_text": _truncate_text(new_block.get("content", ""), 200),
                    "block_id": new_block.get("block_id"),
                })
        
        elif match_type == "removed":
            stats["removed_blocks"] += 1
            # Return generic "removed" change
            old_block = match.get("old_block")
            if old_block:
                all_changes.append({
                    "type": "removed",
                    "statement": f"Section removed: {old_block.get('heading', 'Untitled')}",
                    "old_text": _truncate_text(old_block.get("content", ""), 200),
                    "new_text": "",
                    "block_id": old_block.get("block_id"),
                })
        
        elif match_type == "matched":
            stats["matched_pairs"] += 1
            stats["api_calls"] += 1
            
            old_block = match.get("old_block")
            new_block = match.get("new_block")
            
            changes = compare_blocks(old_block, new_block, debug=debug)
            all_changes.extend(changes)
    
    stats["total_changes_detected"] = len(all_changes)
    
    logger.info(
        "Block comparison summary: comparisons=%s changes=%s added=%s removed=%s",
        stats["total_comparisons"],
        stats["total_changes_detected"],
        stats["added_blocks"],
        stats["removed_blocks"],
    )
    
    print(f"\n⚖️  Block Comparison Results:")
    print(f"   Total comparisons: {stats['total_comparisons']}")
    print(f"   Changes detected: {stats['total_changes_detected']}")
    print(f"   Added blocks: {stats['added_blocks']}")
    print(f"   Removed blocks: {stats['removed_blocks']}")
    print()
    
    return all_changes, stats
